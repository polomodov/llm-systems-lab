# LAB48. An educational AWS account as code: budget, remote state and residual-resource checks

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the AWS and Terraform branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB01](LAB01-reproducibility.md); a personal AWS account where you are an administrator; Terraform 1.10 or later, AWS CLI v2 |
| Environment | AWS, `aws-NN` sessions; control machine: HONOR or Ryzen |
| Minimum | Bootstrap remote S3 state with locking, AWS Budgets with alerts, a working IAM role instead of root keys, mandatory `default_tags`, residual-resource checker, apply → drift → destroy cycle |
| Extensions | AWS Organizations with a separate sandbox account and an SCP prohibiting expensive instance types; IAM Identity Center instead of an IAM user |
| Time | Allow half a day; request GPU quota on day one—processing takes hours to several days |
| Readiness | `target-machine`; requires an AWS account |
| Initial state | Educational manifest: `not-started` |

## Objective

Create an account where subsequent labs in this branch (LAB49–52 and [LAB47](LAB47-k8s-gpu-eks-autoscaling.md)) cannot accidentally remain running or lose state. This is the baseline hygiene expected of an infrastructure lead: costs controlled, access without long-lived root keys, everything created and deleted through code.

## Hypothesis

1. The base layer (state bucket, budget, role, tags) costs less than 1 USD per idle month, and a full working-layer `apply` → `destroy` cycle takes less than 5 minutes.
2. Manual console changes are detected by the next `terraform plan` in 100% of cases for managed attributes, and the residual-resource checker finds a resource created outside Terraform with the lab tag.

Fix thresholds and the list of checked resource types in the protocol before execution.

## Preparation

- Read: Terraform S3 backend documentation (locking with `use_lockfile`), AWS Budgets, AWS provider `default_tags`, EC2 Service Quotas.
- **GPU quota.** New accounts often have a zero vCPU limit for G and P instances. At the start, request “Running On-Demand G and VT instances” quota in the chosen region through Service Quotas; record request and response dates.
- **Secrets.** Do not create root access keys. Credentials live in an AWS CLI profile outside the repository. Do not commit `terraform.tfstate`, `*.tfvars` with account identifiers, or `aws sts get-caller-identity` output. Reports include region and resource names without account ID.
- Code belongs in `experiments/aws/terraform/LAB48/`; pin Terraform and provider versions in `required_version` and `.terraform.lock.hcl`.

```bash
npm run lab:new -- --lab LAB48 --session aws-01
LAB_DIR='experiments/aws/measurements/LAB48-aws-01'
```

## Procedure

1. **Bootstrap.** A separate configuration with local state creates the S3 state bucket: versioning, encryption, public-access blocking. Working configurations then switch to an S3 backend with `use_lockfile = true`. Check locking: two simultaneous `terraform plan -lock-timeout=0` invocations in two terminals; the second must refuse. Save output.
2. **Money.** AWS Budgets: a monthly budget (amount fixed in the protocol) with alerts at 50%, 80% and forecast 100%. Enable the `lab` cost-allocation tag in Billing. Record how many hours it takes to appear in Cost Explorer.
3. **Access.** A working IAM role with a limited session, accessed through `aws sts assume-role` or IAM Identity Center. Use root only for billing setup. Verify with `aws sts get-caller-identity` that you are using the role (omit ID from the report).
4. **Tags.** Provider `default_tags`: `lab`, `session`, `owner`, `expires`. Verify that tags appear on all working-layer resources.
5. **Working layer.** A small configuration with inexpensive resources (e.g. VPC without NAT, security group, S3 bucket). Measure `apply` and `destroy` time.
6. **Drift.** Change three attributes in the console (tag, security-group rule, bucket setting). Run `terraform plan -detailed-exitcode`; record return code and detected changes.
7. **Residual resources.** `experiments/aws/janitor.sh` uses Resource Groups Tagging API and AWS CLI to find resources with the `lab` tag in the region, plus untagged EC2, EBS, Elastic IP, NAT gateways, load balancers and snapshots. Manually create one resource outside Terraform with the lab tag and verify the script finds it. After `destroy`, the script must return an empty list.

## Results tables

| Operation | Time, s | Resources | Note |
| --- | --- | --- | --- |
| Bootstrap apply | | | |
| Working layer apply | | | |
| Working layer destroy | | | |

| Drift change | Detected by `plan` | Return code |
| --- | --- | --- |
| Tag | | |
| Security-group rule | | |
| Bucket setting | | |

| Check | Expected | Actual |
| --- | --- | --- |
| Second plan while lock held | refused | |
| Resource outside Terraform found by script | yes | |
| Residual resources after destroy | none | |
| Monthly base-layer cost, USD | < 1 | |
| G-instance quota: requested → response | | |

## Deliverables

- Report, bootstrap and working-layer Terraform code, `janitor.sh`, lock/drift/residual-resource check output without account identifiers.
- Budget-settings screenshot or export without account ID.

## Completion criteria

- Remote state with versioning and locking; budget alerts enabled.
- Both hypotheses accepted or rejected with figures.
- Residual-resource script works and is used at the end of every subsequent AWS session in this branch.

## Review questions

1. Why must state not be stored in git, and what secrets can it contain?
2. What happens if two people apply changes simultaneously without locking?
3. How does an alerting budget differ from a hard spending limit, and how can a hard limit be implemented?
4. How would you arrange AWS access for a team of 15 engineers on a new platform?

## Sources

- Terraform documentation: S3 backend, AWS provider `default_tags`.
- AWS documentation: Budgets, Cost allocation tags, Service Quotas, IAM roles, Resource Groups Tagging API.
- This repository: [LAB47](LAB47-k8s-gpu-eks-autoscaling.md), [protocol](../method.md).
