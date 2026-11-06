# LAB50. Terraform as a team product: GPU-pool module, tests and CI without long-lived keys

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the AWS and Terraform branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB49](LAB49-aws-network-iam.md) (VPC module); a GitHub repository where Actions can be enabled |
| Environment | AWS, `aws-NN` sessions; GitHub Actions; module tests create no GPU instances |
| Minimum | Custom GPU-pool module (Karpenter NodePool and EC2NodeClass or EKS managed node group) with variables and input validation; `terraform test` with a mock provider; tflint and configuration scanner (Checkov or Trivy); GitHub Actions with AWS OIDC roles: read-only pull-request plan, apply to dev on merge to main |
| Extensions | Two environments (dev/prod) with different limits from one module; policy as code with OPA/Conftest on the JSON plan; Atlantis or Terraform Cloud instead of custom CI |
| Time | Allow 1 day |
| Readiness | `target-machine`; requires an AWS account and a repository with Actions |
| Initial state | Educational manifest: `not-started` |

## Objective

Move from “I can run apply” to what a platform infrastructure owner is expected to provide: infrastructure code that fifteen people can change safely. A module, tests, pull-request plan review, CI access to AWS without static keys. The GPU-pool module is later used in [LAB47](LAB47-k8s-gpu-eks-autoscaling.md).

## Hypothesis

1. Of 10 deliberately introduced configuration errors (list fixed before execution: public bucket, SSH open to `0.0.0.0/0`, unlimited GPU pool, wrong instance type, missing tag, unencrypted volume, etc.), `terraform validate` + `terraform test` + tflint + scanner catch at least 8 before apply, with the detecting tool known for each.
2. The CI pipeline operates without a single long-lived AWS key: repository secrets contain no `AWS_ACCESS_KEY_ID`, and the apply-capable role cannot be assumed from a pull request, another branch or another repository.

## Preparation

- Read: Terraform modules, variable `validation`, `terraform test` and mock-provider documentation; GitHub Actions OIDC for AWS (`aws-actions/configure-aws-credentials`); tflint with AWS plugin; Checkov or Trivy for Terraform.
- **Secrets.** AWS keys never enter the repository or Actions secrets. Pass account ID and role ARN through repository variables and omit them from the report.
- Code belongs in `experiments/aws/terraform/modules/gpu-pool/` and `experiments/aws/terraform/LAB50/`; workflow in a separate educational repository or a branch where the owner permits Actions.

```bash
npm run lab:new -- --lab LAB50 --session aws-01
LAB_DIR='experiments/aws/measurements/LAB50-aws-01'
```

## Procedure

1. **Module.** Inputs: pool name, allowed instance types, maximum nodes, capacity type (on-demand or spot), tags. `validation` rejects an empty limit and types outside the allowlist. Outputs: pool name and node-role ARN. Generate input documentation with `terraform-docs`.
2. **Tests.** `terraform test` with a mock AWS provider: positive cases and expected validation failures (`expect_failures`). Record test runtime.
3. **Static checks.** tflint with the AWS plugin and a configuration scanner. Record versions and enabled rules.
4. **Errors.** Introduce the protocol's 10 errors one at a time; record which tool catches each, or whether it would reach apply.
5. **OIDC.** Terraform creates the GitHub OIDC provider and two roles. The plan role is read-only (state and resource descriptions); its trust policy accepts `sub` of the form `repo:<owner>/<repo>:pull_request`. The apply role can modify dev; its trust policy accepts only `repo:<owner>/<repo>:ref:refs/heads/main`, or `repo:<owner>/<repo>:environment:dev` if the job references a protected environment. Pull requests and environment jobs have a different `sub` from a branch, so a single “main branch” role will not admit pull-request plans. Verify denial of the apply role from a pull request and another branch.
6. **Pipeline.** On pull requests with the plan role: fmt, validate, test, tflint, scanner, `plan` with a brief plan posted as a comment. On merge to main with the apply role: `apply` to dev. Measure pipeline runtime.
7. **Teardown.** Delete dev; retain the OIDC role only if needed later; run LAB48 `janitor.sh`.

## Results tables

| Introduced error | validate | test | tflint | scanner | Would reach apply |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |

| OIDC check | Expected | Actual |
| --- | --- | --- |
| Long-lived keys in secrets | 0 | |
| Plan role from pull request | success | |
| Plan role: resource modification attempt | denied | |
| Apply role from main | success | |
| Apply role from pull request | denied | |
| Apply role from another branch | denied | |

| Pipeline stage | Time, s |
| --- | --- |
| fmt + validate + test | |
| tflint + scanner | |
| plan | |
| apply to dev | |

## Deliverables

- Report, module with tests and documentation, workflow, error table with tool outputs, link to the educational pull request with the plan comment.

## Completion criteria

- GPU-pool module with tests ready for LAB47.
- Both hypotheses accepted or rejected; detection options recorded for uncaught errors.
- Pipeline completed at least one pull request → merge → apply cycle without static keys.

## Review questions

1. Where is the boundary between a module and environment configuration? What would you keep out of a module?
2. How do you review a plan with 300 changes, and when should such a plan be prohibited?
3. Why is applying from an engineer's laptop bad for a team, and how should emergency changes be handled?
4. Which rules would you make mandatory for every pull request to a platform infrastructure repository?

## Sources

- Terraform documentation: modules, input validation, `terraform test`, mock providers.
- GitHub documentation: OpenID Connect for AWS; `aws-actions/configure-aws-credentials`.
- tflint and `tflint-ruleset-aws`; Checkov or Trivy; `terraform-docs`.
- This repository: [LAB49](LAB49-aws-network-iam.md), [LAB47](LAB47-k8s-gpu-eks-autoscaling.md), [protocol](../method.md).
