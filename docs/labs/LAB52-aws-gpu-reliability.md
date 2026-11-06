# LAB52. GPU-serving reliability in AWS: GPU metrics, Spot interruption and game day

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the AWS and Terraform branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB47](LAB47-k8s-gpu-eks-autoscaling.md) (cluster, vLLM, load generator); preferably [LAB51](LAB51-aws-gpu-cold-start.md) for faster new-replica startup |
| Environment | AWS, `aws-NN` sessions; LAB47 cluster, 2 GPU nodes of one small instance type, one Spot |
| Minimum | DCGM exporter and GPU metrics in Prometheus; three alerts (utilization, GPU memory, XID errors or failed health check); Karpenter with SQS interruption queue; PodDisruptionBudget and 2 vLLM replicas; three-scenario game day under load with error and TTFT measurements |
| Extensions | AWS Fault Injection Service for Spot interruption instead of manual action; Amazon Managed Prometheus/Grafana versus self-hosted; an on-call runbook per scenario |
| Time | Allow 1 day |
| Readiness | `target-machine`; requires an AWS account, GPU/Spot quotas and spending |
| Initial state | Educational manifest: `not-started` |

## Objective

Verify that serving survives typical cloud GPU-fleet failures and learn to detect them in metrics. Site Lead requirements call this “robust systems for deployment, monitoring, scalability, and reliability of infrastructure supporting AI/ML workloads”. This lab provides your own figures and runbooks instead of generalities.

## Hypothesis

1. With two replicas, a PodDisruptionBudget of `minAvailable: 1` and Karpenter interruption handling, interrupting a Spot node at load below one replica's capacity causes fewer than 1% failed requests, and TTFT p95 rises by no more than a factor of 3 during the event.
2. Without PodDisruptionBudget and interruption queue, the same scenario causes at least 5% failed requests.
3. Each of the three alerts fires in its game-day scenario within the acceptable time fixed in the protocol.

Fix thresholds, load, instance type and dated Spot/On-Demand prices in the protocol before execution.

## Preparation

- Read: NVIDIA DCGM exporter, Karpenter (interruption handling, disruption budgets, Spot), Kubernetes PodDisruptionBudget, AWS Fault Injection Service (Spot interruption action), NVIDIA XID-code documentation.
- A new account has a separate Spot quota; check it in Service Quotas beforehand.
- Manifests and alert rules belong in `experiments/k8s-gpu/manifests/LAB52/`; Terraform changes in `experiments/k8s-gpu/terraform/`.

```bash
npm run lab:new -- --lab LAB52 --session aws-01
LAB_DIR='experiments/aws/measurements/LAB52-aws-01'
```

## Procedure

1. **Observability.** DCGM exporter as a DaemonSet on GPU nodes, Prometheus and a dashboard: GPU utilization, memory, temperature, errors, plus vLLM metrics (queue, TTFT, ITL). Three alert rules with protocol thresholds.
2. **Resilience.** Two vLLM replicas on different nodes (anti-affinity), PodDisruptionBudget, SQS interruption queue in Karpenter settings.
3. **Scenario 1: Spot interruption.** Under constant load, interrupt the Spot node through FIS or emulate a queue event. Record error rate, TTFT p95 before/during/after, and time to restore the second replica.
4. **Scenario 2: the same failure without protection.** Remove PodDisruptionBudget and interruption queue; repeat.
5. **Scenario 3: GPU degradation.** Simulate a failure: vLLM process crash with a CUDA error, GPU memory filled by another process, or a disabled health check. Verify that the alert fires and the pod leaves load balancing.
6. **Runbook.** Half a page per scenario: how to notice, what to check, what to do, when to escalate.
7. **Teardown.** `terraform destroy`, LAB48 `janitor.sh`.

## Results tables

| Scenario | Failed requests, % | TTFT p95 before / during / after, ms | Recovery, s | Alert fired after, s |
| --- | --- | --- | --- | --- |
| Protected Spot interruption | | | | |
| Unprotected Spot interruption | | | | |
| GPU degradation | | | | |

| Item | USD per hour (source, date) | Session cost, USD |
| --- | --- | --- |
| GPU On-Demand | | |
| GPU Spot | | |
| Other (system-pod node, control plane, FIS) | | |

## Deliverables

- Report, manifests, alert rules, dashboard export, raw load-generator results per scenario, three runbooks, `janitor.sh` output.
- Actual AWS Billing session expenses without account ID.

## Completion criteria

- All three hypotheses accepted or rejected with figures.
- A runbook written for every scenario; resources deleted, residual-resource check empty.

## Review questions

1. What share of the serving GPU fleet would you keep on Spot, and what does that depend on?
2. Which XID errors mean “restart the pod”, and which mean “retire the node”?
3. Which three metrics would you present at the London site's weekly reliability review?
4. How would you organize on-call duties for five infrastructure engineers without burning out the team?

## Sources

- NVIDIA DCGM exporter; NVIDIA XID-code documentation.
- Karpenter documentation: interruption handling, disruption; Kubernetes PodDisruptionBudget; AWS Fault Injection Service.
- This repository: [LAB47](LAB47-k8s-gpu-eks-autoscaling.md), [LAB51](LAB51-aws-gpu-cold-start.md), [protocol](../method.md).
