# LAB 05. 8/16/32K context, streaming, and tools

## Profile

| Field | Value |
| --- | --- |
| Estimated time | 2–4 hours for one candidate; this is not a prediction of model speed |
| Prerequisites | LAB 04 completed; model passed basic smoke tests; target Linux and pinned llama.cpp available |
| Readiness status | Instructions and fixtures ready; hardware capacity and each configuration's protocol remain `unverified` |
| Outcome | Context × protocol matrix and an archive of reproducible HTTP requests |

## Objective

Verify that the server actually handles the selected context, returns correct streaming events, and preserves the tool round trip. Separately check how reasoning counts toward the output limit and is separated from the final answer.

## Hypothesis

For one pinned model, increasing context from 8K to 16K and 32K does not violate memory or protocol requirements. Starting the server with a large `-c` alone cannot confirm this hypothesis: the context must be filled. Valid ordinary chat does not prove tool support.

## Preparation

- Use the GGUF, binary SHA, template, GPU offload, KV precision, and FA that passed LAB 04. Start with one backend; repeat the lab in a new archive for the other.
- Use one server slot and one model. Neither the server nor the HTTP client receives tools for accessing a shell, task files, or hidden checks.
- Shared inputs: [chat-request.json](fixtures/chat-request.json) and [tool-request.json](fixtures/tool-request.json). Expected final values are `LAB_READY` and `LAB_VALUE_42`; reasoning is evaluated separately. The fixtures' 2048-output-token limit does not guarantee that every thinking model finishes: record `finish_reason=length` as a configuration limitation.
- Prepare Python 3, curl, and dependencies from the previous lab. New packages and weights are not installed automatically.

## Procedure

1. Create an archive and set paths, replacing absolute placeholders:

   ```sh
   npm run lab:new -- --lab LAB05 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB05-my-session'
   export LLAMA_BIN='/absolute/path/to/LAB04-my-session/build-hip/bin'
   export LOCAL_GGUF='/absolute/path/to/model.gguf'
   cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
   cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
   sha256sum "$LAB_DIR/raw/chat-request.json" "$LAB_DIR/raw/tool-request.json" \
     > "$LAB_DIR/raw/fixtures.sha256"
   "$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   "$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
   sha256sum "$LLAMA_BIN/llama-server" "$LLAMA_BIN/llama-bench" \
     > "$LAB_DIR/raw/binaries.sha256"
   ```

   Preserve the SHA values of all shards from LAB 03/04. Check for `--alias`, `--no-context-shift`, `-np`, `-fa`, and `-d` in the pinned help. Record sampling/reasoning parameters from the model card in `raw/model-settings.txt` and the manifest; apply them identically across all three contexts. Any modified template receives its own SHA and a separate variant.

2. Test memory occupancy without HTTP at 8K. Then, only after checking the budget, repeat for 16K and 32K by changing `CTX`:

   ```sh
   export CTX=8192
   DEPTH=$((CTX - 128))
   free -b > "$LAB_DIR/raw/context-$CTX-memory-before.txt"
   cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-before.txt"
   if /usr/bin/time -v -o "$LAB_DIR/raw/context-$CTX-process.txt" \
     "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
     -p 0 -n 128 -d "$DEPTH" -r 3 -o json \
     > "$LAB_DIR/raw/context-$CTX-bench.json" \
     2> "$LAB_DIR/raw/context-$CTX-bench.log"; then
     bench_status=0
   else
     bench_status=$?
   fi
   printf '%s\n' "$bench_status" > "$LAB_DIR/raw/context-$CTX-exit.txt"
   free -b > "$LAB_DIR/raw/context-$CTX-memory-after.txt"
   cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-after.txt"
   test "$bench_status" -eq 0
   ```

   The depths are 8064, 16256, and 32640 tokens before 128 generated tokens. In a second terminal with the same `LAB_DIR` and `CTX`, start `vmstat -w 1 > "$LAB_DIR/raw/context-$CTX-vmstat-series.txt"` beforehand; stop it with Ctrl-C after the measurement. Preserve GPU allocations from the bench log, GNU time RSS, and swap changes. The built-in warmup is excluded from the three measured repetitions. Check the saved bench exit code before proceeding. On OOM, GPU reset, persistent swapping, fallback, or budget violation, stop this configuration; do not automatically run a longer context. Changing KV/FA to fit is a new variant, not a correction to the result.

