# LAB32. Context, streaming and tools on Mac

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Protocol and resource measurements / `target-machine` |
| Time | 3–5 hours |
| Prerequisites | Successful LAB30 **or** LAB31; both for an engine comparison |
| Minimum | One engine, 8K/16K/32K, four chat/tool × JSON/SSE cases; warmup and three repetitions each, long input, cancellation and overflow |

## Objective

Establish actual working-context limits and whether the local server protocol is suitable for an agent loop.

## Hypothesis

At an admitted context size, the server completes text and tool round trips, assembles SSE correctly and recovers from failure/cancellation without a deployment change.

## Preparation

```sh
npm run lab:new -- --lab LAB32 --session apple-protocol
export LAB_DIR='experiments/local-models/measurements/LAB32-apple-protocol'
export LOCAL_URL='http://127.0.0.1:8080'
export MODEL_ALIAS='lab-model'
export CTX=8192
```

For MLX, use port 8081 and the model identifier from LAB31. Run only one server. Record the protocol/attempts and [shared conditions](../../experiments/local-models/apple/README.md). Reuse `http_probe.py` from LAB05 step 4: completing the Linux lab is not required. The following code extracts that exact published block, removes Markdown indentation and checks syntax without running it:

```sh
python3 - "$LAB_DIR" <<'PY'
import pathlib, sys, textwrap
source = pathlib.Path('docs/labs/LAB05-context-tools.md').read_text()
marker = '   cat > "$LAB_DIR/raw/http_probe.py" <<\'PY\'\n'
assert source.count(marker) == 1
script = textwrap.dedent(source.split(marker, 1)[1].split('\n   PY\n', 1)[0]) + '\n'
compile(script, 'http_probe.py', 'exec')
with (pathlib.Path(sys.argv[1]) / 'raw/http_probe.py').open('x') as out:
    out.write(script)
PY
```

This is an educational HTTP client for trusted loopback, not an isolating provider bridge. It is not intended for arbitrary URLs or production access. Exclude loopback from HTTP proxies (`export no_proxy='127.0.0.1,localhost,::1'`). Inputs are public; the server must not redirect the client.

## Procedure

1. For llama.cpp, start the pinned LAB30 server in a separate terminal (set `LLAMA_BIN`, `LOCAL_GGUF`, `LAB_DIR`, `CTX` there too):

   ```sh
   "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" --host 127.0.0.1 --port 8080 \
     --alias lab-model -ngl 999 -c "$CTX" -np 1 --jinja --no-context-shift \
     > "$LAB_DIR/raw/server-$CTX.txt" 2>&1
   ```

   Check flags against pinned help. Save `/health`, `/props`, `/v1/models` and GPU allocations. For MLX, use the LAB31 command; save model/device identity and available runtime limits. Client-side `CTX` alone does **not** set the MLX server cap: if the selected version cannot fix a hard context limit, investigate 8K/16K/32K input budgets and mark the hard-limit check `unavailable`. Do not present this as the same KV reservation as llama.cpp.

2. Prepare four requests per context, preserving original parameters and alias. Before the first series, add identical model-specific sampling/reasoning settings to the copies and record hashes:

   ```sh
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   for kind in ('chat', 'tool'):
       data = json.loads(pathlib.Path(f'docs/labs/fixtures/{kind}-request.json').read_text())
       data['model'] = sys.argv[2]
       for stream in (False, True):
           data['stream'] = stream
           suffix = '-stream' if stream else ''
           with (raw / f'{kind}{suffix}-request.json').open('x') as out:
               json.dump(data, out, ensure_ascii=False, indent=2)
   PY
   shasum -a 256 "$LAB_DIR"/raw/*-request.json > "$LAB_DIR/raw/requests.sha256"
   ```

3. For each case, run a separate warmup (`REPEAT=warmup`) and three repetitions (`1`, `2`, `3`), inspecting results between runs. Example text and tool calls; then change kind to `chat-stream`/`tool-stream`:

   ```sh
   export REPEAT=warmup
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LOCAL_URL" \
     --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-chat-r$REPEAT"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LOCAL_URL" \
     --request "$LAB_DIR/raw/tool-request.json" --out "$LAB_DIR/raw/ctx$CTX-tool-r$REPEAT" --follow-tool
   ```

   Require `LAB_READY` and `LAB_VALUE_42` in the final response; one `lookup_lab_value`, arguments exactly `{"key":"alpha"}`, a nonempty call ID and a linked tool result. Model code is not executed: the client returns a fixed string. HTTP 200 alone is not a pass. Repeat the offline allowlist cases from LAB05 step 6: unknown name, wrong key and missing ID must be rejected by the validator itself, not an accidental Python error. Label their synthetic evidence separately from model measurements.

