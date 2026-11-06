# LAB47. EKS, Karpenter and KEDA: GPU-serving autoscaling and token cost

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the Kubernetes and GPU branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB45](LAB45-k8s-gpu-vllm-capacity.md) (load methodology and replica capacity); [LAB49](LAB49-aws-network-iam.md) (LAB48 account with budget and GPU quota, VPC module with endpoints) |
| Environment | AWS: EKS, Karpenter, one small GPU instance type (e.g. `g6.xlarge` or `g5.xlarge`; verify regional availability) |
| Minimum | Terraform deployment, vLLM with a small model, KEDA using a queue metric, step load, scaling-time breakdown, cost per million tokens, `terraform destroy` with residual-resource check |
| Extensions | Spot instances and interruption behavior; scale to zero; NVIDIA GPU Operator versus a ready-made EKS AMI with driver |
| Time | Allow 1 day; keep the cluster running only while working |
| Readiness | `target-machine`; requires an AWS account and costs estimated by the operator |
| Initial state | Educational manifest: `not-started` |

## Objective

Test GPU-serving scaling in the cloud, where every new replica means another machine, and calculate cost per million tokens at different utilization levels. Also build a GPU-node EKS cluster end to end with Terraform.

## Hypothesis

1. After a step increase in load, a new replica takes more than 3 minutes to become ready; node bring-up, driver readiness and image download account for over half of that, rather than loading the small model's weights.
2. Cost per million output tokens near the LAB45 replica capacity (recalculated for the cloud GPU) differs by at least a factor of 3 from cost at 20% utilization.

Fix thresholds, model and instance price (with date and source) in the protocol before execution.

## Preparation

- Read: EKS GPU-node documentation, Karpenter (NodePool, EC2NodeClass, limits, disruption), KEDA (ScaledObject, Prometheus scaler), `terraform-aws-modules/eks`.
- **Costs.** Before creating resources, enable an AWS Budgets budget with alerts, set Karpenter NodePool `limits` (at most 2 GPU nodes), and record expected session cost using prices from the AWS website. Prices are AWS data as of the access date, not your measurements.
- **Secrets.** AWS credentials come from a profile or environment variables outside the repository; do not commit `terraform.tfstate`, `*.tfvars` containing account identifiers, or kubeconfig. Reports include region and instance types, without account ID.
- Terraform code and manifests belong in `experiments/k8s-gpu/terraform/`, with pinned provider and module versions. Use the LAB49 VPC module; the GPU NodePool can use the [LAB50](LAB50-aws-terraform-ci.md) module; store state in the [LAB48](LAB48-aws-account-baseline.md) bucket.

```bash
npm run lab:new -- --lab LAB47 --session aws-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB47-aws-01'
```

## Procedure

1. **Cluster.** `terraform apply`: VPC, EKS, a managed node group for system pods, Karpenter with a limited GPU-instance NodePool. Save the plan (without account identifiers), apply time and versions.
2. **GPU readiness.** The first pod requesting `nvidia.com/gpu: 1` causes Karpenter to provision a node. Record timestamps: pod created → NodeClaim created → instance launched → node `Ready` → `nvidia.com/gpu` in allocatable → pod `Running`.
3. **Serving.** vLLM with a small open model, Prometheus for vLLM metrics, KEDA ScaledObject using waiting-request queue metrics (threshold fixed in the protocol), `maxReplicaCount` 2.
4. **Step load.** LAB45 load generator: N minutes below one replica's capacity, then a step above it. Record stages of the second replica's appearance and TTFT p95 during and after the wait.
5. **Cost.** Ten-minute runs at three utilization levels. Cost per million output tokens = Σ across all GPU instances (hourly price × billed hours for the run, including idle time) / (all replicas' output tokens / 10⁶). Before each run, record GPU-node count from `kubectl get nodeclaims`; if the second replica from step 4 remains alive, include its instance in the sum. Account separately for the system-pod node and EKS control plane.
6. **Teardown.** `terraform destroy`. Then use LAB48 `janitor.sh` and AWS CLI to verify that no EC2 instances, EBS volumes, load balancers, NAT gateways or Elastic IPs remain with this lab's tags. Save verification output without account identifiers.

## Results tables

| GPU-replica stage | First node, s | Scaling under load, s |
| --- | --- | --- |
| NodeClaim created | | |
| Instance launched | | |
| Node `Ready` | | |
| `nvidia.com/gpu` in allocatable | | |
| Image downloaded | | |
| Weights loaded | | |
| Readiness | | |
| Total | | |

| Utilization | GPU instances | Output tokens in 10 min | Instance price, USD/h (source, date) | Cost per 1M tokens, USD |
| --- | --- | --- | --- | --- |
| ~20% | | | | |
| ~60% | | | | |
| near capacity | | | | |

| Resource after destroy | Expected | Actual |
| --- | --- | --- |
| EC2 / EBS / LB / NAT / EIP | none | |

## Deliverables

- Report, Terraform code and manifests in `experiments/k8s-gpu/terraform/`, raw timestamps and load-generator results, residual-resource check output.
- Actual AWS Billing session expenses (amount and period, without account ID).

## Completion criteria

- Replica startup time broken down by stage; hypothesis 1 accepted or rejected.
- Cost per million tokens calculated for three utilization levels, with price and date.
- Resources deleted; residual-resource check empty.

## Review questions

1. Why cannot GPU nodes scale as quickly as CPU nodes, and how is this addressed in practice (reserve, warm pool, prepared AMIs, image cache)?
2. Traffic will double next month. How will you calculate GPU procurement needs, and what will you do if they are unavailable?
3. Why is scale to zero risky for LLM serving, and when is it justified?
4. Which expenses are absent from instance price but contribute to token cost?

## Sources

- Amazon EKS, Karpenter and KEDA documentation; `terraform-aws-modules/eks`.
- vLLM documentation: metrics and Kubernetes deployment.
- This repository: [LAB45](LAB45-k8s-gpu-vllm-capacity.md), [protocol](../method.md).
