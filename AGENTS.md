# AGENTS.md

This repository is a lab for running the same autonomous agents in different agent harnesses on the same tasks, and recording what each harness needed. Read this file as a map; details live in the files it points to.

## What you are working in

- `docs/method.md` — the experiment protocol: replayable episodes, evidence classes, what a run record must contain.
- `docs/harnesses.md` — the harness matrix and install notes.
- `docs/harness-ledger.md` — the harness ledger. Every component added to a harness for a task gets a row: component → assumption about the model → evidence → date/model → retest trigger → ownership mode.
- `agents/<code>/spec.md` — harness-independent agent specifications (mission, inputs, outputs, boundaries, stop criteria).
- `tasks/<id>/task.md` — replayable episodes. `tasks/<id>/check/` holds the hidden check. **Never read or modify `tasks/*/check/` while solving that task.** Never modify `tasks/*/task.md` at all.
- `experiments/<harness>/` — everything harness-specific: config, hooks, launch commands, agent implementations, notes.
- `results/runs/<run-id>/run.json` — one record per run, validated against `results/schema.json`.
- `scripts/new-run.mjs`, `scripts/check.mjs` — create a run record; validate all records and the ledger.

## Conventions

- A run without a record does not exist. Fill every field of `run.json`: harness and its exact version, model and its exact id, permission mode, sandbox kind, turns, tokens, cost, wall-clock, the hidden-check verdict, and what you changed in the harness.
- Numbers carry their conditions. Vendor claims are labeled as claims; our own measurements as ours, with the task id and run id.
- Secrets come only from `.env` through the harness. Do not print, copy or commit them.
- Write only inside `results/runs/<run-id>/` and `experiments/<harness>/` unless the task says otherwise. Task workspaces live in `results/runs/<run-id>/workspace/` and are git-ignored.
- Prefer deleting a harness component over adding one. If you add one, add its ledger row in the same change.
- Checks: `npm run check` validates run records, the ledger, harness version pins (profile ↔ Dockerfile ↔ documentation) and task budget contracts. Run it before finishing.
- A harness version is pinned once, in `experiments/<harness>/harness.json`. Dockerfile and documentation repeat it; the runner compares it with the version the image reports.
- Turn and USD limits belong to `tasks/<id>/task.md`. The runner reads them from the sealed copy of the contract and never carries its own defaults.

## Style

- Documentation is in Russian, identifiers and file names in English. Agent specs and task contracts must be readable by any harness, so keep them plain Markdown without harness-specific syntax.
- Do not invent facts about a harness. If a feature is unverified, say "unverified" and where to verify.
