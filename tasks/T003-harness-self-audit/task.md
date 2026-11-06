# T003 · Audit this repository’s harness

## Initial state
The working directory is a clone of `llm-systems-lab` with one harness configuration from `experiments/<harness>/` (identified in `brief.md`), copied to the root as the harness would see it at startup.

## Contract
Agent A3 follows its specification to create `artifacts/ledger.md` and `artifacts/ablation-plan.md`.

## Visible evaluation
- Every configuration file is mentioned in the ledger.
- Every row has all six columns filled in.
- Boundaries (the `check/` prohibition, sandbox, permissions) have a “never” trigger.

## Budget
Up to 20 turns or $1 in cost.
