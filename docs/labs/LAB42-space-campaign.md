# LAB42. Agent campaigns on SPACE: concurrent episodes and Docker comparison

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisites | [LAB09](LAB09-agent-campaign.md), [LAB37](LAB37-space-harness-vm.md), [LAB41](LAB41-space-network-secrets.md) |
| Harnesses | Pi and OpenHands (both with the LAB37 SPACE backend); others after their own lab and template |
| Minimum | The same series (2 harnesses × T002 × 3 repetitions) through Docker and SPACE on machine A at concurrency 1 and 2 |
| Extensions | Concurrency 4 on machine A; find machine B's concurrency limit; T001 replay |
| Time | Allow 1 day plus series runtime |
| Readiness | `implementation-required`: the runner executes one record per invocation; the series scheduler is written during the lab |
| Initial state | Experiment `not-run`; educational manifest `not-started` |

## Objective

Run the LAB09 comparison series through the SPACE backend with concurrent episodes and compare with the Docker runner under the same conditions: pass rate, series wall-clock, infrastructure failures separately from agent failures, peak host memory.

## Hypothesis

1. Docker and SPACE pass rates for the same series differ no more than repetitions can explain (fix the LAB09 comparison rule before the series).
2. At concurrency 2, SPACE series wall-clock is lower than sequential execution, without an increase in infrastructure failures.
3. Machine B's concurrency limit is determined by memory: exceeding the LAB36-derived budget produces sandbox-creation failures rather than silent agent degradation.

## Preparation

- LAB09 series conditions: model, provider, variant, task budgets from the contract, attempt order, repetition count. Changed conditions mean a new series.
- Machine memory budget: free RAM after LAB36 bring-up minus the OS reserve; template memory × concurrency must not exceed the budget.
- Every attempt is a new `new-run` record with its own run ID; repeating `run` on one record is prohibited.

```bash
npm run lab:new -- --lab LAB42 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB42-ryzen-01'
```

## Procedure

1. **Series scheduler.** A script in `experiments/space/campaign/` creates and prepares records from a series plan, launches up to P simultaneous attempts through `npm run run -- --sandbox ...`, preserves sealed conditions and records start/end timestamps for each attempt. Offline test with a fake runner.

2. **Plan before execution.** `raw/protocol.md`: matrix (harness × environment × concurrency × repetition), randomized order, stop criterion (e.g. 3 consecutive infrastructure failures).

3. **Series on machine A.** Docker P=1, SPACE P=1, SPACE P=2; collect `vmstat` and live sandbox counts in parallel.

4. **Evaluation.** An independent judge for each record according to [harness-workflow](harness-workflow.md); use `npm run compare` only under identical conditions.

5. **Machine B.** SPACE P=1, then P=2 and higher until the first creation failure or OOM; a Docker series is optional.

## Results tables

| Machine | Environment | P | Harness | Attempts | Pass / partial / fail | Infrastructure failures | Series wall-clock, s | Peak used RAM, MiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | Docker | 1 | pi | | | | | |
| A | SPACE | 1 | pi | | | | | |
| A | SPACE | 2 | pi | | | | | |
| A | Docker | 1 | openhands | | | | | |
| A | SPACE | 1 | openhands | | | | | |
| A | SPACE | 2 | openhands | | | | | |
| B | SPACE | 1…N | | | | | | |

An infrastructure failure is an `aborted` record caused by the environment (sandbox creation, network, timeout before the first turn). State the cause in the report and keep it distinct from agent fail.

## Deliverables

- Scheduler and test, report with protocol, all run IDs, judge verdict for each, `npm run compare` output.
- Raw: attempt timestamps, `vmstat`, sandbox state.

## Completion criteria

- All planned attempts have records or an explained `not-run`.
- Verdicts assigned by an independent judge; comparison only under identical conditions.
- Machine B's concurrency limit found, or the earlier stop explained.
- `npm test` and `npm run check` pass.

## Review questions

1. Which failures appeared only on SPACE, and what caused them?
2. What limited concurrency on machine B: memory, CPU, disk or the platform itself?
3. Does concurrency affect agent behavior (e.g. via provider rate limits), and how can this be separated from environment effects?
4. Which LAB37–41 component proved optional for this series?

## Sources

- This repository: [LAB09](LAB09-agent-campaign.md), [LAB10](LAB10-ablation.md), [LAB26](LAB26-concurrent-load.md), [method](../method.md), `scripts/compare.mjs`.
- SPACE: `scripts/benchmarks/bench-sbx-concurrent.sh`, `docs/warm-pools.md`.
