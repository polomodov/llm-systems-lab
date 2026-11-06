# LAB 01. Reproducible episodes and experiment boundaries

## Profile

| Parameter | Condition |
| --- | --- |
| Operator time | 1–2 hours |
| Previous labs | None |
| Environment | Node.js ≥22, Git, Bash; no GPU required |
| Readiness | Can be completed with the repository's current commands |
| Minimum scope | One prepared T002 and two preparation/integrity checks using synthetic fixtures |
| Extension | Separate Docker isolation smoke test; preparation of a second harness |

## Objective

Learn to create a reproducible episode, distinguish preparation from task execution, and check what data the agent can see. The result is a prepared run record and an explanation of the boundaries between inputs, workspace, trace, and independent evaluation.

## Hypothesis

“Preparing the same task again preserves its initial content, and changes to sealed inputs are detected before execution.” A separate boundary requirement is that hidden checks and `.env` must not be in the agent workspace. Do not test this by reading actual hidden checks; use the original manifest and synthetic tests.

## Preparation

1. Open the repository root. No API keys are required for this lab.
2. Read the [method](../method.md), [record description](../../results/README.md), public [T002 contract](../../tasks/T002-repo-janitor/task.md), and [A2 specification](../../agents/a2-janitor/spec.md). Do not open the `check` directory.
3. Create a report:

```bash
npm run lab:new -- --lab LAB01 --session first-pass
LAB_DIR='experiments/local-models/measurements/LAB01-first-pass'
node --version > "$LAB_DIR/raw/node-version.txt"
git --version > "$LAB_DIR/raw/git-version.txt"
bash --version > "$LAB_DIR/raw/bash-version.txt"
```

If the directory already exists, choose a new session ID. Use the created directory's path in all subsequent commands. Do not overwrite raw logs when repeating an experiment.

## Procedure

1. **Before execution**, fill in the hypothesis and protocol in `report.md`: the experiment will examine preparation without calling a model. Record the current commit and whether the working tree has changes:

```bash
git rev-parse HEAD > "$LAB_DIR/raw/revision.txt"
git status --short > "$LAB_DIR/raw/status.txt"
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
npm run check > "$LAB_DIR/raw/check-before.txt" 2>&1
```

2. **Create one new episode**, choosing an implemented harness:

```bash
npm run new-run -- --harness claude-code --agent a2-janitor --task T002
```

The output will contain the path `results/runs/<run-id>/run.json`. Copy that exact identifier into the next variable. This is a manual substitution from the actual output; do not use the placeholder string literally.

```bash
RUN_ID='<run-id from the previous command>'
test -f "results/runs/$RUN_ID/run.json"
npm run prepare-run -- --run "$RUN_ID" > "$LAB_DIR/raw/prepare.txt" 2>&1
```

If `test -f` did not succeed, fix the variable before the next step. Add the resulting ID to `run_ids` in the lab report's `manifest.json`. Do not edit the experimental `run.json` manually.

3. **Check the snapshot's state and contents**, reading only known public files. The command does not access hidden checks:

```bash
node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/prepared-summary.json"
import { readFileSync } from 'node:fs';
const id = process.argv[2];
const record = JSON.parse(readFileSync(`results/runs/${id}/run.json`, 'utf8'));
const manifest = JSON.parse(readFileSync(`results/runs/${id}/inputs/manifest.json`, 'utf8'));
const forbidden = manifest.workspace.filter(x => /(^|\/)(check|\.env)(\/|$)/.test(x.path));
console.log(JSON.stringify({
  run_id: id, status: record.status, seed_commit: manifest.seed_commit,
  source_mode: manifest.source_mode, input_files: manifest.files.length,
  workspace_files: manifest.workspace.length, forbidden_workspace_paths: forbidden
}, null, 2));
if (record.status !== 'prepared' || forbidden.length) process.exitCode = 1;
NODE
```

The expected structural result is `prepared`, a nonempty `seed_commit`, and no forbidden paths. This is an expected condition of the assignment, not a result already obtained in your session. Compare `inputs/control/prompt.txt` with the public specification/contract and note where the agent should work and save artifacts. Do not run commands from the task prompt yourself to fix the task.

