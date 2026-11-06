# LAB40. Sandbox latency: cold create, warm pool, base snapshot, restore

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB36](LAB36-space-deploy-smoke.md) on each measured machine |
| Startup paths | `cold`, `pool` (`docs/warm-pools.md`), `base-snapshot` (`docs/base-snapshots.md`), restore after `suspend` |
| Minimum | One template, ≥10 repetitions per path, both machines; confirmed actual boot mode for every attempt |
| Extensions | `bench-sbx-lifecycle.sh` and `bench-sbx-concurrent.sh`; harness templates from [LAB37](LAB37-space-harness-vm.md) |
| Time | Allow 3–4 hours per machine |
| Readiness | `target-machine` |
| Initial state | Educational manifest: `not-started` |

## Objective

Measure time to the first command for four sandbox startup paths on two machines. For an agent, this is the wait before the first action and the cost of each new attempt.

## Hypothesis

Median time from request to first stdout is ordered pool < base snapshot < restore < cold on both machines. The cold/pool ratio on machine B is no worse than twice that on machine A. Fix the ordering and thresholds in the protocol before measurement.

Figures in SPACE documentation are platform developer claims; label them as such in the report and keep them separate from your measurements.

## Preparation

- SPACE silently falls back to a slower path when the requested one is unavailable: `base-snapshot` and `pool` may fall back as far as cold boot without an error. Check every attempt's actual boot mode (`Boot mode:` from `space-sbxmgr` or the API response field); exclude and label mismatches.
- One template for the entire series (default `seed:latest`), fixed vCPU and memory.
- Randomize attempts across paths; record warmup (the first 2 attempts per path) separately.

```bash
npm run lab:new -- --lab LAB40 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB40-ryzen-01'
```

## Procedure

1. **Prepare paths.** Base snapshot (`space-tmplmgr base-snapshot --template ... --state true` on the node), warm pool (`space-admin-cli warm-pool create ...` with a small `--target-ready-slots`), one sandbox for suspend. Save commands and responses as raw evidence.

2. **Measurement tool.** A script in `experiments/space/bench/` records timestamps: create request → operation succeeded → `running` → first stdout from `echo ready` → `process_exited`. Use the native API and `time.monotonic_ns()`. Measure restore from `:wake` to first stdout.

3. **Series.** ≥10 counted attempts per path and machine, randomized order; after each, delete the sandbox and wait for pool replenishment.

4. **Host load.** Run `vmstat` in the background; mark attempts with load average above the protocol threshold.

5. **Extension.** `scripts/benchmarks/bench-sbx-lifecycle.sh` to compare with your measurement tool; `bench-sbx-concurrent.sh` for 1/2/4 concurrent creates.

## Results tables

| Machine | Path | Counted N | Excluded (boot mode) | Median to first stdout, ms | p90, ms | min / max, ms |
| --- | --- | --- | --- | --- | --- | --- |
| A | cold | | | | | |
| A | pool | | | | | |
| A | base-snapshot | | | | | |
| A | restore | | | | | |
| B | cold | | | | | |
| B | pool | | | | | |
| B | base-snapshot | | | | | |
| B | restore | | | | | |

One `measurements.tsv` row is one attempt and one metric; aggregates belong only in the report.

## Deliverables

- Reports for both machines, measurement tool in `experiments/space/bench/`, raw timestamps for all attempts including excluded ones.
- Boot-mode confirmation for every counted attempt.

## Completion criteria

- At least 10 counted attempts with confirmed boot mode for each machine and path.
- Ordering and threshold hypothesis accepted or rejected from raw data.
- Excluded attempts and reasons listed.

## Review questions

1. Which stage dominates cold create, and why does the pool eliminate it?
2. Why is silent boot-mode fallback dangerous for a benchmark?
3. How does template memory size affect restore?
4. Which path would you choose for a batch of 30 agent attempts, and why?

## Sources

- SPACE: `docs/warm-pools.md`, `docs/base-snapshots.md`, `scripts/benchmarks/README.md`, `scripts/benchmarks/bench-sbx-lifecycle.sh`, `docs/using-api.md`.
- This repository: [protocol](../method.md), [LAB26](LAB26-concurrent-load.md) as an example concurrent-load report.
