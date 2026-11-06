# Educational episode: migrate a report to API v2

## Mission

The provider moved invoice export to cursor API v2. Migrate the client and report consumer to the new contract, preserving record order and exact integer minor-unit monetary amounts.

## Inputs and new contract

`fixture-api.mjs` is a fixed local network substitute; `fetchPage(cursor)` returns `{ records, next_cursor }`. Request the first page with `null`; termination is signaled **only** by `next_cursor === null`. An empty page with a nonempty cursor does not end traversal. A cursor cycle must raise an error. The method returns `calls` for the open invocation-count check.

Each record has `invoice_id` (string identifier), `amount_minor` (nonnegative safe integer) and `currency`. `loadInvoices(fetchPage)` must return one array of `{ id, amountMinor, currency }` in original order. Do not convert IDs to numbers: leading zeros matter. Do not convert monetary amounts to floats. Reject invalid records, including unknown currency; this episode supports only `RUB`.

`buildReport(loadInvoices, fetchPage)` returns `{ invoiceIds, count, totalMinor, currency: 'RUB' }`, where the total is a safe integer. `src/main.mjs` prints the object as one JSON line. Legacy `items`, `total` and `amount` are no longer the contract. Legacy API support is not required.

## Allowed actions

Copy the episode according to the [shared guide](../README.md). You may modify `src/*.mjs`; keep extra tests in `extra-tests/`. `fixture-api.mjs`, `check.mjs` and the contract are fixed. No network, secrets or package installation. After checks pass, explain migration across modules and stop.

```bash
node "$EPISODE_DIR/check.mjs"
node "$EPISODE_DIR/src/main.mjs"
```

The initial check must yield **1 pass / 3 fail**, exit 1: `result-is-array` passes; `load-all-pages-and-map`, `report-consumes-v2`, `reject-cursor-cycle` fail. Correct initial diagnosis is an empty client list and incorrect report, not missing Node or an import error. After the fix, expect **4 pass / 0 fail**, exit 0. Also add your own invalid-field and total-overflow checks: the four open scenarios do not cover the full contract.

## Deliverables

Initial and final checks, CLI output, diff, page/call log, and an explanation of pagination termination. When delegating, separately record API/consumer owners, agreed interface, conflicting changes and integration. This is a public exercise, not a task supported by the current `new-run`.
