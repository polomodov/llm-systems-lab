# Native pilot accounting bridge

`accounting.py` is a data importer, not a launcher. It never reads credentials,
contacts a provider, or executes a Harbor trial. Preparation and all tests can
run without network access. Only `prepare` and `check` are exposed by its CLI.
Python imports of `mark_started`, `finish` and `admission` are available for a
future separately authorized coordinator; they do not authorize execution.

The exact `harbor-native-normalize` / `harbor-native-normalizer` registration is
owned by this experiment. The core record validator accepts only this pair,
the five named native CLI harnesses, and the fixed registration path. It does
not add a generic external-task bypass or change campaign descriptors.

## Prepare an unexecuted record

After `materialize.py` has frozen the runtime and package locks, the CLI accepts
`prepare --root <repository> --slot HN-O01 --run-id <date-and-unique-id>
--package <materialized-prepared-slot> --runtime-lock <runtime-lock.json>
--package-lock <package-lock.json> --plan <plan.json>`.

Preparation checks the slot, version, immutable image, verifier image, complete
package inventory and official Harbor package digest against the locks. It
seals the exact package, plan, slot, locks, contract and specification in
`inputs/`. The prepared record has no start timestamp, no command, no observed
model or usage, and no measured cost. Reusing an existing run directory fails.
The manifest uses the lab's native version-1 integrity format and an explicit
`harbor-native-pilot-v1` importer marker. `check --root <repository> --run-id <id>`
uses the existing lab schema, lifecycle, catalog and integrity validators. CLI
paths must point to this repository and the canonical plan, locks and selected
materialized package; arbitrary external files and symlink paths are rejected.
The Python API remains available for isolated fixture repositories.

## Import actual evidence later

`mark_started(root, run_id, receipt)` requires a prepared record and a receipt
containing the independently observed exact `image_id`, `observed_version`,
`command`, `cwd`, and UTC `started_at`. It imports this observation; it does not
execute the command. `finish(root, run_id, evidence_dir, observation)` accepts
only a running attempt and preserves the supplied evidence tree under
`trace/evidence/`. A lock prevents concurrent updates. Interrupted imports keep
their evidence and must be inspected; they cannot be silently overwritten.

The observation names `native_log`, optional `atif`, `terminal_native_trace`,
execution fields (`finished_at`, `exit_code`, `signal`, `timed_out`), and explicit
JSON/JSONL references. A reference is `{ "file": "native.jsonl", "pointer":
"/0/model", "kind": "native_response" }`. JSONL is addressed as an array of
records. Paths must stay inside the evidence tree and cannot use symlinks.

- `identity` accepts response-level native/provider identity. Requested model
  configuration and ATIF agent metadata do not prove observed identity.
- `metrics` accepts references for turns, input/output tokens, wall time,
  compactions, subagents and `permissions.asked`; `tool_operations` references a
  native task-tool count. Allowed sources are native usage, provider responses
  or coordinator observations as appropriate. An operator must supply the
  actual source locations; this module does not manufacture telemetry that a
  native adapter failed to capture.
- `billing` must point to independently collected provider billing with
  `{ "status": "settled", "run_id": "...", "cost_usd": 0.01 }`, attributed to
  this attempt. Native cost estimates, Harbor summaries and ATIF zero defaults
  cannot populate `loop.cost_usd`. Unknown or settling costs stay null.
- `verifier` points to a separate-verifier report with `result`, `check_output`,
  `artifact_file`, `artifact_sha256`, and `verifier_sha256`. Artifact bytes and
  the frozen `tests/evaluate.py` must match. A failing missing-output verdict may
  explicitly declare `artifact_absent: true` and `artifact_sha256: null`, with
  `artifact_file` naming a path that is actually absent. This retains the failing
  verifier report and settled spend without creating fake output. Passing
  verdicts and existing artifacts cannot use this exception. `boundary` points to independent
  boolean `passed` and `cleanup_complete` observations.

The pinned Harbor `TrajectoryValidator` validates the declared ATIF version.
Model mismatch, timeout, nonzero exit, signal, boundary/cleanup failure or
missing terminal evidence aborts the attempt while retaining actual costs.
Independent task pass/fail is distinct from qualification: missing identity,
valid ATIF, task-tool evidence, measurements or settled billing yields an
inconclusive qualification, even if the verifier passes. All raw evidence,
execution receipt, accounting and evaluation are hash-bound and checked by
`scripts/lib/integrity.mjs`. No result is inferred from fixtures.

`admission(root, run_ids, next_slot, plan)` requires the complete prior ordered
slot prefix, the exact frozen plan and every discovered started attempt. It
rejects skips, duplicate slots, unknown/unsettled costs, failed or inconclusive
attempts, per-attempt overruns and insufficient provider/total allocations.
Accounting admission still requires separate execution authorization. There
is no provider spend cap; delayed billing can exceed observed targets.

## Offline validation

Run with the pinned Harbor Python environment and pinned Node on PATH:

```sh
mise exec -- experiments/common/harbor-interop/.venv/bin/python -m unittest discover -s experiments/common/harbor-native-pilot -p 'test_accounting.py' -v
```

Fixtures create only temporary repositories. They cover prepared/completed/
aborted lifecycles, raw/ATIF reconciliation, missing metrics and billing,
identity mismatch, native failure, artifact binding, exact registration,
manifest/package/receipt/evidence integrity, path containment, no overwrite and
admission omissions. They neither create measured campaign results nor prove
real model access, routing, billing availability or performance.
