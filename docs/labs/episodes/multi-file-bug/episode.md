# Educational episode: order stock

## Mission

Fix order processing in a small shop. A client may submit an item across multiple lines with whitespace around its SKU. Do not sell more than available stock or partially change inventory after a rejected order.

## Inputs

- `src/basket.mjs`: client-line normalization.
- `src/inventory.mjs`: stock reservation.
- `src/checkout.mjs`: public checkout entry point.
- `check.mjs`: open educational scenarios; reading them is permitted.

## Output contract

`checkout(lines, stock)` accepts an array of `{ sku, quantity }` and a mutable stock object. SKU is a nonempty string after `trim`; quantity is a positive safe integer. Merge duplicate normalized SKUs, preserving first-appearance order. Combined quantities must also be safe integers.

On success, return `{ items }` with normalized merged items and decrement stock once by total quantity. Unknown SKUs, invalid input or insufficient stock raise an error and leave the **entire** `stock` object unchanged. Empty orders are valid and change nothing. Exact error text is not assessed.

`reserve(items, stock)` is also public: it must preserve atomicity on failure independently of invocation through `checkout`. Do not assume all callers validate stock beforehand.

## Allowed actions and stopping

Work on a copy under the [shared guide](../README.md). Modify only `src/*.mjs`; add separate tests in `extra-tests/`. No network or additional dependencies are needed. Do not modify `check.mjs`, the contract or the repository's original fixture. Stop after the open scenarios pass and you explain the cause; do not add business functionality.

```bash
node "$EPISODE_DIR/check.mjs"
```

The initial copy should yield **2 pass / 3 fail**, exit 1: `valid-single` and `reject-zero` pass; `merge-duplicates`, `duplicate-shortage-is-atomic`, `direct-reserve-is-atomic` fail. After the fix, expect **5 pass / 0 fail**, exit 0. These are expected exercise conditions, not model-run results or exhaustive contract checks.

## Deliverables

Initial and final check output, three-module diff, extra checks, explanation of normalization/atomicity interaction, solution limitations. For LAB21, also save a checkpoint with requirements, already modified files and remaining work. Do not include the answer or patch in the next repeated initial assignment.
