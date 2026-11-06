# Shared workflow for agent-harness labs

This guide supplements **LAB11–19**: exact versions, build commands, providers, smoke tests and investigated features are in each harness's dedicated lab. Run all commands from the repository root in Bash. `LAB_DIR` comes from the created report for the selected lab; always copy `RUN_ID` from actual `new-run` output.

Before the portable examples below, set consistent variable names using your task's actual conditions. Individual labs may call the image `IMAGE_ID` or specify the provider directly in a command; Bash does not transfer these values automatically:

```bash
HARNESS_ID='<harness from the chosen lab, e.g. pi>'
PROVIDER_ID='<its selected provider, e.g. anthropic>'
MODEL_ID='<exact ID or managed:mode from your report>'
IMAGE_REF='<immutable image ID of the built harness>'
PROXY_IMAGE_REF='<immutable ID of the prepared proxy image>'
```

## What counts as a completed lab

The mandatory minimum is to prepare and verify the selected harness, execute **one new T002**, obtain an independent evaluation and analyze its trace. Installation checks without API access can be completed beforehand; they do not replace a model experiment. `completed/fail` or `completed/partial` can be valid educational outcomes: completeness of investigation is assessed, not mandatory model success. Preserve `aborted`, but if the minimum series requires an evaluated task, an infrastructure error alone does not complete the lab. A retry after a fix gets a new run ID.

Before execution, fill in hypothesis, outcomes, limits, attempt count and order in the report. Assign extra T001/T003 tasks, triplets and ablations in advance; do not add repetitions only until the first success.

| Stage | Acceptable evidence | What it does not yet establish |
| --- | --- | --- |
| Unit/offline smoke | Test/version/import log and exit code | Account access to the model or task quality |
| Prepared | Sealed inputs and initial workspace | Agent execution |
| Awaiting review | Trace, artifacts, final workspace | Independent verdict |
| Completed | Evaluation tied to result hashes | Universal reliability from one attempt |
| Aborted | Stop reason and all remaining data | Pass, zero cost or missing token counts |

## Environment and secrets

Docker executes a Linux container even when the coordinator runs on another OS. Cloud LAB11–19 do not require a GPU or Ryzen. Use the image's actual supported architecture from the task; incompatible architecture is an installation blocker, not a model error.

Credential values live only in root `.env` and are passed through the coordinator for the selected provider. Do not run `source .env`, print variables/the file, or pass the whole file through `docker --env-file`. Edit existing `.env` without overwriting other keys. `npm run harnesses` shows only required variable names and profile capabilities.

For every image and series, preserve the exact CLI/SDK version and immutable image ID. Also verify the local proxy image from the shared guide before starting the agent. Networkless, keyless smoke makes no API calls. Task `run` commands, however, contact the selected service and may consume its quota.

The primary mode for all nine labs is `--budget-mode observed --timeout 900`. `observed` does not enforce USD limits: it is an explicitly recorded deviation from the task-contract budget. Claude Code additionally investigates `hard` separately from the shared series. The outer timeout is identical; native turn/step/iteration limits and their semantics remain those implemented by each adapter.

## Checking execution results

After `run`, read the state before choosing the next step. Save a brief profile from **your own** record; the code reads only `run.json`, not `.env` or hidden checks:

```bash
node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/result-$RUN_ID.json"
import { readFileSync } from 'node:fs';
const record = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
console.log(JSON.stringify({
  run_id: record.run_id, status: record.status,
  harness: record.harness, model: record.model,
  permissions: record.permissions, sandbox: record.sandbox,
  image_id: record.execution.image_id, timeout_s: record.execution.timeout_s,
  budget_policy: record.execution.budget_policy,
  exit_code: record.execution.exit_code, timed_out: record.execution.timed_out,
  loop: record.loop, metrics_unavailable: record.metrics_unavailable,
  verdict: record.verdict
}, null, 2));
NODE
```

Compare aggregates with the selected harness's original trace. Requested model ID and observed model are separate fields; Amp's managed selector and Copilot's selector cannot become proof of an exact snapshot. An incomplete trace or native error at exit 0 can produce `aborted`. At `planned/prepared`, the model has not run; at `running`, first establish the state of your coordinator and container. Do not manually edit JSON to advance stages.

`awaiting_review` permits independent evaluation. `aborted` remains a recorded failed attempt; do not send it to `judge-run` to turn it into success. Preserve stop reason, error details and the decision on a new attempt.

## Independent evaluation

