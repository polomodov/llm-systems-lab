# LAB39. State layer: suspend/restore and fork for agent episodes

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisites | [LAB36](LAB36-space-deploy-smoke.md); either [LAB37](LAB37-space-harness-vm.md) or [LAB38](LAB38-space-tool-layer.md) |
| SPACE operations | `:suspend`, `:wake` (restore), `:pause`; durable fork through ECW (`scripts/tests/smoke-kind-sandbox-fork.py`) |
| Minimum | Mid-episode checkpoint: suspend → release node resources → restore → verify state → continue; fork prepared state into 3 copies and run three T002 attempts |
| Extensions | Move to another node via forced drain; `bench-sbx-balloon.py` for snapshot size |
| Time | Allow 1 day plus runs |
| Readiness | `implementation-required`: the runner has no episode pause/resume point |
| Initial state | Experiment `not-run`; educational manifest `not-started` |

## Objective

Test whether SPACE snapshots can provide agent state management: freeze a long episode and resume it later, or launch multiple independent attempts from one prepared state.

## Hypothesis

1. After `suspend` and restore, sandbox files, running processes and memory contents match their pre-snapshot state (control SHA-256 hashes), and the agent continues from the same turn.
2. Three attempts forked from one state behave as independent repetitions: their workspaces diverge only because of agent actions.

A checksum mismatch or lost process falsifies 1. A shared mutable resource between copies (file, port, cache) falsifies 2.

## Preparation

- SPACE terminology: `pause/resume` keeps the VM in memory; `suspend/restore` saves memory and state, releases node resources and later restores the snapshot; `wake` accepts any valid bring-up path. ECW `pause` corresponds to SPACE `suspend`, and `resume` to `restore`.
- Agent state is not confined to the VM: message history, provider cache and harness counters live outside it. Decide before execution which of these you preserve and how.
- The protocol fixes the snapshot turn and whether a resumed episode is the same run or a new one (describe explicitly under the [method](../method.md)).

```bash
npm run lab:new -- --lab LAB39 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB39-ryzen-01'
```

## Procedure

1. **Synthetic check without an agent.** In a sandbox: a random-data file on rootfs and in `/dev/shm`, a background process with an in-memory buffer; record SHA-256. `suspend`, await operation completion, verify node resources are released, `wake`, compare hashes and PID. 5 repetitions; suspend/restore time and snapshot size.

2. **Runner pause point.** Add a mode that saves external agent state (history/harness session if supported) after the Nth completed turn and calls `suspend`. Continuation restores the sandbox and external state. If the harness cannot resume a session, record that as a result and use the LAB38 design, where you control external state.

3. **Checkpointed episode.** T002 with a snapshot after turn N; pause at least 5 minutes between suspend and restore. Compare the outcome with an episode of the same harness without a snapshot.

4. **Fork.** Prepare a sandbox before the first agent turn (workspace uploaded, dependencies installed), fork it into 3 copies and run three T002 attempts. Record `pass@3` and `pass^3` only as observations from one triplet.

5. **Extension: migration.** On a cluster with two workers, repeat step 1 through `local.forced_drain_evacuates_sandbox` or a manual forced drain.

## Results tables

**Synthetic snapshot**

| Repetition | Suspend, s | Restore, s | Snapshot size, MiB | SHA rootfs | SHA shm | Process alive |
| --- | --- | --- | --- | --- | --- | --- |

**Episodes**

| Run ID | Mode | Snapshot turn | Pause, s | Verdict | Turns | USD | External state restored |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | no snapshot | — | — | | | | — |
| | with snapshot | | | | | | |
| | fork 1/3 | — | — | | | | |
| | fork 2/3 | — | — | | | | |
| | fork 3/3 | — | — | | | | |

## Deliverables

- Report, runner changes with tests and ledger rows.
- Raw: SPACE operation logs (operation IDs, states), checksums, `run.json` for every attempt.

## Completion criteria

- Synthetic check repeated 5 times; every discrepancy explained.
- Checkpointed episode has a record and verdict; continuation method described.
- Three forked attempts have records; independence checked by comparing workspaces.
- `npm test` and `npm run check` pass.

## Review questions

1. Which part of agent state does not fit into a VM snapshot?
2. Are forked attempts independent repetitions under the protocol if they share a provider cache?
3. How does snapshot size depend on the agent's prior actions?
4. When is `pause/resume` preferable to `suspend/restore` for an agent?

## Sources

- SPACE: `docs/architecture.md` (lifecycle), `docs/using-api.md`, `scripts/tests/smoke-kind-sandbox-fork.py`, `scripts/benchmarks/README.md` (balloon suspend/restore), `infra/space/kind/README.md` (forced drain).
- This repository: [method](../method.md), [LAB09](LAB09-agent-campaign.md) (pass@k).
