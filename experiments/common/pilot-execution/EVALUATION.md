# Independent evaluation procedure for T002 and T004

This is an operational protocol, not a task solution or a replacement for either hidden check. It applies to the current English campaign condition. Preparation here uses only synthetic transport fixtures; actual checker interpretation belongs to a separate evaluator context.

| Task | Solving agent | Required final artifact | Method | Readiness before real evaluation |
| --- | --- | --- | --- | --- |
| T002-repo-janitor | a2-janitor | `artifacts/report.md` | hidden-check | Independent evaluator pins the trusted checker revision/entrypoint and demonstrates its applicability to the sealed T002 workspace |
| T004-feature-from-spec | a4-implementer | `artifacts/report.md` | hidden-check | Same requirement for T004, including its own checker semantics; do not infer readiness from T002 |

Both task descriptors require a repository workspace under `workspace/sample`. Their actual contracts/criteria remain authoritative. Do not change a task contract, open hidden checks in the solving/preparation context, or reinterpret a missing artifact as success.

## Roles and preflight

The operator records the solving actor and assigns a different evaluator actor/context. The evaluator obtains the trusted checker source independently at a frozen Git revision or SHA256 content revision. The coordinator does not package hidden checks or invent an entrypoint/arguments. The evaluator determines those in their own context and records the exact command, applicability, exit semantics, environment and calibration evidence before the first campaign pilot. Use a disposable copy and network-disabled environment; if dependencies/checks cannot run offline, stop and arrange a pinned evaluator environment rather than enable network or alter the result.

Calibration must distinguish a known valid case, an intentionally invalid case, and an infrastructure error according to the trusted checker. This directory's invented-check tests establish handoff/container plumbing only; they do not certify the real task checkers. Human/context independence is an operator responsibility; different actor strings in a receipt are an audit assertion, not cryptographic proof of independence.

## 1. Export unchanged final results

Only `awaiting_review` records for T002/T004 are accepted. Aborted, prepared or already completed records cannot be evaluated through this procedure. The tool verifies sealed inputs and final artifact/workspace manifests before and after copying. It never executes task code or reads hidden checks.

```sh
node experiments/common/pilot-execution/evaluation.mjs --action prepare \
  --run '<actual awaiting_review run ID>' \
  --out '<new independent handoff directory>' \
  --solver '<solving actor/context ID>' \
  --checker-revision '<40-character Git revision or 64-character SHA256 agreed with evaluator>'
```

Give only `<handoff>/submission/` to the evaluator. Keep `private-binding.json` with the coordinator. Preserve the complete source run archive and live final workspace until existing `judge-run` validation finishes; this procedure cannot reconstruct a missing live workspace from an artifact report.

## 2. Separate evaluator runs the pinned opaque check

In the independent context, use the trusted checker package and its actual documented command. Do not assume a filename or that exit0 means task success. The checker sees `/work/workspace` (a disposable final workspace copy), `/work/submission/artifacts` and `/work/check-package`; default cwd is `/work/workspace/sample`. Supply any required absolute arguments explicitly.

```sh
python experiments/common/pilot-execution/evaluator_container.py \
  --submission '<received submission directory>' \
  --checks '<independently obtained pinned trusted checker directory>' \
  --command-json '<literal JSON argv for that checker>' \
  --out '<new assessment directory>' \
  --docker-host '<local Docker Unix socket>'
```

The operator must confirm the checker checkout is clean at the agreed revision and retain the trusted-package hash/calibration record. The wrapper requires a sealed submission inventory and immutable toolchain image, passes no provider credentials and mounts only the two input directories read-only. It removes the disposable container afterward. Work is bounded by a 120 second checker timeout; an inadequate timeout/toolchain is an infrastructure issue requiring investigation, not a task fail.

## 3. Evaluator supplies a verdict

Retain `stdout.txt`, `stderr.txt` and `receipt-template.json`. Copy the template to `completed.json` in the same assessment directory. Fill only:

- `evaluator`: independent actor/context identity;
- `result`: `pass`, `fail` or `partial`, supported by the trusted checker and task contract;
- `check_output`: substantive observations, checker applicability and interpretation of the retained output.

Preserve submission/check/toolchain/log hashes and all provenance fields. A successful checker process is necessary for `pass` but does not determine it. An infrastructure failure, changed input or missing log is not an evaluable task verdict. Return the completed receipt plus both raw logs to the coordinator; retain checker source/calibration evidence separately in the evaluator-controlled archive.

## 4. Import and independently verify binding

```sh
node experiments/common/pilot-execution/evaluation.mjs --action import \
  --handoff '<original handoff directory>' \
  --receipt '<returned assessment directory>/completed.json'
npm run check
```

The tool rejects wrong submissions, solver-as-judge, changed checker revision, altered source/submission/log bytes, infrastructure errors, unbound hashes and repeat imports. It embeds the bound checker provenance and raw logs in the existing evaluation record, then calls the existing `judgeRun`; it does not change the underlying task artifacts or invent a verdict. `completed/fail` and `completed/partial` are preserved as legitimate evaluated outcomes. Every started failed attempt remains in the campaign denominator. A retry is a new separately planned attempt, never an overwritten result.

## Campaign freeze

Record the evaluator identity and task-specific procedure/calibration evidence before opening the pilot gate. After valid pilots, freeze T002/T004 initial workspace fingerprints and exact source/model/image conditions before the 36 comparison slots. Do not treat this procedural implementation or synthetic tests as those missing real evaluator assignments, calibrations or paid-pilot results.
