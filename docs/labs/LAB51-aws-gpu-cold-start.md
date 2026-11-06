# LAB51. GPU-replica cold start in AWS: image, weights and a warm node

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the AWS and Terraform branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB47](LAB47-k8s-gpu-eks-autoscaling.md) (EKS cluster with Karpenter and replica-startup breakdown) and [LAB49](LAB49-aws-network-iam.md) (S3/ECR endpoints) |
| Environment | AWS, `aws-NN` sessions; LAB47 cluster, at most 2 GPU nodes of one small instance type |
| Minimum | LAB47 baseline; three improvements one at a time: same-region ECR image and a smaller image, weights from S3 via endpoint instead of Hugging Face Hub, image/weight preloading onto the node (data EBS snapshot for EC2NodeClass or preload DaemonSet); final time to a ready replica |
| Extensions | Lazy image loading (SOCI or equivalent; support on the selected AMI is `unverified`, check current documentation); a warm pool with one stopped node; faster-loading weight format (safetensors versus others if the model exists in both) |
| Time | Allow 1 day; keep the cluster running only during measurements |
| Readiness | `target-machine`; requires an AWS account, GPU quota and spending |
| Initial state | Educational manifest: `not-started` |

## Objective

[LAB47](LAB47-k8s-gpu-eks-autoscaling.md) shows the components of GPU-replica startup time. Here, reduce that time one item at a time and calculate each measure's benefit and cost. This answers “how quickly can you handle a traffic spike?”, a question for a serving-infrastructure lead.

## Hypothesis

1. A same-region ECR image via endpoint and S3 weights via endpoint together reduce NodeClaim-to-readiness time by at least 30% relative to the LAB47 baseline.
2. Preloading image and weights onto the node reduces time by at least another 30%, but adds an ongoing cost (snapshot storage or idle disk) that must be calculated in USD per month.

Fix thresholds, model (identifier, revision, size), instance type and AMI in the protocol before execution.

## Preparation

- Read: Karpenter EC2NodeClass documentation (`blockDeviceMappings`, `amiSelectorTerms`, user data), EKS GPU AMI documentation, Amazon ECR (replication, scanning), vLLM model loading from a local path and S3.
- Reapply LAB47 spending rules: budget, NodePool `limits`, dated instance price.
- Code and manifests belong in `experiments/k8s-gpu/terraform/` and `experiments/k8s-gpu/manifests/LAB51/`, building on LAB47 code.

```bash
npm run lab:new -- --lab LAB51 --session aws-01
LAB_DIR='experiments/aws/measurements/LAB51-aws-01'
```

## Procedure

1. **Baseline.** Repeat the LAB47 measurement for one cold node: pod created → NodeClaim → instance → `Ready` → `nvidia.com/gpu` → image downloaded → weights loaded → readiness. Three repetitions, median.
2. **Image.** Move the vLLM image to ECR in your region; build a reduced variant (only required components), record sizes. Repeat measurement.
3. **Weights.** Download weights from S3 via gateway endpoint to local node NVMe or EBS (init container or sidecar) instead of the Hub. Repeat measurement.
4. **Preloading.** Prepare an EBS snapshot with image and weights and attach it in EC2NodeClass, or a preload DaemonSet on a warm node. Repeat measurement and calculate monthly storage cost.
5. **Outcome.** Compare medians and break down improvements by stage. If LAB47 hypothesis 1 was rejected (image and weights took less than half the time), explain why this lab's measures yield little benefit.
6. **Teardown.** `terraform destroy`, delete snapshots and ECR images if not needed later, run LAB48 `janitor.sh`.

## Results tables

| Stage, s (median of 3) | LAB47 baseline | ECR + smaller image | + S3 weights | + preloading |
| --- | --- | --- | --- | --- |
| NodeClaim → instance | | | | |
| Instance → `Ready` | | | | |
| `Ready` → GPU in allocatable | | | | |
| Image downloaded | | | | |
| Weights loaded | | | | |
| Readiness | | | | |
| Total | | | | |

| Measure | Improvement, s | Ongoing cost, USD/month (source, date) | Maintenance complexity |
| --- | --- | --- | --- |
| Same-region ECR | | | |
| Smaller image | | | |
| S3 weights | | | |
| Preloading | | | |

## Deliverables

- Report, Terraform/manifest changes, image sizes, raw timestamps for all repetitions, cost calculations for measures, `janitor.sh` output.
- Actual AWS Billing session expenses without account ID.

## Completion criteria

- Every measure has a stage-by-stage improvement and cost; both hypotheses accepted or rejected.
- Resources, snapshots and unnecessary images deleted; residual-resource check empty.

## Review questions

1. Which cold-start stage cannot be shortened by spending money, and what is done instead?
2. When is keeping a warm reserve cheaper than losing requests during scaling?
3. How does the picture change for a 140 GB model on an 8-GPU node?
4. What would you measure in production to detect that cold start has become slow again?

## Sources

- Karpenter documentation: EC2NodeClass; Amazon EKS documentation: GPU AMI; Amazon ECR.
- vLLM documentation: model loading and Kubernetes deployment.
- This repository: [LAB47](LAB47-k8s-gpu-eks-autoscaling.md), [LAB49](LAB49-aws-network-iam.md), [LAB46](LAB46-k8s-gpu-inference-routing.md), [protocol](../method.md).
