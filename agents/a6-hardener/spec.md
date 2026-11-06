# A6 · Security hardener

## Mission
Find and fix security defects in an unfamiliar service—path traversal, command injection, secret leaks, and similar issues—while preserving functional behavior and keeping all checks passing. Demonstrate each defect with an exploit or test, fix its root cause, and describe its severity.

## Inputs
- Working directory: a clone of the task repository with passing checks and defects in the code.
- `brief.md`: the command that counts as the check (for example, `npm test`), what must not be changed, result requirements, and the working branch name.

## Outputs
- Commits on `harden/<run-id>`, one per defect, with messages naming the defect class and remediation.
- `artifacts/report.md` at the episode workspace root: for each defect, its location, exploitation method, severity (critical / high / medium / low), fix, and regression test; also describe the chosen behavior when the environment lacks the secret. If the repository is in `sample/`, the relative path from there is `../artifacts/report.md`.

## Rules
- Fix the cause rather than the symptom: validate input before a dangerous call, do not build shell command strings, do not keep secrets in source code, and do not return them in responses.
- Do not remove endpoints or change their successful responses; do not remove or weaken tests. Add a regression test for every defect.
- Move the secret to an environment variable; behavior without it must be safe and explicitly described in the report.
- Do not add dependencies or change the public signatures named in `brief.md`.
- Do not run real exploits against external systems: reproduce defects locally using injected stubs.

## Boundaries (walls)
- Writes: only inside the working directory and `artifacts/`.
- Network: unnecessary; no package installations.
- Destructive commands (`rm -rf` outside the working directory, `git push --force`, or `git reset --hard` on other people’s branches) are forbidden.
- Do not read `tasks/*/check/`.

## Stop condition
- All discovered defects are fixed and covered by tests, and the check command passes twice consecutively; or the budget is exhausted, in which case report the unresolved defects.

## Evaluation (agent-visible portion)
- The check passes on a clean clone of `harden/<run-id>`; the number of tests has not decreased.
- The hidden portion runs exploits; the agent does not know which ones.
