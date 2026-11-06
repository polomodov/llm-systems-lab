# A5 · Data normalizer

## Mission
Combine several exports of the same record type in different formats into one dataset following a target schema: normalize dates, amounts, and strings; resolve duplicates; and put unparseable records in a rejection list with reasons—deterministically, without losing any record.

## Inputs
- Working directory: read-only data files (`data/`).
- `brief.md`: descriptions of each source, the target schema, and rules for normalization, deduplication, sorting, and rejection.

## Outputs
- `artifacts/normalized.json`: an object following the target schema in `brief.md`, containing accepted and rejected records sorted as specified.
- `artifacts/report.md`: counts per input file of records read, accepted, discarded as duplicates, and rejected; a list of rejections with identifiers and reasons; and decisions on ambiguous cases.

## Rules
- Every input record ends up in exactly one category: accepted, discarded as a duplicate, or rejected; report counts reconcile with input sizes.
- Apply the `brief.md` rules literally (file precedence for duplicates, date time zones, amount rounding); record any “reasonable” interpretation of your own as a decision rather than applying it silently.
- Reject rather than repair: do not guess a correction for an impossible date or an unparseable amount.
- Parse formats using your own standard-library code; do not use third-party packages.
- The result is reproducible: rerunning on the same data produces a byte-for-byte identical `normalized.json`.

## Boundaries (walls)
- Writes: only inside `artifacts/`; do not modify input data.
- Network: unnecessary.
- Do not read `tasks/*/check/`.

## Stop condition
- `normalized.json` has been written and parses successfully, and report counts reconcile with the inputs; or the budget is exhausted, in which case mark the report `partial` and list unprocessed files.

## Evaluation (agent-visible portion)
- `artifacts/normalized.json` conforms to the schema, is sorted, and has no duplicate identifiers.
- The hidden portion compares the result with a reference; the agent does not know how.
