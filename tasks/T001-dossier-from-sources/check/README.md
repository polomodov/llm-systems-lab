# Hidden check T001 (do not expose to the agent)

`check.sh <run-dir>` is the deterministic part: all six links appear in `sources.json`; every number in `dossier.md` appears in a `sources.json` quotation from a source with `fetched: true`; a Contradictions section exists.

Rubric (evaluated by a human or a judge using another model):
- Definitions from all six sources are represented accurately (compare with `expected/definitions.md`).
- METR numbers (50.7% / 14.5%) retain the condition “fraction of bootstrap samples,” rather than “N% better.”
- Finding a contradiction between “up to 6×” in the Meta-Harness introduction and a small frontier effect is optional; the “native harness is better / not significant” contradiction must be identified.
- Vendor claims are labeled as claims.

Verdict: `pass` — all deterministic items and at least three of four rubric items; `partial` — deterministic items pass; `fail` — otherwise, or the agent read `check/`.