4. Investigate genuinely long input. In llama.cpp, use the `/apply-template` + `/tokenize` generator from LAB05 step 7 with the current `CTX`; this HTTP code is portable to macOS. For MLX, count input with the pinned tokenizer from **your own** artifact. Example preparation without loading weights (Python from LAB31):

   ```sh
   "$MLX_ENV/bin/python" - "$LOCAL_MLX" "$LAB_DIR" "$CTX" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   from transformers import AutoTokenizer
   tokenizer = AutoTokenizer.from_pretrained(sys.argv[1], local_files_only=True, trust_remote_code=False)
   ctx = int(sys.argv[3])
   def make(n):
        return [{'role':'user', 'content':'Sentinel value LAB_SENTINEL_42.\n' +
            ''.join(f'Line {i}: neutral data.\n' for i in range(n)) +
            'Return the sentinel value from the first line.'}]
   def count(messages):
       ids = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
           add_generation_prompt=True, enable_thinking=False)
       assert isinstance(ids, list) and ids and all(isinstance(token, int) for token in ids)
       return len(ids)
   lo, hi = 0, ctx
   while lo < hi:
       mid = (lo + hi + 1) // 2
       if count(make(mid)) <= ctx - 4096: lo = mid
       else: hi = mid - 1
   messages = make(lo)
   payload = {'model':sys.argv[4], 'messages':messages, 'max_tokens':2048, 'stream':True}
   raw = pathlib.Path(sys.argv[2]) / 'raw'
   for name, data in [(f'ctx{ctx}-long-request.json',payload),
                      (f'ctx{ctx}-long-count.json',{'input_tokens':count(messages),'input_budget':ctx-4096})]:
       with (raw / name).open('x') as out: json.dump(data,out,ensure_ascii=False,indent=2)
   PY
   ```

   In Transformers 5.19, `return_dict` defaults to `True`: `len(BatchEncoding)` counts fields, not tokens. Explicit `return_dict=False` and validation of a flat ID list are mandatory; save and check the count before loading weights. In this example the server must use `enable_thinking=false`.

   Confirm that the server uses the same template and reasoning options; otherwise the count is unproven. Run the long request with the same probe: warmup and three repetitions, expecting `LAB_SENTINEL_42`. Check actual input usage, truncation and memory. A short prompt in a large empty context does not measure “32K”.

5. Cancellation: prepare a separate long streaming request with a sufficient output cap; save the `curl --no-buffer --max-time 1` response/exit code. Then check the server queue and recovery chat before returning to baseline. A client timeout does not prove GPU generation was cancelled. Save slot-release time and memory change; if the request completed before the timeout, the cancellation experiment did not occur—record that.

6. Overflow: for a runtime with a confirmed hard cap, create input that **after template/tokenization** exceeds the cap including the output reserve. Save the exact count, request and response/error, then a normal recovery chat. Record silent truncation or context shifting as behavior, not successful limit enforcement. If a cap is unavailable, document a blocker for this experiment; do not force the machine into OOM to simulate it.

7. Only after checking 8K, proceed to 16K, then 32K with a new runtime condition and a restart of your own server. Create a separate session for a second engine. Do not combine warm/prefix-cached and cold requests; show content TTFT separately from reasoning, and do not replace missing usage with character-count estimates.

## Results tables

| Engine / context | Case / repetition | Input/output tokens | TTFT content / reasoning s | Total s | Final / tool / SSE correct | Memory / swap | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

| Intervention | Confirmed cap/count | Response | Recovery / slot release | Admission / blocker |
| --- | --- | --- | --- | --- |
| Cancellation | | | | |
| Overflow | | | | |

## Deliverables

Report/TSV/manifest, four request fixtures and hashes, probe, runtime identity, all JSON/SSE outputs, token counts, memory timeline, cancellation/overflow/recovery evidence and offline validation. Skipped contexts/cases remain in planned attempts.

## Completion criteria

- [ ] Contexts confirmed by actual input length and runtime conditions.
- [ ] Four protocol cases have a warmup and three repetitions at every admitted context size.
- [ ] Tool allowlist, IDs, final content and SSE completion checked.
- [ ] Cancellation/overflow not marked pass without recovery evidence.
- [ ] Separate admission/blocker issued for LAB08 and load labs.
- [ ] Submission checked against the shared protocol.

## Review questions

1. Why cannot TTFT be derived from non-streaming response time?
2. Why does client CTX not set the server context limit?
3. How does a connection timeout differ from cancelling generation?
4. Why do prefix cache and reasoning affect latency interpretation?

## Sources

- [LAB05: portable HTTP/SSE probe and allowlist](LAB05-context-tools.md).
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server).
- [MLX-LM server](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py).
- [Transformers chat templates](https://huggingface.co/docs/transformers/chat_templating).
