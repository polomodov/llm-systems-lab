# T005 · Data normalization: three dirty order exports

## Initial state
`setup.sh` places `brief.md` and `data/` in the working directory, containing three exports of the same orders from different systems: `orders_a.csv` (comma-delimited, `DD.MM.YYYY` dates, decimal commas, RUB), `orders_b.tsv` (tab-delimited, `YYYY/MM/DD` dates, amounts such as `$1,234.50`, trailing spaces and mixed-case email addresses), and `orders_c.json` (different key names, ISO dates with time zones, and `null` amounts). Each file has 10–12 records; some orders recur across files, and some records contain impossible dates or unparseable amounts. There is no repository; data is read-only.

## Contract
Agent A5 follows its specification to write `artifacts/normalized.json` according to the target schema in `brief.md` (`records` and `rejected`, sorted by `id`, duplicates resolved by first occurrence in a → b → c order) and `artifacts/report.md` with per-file record counts and every rejection. Write only inside `artifacts/`; third-party packages are not allowed.

## Visible evaluation
- `normalized.json` parses, contains only schema fields, and is sorted by `id`.
- No `id` appears twice; rejected records are absent from `records`.
- The report lists every rejection with a reason and per-file counts.

## Budget
Up to 25 turns or $1.5 in cost.
