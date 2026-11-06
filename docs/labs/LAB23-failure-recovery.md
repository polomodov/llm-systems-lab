# LAB23. Agent recovery after controlled failures

## Profile

| Field | Value |
| --- | --- |
| Type | Tool fault injection and observation of agent behavior |
| Time | 3–6 hours of engineering preparation; then 6 attempts and evaluation |
| Prerequisites | LAB09; LAB20 is useful for aligning trace annotations |
| Readiness | `implementation-required` for a real agent; four offline scenarios are already available |
| Minimum scope | One task × no fault/one controlled fault × three pairs = 6 attempts |
| Extension | Separate series: 429, timeout, interrupted stream, repeating an operation after a lost response |

## Objective

Test whether an agent can recognize a failure, preserve state, and continue without duplicating actions. Distinguish HTTP client recovery from a decision the agent actually made.

## Hypothesis

“After one prescheduled temporary read error, the agent completes the selected task without changing the outcome or exceeding a predefined recovery limit.” The factor is one response from the selected tool at a specified point: a normal result or a controlled temporary error.

For the minimal pilot, set a limit of no more than two additional calls to this tool and 60 seconds of additional wall-clock time relative to the paired baseline. These training thresholds may be changed **before** the series with a workload-based justification. Pilot support requires a pass in every fault attempt, no duplicated changes, and compliance with both limits in every measured pair. Three pairs do not assess rare production failures.

## Preparation

```bash
npm run lab:new -- --lab LAB23 --session recovery-pilot
LAB_DIR='experiments/local-models/measurements/LAB23-recovery-pilot'
npm run lab:practice -- --scenario retry-429 --session recovery-pilot
npm run lab:practice -- --scenario interrupted-stream --session recovery-pilot
npm run lab:practice -- --scenario duplicate-action --session recovery-pilot
npm run check
```

Using [practice.md](practice.md), complete a worksheet for each scenario: where the error became visible, which events were confirmed, and why an unknown outcome cannot be recorded as successful. These are fixed artificial traces, not an API test of the current harness. Their metrics must not be added to real runs.

For the first real series, choose a read-only operation in the existing T002 or a registered [migration episode](episodes/interface-migration/episode.md). Do not induce a failure by disconnecting the user's network, GPU, shared model server, or working service. An isolated test layer introduces the error only into this attempt's traffic; tools with external side effects are replaced with fixtures.

## Procedure

1. **Define the causal model of the failure.** The minimal variant returns a structured `temporary-unavailable` error on the first read of a known file; the next call with the same arguments returns the original contents. The file does not change. The event is defined by tool name, normalized arguments, and match count, rather than a random delay. If the agent never calls the selected operation, record the attempt as `fault-not-triggered`, not successful recovery. Retain it and plan a separate new complete series when correcting the protocol.

2. **Implement engineering acceptance.** Add a test-only shim to one adapter, a fixed fault manifest, and a trace of `scheduled`, `triggered`, `delivered`, and `recovered/failed` events. The fault policy, its hash, and stage must be sealed and separate comparison groups. Normal configurations must not activate the shim. The current runner provides no general `--fault` flag; do not invent commands before implementation. A new public episode additionally requires registration of a task ID, seed, and external judge.

3. **Separate retry layers.** Document native HTTP retries, SDK retries, tool retries, and agent actions. For an experiment on agent behavior, the error must reach its transcript as an error result. If the SDK silently recovers the response, the measurement concerns client resilience; the agent did not see the failure. Do not disable retries without recording that change identically in both configurations. Do not deliberately exceed quotas to trigger real vendor 429 responses: use a local mock.

4. **Test the shim without a model.** The same request sequence must introduce exactly one failure, return a normal result afterward, and leave parallel runs unaffected. Checks cover an incorrect fault target, duplicate registration, cleanup after timeout, recording error delivery, and absence of secrets in the raw trace. A structurally incomplete stream must not silently become a successful empty response. For `duplicate-action`, the test tool keeps an operation log with a unique request ID; verify state, not just request count.

