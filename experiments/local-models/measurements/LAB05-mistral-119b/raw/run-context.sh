#!/usr/bin/env bash
set -u
CTX="$1"
LAB_DIR="${LAB_DIR:?}"
VUL="${VUL:?}"
GGUF="${GGUF:?}"
PORT=8080
cd "$LAB_DIR" || exit 1
P=raw/context-$CTX
DEPTH=$((CTX - 128))

echo "ctx=$CTX bench start $(date -u +%FT%TZ)" >> raw/progress.txt
free -b > "$P-memory-before.txt"
cat /proc/vmstat > "$P-vmstat-before.txt"
/usr/bin/time -v -o "$P-process.txt" \
  "$VUL/llama-bench" -m "$GGUF" -ngl 999 -t 8 -b 512 -ub 256 \
  -ctk f16 -ctv f16 -fa 1 -p 0 -n 128 -d "$DEPTH" -r 3 -o json \
  > "$P-bench.json" 2> "$P-bench.log"
echo "$?" > "$P-exit.txt"
free -b > "$P-memory-after.txt"
cat /proc/vmstat > "$P-vmstat-after.txt"
echo "ctx=$CTX bench exit=$(cat $P-exit.txt) $(date -u +%FT%TZ)" >> raw/progress.txt
if [ "$(cat $P-exit.txt)" != "0" ]; then echo "ctx=$CTX bench failed, stop" >> raw/progress.txt; exit 1; fi

"$VUL/llama-server" -m "$GGUF" --host 127.0.0.1 --port "$PORT" --alias lab-model \
  -ngl 999 -c "$CTX" -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1 \
  --jinja --no-context-shift > "raw/server-$CTX.log" 2>&1 &
SRV=$!
echo "$SRV" > "raw/server-$CTX.pid"
ok=0
for i in $(seq 1 180); do
  if curl -sf --max-time 5 "http://127.0.0.1:$PORT/health" > "raw/health-$CTX.json"; then ok=1; break; fi
  sleep 5
done
echo "ctx=$CTX server ready ok=$ok $(date -u +%FT%TZ)" >> raw/progress.txt
curl -sf --max-time 10 "http://127.0.0.1:$PORT/props" > "raw/props-$CTX.json" 2>/dev/null
curl -sf --max-time 10 "http://127.0.0.1:$PORT/v1/models" > "raw/models-$CTX.json" 2>/dev/null
if [ "$ok" != "1" ]; then kill "$SRV" 2>/dev/null; exit 1; fi

for repeat in 1 2; do
  for kind in chat chat-stream; do
    python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" \
      --request "raw/$kind-request.json" --out "raw/ctx$CTX-$kind-r$repeat" >/dev/null 2>&1
    echo "ctx=$CTX $kind r$repeat exit=$?" >> raw/progress.txt
  done
  for kind in tool tool-stream; do
    python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" \
      --request "raw/$kind-request.json" --out "raw/ctx$CTX-$kind-r$repeat" --follow-tool >/dev/null 2>&1
    echo "ctx=$CTX $kind r$repeat exit=$?" >> raw/progress.txt
  done
done

# offline allowlist checks
python3 - <<'PYEOF'
import copy, json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
valid = {'role':'assistant','content':None,'tool_calls':[{'id':'offline-case-1','type':'function','function':{'name':'lookup_lab_value','arguments':'{"key":"alpha"}'}}]}
cases = {'valid': valid}
for name, field, value in [('unknown-name','name','unexpected_tool'),('wrong-arguments','arguments','{"key":"beta"}')]:
    msg = copy.deepcopy(valid); msg['tool_calls'][0]['function'][field] = value; cases[name] = msg
msg = copy.deepcopy(valid); del msg['tool_calls'][0]['id']; cases['missing-id'] = msg
results = {}
for name, message in cases.items():
    prefix = root / ('offline-tool-' + name)
    source = pathlib.Path(str(prefix) + '-message.json')
    source.write_text(json.dumps(message, indent=2))
    r = subprocess.run([sys.executable, str(root/'http_probe.py'), '--validate-tool-message', str(source), '--out', str(prefix)], check=False)
    results[name] = {'exit_code': r.returncode, 'expected_exit_code': 0 if name=='valid' else 1}
(root/'offline-tool-checks.json').write_text(json.dumps(results, indent=2))
PYEOF
echo "ctx=$CTX offline checks exit=$?" >> raw/progress.txt

