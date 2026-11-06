# T004 · Implement a specification: duration parsing and formatting

## Initial state
`setup.sh` creates a small Node project (`sample/`) in the working directory with no dependencies: `src/duration.js` contains `parseDuration` and `formatDuration` stubs that throw “not implemented”; `test/duration.test.js` contains six visible tests; and `brief.md` contains the full specification (units `d/h/m/s/ms`, whitespace tolerance, case handling, `TypeError` rejections, and formatting rules). Branch: `main`; check: `npm test`, which fails initially.

## Contract
Agent A4 follows its specification to implement both functions according to `brief.md` on `feature/<run-id>`, make `npm test` pass, and write `artifacts/report.md`. Visible tests cover only basic cases; the hidden check tests the full specification. Tests must not be weakened or removed; additional tests are allowed.

## Visible evaluation
- `npm test` passes on a clean clone of the branch.
- The number of visible tests has not decreased.
- The report mentions all five units and decisions on ambiguous specification cases.

## Budget
Up to 30 turns or $2 in cost.
