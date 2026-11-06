# Run records

Each attempt has one directory: `results/runs/<date>-<harness>-<agent>-<task>[-n]/`. States progress through `planned → prepared → running → awaiting_review → completed`; an unfinished run can become `aborted`. Only completed records contain an independent evaluator's pass/fail/partial verdict. Creating a template is not an experiment.

- `run.json` — a strict record following schema.json. Unknown measurements are null with an explanation in metrics_unavailable, never zero.
- `inputs/` — sealed instruction/configuration/coordinator sources and the initial tree's SHA-256 manifest. Changes are detected before execution and evaluation.
- `workspace/` — an isolated working copy, excluded from Git. After evaluation, local validation can compare it with the final manifest again.
- `runtime-control/` — prepared read-only settings for a specific execution, without keys.
- `trace/` — stdout/stderr, source archive, output manifests, CLI version and independent evaluation; T002 also includes a patch.
- `artifacts/` — copies of files the agent created under the contract.

The root README describes creation, preparation, execution, independent evaluation and comparison. Do not edit completed records by hand: that can break the binding between the evaluation and output bytes. An empty lab passes structural validation with an explicit warning that no experimental evidence exists.

Historical records retain their original source language and sealed inputs. The current English project interface does not change their experimental conditions; see [publication provenance](../docs/publication.md).
