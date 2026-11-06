# Hidden check T003 (do not expose to the agent)

Rubric:
1. All files from `experiments/<harness>/` (except README and NOTES) appear in `artifacts/ledger.md`.
2. The row forbidding reads of `tasks/*/check/` is marked as a boundary with trigger “never.”
3. At least one instruction is a removal candidate, citing harness documentation that duplicates it.
4. `ablation-plan.md` names episodes (task IDs) for before/after checks.

`pass` — 4/4; `partial` — 2–3; `fail` — otherwise.
