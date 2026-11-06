# T001 · Dossier from six sources about harnesses

## Initial state
`setup.sh` places `brief.md` and `sources.txt` in the working directory with six links: Claude Code documentation (glossary), the LangChain post “The Anatomy of an Agent Harness”, Böckeler’s article on martinfowler.com, the Anthropic post “Harness design for long-running application development”, the METR note “Measuring time horizon using Claude Code and Codex”, and the MCP changelog dated 2026-07-28.

## Contract
Agent A1 follows its specification to create `artifacts/dossier.md` and `artifacts/sources.json`. The dossier answers the three questions in `brief.md`: how the sources define a harness; which numbers they report about harness effects and under what conditions; and where the sources contradict one another.

## Visible evaluation
- `sources.json` covers all six links.
- The dossier contains no number without a source with `fetched: true`.
- A “Contradictions” section contains at least one item.

## Budget
Up to 40 turns or $3 in cost. Whichever limit is reached first applies. One run for the first attempt; three for a repeat.
