# LAB26. Concurrent load on a local server

## Profile

| Field | Value |
| --- | --- |
| Type | Bounded HTTP load test of a local inference service |
| Time | 2–3 hours of operator time plus execution; duration depends on the model and selected timeouts |
| Prerequisites | Completed LAB05, hardware profile, and a verified model server on Ryzen AI Max+ 395 / 128 GB / Linux |
| Readiness | `target-machine`; the HTTP driver and its offline tests are ready; the LAB08 bridge is not needed for this experiment |
| Minimum scope | Warmup and three series of 12 requests at client concurrency 1, 2, and 4; one model and server configuration |
| Extension | Three repetitions per concurrency with balanced order; then sustained stability, energy, or another server configuration |

## Objective

Find useful parallelism for the selected local deployment: how many requests the server completes per unit time and the associated latency, memory, and error costs. Produce a reproducible profile on a real machine while retaining every unsuccessful request.

## Hypothesis

Increasing client concurrency from 1 to 2 and 4 improves aggregate throughput within predefined acceptable latency and memory headroom. Record acceptance boundaries before running: request timeout, acceptable HTTP/protocol error rate, available RAM reserve, and whether swap is allowed. Do not assign numerical Ryzen performance values before measuring.

Concurrent HTTP requests do not guarantee parallel GPU execution: the server may queue them. This lab measures the behavior of the entire deployment with fixed server slots and scheduling policy. Increasing server slots is a separate intervention and a separate series.

## Preparation

```bash
npm run lab:new -- --lab LAB26 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB26-my-session'
python3 -B docs/labs/fixtures/concurrency_test.py
python3 -B docs/labs/fixtures/concurrency_driver.py --help
npm run check
```

Use a verified server from LAB05–07 with pinned weight hashes, backend/build, template, context, KV dtype, sampling/reasoning, and launch command. Record the hardware snapshot, power mode, background processes, and cache policy. Verify required slots/queue/prefix-cache options in `--help` and documentation for **your pinned runtime**. This manual does not claim identical parameter semantics across engines.

The driver runs on the same Linux host as the inference service. Only explicitly specified `http://127.0.0.1:PORT/v1/chat/completions` or `http://[::1]:PORT/v1/chat/completions` endpoints are allowed. It does not read `.env`, send authentication, follow redirects, use an HTTP proxy, call tools, or retry failed requests. This minimal driver is unsuitable for a server requiring authentication: retain a blocker or prepare a separately verified client that passes secrets according to repository rules. Do not remove existing server protection for a probe.

## Procedure

1. **Prepare a public load request.** The [ready-made fixture](fixtures/concurrency-request.json) requests text with an output cap of 512. This is load, not a model quality check. Create a working copy with the alias of the model actually running; repeating this step will not overwrite the file:

   ```bash
   MODEL_ALIAS='<verified local model alias>'
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   data = json.loads(pathlib.Path('docs/labs/fixtures/concurrency-request.json').read_text())
   data['model'] = sys.argv[2]
   with (pathlib.Path(sys.argv[1]) / 'raw' / 'load-request.json').open('x') as out:
       json.dump(data, out, ensure_ascii=False, indent=2)
       out.write('\n')
   PY
   ```

   Only one text user message, model, `max_tokens` 1…4096, `stream:false`, and optional `temperature`, `top_p`, and `seed` are allowed. If sampling is absent from the JSON, pin server defaults. Do not add keys, private data, or tools. Server acceptance of seed is checked separately and does not promise determinism. Keep this single request for the entire series.

2. **Check hardware headroom and server identity.** Save readiness logs, selected GPU/offload, allocations, PID/cgroup, and server-side limits. Context and slot count must accommodate four requests or return an explicit documented rejection; do not increase limits between the three experiments. Record initial memory/swap using LAB02. On UMA, do not add RSS and GPU allocation as independent uses of shared RAM.

