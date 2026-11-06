# Kubernetes and GPUs: orchestrating training and inference workloads

> **Frozen on 2026-11-05.** The lab guide is retained, but new `lab:new` sessions are disabled: the Kubernetes and GPU track has no measurements or implementation and is being separated into a training repository. Unfreezing requires a separate decision recorded in the [course status](../../docs/labs/README.md#frozen-infrastructure-tracks).

Directory for the [LAB43–47 track](../../docs/labs/README.md#kubernetes-and-gpu-track). It tests how Kubernetes manages GPUs, from exposing a device in a pod to scheduling a shared fleet, serving LLMs, and cloud autoscaling. This is not a harness: there is no `harness.json` here, and there should not be one.

Status: **lab guides ready; no measurements**. AMD device-plugin support for the `gfx1151` APU is `unverified` until the first LAB43 session.

## Test environments

| Environment | Machine | Role |
| --- | --- | --- |
| A, `ryzen-NN` sessions | Ryzen AI Max+ 395 / 128 GB / Linux, Radeon 8060S (`gfx1151`), the same machine as LAB02 | Real GPU in single-node k3s: LAB43, 45, and part of 46 |
| B, `honor-NN` sessions | HONOR MagicBook X16, Ryzen 7 PRO 8845HS / 32 GB / Ubuntu | Kind with fake GPUs: LAB44 and part of 46 |
| AWS, `aws-NN` sessions | Training account, EKS with one small GPU instance type | LAB47 |

## Contents

| Path | Contents | Introduced in |
| --- | --- | --- |
| `measurements/LABxx-session/` | Reports created with `npm run lab:new -- --lab LAB43 --session ryzen-01` | LAB43–47 |
| `manifests/LABxx/` | Kubernetes manifests by lab | LAB43, 45, 46, 51, 52 |
| `sim/` | KWOK fleet, Kueue configuration, deterministic job-stream generator | LAB44 |
| `bench/` | Load generators for inference engines | LAB45, 46 |
| `terraform/` | EKS, Karpenter, KEDA; LAB51–52 changes from the [AWS track](../aws/README.md) | LAB47, 51, 52 |

Each lab creates the subdirectories it needs.

## Rules

- Pin Kubernetes, k3s/Kind, driver, plugin, operator, and image versions in every report; pin images by digest.
- Keep AWS credentials, `terraform.tfstate`, kubeconfig, and account IDs out of reports, raw artifacts, and commits.
- Cloud resources exist only during the session: finish with `terraform destroy` and a leftover-resource check.
- Project documentation numbers and cloud prices are vendor claims with an access date; identify our own measurements by session.
