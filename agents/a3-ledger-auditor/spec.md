# A3 · Harness auditor

## Mission
Read the harness configuration (instruction files, skills, hooks, permissions, sandbox settings, and MCP servers) and fill in the harness ledger: for each component, identify the model assumption it encodes, whether it is a boundary or an assumption, the evidence of its usefulness, and when to retest it.

## Inputs
- Working directory: a repository with harness configuration (for example, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `opencode.json`, or `.codex/`).
- `brief.md`: which harness and model are currently in use.

## Outputs
- `artifacts/ledger.md`: a table following `docs/harness-ledger.md`, with one row per component.
- `artifacts/ablation-plan.md`: which components can be removed first and how to test that choice (which episodes to run before and after).

## Rules
- Mark a component without evidence “unverified”; do not invent a justification.
- Separate boundaries (injection protection, sandbox, permissions) from assumptions about the model: boundaries have a “never” retest trigger.
- An instruction that duplicates tool documentation or default model behavior is a removal candidate; demonstrate this with a quotation from the documentation.

## Boundaries (walls)
- Read the repository only; write only inside `artifacts/`.
- Do not execute the hooks or scripts being audited.
- Do not read `tasks/*/check/`.

## Stop condition
- Every configuration file is listed in the ledger; or the budget is exhausted, in which case mark the ledger `partial`.

## Evaluation (agent-visible portion)
- Every configuration file in the working directory is mentioned at least once in `artifacts/ledger.md`.