5. **Fix pairs and limits.** Order: baseline → fault, fault → baseline, baseline → fault. Initial files, model, harness, network, tools, output/context, seed where supported, overall budget, and timeout must match. The fault variant receives no extra budget: its costs fit within the same boundaries. The recovery limits in the hypothesis are analytical criteria inside the overall budget, not permission to exceed it.

6. **Run six real attempts after acceptance.** Use the accepted extension interface and normal record lifecycle. Each attempt receives a new ID and isolated workspace; fault manifest traces are linked to it. Do not adjust the prompt, retry limit, or fault target midway through the series. If a fault leaks between runs, stop the experiment, retain every started attempt, and create a new mechanism version.

7. **Obtain an independent verdict.** The judge evaluates the final task against the normal contract. Separately, an analyst checks error delivery, subsequent calls, confirmed writes, and boundary compliance. A process marked `Completed` does not mean a write happened exactly once. If the trace cannot confirm state, mark the recovery outcome unknown, even if the model's answer looks plausible.

8. **Calculate recovery cost.** For each fault run, show trigger/delivery, outcome, additional call count, input/output above baseline, total wall-clock time, and paired difference. Include all retries, including hidden SDK retries when observable. For an error after a state change, separately record the number of **applied operations** and requests: these differ with correct deduplication. Missing tokens/cost remain unknown; an incomplete metric does not become zero.

9. **Extend one failure class at a time.** After the read-only experiment, separately study a lost response after a confirmed write, HTTP 429, timeout, and an interrupted stream. Redefine the intervention point, normal outcome, and recovery rule for each series. Several random failures in one attempt may suit a stress test but do not explain the contribution of a specific retry mechanism. Do not mix this experiment with LAB08 isolation checks: the subject here is behavior after a delivered failure.

## Results tables

| Fault policy | Target operation | Point/counter | What the agent sees | What changed in state | Raw evidence |
| --- | --- | --- | --- | --- | --- |
| Before running | Tool + arguments | First matching call | Error result | Nothing in the minimal experiment | Manifest/hash |

| Pair | Baseline ID/verdict | Fault ID/verdict | Triggered/delivered | Additional calls | Δ time, s | Δ tokens | Threshold met |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1/2/3 | After judging | After judging | Yes/no/unknown | From trace | From measurements | Only if known | Yes/no/insufficient data |

| Run / operation | Requests | Confirmed applications | State afterward | Who retried | Evidence |
| --- | --- | --- | --- | --- | --- |
| Actual ID | From trace | From test tool log | Verified/unknown | SDK/harness/agent | File/event ID |

## Deliverables

Three completed offline worksheets, the fault policy and engineering checks, the preregistered protocol, six real records after acceptance, independent verdicts, trace annotations, and the test tool's final state. List faults that were not triggered/not delivered separately. If the engineering component is not implemented, the report contains only synthetic/protocol evidence and explicitly marks measurements `not-run`. Format: [report-validation.md](report-validation.md).

## Completion criteria

- [ ] The minimal intervention affects one defined operation in this run.
- [ ] The shim is tested offline and does not affect user services or other attempts.
- [ ] SDK retries are separated from model actions after a visible error.
- [ ] All three pairs are retained; triggered/delivered events are confirmed by the trace.
- [ ] Task outcome and state are verified, including the applied-operation count for the write extension.
- [ ] The recovery threshold is predefined; a negative result is retained and explained.
- [ ] Synthetic traces are not called model measurements; `npm run check` passes.

## Review questions

1. Why does repeating an HTTP request not prove that a business operation was repeated?
2. What is measured if the SDK hides a temporary error from the agent?
3. Why can a fault that never occurred not count as successful recovery?
4. How does a timeout before execution differ from a timeout after a write?
5. How can recovery cost be separated from changes in a nondeterministic model's normal behavior?

## Sources

- [Method: observability and errors](../method.md), [common infrastructure](../../experiments/common/README.md).
- [Offline practice](practice.md), [LAB08: local bridge acceptance](LAB08-local-bridge.md), [LAB20: evaluation agreement](LAB20-judge-calibration.md).
- [Record lifecycle](../../results/README.md), [public episodes](episodes/README.md).