3. After a successful probe, start the server for this context in a separate terminal, from the repository root with the same variables. Add the previously recorded model-specific sampling/reasoning flags. The server remains on loopback only:

   ```sh
   "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" \
     --host 127.0.0.1 --port 8080 --alias lab-model \
     -ngl 999 -c "$CTX" -np 1 -t 8 -b 512 -ub 256 \
     -ctk f16 -ctv f16 -fa on --jinja --no-context-shift \
     > "$LAB_DIR/raw/server-$CTX.log" 2>&1
   ```

   In the working terminal, wait for a successful health response and save properties:

   ```sh
   curl --fail --max-time 10 http://127.0.0.1:8080/health \
     > "$LAB_DIR/raw/health-$CTX.json"
   curl --fail --max-time 10 http://127.0.0.1:8080/props \
     > "$LAB_DIR/raw/props-$CTX.json"
   curl --fail --max-time 10 http://127.0.0.1:8080/v1/models \
     > "$LAB_DIR/raw/models-$CTX.json"
   ```

   Confirm the `lab-model` alias, GPU offload, effective context/slots, and template. `--reasoning-format` describes output parsing, not thinking mode itself. Do not declare thinking disabled merely because reasoning is absent from `content`.

4. Create a portable HTTP/SSE measurement client. It reads prepared fixtures and allows only one dummy function; no model-generated code is executed. This file can be reused in subsequent labs with another endpoint:

   ```sh
   cat > "$LAB_DIR/raw/http_probe.py" <<'PY'
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
                               thought = delta.get('reasoning_content') or ''
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
   PY
   ```

   This client measures TTFT only for streaming: the delay until a complete JSON response is not TTFT. `ttft_content_s` is separate from the first reasoning token. An unsupported reasoning format requires a separately documented parser, not guesses based on tags. Errors and rejected tools remain in the archive.

