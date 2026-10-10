import argparse, json, pathlib, time, urllib.error, urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url')
parser.add_argument('--request')
parser.add_argument('--out', required=True)
parser.add_argument('--follow-tool', action='store_true')
parser.add_argument('--validate-tool-message')
args = parser.parse_args()
def save(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def validate_tool(message):
    calls = message.get('tool_calls', [])
    if len(calls) != 1:
        raise ValueError('expected exactly one tool call')
    tool = calls[0]
    function = tool['function']
    arguments = json.loads(function['arguments'])
    if tool.get('type') != 'function':
        raise ValueError('only function tools allowed')
    if function['name'] != 'lookup_lab_value' or arguments != {'key': 'alpha'}:
        raise ValueError('tool/arguments rejected by allowlist')
    if not tool.get('id'):
        raise ValueError('missing tool call id')
    return tool

if args.validate_tool_message:
    try:
        validate_tool(json.loads(pathlib.Path(args.validate_tool_message).read_text()))
        save(args.out + '.tool-validation.json', {'accepted': True})
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise SystemExit(1)
    raise SystemExit(0)
if not args.url or not args.request:
    parser.error('--url and --request are required for HTTP probes')

def call(payload, prefix):
    save(prefix + '.request.json', payload)
    metrics = {'ttft_content_s': None, 'ttft_reasoning_s': None, 'usage': None}
    start = time.perf_counter()
    request = urllib.request.Request(args.url.rstrip('/') + '/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            metrics['http_status'] = response.status
            if not payload.get('stream'):
                value = json.load(response)
                save(prefix + '.response.json', value)
                message = value['choices'][0]['message']
                metrics['finish_reason'] = value['choices'][0].get('finish_reason')
                metrics['usage'] = value.get('usage')
            else:
                message = {'role': 'assistant', 'content': ''}
                tools, reasoning, done = {}, '', False
                with open(prefix + '.sse', 'wb') as raw:
                    for line in response:
                        raw.write(line)
                        raw.flush()
                        if not line.startswith(b'data:'):
                            continue
                        data = line[5:].strip()
                        if data == b'[DONE]':
                            done = True
                            break
                        if not data:
                            continue
                        event = json.loads(data)
                        if event.get('error'):
                            raise ValueError(str(event['error']))
                        if event.get('usage') is not None:
                            metrics['usage'] = event['usage']
                        for choice in event.get('choices', []):
                            delta = choice.get('delta', {})
                            content = delta.get('content') or ''
                            thought = delta.get('reasoning_content') or delta.get('reasoning') or ''
                            if content and metrics['ttft_content_s'] is None:
                                metrics['ttft_content_s'] = time.perf_counter() - start
                            if thought and metrics['ttft_reasoning_s'] is None:
                                metrics['ttft_reasoning_s'] = time.perf_counter() - start
                            message['content'] += content
                            reasoning += thought
                            for piece in delta.get('tool_calls', []):
                                item = tools.setdefault(piece['index'], {'id': '',
                                    'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                if piece.get('id'):
                                    item['id'] = piece['id']
                                function = piece.get('function', {})
                                item['function']['name'] += function.get('name') or ''
                                item['function']['arguments'] += function.get('arguments') or ''
                            if choice.get('finish_reason') is not None:
                                metrics['finish_reason'] = choice['finish_reason']
                if tools:
                    message['tool_calls'] = [tools[index] for index in sorted(tools)]
                if reasoning:
                    message['reasoning_content'] = reasoning
                metrics['stream_done'] = done
                save(prefix + '.assembled.json', message)
                if not done:
                    raise ValueError('SSE ended without [DONE]')
            metrics['duration_s'] = time.perf_counter() - start
            save(prefix + '.metrics.json', metrics)
            return message
    except Exception as error:
        if isinstance(error, urllib.error.HTTPError):
            metrics['http_status'] = error.code
            pathlib.Path(prefix + '.http-error.txt').write_bytes(error.read())
        metrics.update(error=str(error), duration_s=time.perf_counter() - start)
        save(prefix + '.metrics.json', metrics)
        raise

payload = json.loads(pathlib.Path(args.request).read_text())
message = call(payload, args.out)
if args.follow_tool:
    try:
        tool = validate_tool(message)
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise
    followup = dict(payload)
    followup['messages'] = payload['messages'] + [message, {
        'role': 'tool', 'tool_call_id': tool['id'], 'content': 'LAB_VALUE_42'}]
    message = call(followup, args.out + '.followup')
save(args.out + '.final.json', {'content': message.get('content'),
    'tool_calls': message.get('tool_calls'), 'reasoning_content': message.get('reasoning_content')})
