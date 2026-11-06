# Educational report completeness validation

`lab:check` reads an existing bundle and reports missing data. It does not run models, change files, award credit or assign `pass`. `npm run check` continues to validate the catalog and real run records; individual educational-report completeness is checked explicitly.

## Two modes

From the repository root:

```bash
npm run lab:new -- --lab LAB20 --session calibration-01
npm run lab:check -- --report experiments/local-models/measurements/LAB20-calibration-01
```

The default is `mode=draft`: a new blank report is allowed, but entered links, statuses, numbers and run IDs must already be valid. For submission:

```bash
npm run lab:check -- --report experiments/local-models/measurements/LAB20-calibration-01 --mode submission
```

Both commands output JSON and return nonzero on errors. `ready_for_review=true` means the bundle is complete for review. A properly documented `blocked` report may also qualify; blocking does not become lab completion. `experiment_pass` is always `null`. A human uses the manual to assess substantive tables, answers, minimum experiment counts and conclusion correctness.

## Manifest v2

New `lab:new` sessions use version 2. Immutable report identifiers must match the catalog and directory. Fill `operator`, `hypothesis`, `conclusion` for submission; leave `reviewer_decision` `null` until the reviewer decides.

- `evidence_class`: `experimental` for real observations/runs, `synthetic` for educational data and recorded responses, `protocol` for preparation checks without model measurements. Use separate sessions for educational and real routes. `synthetic` references no real `run_ids`; `protocol` permits only unstarted `planned`/`prepared`/`aborted` records. Any model execution requires `experimental`.
- `protocol_before_run`: path **relative to the report directory** to the original protocol, e.g. `raw/protocol.md`. Include it in `evidence_files`. `protocol_recorded_at` is the UTC timestamp when the protocol was saved before execution: `YYYY-MM-DDTHH:mm:ssZ` or `YYYY-MM-DDTHH:mm:ss.sssZ`. The same format applies to `created_at`; nonexistent dates are rejected. For real run IDs, this date must not be later than `execution.started_at`; the author separately establishes date authenticity and pre-experiment plan immutability.
- `conditions`: paths **relative to the repository root** to hardware profile, weight/runtime manifest and harness profile. For an inapplicable field, leave `null` and add a reason string, e.g. `unavailable["conditions.model_artifact_manifest"] = "Educational evaluation of recorded responses without a model"`. An applicable file must exist in `docs/`, `experiments/` or `results/runs/`.
- `evidence_files`: unique paths **relative to the report directory** to all raw materials. For other sessions' materials, preserve a needed copy with provenance; `..`, absolute paths, URLs, symlinks, `.env` and hidden `check` paths are prohibited. Never publish secrets. Archive `*.log` separately: Git ignores them.
- `run_ids`: all linked real records. Schema, hashes and available snapshot integrity are checked. Do not add a synthetic `lab:practice` trace here.
- `planned_attempts`: complete advance list of attempts; populate outcomes after execution. Do not delete failed rows.

Example record **shape** before execution; this is not a result:

```json
{
  "id": "reviewer-a-sample-01",
  "configuration_id": "rubric-v1",
  "kind": "exercise",
  "status": "planned",
  "run_id": null,
  "evidence_files": [],
  "reason": null
}
```

`id` and `configuration_id` are English slugs. `kind` accepts `agent-run`, `measurement`, `exercise`. `measurement` and `exercise` receive no run ID. A completed exercise or measurement needs `evidence_files` references also listed at manifest top level.

| Attempt status | Rule |
| --- | --- |
| `planned` | Not yet resolved; for submission, complete every such row or explain its omission |
| `completed` | Work performed. `agent-run` requires an independently evaluated `completed` run; any honest `pass`/`partial`/`fail` is acceptable |
| `awaiting-review` | `agent-run` only: execution finished, linked run is `awaiting_review/pending`, with start/end times. Reason required. Submission allowed only as `blocked` with `unavailable.completion`; no independent verdict yet |
| `failed` | A started attempt was interrupted. `agent-run` requires `aborted` with `execution.started_at`; reason required |
| `not-run` | Never started; reason required. A `planned`/`prepared` ID or pre-start `aborted` is allowed; never use this for a started attempt |

Every run ID appears in exactly one planned row and top-level `run_ids`. Reverse validation detects records missing a plan row. The command cannot detect an experiment hidden by the author from both report and plan: independent preservation of the original protocol remains part of the method.

Measured time and tokens from an executed `awaiting-review` attempt may be saved in TSV with primary evidence. This status does not permit marking the lab `completed` or replacing independent evaluation. Do not relabel such a run `not-run`, `failed` or `completed` just to pass completeness checks.

For a general assignment without a model, use `exercise` rows, e.g. LAB01 preparation or LAB20 independent evaluations. In LAB01, set `protocol`: record completed preparation as `exercise/completed`, and its unstarted run ID separately as `agent-run/not-run` with reason “only preparation is checked”. This preserves a sealed-input link without implying model execution. An empty attempt list fails submission; `completed` requires at least one completed or interrupted attempt. `blocked` requires `unavailable.completion`; list planned but impossible actions as `not-run`. A dedicated harness lab marked `completed` requires at least one real evaluated run of its own harness.

## Measurements

Preserve the original `measurements.tsv` header. Each row has a unique `observation_id`, nonempty `configuration_id` and `metric`; the configuration must appear in the plan. Populated `context_tokens`/`repeat` are positive integers.

- `measured`: a finite decimal number, unit and existing `evidence_path` included in the manifest. Zero is allowed as a measured value.
- `failed`, `not-run`, `unavailable`: empty `value`, populated `unavailable_reason`. Unknown never becomes zero.
- If an interrupted request's duration was measured, record a separate `measured` row; the overall attempt stays `failed`.
- If there were no numeric observations, retain only the header and explain in `unavailable.measurements`.

## Legacy reports and educational traces

Version 1 remains readable in `draft`. For submission, make a backup, set `schema_version` to 2, add `evidence_class`, `protocol_recorded_at`, `planned_attempts`, and make `protocol_before_run` a file path. Do not retrospectively reconstruct an advance plan: if missing, set `status=blocked`, fill `unavailable.completion` and `unavailable.protocol_before_run`. Protocol fields may remain `null`, or use an honest late date explained in the same reason. This is the only exception for missing/late protocol; it is prohibited for `completed`. Reconstruct the completed/skipped action registry with an explicit report note that it is not preregistration. Then create a new session planned in advance. The validator itself never rewrites legacy reports.

`lab:practice` creates a different format, `kind=lab-practice`, in `experiments/local-models/practice/`. `lab:check` rejects it. To submit an educational analysis, create a normal LAB20/22/23 report, set `synthetic`, copy the trace into `raw/` and attach your independently completed answers. Such analysis does not fulfill the engineering or model minimum of the corresponding lab.