5. Prepare streaming variants and run the four protocol cases twice each:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   for kind in ('chat', 'tool'):
       value = json.loads((root / (kind + '-request.json')).read_text())
       value['stream'] = True
       (root / (kind + '-stream-request.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
   PY

   for repeat in 1 2; do
     for kind in chat chat-stream; do
       python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
         --request "$LAB_DIR/raw/$kind-request.json" \
         --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat"
     done
     for kind in tool tool-stream; do
       python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
         --request "$LAB_DIR/raw/$kind-request.json" \
         --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat" --follow-tool
     done
   done
   ```

   Check the final `LAB_READY` / `LAB_VALUE_42`, correct `call_id`, valid JSON arguments, terminal event, and finish reason. A second request to the same process may use the prefix cache: label first and repeated requests separately. Record missing usage as `null`; do not infer tokens from text length. An incomplete tool round trip is not a pass even with HTTP 200.

6. Test the local dispatcher's rejection of an unknown tool using a synthetic response. The real round trip and the test below use the same `validate_tool`; no endpoint is called:

   ```sh
   python3 - <<'PY'
   import copy, json, os, pathlib, subprocess, sys
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   valid = {'role': 'assistant', 'content': None, 'tool_calls': [{
       'id': 'offline-case-1', 'type': 'function',
       'function': {'name': 'lookup_lab_value', 'arguments': '{"key":"alpha"}'}}]}
   cases = {'valid': valid}
   for name, field, value in [('unknown-name', 'name', 'unexpected_tool'),
                             ('wrong-arguments', 'arguments', '{"key":"beta"}')]:
       message = copy.deepcopy(valid)
       message['tool_calls'][0]['function'][field] = value
       cases[name] = message
   message = copy.deepcopy(valid)
   del message['tool_calls'][0]['id']
   cases['missing-id'] = message
   results = {}
   for name, message in cases.items():
       prefix = root / ('offline-tool-' + name)
       source = pathlib.Path(str(prefix) + '-message.json')
       source.write_text(json.dumps(message, indent=2))
       result = subprocess.run([sys.executable, str(root / 'http_probe.py'),
           '--validate-tool-message', str(source), '--out', str(prefix)], check=False)
       expected = 0 if name == 'valid' else 1
       results[name] = {'exit_code': result.returncode, 'expected_exit_code': expected}
   (root / 'offline-tool-checks.json').write_text(json.dumps(results, indent=2))
   assert all(row['exit_code'] == row['expected_exit_code'] for row in results.values())
   PY
   ```

   In `offline-tool-*.tool-rejected.json`, confirm the specific reasons `tool/arguments rejected by allowlist` and `missing tool call id`, rather than an arbitrary Python error; the valid case should return `accepted: true`. This tests the client's boundary; it does not prove the model independently avoids unknown functions.

7. Prepare a **long HTTP input**, accounting for the template. The following generator uses `/apply-template` and `/tokenize` without running inference. It selects an input no longer than `CTX − 4096`, leaving an output reserve. If the pinned server does not support these endpoints, record a blocker for this method and count length using its tokenizer separately:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib, urllib.request
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   context = int(os.environ['CTX'])
   budget = context - 4096
   def post(route, value):
       request = urllib.request.Request('http://127.0.0.1:8080' + route,
           data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
       with urllib.request.urlopen(request, timeout=60) as response:
           return json.load(response)
   def candidate(rows):
       text = 'Control value: LAB_SENTINEL_42.\n'
       text += ''.join(f'Line {i}: neutral measurement data.\n' for i in range(rows))
       text += 'Return only the control value from the first line.'
       messages = [{'role': 'user', 'content': text}]
       prompt = post('/apply-template', {'messages': messages})['prompt']
       tokens = post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens']
       return messages, prompt, len(tokens)
   low, high, best = 0, context, None
   while low <= high:
       middle = (low + high) // 2
       messages, prompt, count = candidate(middle)
       if count <= budget:
           best = (messages, prompt, count)
           low = middle + 1
       else:
           high = middle - 1
   if best is None:
       raise RuntimeError('template exceeds input budget')
   messages, prompt, count = best
   payload = {'model': 'lab-model', 'messages': messages, 'max_tokens': 4096, 'stream': True}
   prefix = root / ('ctx' + str(context) + '-long')
   pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
   pathlib.Path(str(prefix) + '-prompt.txt').write_text(prompt)
   pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({
       'context': context, 'input_tokens': count, 'output_reserve': 4096, 'input_budget': budget}, indent=2))
   PY

   for repeat in 1 2; do
     python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
       --request "$LAB_DIR/raw/ctx$CTX-long-request.json" \
       --out "$LAB_DIR/raw/ctx$CTX-long-r$repeat"
   done
   ```

   Compare server `usage.prompt_tokens` with the preliminary count. A difference indicates another effective template/tokenization and requires explanation. This counts as a test of the given long input only if there is no truncation/context shift; the expected final answer is `LAB_SENTINEL_42`. A synthetic string does not evaluate the model's research quality.

8. Test overflow in the same context. Create an input longer than `CTX` and preserve its tokenizer count:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib, urllib.request
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   context = int(os.environ['CTX'])
   source = root / ('ctx' + str(context) + '-long-request.json')
   payload = json.loads(source.read_text())
   text = payload['messages'][0]['content']
   for attempt in range(8):
       text = text + '\n' + text
       payload['messages'][0]['content'] = text
       def post(route, value):
           request = urllib.request.Request('http://127.0.0.1:8080' + route,
               data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
           with urllib.request.urlopen(request, timeout=60) as response:
               return json.load(response)
       prompt = post('/apply-template', {'messages': payload['messages']})['prompt']
       count = len(post('/tokenize', {'content': prompt,
           'add_special': False, 'parse_special': True})['tokens'])
       if count > context:
           break
   else:
       raise RuntimeError('could not construct overflow within bounded attempts')
   payload['max_tokens'] = 128
   prefix = root / ('ctx' + str(context) + '-overflow')
   pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False))
   pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({'input_tokens': count, 'context': context}))
   PY
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/ctx$CTX-overflow-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-overflow"
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/chat-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-overflow-recovery"
   ```

   Run recovery as a separate command, even when the expected HTTP error causes the probe to exit nonzero. An explicit rejection or a documented limit is expected; silent truncation is incompatible with the baseline. Then test cancellation and another short request:

   ```sh
   if curl --no-buffer --max-time 1 -H 'Content-Type: application/json' \
     --data-binary @"$LAB_DIR/raw/ctx$CTX-long-request.json" \
     http://127.0.0.1:8080/v1/chat/completions \
     > "$LAB_DIR/raw/ctx$CTX-cancel.sse" 2> "$LAB_DIR/raw/ctx$CTX-cancel.log"; then
     printf '0\n' > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
   else
     printf '%s\n' "$?" > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
   fi
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/chat-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-cancel-recovery"
   ```

   A client timeout does not prove the server cancelled computation: check the server log, slot, and recovery time. If the request finished within a second, cancellation was not tested; repeat with a previously saved longer-running request.

9. Stop the server with Ctrl-C in its terminal; verify that the process exits and memory is released. Repeat steps 2–8 for `CTX=16384`, then `CTX=32768`, only if earlier budgets were respected. Do not start three servers simultaneously. Preserve identical settings in the manifest and record each run's context separately. The main agent baseline is 16K; 32K remains a separate variant.

## Results tables

| Context | Depth + generation | Three bench repetitions / raw | Peak memory / source | Swap / full GPU offload | Admission |
| --- | --- | --- | --- | --- | --- |
| 8192 | 8064 + 128 | | | | |
| 16384 | 16256 + 128 | | | | |
| 32768 | 32640 + 128 | | | | |

| Context | Case | Repetition | HTTP / finish reason | Final / tool validity | TTFT content / reasoning, s | Total, s | Raw prefix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | chat | | | | | | |
| | chat-stream | | | | | | |
| | tool round trip | | | | | | |
| | tool-stream round trip | | | | | | |
| | long context | | | | | | |
| | overflow / cancel / recovery | | | | | | |

| Context | Input count before execution | usage.prompt_tokens | Output / reasoning tokens | Truncation / shift | Conclusion |
| --- | --- | --- | --- | --- | --- |
| 8192 | | | | | |
| 16384 | | | | | |
| 32768 | | | | | |

## Deliverables

- `report.md`, `measurements.tsv`, and `manifest.json` referencing LAB 04 and pinned settings.
- `raw/http_probe.py`, SHA values of shared fixtures and their local copies, `raw/model-settings.txt`, help, and binary hashes.
- `raw/context-*-bench.*`, `raw/server-*.log`, `raw/props-*.json`, `raw/health-*.json`, `raw/models-*.json`, and memory/swap observations.
- All HTTP requests/responses/SSE, assembled messages, metrics, followups, errors, and rejected tools; long prompts and token counts.
- Descriptions of overflow/cancel/recovery cases and answers to review questions.

## Completion criteria

- [ ] A context-filling probe was performed for each context, or a blocker was preserved.
- [ ] Admitted contexts have two repetitions each of chat, streaming, tools, and streaming tools.
- [ ] The tool round trip was checked through an allowlist without executing arbitrary code.
- [ ] The long HTTP input was counted with the tokenizer and checked for silent truncation.
- [ ] Reasoning and final output, output cap, and finish reason are described separately.
- [ ] Error/cancellation handling and slot recovery were tested.
- [ ] Short smoke tests are not conflated with 32K confirmation; unsuccessful cases are preserved.

A lab that correctly records a 16K limit counts as completed. This does not mean the model passed the 32K configuration or is ready for every agent protocol.

## Review questions

1. Why do `-c 32768` and a short successful response not confirm 32K capacity?
2. How does TTFT for the first reasoning token differ from TTFT for final content?
3. Why can HTTP 200 with `finish_reason=length` indicate an incomplete tool round trip?
4. How does confirming allowlist rejection differ from the model refusing to call an unknown tool?
5. Why does the prefix cache affect repeated prefill, and how should this be reflected in the report?

## Sources

- [llama-server: API, context, slots, reasoning, tokenize, and apply-template](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- [llama.cpp: function calling and tool-aware templates](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md).
- [llama-bench: filling context and repetitions](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md).
- [Lab course](README.md), [fixture descriptions](fixtures/README.md), [LAB 04](LAB04-backends.md).
