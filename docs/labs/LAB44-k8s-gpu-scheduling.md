# LAB44. Scheduling a simulated GPU fleet: DRA, Kueue and gang scheduling

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the Kubernetes and GPU branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB01](LAB01-reproducibility.md); Linux with Docker and 16+ GB RAM |
| Machine | B: HONOR MagicBook X16 / 32 GB / Ubuntu, Kind; no real GPU required |
| Minimum | Part A (DRA with example driver), part B (Kueue quotas on a KWOK fleet), part D (CPU training through JobSet with pod termination) |
| Extensions | Part C (Topology Aware Scheduling and native gang scheduling); repeat part B with a different preemption policy |
| Time | Allow 1 day |
| Readiness | `target-machine` |
| Initial state | Educational manifest: `not-started` |

## Objective

Learn to manage a shared GPU fleet as a platform owner: request devices by attributes through DRA, divide the fleet between teams with quotas, launch distributed jobs on an all-or-nothing basis, and observe training recovery after pod loss. All of this is tested on simulated devices because scheduler logic does not depend on whether the GPU is real.

## Hypothesis

1. A DRA claim with a CEL selector on a device attribute is placed only on suitable simulated GPUs; an unsatisfiable claim leaves the pod `Pending` with an understandable event.
2. For the same job stream, a Kueue cohort with borrowing raises average simulated GPU occupancy by at least X percentage points versus strict quotas, while the largest job's wait time grows by no more than a factor of Y.
3. A CPU DDP job through JobSet restarts after one worker is killed and resumes training from the latest checkpoint, losing at most one checkpoint interval.

Fix X, Y and the checkpoint interval in the protocol before the first run.

## Preparation

- Read: Kubernetes Dynamic Resource Allocation documentation; `kubernetes-sigs/dra-example-driver`, `kubernetes-sigs/kwok`, `kubernetes-sigs/kueue` (ClusterQueue, LocalQueue, cohort, preemption, Topology Aware Scheduling), `kubernetes-sigs/jobset`; Kubernetes 1.37 gang-scheduling release notes (KEP 4671, beta).
- The Kind Kubernetes version must be at least 1.34 (DRA GA). Check release notes and record whether the selected version requires a gang-scheduling feature gate.
- Pin Kind, node image, example driver, KWOK, Kueue and JobSet versions.
- The job-stream generator is deterministic (fixed seed) and lives in `experiments/k8s-gpu/sim/`.

```bash
npm run lab:new -- --lab LAB44 --session honor-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB44-honor-01'
```

## Procedure

1. **Part A: DRA.** A Kind cluster with `dra-example-driver`, publishing simulated GPUs with attributes. Write and apply:
   - a claim for one device with memory attribute at least the threshold;
   - a claim for two devices on one node;
   - a ResourceClaim shared by two pods;
   - a deliberately unsatisfiable claim.
   Save `ResourceSlice`, `DeviceClass`, claims, events and final placement.
2. **Part B: fleet and quotas.** A separate Kind cluster, 8 KWOK nodes with extended resource `example.com/gpu: 8` and `rack`, `block` labels. KWOK Stage resources define pod “training” duration. Install Kueue: three LocalQueues for `research`, `product`, `eval`, one ClusterQueue per team.
   - Run B1: strict quotas without a cohort.
   - Run B2: the same job stream, shared cohort with borrowing and preemption.
   Stream: long 16–32 “GPU” jobs for `research`, short 1–4 jobs for `product` and `eval`, fixed total series duration. Capture GPU occupancy and queues by team every minute.
3. **Part C (extension): topology and gang.** Require “all 16 pods in one `block`” through Kueue Topology Aware Scheduling, then deliberately fragment the fleet with small jobs. Separately try native Kubernetes 1.37 gang scheduling and compare behavior when capacity is insufficient.
4. **Part D: training and failure.** JobSet with PyTorch DDP on CPU (`gloo` backend), 2–4 workers, a small model on synthetic data, checkpoint every N steps to a shared volume. Delete one pod halfway through training. Record when the job noticed, restart duration, resume step and steps lost.
5. **Teardown.** Delete both Kind clusters.

## Results tables

| Claim (part A) | Expected | Actual: placement / event |
| --- | --- | --- |
| Memory attribute ≥ threshold | | |
| Two devices on one node | | |
| Shared claim for two pods | | |
| Unsatisfiable | `Pending` | |

| Run (part B) | Average GPU occupancy, % | `research` job wait, median / max | Small-job wait, median | Preemptions |
| --- | --- | --- | --- | --- |
| B1: strict quotas | | | | |
| B2: cohort + borrowing | | | | |

| Event (part D) | Time since pod deletion, s | Training step |
| --- | --- | --- |
| Last checkpoint before failure | — | |
| Failure detected | | — |
| All workers back in `Running` | | — |
| Training resumed | | |

## Deliverables

- Report, manifests and stream generator in `experiments/k8s-gpu/sim/`, raw occupancy/queue snapshots, scheduler events, training logs.
- X, Y and checkpoint interval values fixed before execution.

## Completion criteria

- All four part A claims compared with expectations.
- B1 and B2 run on the same stream with the same seed; hypothesis 2 accepted or rejected from raw data.
- Part D quantifies restart and lost steps.

## Review questions

1. How is DRA better than device plugins and extended resources? When is a device plugin still reasonable?
2. Why does distributed training need gang scheduling, and what happens without it when GPUs are scarce?
3. How would you design quotas and priorities for 512 GPUs and five teams to keep utilization high without starving multi-day jobs?
4. How does part D differ from real multi-node GPU training (NCCL, network topology, Xid errors), and which conclusions therefore do not transfer?

## Sources

- Kubernetes documentation: Dynamic Resource Allocation; [Kubernetes v1.36: DRA updates](https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/); v1.37 release notes.
- `kubernetes-sigs/dra-example-driver`, `kubernetes-sigs/kwok`, `kubernetes-sigs/kueue`, `kubernetes-sigs/jobset`.
- This repository: [protocol](../method.md).