The evaluator operates outside the agent container and does not give the hidden check to the agent. T002 uses `hidden-check`; T001/T003 use `rubric`, with T001 evaluation including its prescribed external verification. Take the hidden evaluator's exact invocation from its operator guide. This project has no universal command that automatically delivers substantive verdicts for every task.

At `awaiting_review`, create a **new** template; `noclobber` preserves an already completed evaluation on repeated invocation:

```bash
EVALUATION_FILE="$LAB_DIR/raw/evaluation-$RUN_ID.json"
(
  set -o noclobber
  npm run --silent evaluation-template -- --run "$RUN_ID" > "$EVALUATION_FILE"
)
```

If the command fails, investigate before proceeding. The judge fills `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` and optionally `human_notes`. `check_output` must contain check/rubric version, applicability conditions and observations supporting the verdict. Preserve `artifacts_sha256`, `workspace_sha256`, `run_id` and `method` from the template. Do not edit agent results before or after evaluation.

```bash
npm run judge-run -- --run "$RUN_ID" --evaluation "$EVALUATION_FILE"
npm run check
```

`judge-run` checks evaluation binding and integrity. It does not replace the judge. Successful import should yield `completed` with the actual verdict; without an evaluator, retain `awaiting_review` and an unfinished lab status. Transfer final fields to the report after import, keeping the original execution profile separately.

## Extra task T001: one source archive

Before the series, decide whether a new discovery run is needed. If no archive exists, create a separate T001 with `a1-dossier`, prepare it with the chosen `--as-of` date, follow the same lifecycle and save `trace/sources.jsonl`. It must contain URLs, statuses and **response bodies**. Discovery is excluded from controlled comparison.

Use the same archive and date for every new replay attempt. Replace these values with actual ones before execution:

```bash
AS_OF_DATE='<discovery date YYYY-MM-DD>'
SOURCE_ARCHIVE='results/runs/<discovery-run-id>/trace/sources.jsonl'
npm run new-run -- --harness "$HARNESS_ID" --agent a1-dossier --task T001 --provider "$PROVIDER_ID" --model "$MODEL_ID"
RUN_ID='<new ID from output>'
npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --provider "$PROVIDER_ID" --model "$MODEL_ID" --timeout 900 --budget-mode observed
```

Use your own output prefix/run ID for the new evaluation and trace. Replay does not fetch missing pages; the model API remains online. Preserve archive hash; do not compare live/replay as identical inputs.

## Extra task T003: harness audit

```bash
npm run new-run -- --harness "$HARNESS_ID" --agent a3-ledger-auditor --task T003 --provider "$PROVIDER_ID" --model "$MODEL_ID"
RUN_ID='<another new ID from output>'
npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --provider "$PROVIDER_ID" --model "$MODEL_ID" --timeout 900 --budget-mode observed
```

Evaluate with the external rubric. The T003 workspace contains an allowed read-only snapshot of the selected harness and a separate writable artifact directory. Different harnesses supply different inputs, making this series diagnostic. An agent's claim that a component helps does not confirm a ledger row.

## Repetitions, comparison and submission bundle

For a triplet, assign three new run IDs before knowing outcomes; repeat the full lifecycle. Do not retrospectively turn a pilot into the first successful attempt. Preserve all started failures; `compare` includes started aborted attempts in the denominator and separately shows unfinished/unstarted records:

```bash
SERIES_RUN_IDS='<first ID>,<second ID>,<third ID>'
npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-triple.json"
```

Show outcomes, measurement coverage and separate groups. Do not merge different models/providers/policies into one ranking. Controlled harness comparison is described in [LAB09](LAB09-agent-campaign.md); six paired `baseline/without-spec` attempts in [LAB10](LAB10-ablation.md). Ablation does not remove sandbox/network boundaries.

Each LAB11–19 submission has its own completed tables, `report.md`, educational `manifest.json`, numeric TSV observations, raw evidence and links to real `results/runs/<run-id>/`. The educational manifest's `harness_id` identifies the chosen harness; it does not certify execution. Do not overwrite logs when changing model, provider, image or attempt. Git ignores `*.log`: preserve the full evidence archive separately from a normal commit.

Record measured limitations and run IDs in `experiments/<harness>/NOTES.md`. If a component was added, add its [ledger](../harness-ledger.md) row in the same change; do not use “confirmed” status before its effect is demonstrated. The conclusion must answer the hypothesis within this series' conditions.

Sources: [method](../method.md), [record lifecycle](../../results/README.md), [shared infrastructure](../../experiments/common/README.md), [harness matrix](../harnesses.md), [evaluation-template](../../scripts/evaluation-template.mjs), [judge-run](../../scripts/judge-run.mjs), [compare](../../scripts/compare.mjs).
