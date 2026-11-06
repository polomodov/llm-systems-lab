# LAB34. Concurrent load and Mac stability

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | HTTP load test / `target-machine` |
| Time | 2–4 hours plus a 30-minute series |
| Prerequisites | LAB32; LAB33 only when using a wrapper |
| Minimum | Warmup; three 12-request series each at concurrency 1/2/4; then 30 minutes for a passing configuration |

## Objective

Measure useful deployment concurrency and stability on Mac while retaining latency, failures and shared-memory dynamics.

## Hypothesis

Increasing concurrency raises throughput without violating preselected latency/error/memory limits; an admitted configuration maintains these limits during sustained operation.

## Preparation

```sh
npm run lab:new -- --lab LAB34 --session apple-load
export LAB_DIR='experiments/local-models/measurements/LAB34-apple-load'
python3 -B docs/labs/fixtures/concurrency_test.py
python3 -B docs/labs/fixtures/concurrency_driver.py --help
export LOCAL_ENDPOINT='http://127.0.0.1:8080/v1/chat/completions'
export MODEL_ALIAS='lab-model'
```

Use the [shared Apple protocol](../../experiments/local-models/apple/README.md). The LAB26 driver is portable for HTTP, but its `/proc` telemetry targets Linux: on macOS these fields are expected to be `null` with a reason. **A separate macOS memory timeline is mandatory**, starting before load. Missing Linux metrics must not be interpreted as zero swap or sufficient memory.

## Procedure

1. Record endpoint, model identity, context, fixed server slots/queue/cache, output cap, power and stop criteria. The server uses loopback only. The driver does not support auth: if authorization is mandatory, record a blocker rather than disabling protection. Do not include tools in the load request.

   ```sh
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   data = json.loads(pathlib.Path('docs/labs/fixtures/concurrency-request.json').read_text())
   data['model'] = sys.argv[2]
   with (pathlib.Path(sys.argv[1]) / 'raw/load-request.json').open('x') as out:
       json.dump(data, out, ensure_ascii=False, indent=2)
   PY
   ```

2. Collect LAB28 memory/swap and start the time series. Run a separate warmup:

   ```sh
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 2 --timeout 120 --out "$LAB_DIR/raw/warmup"
   ```

   Stop on error. A 120 s timeout is an initial boundary, not a latency promise; set any different limit (no more than 600 s) before the entire comparison series.

3. Run one series at a time, checking summary and memory after each. Order: r1 — 1→2→4; r2 — 2→4→1; r3 — 4→1→2. For the first:

   ```sh
   export REPEAT=1
   export CONCURRENCY=1
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency "$CONCURRENCY" --requests 12 --timeout 120 \
     --out "$LAB_DIR/raw/r$REPEAT-c$CONCURRENCY"
   ```

   After a timeout, verify that no generation remains before the next series. Do not change slots alongside client concurrency: the server queue is part of the result. OOM, loss of readiness, sustained swap growth, critical pressure or violation of the preselected reserve means stop; mark subsequent cells `not-run` with a reason.

4. Choose a concurrency that passed the short series. Record the choice and enable the memory timeline before the long series. The following command schedules 12-request blocks for 1800 seconds; the last block may finish later (up to its deadline), reflected in wall time. The driver stops the series at the first HTTP/protocol error. At a memory stop criterion, the operator interrupts with Ctrl-C; the final status record is preserved:

   ```sh
   export CONCURRENCY=1
   python3 - "$LAB_DIR" "$LOCAL_ENDPOINT" "$CONCURRENCY" <<'PY'
   import json, pathlib, subprocess, sys, time
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   target = raw / 'sustained'
   target.mkdir()
   started = time.monotonic()
   blocks, status = [], 'completed'
   try:
       while time.monotonic() - started < 1800:
           out = target / f'block-{len(blocks)+1:04d}'
           command = [sys.executable, '-B', 'docs/labs/fixtures/concurrency_driver.py',
               '--endpoint', sys.argv[2], '--request', str(raw/'load-request.json'),
               '--concurrency', sys.argv[3], '--requests', '12', '--timeout', '120', '--out', str(out)]
           p = subprocess.run(command, check=False)
           blocks.append({'directory':out.name, 'exit_code':p.returncode})
           if p.returncode:
               status = 'failed'
               break
   except KeyboardInterrupt:
       status = 'interrupted'
   finally:
       (target/'series.json').write_text(json.dumps({'planned_seconds':1800,
           'actual_seconds':time.monotonic()-started, 'status':status, 'blocks':blocks}, indent=2))
   if status != 'completed': raise SystemExit(1)
   PY
   ```

   These are sequential bounded blocks with short client pauses. Their wall time counts toward campaign duration; do not describe this as continuous maximum GPU occupancy. After interruption, check child-client termination and the server queue before other experiments. Collect energy/temperature only with available verified tools; otherwise they are unknown.

5. Examine every `summary.json` and individual request: median/p95/max successful latency, failure counts/latencies, successful requests/s and tokens/s when usage is complete. With 12 observations, p95 is coarse, almost the maximum. The driver is non-streaming: TTFT and decode-only speed are unavailable. Calculate overall throughput from total tokens and wall interval, not an average of block rates. Missing usage leaves overall tokens/s unknown.

6. Align load intervals with memory pressure/swap and compare the start/end of the long series. Do not attribute degradation to thermal throttling without thermal evidence. Record the permitted operating mode and limiting factor: queue, memory, errors or latency.

## Results tables

| Repetition / concurrency | Success / total | Median / p95 / max s | Requests/s | Tokens/s | Failures | Swap / pressure | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

| Sustained concurrency | Planned / actual s | Start / end throughput | Peak memory / source | Errors / stop reason |
| --- | --- | --- | --- | --- |
| | | | | |

## Deliverables

Report/TSV/manifest, request and deployment conditions, all driver output directories, `sustained/series.json`, separate macOS memory timeline and stops/skips. Give reasons for unknown `/proc`, energy and temperature data.

## Completion criteria

- [ ] Three series each for 1/2/4 or a documented stop/blocker.
- [ ] The 30-minute series records actual duration and all blocks, including failures.
- [ ] macOS memory collected separately; `/proc` null not interpreted as zero.
- [ ] TTFT not inferred from non-streaming latency; usage and failures represented honestly.
- [ ] Submission checked against the shared protocol.

## Review questions

1. Why is client concurrency not equal to GPU parallelism?
2. How do short series limit p95 estimation?
3. Why does averaging block tokens/s give incorrect overall throughput?
4. What evidence is required to conclude throttling occurred?

## Sources

- [Driver](fixtures/concurrency_driver.py), [offline tests](fixtures/concurrency_test.py), [LAB26 methodology](LAB26-concurrent-load.md).
- [macOS hardware profile](LAB28-apple-hardware.md), pinned server documentation and local man pages.
