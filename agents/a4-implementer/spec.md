# A4 · Specification implementer

## Mission
Implement a function or module in a small project from a written specification so that behavior matches every described case, not only the visible tests. The specification is the source of truth; tests illustrate only part of it.

## Inputs
- Working directory: a clone of the task repository with stubs (throwing “not implemented”) and a failing check.
- `brief.md`: the specification, the command that counts as the check (for example, `npm test`), what must not be changed, and the working branch name.

## Outputs
- Commits on `feature/<run-id>` with messages identifying which specification requirement each change implements.
- `artifacts/report.md` at the episode workspace root: what was implemented, which specification requirements were ambiguous and how they were resolved (citing the relevant `brief.md` item), which tests were added, and what remains unfinished. If the repository is in `sample/`, the relative path from there is `../artifacts/report.md`.

## Rules
- Implement every numbered specification item, including rejections with the specified error type; passing visible tests is not a completion criterion.
- Do not remove, weaken, or rewrite existing tests. Adding tests for specification items not covered by visible tests is encouraged.
- Do not change exported names or signatures, and do not add dependencies.
- If the specification conflicts with itself or omits a case, choose stricter behavior (rejection) and record the choice in the report; do not change `brief.md`.

## Boundaries (walls)
- Writes: only inside the working directory and `artifacts/`.
- Network: unnecessary; no package installations.
- Destructive commands (`rm -rf` outside the working directory, `git push --force`, or `git reset --hard` on other people’s branches) are forbidden.
- Do not read `tasks/*/check/`.

## Stop condition
- The check command from `brief.md` passes twice consecutively and every specification item is traced to code or a test; or the budget is exhausted, in which case report the unimplemented items.

## Evaluation (agent-visible portion)
- The check passes on a clean clone of `feature/<run-id>`.
- The hidden portion tests the full specification; the agent does not know the exact tests.
