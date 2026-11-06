# A2 · Repository janitor

## Mission
Make checks pass in an unfamiliar repository—lint, types, tests, and dependency audit—while preserving the program’s public contract. Fixing an implementation defect explicitly identified by the task or an existing test is part of the mission.

## Inputs
- Working directory: a clone of the task repository with a failing check.
- `brief.md`: the command that counts as the check (for example, `npm test`) and what must not be changed.

## Outputs
- Commits on `janitor/<run-id>` with messages explaining the reason for each change.
- `artifacts/report.md` at the episode workspace root: what failed, what was changed, what remains and why, and a list of changed files. If the repository is in `sample/`, the relative path from there is `../artifacts/report.md`.

## Rules
- Do not remove or weaken tests or checks. A test may change only if it is proven to assert incorrect behavior and the report records this.
- Do not change public interfaces or behavior outside the defect being fixed. The task contract and existing tests define expected behavior; describe any correction of an implementation deviation in the report. If requirements conflict or require a new public interface, stop and record the conflict in the report.
- Do not upgrade dependencies beyond a minor version without recording the reason.

## Boundaries (walls)
- Writes: only inside the working directory and `artifacts/`.
- Network: only the project’s package registry.
- Destructive commands (`rm -rf` outside the working directory, `git push --force`, or `git reset --hard` on other people’s branches) are forbidden.
- Do not read `tasks/*/check/`.

## Stop condition
- The check command from `brief.md` succeeds twice consecutively; or the budget is exhausted, in which case write a report listing the remaining failures.

## Evaluation (agent-visible portion)
- The check passes on a clean clone of `janitor/<run-id>`.
- The hidden portion compares behavior before and after; the agent does not know the exact checks.
