# LAB49. GPU-platform network and IAM: VPC, model-weight delivery and pod access to AWS

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the AWS and Terraform branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB48](LAB48-aws-account-baseline.md) (state, budget, residual-resource script) |
| Environment | AWS, `aws-NN` sessions; one small CPU instance and S3, no GPU required |
| Minimum | VPC through `terraform-aws-modules/vpc` with public/private subnets, NAT gateway, S3 gateway endpoint, ECR interface endpoint; model-weight download speed/cost via NAT and endpoint; least-privilege IAM for reading one S3 prefix |
| Extensions | EKS Pod Identity versus IRSA on a small EKS cluster without GPUs; one NAT gateway per VPC versus one per availability zone |
| Time | Allow 1 day; delete the NAT gateway in the same session |
| Readiness | `target-machine`; requires an AWS account and modest spending |
| Initial state | Educational manifest: `not-started` |

## Objective

Understand the network through which GPU nodes obtain images and model weights, and calculate its cost. In AI infrastructure interviews, “why is the NAT bill larger than the GPU bill?” comes up more often than CUDA questions. Also produce a ready-to-use VPC module for [LAB47](LAB47-k8s-gpu-eks-autoscaling.md).

## Hypothesis

1. Downloading 10 GB of model weights from S3 into a private subnet through a NAT gateway costs at least 0.40 USD per run for NAT data processing alone; through an S3 gateway endpoint this cost is zero at equal or higher speed.
2. A role with access to one S3 prefix cannot read a neighboring prefix or write to the allowed prefix: 0 of N violation attempts succeed.

Fix regional NAT data-processing price (date and source), weight size and thresholds in the protocol before execution. Prices are AWS claims as of access date, not your measurements.

## Preparation

- Read: AWS NAT gateway documentation (data-processing pricing), VPC endpoints (gateway and interface), IAM policy evaluation logic, EKS Pod Identity and IRSA; `terraform-aws-modules/vpc`.
- Prepare weights: download an open model of about 10 GB (identifier and revision in the protocol) and upload it to the lab's S3 bucket. Account for storage and intra-region traffic charges in the protocol.
- Code belongs in `experiments/aws/terraform/LAB49/`; extract the VPC module so LAB47 can consume it.

```bash
npm run lab:new -- --lab LAB49 --session aws-01
LAB_DIR='experiments/aws/measurements/LAB49-aws-01'
```

## Procedure

1. **VPC.** Two availability zones, public/private subnets, one NAT gateway. Record the plan and apply time.
2. **Instance.** A CPU instance in a private subnet accessed through SSM Session Manager, without public IP or SSH key. Its role has two separate policies: managed `AmazonSSMManagedInstanceCore`, required for Session Manager connection, and a custom data policy allowing only reads from the weights prefix. Step 6 IAM checks concern the data policy.
3. **Through NAT.** Without an endpoint, download weights to local disk with `aws s3 cp --recursive`. Record time, average speed and CloudWatch NAT-gateway metrics: `Sum(BytesOutToSource)` is downloaded bytes delivered by NAT to the instance, and `Sum(BytesOutToDestination)` is requests toward S3. NAT processing is billed in both directions, so include the sum of both metrics in cost.
4. **Through endpoint.** Add an S3 gateway endpoint to private-subnet route tables. Repeat the download; verify that NAT `BytesOutToSource` barely increases.
5. **ECR.** Add ECR interface endpoints (api and dkr), and pull a vLLM image from your own ECR repository. Compare `docker pull` time with a public registry through NAT. Include interface-endpoint hourly cost.
6. **IAM.** Make N violation attempts: read a neighboring prefix, write, delete, list another bucket. Save `AccessDenied` responses and, if enabled, IAM Access Analyzer output for the policy.
7. **Teardown.** `terraform destroy`, then LAB48 `janitor.sh`. NAT gateways and Elastic IPs are the leading candidates for forgotten resources.

## Results tables

| Path | Volume, GB | Time, s | Speed, MB/s | NAT traffic, GB | NAT processing cost, USD |
| --- | --- | --- | --- | --- | --- |
| S3 through NAT | | | | | |
| S3 through gateway endpoint | | | | | |
| Public-registry image through NAT | | | | | |
| ECR image through interface endpoint | | | | | |

| Item | USD per hour or GB (source, date) | Session cost, USD |
| --- | --- | --- |
| NAT gateway, hourly | | |
| NAT gateway, processing | | |
| Interface endpoint, hourly × count | | |
| S3 weight storage | | |

| IAM violation attempt | Expected | Actual |
| --- | --- | --- |
| Read neighboring prefix | denied | |
| Write to allowed prefix | denied | |
| Delete object | denied | |
| List another bucket | denied | |

## Deliverables

- Report, Terraform code with VPC module, IAM policy, raw download outputs and NAT metrics, `janitor.sh` output.
- Actual AWS Billing session expenses without account ID.

## Completion criteria

- Both hypotheses accepted or rejected with figures and dated prices.
- VPC module ready for LAB47; resources deleted, residual-resource check empty.

## Review questions

1. A fleet of 50 GPU nodes downloads a 140 GB model at every scale-out. Calculate the monthly NAT bill and propose three ways to eliminate it.
2. When is an interface endpoint more expensive than NAT, and when is it cheaper?
3. How does EKS Pod Identity differ from IRSA, and which would you choose for a new platform?
4. How can you verify that a policy is truly minimal, rather than merely “working”?

## Sources

- AWS documentation: NAT gateway pricing, VPC endpoints, IAM policy evaluation logic, IAM Access Analyzer, EKS Pod Identity, IRSA, SSM Session Manager.
- `terraform-aws-modules/vpc`.
- This repository: [LAB48](LAB48-aws-account-baseline.md), [LAB47](LAB47-k8s-gpu-eks-autoscaling.md), [protocol](../method.md).
