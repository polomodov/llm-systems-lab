# A1 · Source dossier writer

## Mission
Compile a dossier from a list of links in the `docs/research/*.md` format used by polomodov.tech: facts with evidence classes, quotations of at most 25 words, a source table, an “Unverified” section, and open questions.

## Inputs
- `sources.txt` in the working directory: one link per line, with an optional comment after `#`.
- `brief.md`: topic, questions the dossier must answer, and cutoff date.

## Outputs
- `artifacts/dossier.md` with these sections: header (topic, verification date, scope), English summary, method, class legend, facts by section (table `| ID | Claim | Number and basis | Source | Date | Class | Method | Limitation | Status |`), contradictions, source register, unverified claims, and open questions.
- `artifacts/sources.json`: for each link, whether it was opened (`fetched: true|false`), HTTP status, date shown on the page, and up to three quotations.

## Rules
- A number may become a fact only if it comes from a page the agent opened during this run; an unavailable page receives status `±`, not a factual claim.
- Companies’ statements about their own products belong to the “product snapshot, vendor claim” class.
- Do not invent dates; if a page has no date, write “date not specified”.

## Boundaries (walls)
- Network: only `GET` requests to links in `sources.txt` and links found on those pages (depth 1). No forms, logins, or executable downloads.
- Writes: only inside `artifacts/`.
- Do not read `tasks/*/check/`.

## Stop condition
- All links have been processed (opened or marked unavailable) and the dossier has been written; or the run budget is exhausted, in which case mark the dossier `partial` and list unprocessed links.

## Evaluation (agent-visible portion)
- `artifacts/sources.json` covers every line in `sources.txt`.
- The dossier contains no number absent from a `sources.json` entry with `fetched: true`.
