# Harness experiments

[LAB11–19](../docs/labs/README.md) provide individual assignments for all nine directories below. For example, `npm run lab:new -- --lab LAB13 --session first-pass` creates a Codex report in `codex/measurements/LAB13-first-pass/`. The [shared submission workflow](../docs/labs/harness-workflow.md) supplements each lab’s individual commands.

Each harness directory records integration status in `README.md` and observations in `NOTES.md`. All nine directories have adapters and profiles; actual model episodes remain unverified until measured. Details and primary sources are in the [matrix](../docs/harnesses.md).

`local-models/` is a separate area for researching models and inference backends for Ryzen AI Max+ 395 / 128 GB / Linux, not an additional harness. It contains a plan and hardware assumptions; the set of existing harness profiles is unchanged.

`space/` contains the [LAB36–42 track](../docs/labs/README.md#space-track): **frozen on 2026-11-05**, with no new sessions created; it covers the SPACE sandbox platform as an agent execution environment. It is also not a harness and has no `harness.json`.

`k8s-gpu/` contains the [LAB43–47 track](../docs/labs/README.md#kubernetes-and-gpu-track): **frozen on 2026-11-05**, with no new sessions created; it covers GPU workload orchestration in Kubernetes on Ryzen and HONOR machines and in a training AWS account. It is not a harness and has no `harness.json`.

`aws/` contains the [LAB48–52 track](../docs/labs/README.md#aws-and-terraform-track): **frozen on 2026-11-05**, with no new sessions created; it covers a training AWS account, Terraform, networking, CI, cold starts, and GPU serving reliability. It is not a harness and has no `harness.json`.

## Shared lifecycle

1. `npm run new-run` creates a separate episode record.
2. `npm run prepare-run` reproduces the initial workspace and records hashed snapshots of the specification, contract, configuration, adapter, and coordinator. A repeat episode receives a new record.
3. `npm run run` pins the actual Docker image ID and CLI version, starts the agent, and saves the trace outside the container. The record includes the budget policy and unknown metrics.
4. `npm run evaluation-template` prepares an independent evaluation form; `npm run judge-run` accepts the completed evaluation. Process termination does not substitute for a task verdict.
5. `npm run compare` groups comparable episodes; `npm run check` validates records and the ledger.

Full command arguments, image builds, and the evaluation format are described in the [root instructions](../README.md). Secrets come from `.env` through the coordinator; never place their values in configuration, prompts, notes, or commits.

## Container boundary

The agent sees only the prepared workspace and a read-only service `/control` directory. For T003, the initial workspace is read-only, with a separate writable artifact directory. The lab root, hidden checks, run records, coordinator logs, and `.env` are not mounted. The Docker socket is not passed through either. The [shared gateway](common/README.md) enforces network restrictions.

Tool rules remain part of the measured configuration. A “do not read check” instruction, regexp hook, or `chmod` is no substitute for excluding hidden data from the agent environment. Verify the boundary independently of the quality of the model’s answer.

## New adapter contract

`experiments/<harness>/adapter.mjs` must provide two exports:

```js
buildCommand({ model, provider, turns, budget, prompt })
// => { command: [executable, ...argv], env: { NAME: 'value' } }

parseTrace(stdout)
// => {
//   loop: { /* measured fields only */ },
//   metrics_unavailable: { 'loop.tokens_in': 'reason unavailable' },
//   modelId: null, modelIds: [], stopReason: 'trace_incomplete', sessionId: null
// }
```

`command` runs without a shell. Pass an exact model ID/supported selector and provider explicitly; for managed harnesses, pass only the selected mode, recorded separately as `managed:<mode>`. Pass supported limits explicitly; an unsupported mandatory limit must stop execution before retrieving a key or calling the model. The parser does not replace missing values with zeros, distinguishes errors and truncation from completion, and does not add an aggregate to its components again. Preserve raw output so the parsed result can be verified.

The Dockerfile accepts a specific `HARNESS_VERSION`. Integration requires parser tests, installation checks, container-boundary checks, a real episode, and a valid `harness.json`; the coordinator does not hardcode the list of supported harnesses. A successful `--version` is an infrastructure check, not an experimental result.

Each component receives a [ledger](../docs/harness-ledger.md) row with its model assumption and retest condition. Record post-episode observations and changes in `NOTES.md` with the run ID. An ablation removes selected components in a new run while keeping hidden checks outside the agent environment.

## harness.json profile

The profile contains `id`, `ledger`, `mode` (`cli` or `sdk`), `model_policy`, `default_provider`, `providers`, `version_command`, `config_files`, `runtime_files`, and `budget`. Configuration entries are `source`/`target` pairs relative to the harness directory and `/control`. Runtime files are a list of relative paths. Directory traversal, symlinks, duplicates, and collisions with the coordinator are forbidden.

Each provider specifies only `credential_env` names, exact `connect_domains` without wildcards, and a semantically optional `model_prefix` (an empty string is allowed). Key values are forbidden in the profile. Provider selection is sealed during preparation; switching requires a new run.

`model_policy=managed` requires `managed_modes`; the service selects the exact model. `native_cache=true` requests a separate executable tmpfs for extracted libraries. Justify this capability with an offline check and record it in the ledger. Container configuration remains shared for the other conditions.
