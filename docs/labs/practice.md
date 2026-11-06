# Practice scenarios without API access

`lab:practice` interprets four recorded synthetic scenarios, producing a trace, mechanical event analysis and a blank worksheet. Only Node.js ≥22 is required. The command does not read `.env` or run a model, adapter, shell, containers or network requests. Trace milliseconds are **virtual**; there is no real-time wait.

These exercises teach the protocols of [LAB20](LAB20-judge-calibration.md), [LAB22](LAB22-tool-design.md) and [LAB23](LAB23-failure-recovery.md). They do not complete those labs or establish properties of a real model or harness. Educational output is stored separately from measurements and `results/runs/`.

## Running

From the repository root:

```bash
npm run lab:practice -- --list true
npm run lab:practice -- --scenario tool-success --session first-pass
npm run lab:practice -- --scenario retry-429 --session first-pass
npm run lab:practice -- --scenario interrupted-stream --session first-pass
npm run lab:practice -- --scenario duplicate-action --session first-pass
```

Use `--list true` separately. Creation requires `--scenario` and `--session`; unknown and duplicate parameters are rejected. Sessions use up to 64 lowercase Latin letters, digits and single separating hyphens. Only the four scenario names above are accepted: arbitrary URLs, files or commands cannot be supplied.

For example, the first invocation creates:

```text
experiments/local-models/practice/tool-success-first-pass/
  manifest.json
  fixture.json
  trace.jsonl
  analysis.json
  worksheet.md
```

Existing directories are never overwritten. Choose a new session to repeat an exercise. Symlinks along source-fixture or destination paths are prohibited. Invalid fixtures are rejected before the output directory is created.

## Scenarios

| Scenario | Reproduces | Student assignment |
| --- | --- | --- |
| `tool-success` | Allowed `lookup_lab_value({"key":"alpha"})`, in-memory `LAB_VALUE_42` result, terminal text | Link request/call/result; distinguish a correct call chain from independent task evaluation |
| `retry-429` | HTTP 429 with Retry-After; next request after the permitted virtual time | Preserve both attempts and the error, calculate permitted retry time, propose limits |
| `interrupted-stream` | Partial text claiming success; interruption before final and usage | Record `incomplete`; do not turn text into a verdict or unknown tokens into zero |
| `duplicate-action` | Dummy counter changed, response lost, operation repeated without an idempotency key | Distinguish “not executed” from “outcome unknown”, identify duplicate effects and propose controls |

The interpreter allows only two functions with fixed arguments. `increment_demo_counter` changes a number in process memory; there are no real side effects. `simulated-action-audit` shows an educational server log unavailable to the client when the response is lost. It is deliberately separate from `tool-response`: a lost response has `result: null` even when the audit log shows a counter change.

## Analysis and submission

1. Read the assignment and questions in `worksheet.md`; first record your hypothesis and the rule distinguishing response completion from task success.
2. Read `trace.jsonl` in `sequence` order. Link events via `request_id` and `call_id`; compare time only within the virtual scenario.
3. Compare the trace with `analysis.json`. Analysis preserves unsuccessful requests and lost responses. `response_state: final-received` means only that a terminal event exists. `verdict` always remains `null`.
4. Complete the “known / unknown” table, answers, handling algorithm and limitations of transfer to a real harness. Cite evidence by file name and `sequence`.
5. Submit the full bundle to the reviewer. They assess reasoning and trace-supported conclusions; the CLI awards no credit. A negative conclusion or discovered defect can be a correct exercise outcome.

`manifest.json` has `kind: lab-practice`, `evidence_class: synthetic` and initial `status: not-started`; answers and reviewer decision are blank. `fixture_sha256`, `trace_sha256`, `analysis_sha256` identify issued materials. Preserve `fixture.json`, `trace.jsonl` and `analysis.json` as issued; record your algorithm changes and conclusions separately in `worksheet.md`.

Tokens, cost and real inference time in `analysis.json` are `null` with reasons. Fast Node execution does not measure model performance. Zero exercise-execution cost does not replace missing model-attempt cost. Even a scenario with a final response gets no automatic `pass`.

`lab:check` completeness validation targets real educational reports with `kind: lab-report` and rejects this manifest. Do not rename `lab-practice` to `lab-report` or `run.json`, or import synthetic traces into `compare`. If attached to a lab report as educational material, label the exercise explicitly `synthetic`; it does not replace required real runs.

## For instructors and developers

Scenario sources are in [fixtures/practice](fixtures/practice/). They are open educational data, not hidden checks. The deterministic interpreter validates request order, response/call matching, allowed arguments, Retry-After and monotonic virtual time. Missing terminal events remain `incomplete`; a lost response leaves the client outcome `unknown`. Only the dummy service supports retry with the same idempotency key: tests verify deduplication and reject reuse for another operation. The CLI accepts only listed scenarios; arbitrary fixtures cannot be executed from the command line.

```bash
node --test tests/lab-practice.test.mjs
```

Tests validate protocol, preservation of unknown values, absence of run-record writes, overwrite prevention and symlink-escape prevention. They do not establish compatibility of any inference engine, provider or harness.