# long input via apply-template/tokenize
python3 - <<PYEOF
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = $CTX
budget = context - 4096
def post(route, value):
    request = urllib.request.Request('http://127.0.0.1:$PORT' + route, data=json.dumps(value).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)
def candidate(rows):
    text = 'Контрольное значение: LAB_SENTINEL_42.\n'
    text += ''.join(f'Строка {i}: нейтральные данные измерения.\n' for i in range(rows))
    text += 'Верни только контрольное значение из первой строки.'
    messages = [{'role':'user','content':text}]
    prompt = post('/apply-template', {'messages': messages})['prompt']
    tokens = post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens']
    return messages, prompt, len(tokens)
low, high, best = 0, context, None
while low <= high:
    middle = (low + high)//2
    messages, prompt, count = candidate(middle)
    if count <= budget:
        best = (messages, prompt, count); low = middle+1
    else:
        high = middle-1
if best is None:
    raise RuntimeError('template exceeds input budget')
messages, prompt, count = best
payload = {'model':'lab-model','messages':messages,'max_tokens':4096,'stream':True}
prefix = root / ('ctx'+str(context)+'-long')
pathlib.Path(str(prefix)+'-request.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
pathlib.Path(str(prefix)+'-prompt.txt').write_text(prompt)
pathlib.Path(str(prefix)+'-count.json').write_text(json.dumps({'context':context,'input_tokens':count,'output_reserve':4096,'input_budget':budget},indent=2))
print('long input tokens', count)
PYEOF
echo "ctx=$CTX long-gen exit=$?" >> raw/progress.txt

for repeat in 1 2; do
  python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" \
    --request "raw/ctx$CTX-long-request.json" --out "raw/ctx$CTX-long-r$repeat" >/dev/null 2>&1
  echo "ctx=$CTX long r$repeat exit=$?" >> raw/progress.txt
done

# overflow
python3 - <<PYEOF
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = $CTX
source = root / ('ctx'+str(context)+'-long-request.json')
payload = json.loads(source.read_text())
text = payload['messages'][0]['content']
count = 0
for attempt in range(8):
    text = text + '\n' + text
    payload['messages'][0]['content'] = text
    def post(route, value):
        request = urllib.request.Request('http://127.0.0.1:$PORT'+route, data=json.dumps(value).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    prompt = post('/apply-template', {'messages': payload['messages']})['prompt']
    count = len(post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens'])
    if count > context:
        break
payload['max_tokens'] = 128
prefix = root / ('ctx'+str(context)+'-overflow')
pathlib.Path(str(prefix)+'-request.json').write_text(json.dumps(payload,ensure_ascii=False))
pathlib.Path(str(prefix)+'-count.json').write_text(json.dumps({'input_tokens':count,'context':context}))
print('overflow tokens', count)
PYEOF
python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" --request "raw/ctx$CTX-overflow-request.json" --out "raw/ctx$CTX-overflow" >/dev/null 2>&1
echo "ctx=$CTX overflow exit=$?" >> raw/progress.txt
python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" --request "raw/chat-request.json" --out "raw/ctx$CTX-overflow-recovery" >/dev/null 2>&1
echo "ctx=$CTX overflow-recovery exit=$?" >> raw/progress.txt

# cancel
if curl --no-buffer --max-time 1 -H 'Content-Type: application/json' \
  --data-binary @"raw/ctx$CTX-long-request.json" "http://127.0.0.1:$PORT/v1/chat/completions" \
  > "raw/ctx$CTX-cancel.sse" 2> "raw/ctx$CTX-cancel.log"; then
  printf '0\n' > "raw/ctx$CTX-cancel-exit.txt"
else
  printf '%s\n' "$?" > "raw/ctx$CTX-cancel-exit.txt"
fi
python3 raw/http_probe.py --url "http://127.0.0.1:$PORT" --request "raw/chat-request.json" --out "raw/ctx$CTX-cancel-recovery" >/dev/null 2>&1
echo "ctx=$CTX cancel exit=$(cat raw/ctx$CTX-cancel-exit.txt) recovery exit=$?" >> raw/progress.txt

kill "$SRV" 2>/dev/null; sleep 5
echo "ctx=$CTX server stopped $(date -u +%FT%TZ)" >> raw/progress.txt
echo "ctx=$CTX done" >> raw/progress.txt
