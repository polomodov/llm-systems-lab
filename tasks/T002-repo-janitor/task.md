# T002 · Janitor: failing `npm test` in a small project

## Initial state
`setup.sh` creates a small Node project (`sample/`) in the working directory with three intentional defects: a failing test caused by an implementation bug, a lint error, and an outdated dependency with a known vulnerability in `package.json`. Branch: `main`; check: `npm test` (runs lint and tests).

## Contract
Agent A2 follows its specification to make `npm test` pass on `janitor/<run-id>` and write `artifacts/report.md`. Tests must not be weakened: the hidden check compares the test set before and after.

## Visible evaluation
- `npm test` passes on a clean clone of the branch.
- Neither the test count nor the set of test names has decreased.
- The report lists all three defects.

## Budget
Up to 30 turns or $2 in cost.