4. **Test the hypothesis using synthetic fixtures**. Do not corrupt an actual prepared run for demonstration purposes. These tests create their own temporary episodes:

```bash
node --test tests/setup.test.mjs > "$LAB_DIR/raw/setup-tests.txt" 2>&1
node --test tests/runtime.test.mjs > "$LAB_DIR/raw/integrity-tests.txt" 2>&1
```

In the first log, find the check for identical initial Git commits; in the second, find detection of a mutated sealed input/manifest. Record the test names and actual results. If a test fails, read and preserve the error; do not change the task contract or checks to obtain a passing result.

5. **Describe the observability boundary.** Using the [shared infrastructure](../../experiments/common/README.md) and `inputs/control/network.json`, fill in the table below: what is mounted/allowed, and where `.env`, hidden checks, run.json, and trace reside. Preparation proves the file inventory; treat the network/process boundary as `unverified` without a Docker test.

6. **Complete the structural check**:

```bash
npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
```

The run remains `prepared`; do not change it to `completed`, because the model was not run and there is no independent verdict. The educational LAB01 can be completed once its criteria are met. Explain in the conclusion why these two statuses differ.

7. **Extension:** if Docker Engine and a local `node:24.13.1-bookworm-slim` image are available, run `npm run test:docker > "$LAB_DIR/raw/docker-tests.txt" 2>&1`. Save version/image details and the result; this smoke test does not call a model. You may prepare a separate T002 for `opencode` and compare the public manifests, preserving both run IDs. The contents of `.git`, including timestamps, need not match byte for byte; compare the initial commit and substantive files according to the method.

## Results tables

| Check | Expected condition | Observation | Raw evidence |
| --- | --- | --- | --- |
| Initial run state | `planned` before prepare | — | — |
| After prepare | `prepared`, without a pass verdict | — | — |
| Initial T002 Git tree | Repeatable seed commit | — | — |
| Sealed inputs | Mutation detected by the test | — | — |
| Workspace | No check/.env | — | — |
| Docker isolation, extension | Synthetic test passes, or reason it is unavailable | — | — |

| Object | Location | Visible to agent | Evidence / check limitation |
| --- | --- | --- | --- |
| Contract/spec | — | — | — |
| T002 working files | — | — | — |
| `.env`, hidden checks | — | — | — |
| `run.json`, trace | — | — | — |
| API credential in the harness environment | — | — | — |

## Deliverables

`report.md` with both tables and answers; the lab `manifest.json` referencing the run ID; `raw/` containing versions, working-tree status, prepare output, summary, tests, and both checks. Leave the actual prepared run in `results/runs/<run-id>/` together with its inputs. `measurements.tsv` may contain no data rows: explain that integrity, rather than model performance, was tested.

## Completion criteria

- [ ] A new episode was created without overwriting an existing one and is in `prepared` state.
- [ ] The run ID, seed commit, manifest check results, and both test suites are included.
- [ ] The absence of hidden checks was confirmed without reading their contents.
- [ ] Preparation verification is distinguished from the optional Docker smoke test.
- [ ] The educational conclusion contains no invented model quality, tokens/s, or cost.
- [ ] `npm run check` passes; the report and questions are completed.

## Review questions

1. Why do `prepared` and exit 0 not mean the task has a `pass` verdict?
2. What does the manifest's SHA-256 record, and what does it not prove?
3. Why are `.git/index` timestamps unsuitable for comparing episode contents?
4. How does the absence of a mount differ from a textual instruction prohibiting the agent from reading a file?
5. What limitation remains if the API key is in the harness environment?

## Sources

[Experiment method](../method.md), [record lifecycle](../../results/README.md), [shared infrastructure](../../experiments/common/README.md), public [T002](../../tasks/T002-repo-janitor/task.md) and [A2](../../agents/a2-janitor/spec.md). Command sources: [new-run](../../scripts/new-run.mjs), [prepare-run](../../scripts/prepare-run.mjs).