3. **Perform a separate warmup.** The endpoint must match the running local server:

   ```bash
   LOCAL_ENDPOINT='http://127.0.0.1:8080/v1/chat/completions'
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 2 --timeout 120 --out "$LAB_DIR/raw/warmup"
   ```

   The value `120` is an upper bound for one request, not a speed prediction. If the pilot shows this limit is insufficient, retain the failure and choose another shared timeout before comparison runs, at most 600 s. The `--out` directory must be new and its parent must already exist. The driver saves config, original request, each request's status/error, and bounded response bodies, even on HTTP errors or timeouts. Exit 1 means request errors; exit 2 means invalid configuration or a file error. Resolve the problem or document a blocker before the next step.

4. **Execute the minimal 1→2→4 sequence.** Run **one** series at a time and inspect its result before proceeding. Example of the first:

   ```bash
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 12 --timeout 120 --out "$LAB_DIR/raw/r1-c1"
   ```

   For the next series, change concurrency to `2` and output to `r1-c2`, then to `4` and `r1-c4`. Do not change prompt/output/context/cache settings. If readiness is lost, OOM occurs, or the recorded memory reserve is violated, stop increasing load, retain logs, and mark the unreached level blocked. There is no automatic restart or retry. A client connection closing on timeout does not prove generation was canceled: check the server queue and absence of outstanding requests before the next series.

5. **Analyze measurements and resources.** Each output directory contains:

   - `config.json`, `request.json`: endpoint, concurrency, request count, deadline, and request SHA;
   - `request-NNNN.json` and `.response.bin`: individual latency/status/error/usage and up to 1 MiB of raw response; `response_truncated` explicitly marks the limit;
   - `system-memory.jsonl`: Linux `MemTotal`, `MemAvailable`, `pswpin/pswpout` before and after the series and at intervals of roughly one second;
   - `summary.json`: entire-series wall-clock time, successful requests/s, successful completion tokens/s when usage is complete, median/p95/max latency of successful responses, and error count.

   Token usage comes from the server response. If usage is unknown for even one successful response, aggregate successful tokens/s remains `null`; this does not hide errors. HTTP 200 with invalid JSON, empty assistant text, an unexpected tool call, or a finish reason other than `stop`/`length` counts as a protocol error. The handler does not judge the text's correctness. `finish_reason=length` is acceptable for bounded load, but show the share of such responses separately.

   Median/p95 describe **successful** responses; always show failures and their latency alongside them, otherwise fast rejections may create a false improvement. p95 uses nearest-rank; with 12 observations it is the maximum, so the minimum lab scope gives only a rough tail estimate. This is full-response latency including server queuing and connection establishment, excluding waiting in the client executor queue. TTFT and decode-only speed are not measured: `stream:false` provides no such data. A new connection for every request is part of the fixed method.

   `minimum_sampled_mem_available_bytes` describes the entire machine and may miss a short peak between samples. Additionally attach available server process/cgroup telemetry, GPU allocations, and temperatures from LAB02, with measurement method and frequency. If the engine creates workers, one PID's RSS does not represent the entire deployment. Retain `null` for peak allocations without a measuring tool; do not call minimum MemAvailable the model's exact peak. Swap counters are system-wide and require accounting for background load.

6. **Build a scaling profile.** For each concurrency, calculate successful requests/s relative to c1 and median latency relative to c1 if both values are measured. Compare completion tokens/s together with output token count and finish reasons: different response lengths change the load. Use logs to identify where the server began queuing, rejecting requests, or evicting memory. Explain prefix cache separately: identical requests may test a warm cache; the conclusion does not automatically apply to unique long prompts.

7. **Extend the series by changing one factor.** For three repetitions, add orders `2→4→1` and `4→1→2`, with 12 new requests per level and new `r2-*` and `r3-*` directories. Check readiness and identical initial conditions between experiments. This totals 108 comparison requests plus warmup. For stability, predefine a bounded number of these batches over 30–60 minutes and an upper bound on total requests; the driver accepts at most 256 requests per execution. Retain planned completion and emergency termination as different outcomes. Separate series can study server slots, another context, Vulkan/HIP, or another engine; do not change them within the concurrency comparison.

