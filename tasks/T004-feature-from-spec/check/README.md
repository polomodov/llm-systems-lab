# Hidden check T004 (do not expose to the agent)

`check.sh <run-dir>`:
1. Clones the `feature/*` branch from `workspace/sample` into a temporary directory, verifies no dependencies were added, and runs `npm test`, which must pass.
2. Counts visible tests (`node --test --test-reporter=tap test/*.test.js`, the `# tests` line): at least the initial six.
3. Copies `hidden.test.js` into the clone’s `test/` directory and runs 17 tests covering the full `brief.md` specification: unit case (`1H 30M`), spaces/tabs (` 90m `), all five units in arbitrary order, leading zeros, and `TypeError` rejection of `1h1h`, `-5s`, `1.5h`, an empty string, unitless `90`, `3w`, `1 h` and non-string inputs; for `formatDuration`, omission of zero components, `0ms`, rejection of negative/fractional/non-numeric values, and `parse(format(x)) === x` round trips over a dozen values.
4. Verifies that `artifacts/report.md` is nonempty and mentions every unit: `d`, `h`, `m`, `s`, `ms`.

The ambiguous point is resolved in `brief.md`: fractional values (`1.5h`) are rejected; the check follows that contract.

`pass` — passing `npm test`, all hidden tests and the report; `partial` — passing `npm test` and at least 70% of hidden tests; `fail` — otherwise. Exit codes: 0 / 2 / 1; final line: `verdict: …`.
