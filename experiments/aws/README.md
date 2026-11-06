# AWS and Terraform: cloud AI infrastructure

> **Frozen on 2026-11-05.** The lab guide is retained, but new `lab:new` sessions are disabled: the AWS and Terraform track has no measurements or implementation and is being separated into a training repository. Unfreezing requires a separate decision recorded in the [course status](../../docs/labs/README.md#frozen-infrastructure-tracks).

Directory for the [LAB48–52 track](../../docs/labs/README.md#aws-and-terraform-track). Here, a training AWS account is brought under infrastructure-as-code management, networking and IAM are built for a GPU platform, infrastructure code receives tests and CI, and GPU-serving cold starts and reliability are measured on the [LAB47](../../docs/labs/LAB47-k8s-gpu-eks-autoscaling.md) cluster. This is not a harness: there is no `harness.json` here, and there should not be one.

Status: **lab guides ready; no measurements**.

## Test environment

| Environment | Description | Labs |
| --- | --- | --- |
| AWS, `aws-NN` sessions | Personal training account; control machine: HONOR or Ryzen | LAB48–50 without GPUs; LAB51–52 on the LAB47 cluster with one or two small GPU instances |

## Contents

| Path | Contents | Introduced in |
| --- | --- | --- |
| `measurements/LABxx-session/` | Reports created with `npm run lab:new -- --lab LAB48 --session aws-01` | LAB48–52 |
| `terraform/LAB48/`, `terraform/LAB49/`, `terraform/LAB50/` | State bootstrap, budget and role; VPC and IAM; CI configuration | LAB48–50 |
| `terraform/modules/` | VPC and GPU-pool modules used by LAB47 | LAB49, 50 |
| `janitor.sh` | Check for leftover resources by tags and resource types | LAB48, then every AWS session |

LAB51–52 cluster changes build on LAB47 code in [`experiments/k8s-gpu/terraform/`](../k8s-gpu/README.md). Each lab creates the subdirectories it needs.

## Rules

- Keep AWS credentials, `terraform.tfstate`, `*.tfvars` containing identifiers, kubeconfig, and account IDs out of reports, raw artifacts, and commits. Do not create root keys.
- Enable budgets and limits before creating any paid resources; record the expected session cost in the protocol.
- Resources exist only during the session: finish with `terraform destroy` and an empty `janitor.sh` result.
- AWS prices are vendor claims with an access date; actual costs come from Billing; identify our own measurements by session.