8. **Add energy if a real meter is available.** Record the instrument, whole-system measurement point, accuracy/frequency, and timestamps; separately measure idle consumption of the same computer with the model loaded. Save total Wh and successful-request count over the entire series interval, then calculate `Wh / successful request`; with zero successful requests, the metric is undefined. Show gross energy and, if subtracting idle, a separate calculation with duration and the constant-idle assumption. TDP and nominal power limits do not substitute for measured watts. Without an instrument, energy remains `null`; the lab can still be completed.

## Results tables

| Deployment fingerprint | Backend / slots / queue policy | Context/output | Sampling / reasoning / cache | Hardware manifest / telemetry |
| --- | --- | --- | --- | --- |
| | | | | |

| Repetition / concurrency | Success / total | HTTP / protocol / timeout errors | Median / p95 / max latency, s | Requests/s | Completion tokens/s / usage coverage | Output tokens / length stops |
| --- | --- | --- | --- | --- | --- | --- |
| 1 / 1 | | | | | | |
| 1 / 2 | | | | | | |
| 1 / 4 | | | | | | |

| Repetition / concurrency | Min sampled MemAvailable, bytes | Server peak / method | GPU allocation / method | Swap delta / background | Temperature / throttling evidence | Raw directory |
| --- | --- | --- | --- | --- | --- | --- |
| 1 / 1 | | | | | | |
| 1 / 2 | | | | | | |
| 1 / 4 | | | | | | |

| Series / instrument | Interval | Gross Wh | Idle W / separate interval | Wh / successful request | Limitations |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Deliverables

A report, training manifest, request and SHA, exact launch command/server identity, tables and **all** new driver output directories, server logs, and available hardware telemetry. Attach the protocol/budget plan and reason for each stopped level separately. Complete the [completeness check](report-validation.md). These are HTTP probes; do not present them as T002 `run.json`, an agent verdict, or real autonomous work.

## Completion criteria

- [ ] Driver offline tests pass; the loopback endpoint and pinned deployment are confirmed.
- [ ] One request, limits, server slots, and cache policy are fixed before execution.
- [ ] Warmup and all three levels are completed, or a specific hardware blocker is documented; errors are retained.
- [ ] Successful-response metrics appear alongside the full failure count; unknown usage is not converted to 0.
- [ ] Memory/swap observations are retained; sampling limitations and UMA are accounted for.
- [ ] Full-response latency, TTFT, decode speed, and agent quality are not conflated.
- [ ] Energy is supported by a meter or explicitly absent; `npm run check` passes.

A level with explicit 429/503 responses from a working server may be a completed observation of a limit, not a reason to remove it from the report. If the machine is unavailable or the initial deployment cannot run, the result is `blocked`, not a successful Ryzen study.

## Review questions

1. How does client concurrency differ from GPU batch size and server slot count?
2. Why can higher requests/s accompany worse user latency?
3. How do short failures and missing usage distort an attractive throughput graph?
4. Why does p95 provide almost no information beyond max with 12 requests?
5. What cannot be measured by this non-streaming driver?
6. How do prefix cache and thermal state affect result transferability?
7. Why do Wh/request and tokens/s still not answer the cost of a successful agent task?

## Sources

- [Public driver](fixtures/concurrency_driver.py), [offline mock tests](fixtures/concurrency_test.py), [load request](fixtures/concurrency-request.json).
- [Python: HTTPConnection and network-operation timeouts](https://docs.python.org/3/library/http.client.html), [ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html). The driver additionally enforces the overall request deadline with a watchdog and does not follow redirects.
- [Linux profile and telemetry](LAB02-hardware.md), [context and protocol preflight](LAB05-context-tools.md), [engine profiles](../local-inference-engines.md).
- The executor attaches version/help and runtime documentation for the selected deployment. Support for specific scheduling/cache flags is not assumed without verification.
