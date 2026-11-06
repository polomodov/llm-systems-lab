# {{LAB_ID}} — {{LAB_TITLE}}

Session: `{{SESSION_ID}}`

Created: {{CREATED_AT}}

Status: **not started**. This is a report draft, not evidence of experimental execution.

## Run profile

| Field | Value |
| --- | --- |
| Operator, start/end dates | — |
| Machine, OS, kernel, BIOS, power mode | — |
| Model/artifact: revision, shards, SHA-256, quant | — |
| Engine, backend, image/binary hash | — |
| Context, KV/state dtype, slots, sampling, reasoning | — |
| Harness/provider/version, if applicable | — |
| Previous reports / run IDs | — |
| Deviations from the assignment and reasons | — |

## Hypothesis and protocol before execution

State a falsifiable hypothesis. Specify the varied factor, fixed conditions, minimum repetitions, execution order, stop criterion and preselected decision rule. Save this text before measurement; mark amendments after the series begins separately.

Save the original protocol as `raw/protocol.md`, reference it in `protocol_before_run` and `evidence_files` of the educational manifest v2. Fill `protocol_recorded_at` and `planned_attempts` before execution; after each step, add status, evidence and actual run ID. Format and validation commands: `docs/labs/report-validation.md` at the repository root. The manifest date is the author's assertion; preserve a commit or independent timestamp as confirmation.

## Execution log

| Assignment step | Action and actual command / config | Result / error | Raw evidence link |
| --- | --- | --- | --- |
| — | — | — | — |

## Results

Copy and complete your lab's specific tables here. One `measurements.tsv` row is one observation, not an average without underlying data. Give units, metric definition and conditions. Empty/`null` means unknown or unmeasured; state the reason explicitly. Zero is valid only as a measured zero.

## Errors and limitations

List incompatibilities, OOM, timeouts, GPU resets, parser issues, skipped cells and reasons. Use `not-run` if a request was not executed. Preserve started failed agent attempts alongside successful ones.

## Hypothesis conclusion

Choose: **supported by data / not supported / insufficient data**. Justify with links to specific measurements and run IDs. Separate single-factor effects from comparisons of different deployments. Do not call the absence of a difference in three repetitions proven equivalence.

## Answers to review questions

Include each lab question and your answer.

## Submission bundle

- [ ] manifest.json completed; missing data has reasons.
- [ ] All planned attempts listed in planned_attempts, including errors and not-run; synthetic kept separate from experimental.
- [ ] Original commands, configurations and raw logs preserved without secrets.
- [ ] Results tables and measurements.tsv completed if measurements were made.
- [ ] All related run IDs listed; real run records are in results/runs/.
- [ ] Individual lab completion criteria checked.
- [ ] Conclusion, limitations and question answers provided.
- [ ] lab:check run in submission mode; substantive judgment remains with the reviewer.

Reviewer decision: **not reviewed**. Assessment of educational-report completeness is not a task hidden-check `pass`.
