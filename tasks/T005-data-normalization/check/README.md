# Hidden check T005 (do not expose to the agent)

`check.sh <run-dir>`:
1. Verifies that `workspace/data/*` matches fresh `setup.sh` output byte for byte: the agent must not change the data.
2. Runs `reference.mjs <workspace/data>`, the reference implementation of the `brief.md` rules, to produce expected `normalized.json`.
3. Compares `artifacts/normalized.json` with the reference using canonical JSON (`compare.mjs`: sorted keys, significant element order), separately for `records` and `rejected`. Differences are printed by `id`.
4. Verifies that `artifacts/report.md` is nonempty and mentions every rejected reference `id` and all three files (`orders_a`, `orders_b`, `orders_c`).

Reference for the fixed data: 25 accepted records, 4 duplicates (`ORD-1002`, `ORD-1007` in b; `ORD-1012`, `ORD-1010` in c), and 3 rejections — `ORD-1004` (`invalid_date`, February 31), `ORD-1015` (`invalid_amount`, `n/a`), `ORD-1023` (`invalid_amount`, `null`). Edge cases: dates from `orders_c.json` use UTC (`ORD-1022` and `ORD-1026` shift by a day), a quoted CSV amount with a comma, a TSV thousands separator, and rounding `15.99 × 100` and `99.99 × 100`.

`pass` — matching `records` and `rejected`, complete report; `partial` — matching `records`, but different `rejected` or incomplete report; `fail` — otherwise, or input data changed. Exit codes: 0 / 2 / 1; final line: `verdict: …`.
