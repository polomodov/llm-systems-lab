# LAB18. Copilot CLI: an autonomous episode, model selector, and AI credits

## Profile

| Field | Value |
| --- | --- |
| Previous lab | [LAB01](LAB01-reproducibility.md) |
| Harness | `copilot-cli`, package `@github/copilot` **1.0.86** |
| Main route | Cloud provider `copilot`; no local bridge required |
| Agent and task | `a2-janitor` / T002 |
| Minimum | Offline smoke test with native cache and one real T002 with independent evaluation |
| Extension | Three new T002 attempts, T001 replay, T003, specification ablation |
| Time | Estimate: 2–4 hours excluding service delays; not a measured result |
| Initial status | `not-run`; this lab contains assignments, not an execution report |

## Objective

Run local Copilot CLI through the shared coordinator and obtain an independently evaluated result. Distinguish the selected Copilot selector from a confirmed model snapshot, and premium requests / AI credits from USD cost. Check whether the container boundary and bounded native cache interfere with the CLI's own loop.

## Hypothesis

CLI 1.0.86 with an explicit available selector will execute T002 without interactive questions and end its JSONL stream with `result`. Complete turn-event pairs provide an observed count of main-agent turns, but the current format does not provide token totals, USD, or actual model ID. An independent verdict checks task quality separately from terminal `exitCode=0`.

## Preparation

You need Node.js ≥22, Bash, Git, Docker, and an account with Copilot CLI access. This is **local CLI execution with a cloud service**, not GitHub Copilot coding agent. Run the coordinator as a regular user from the repository root. Repeat smoke tests yourself on Linux x64: saved infrastructure measurements concerned Linux arm64.

Read the [README](../../experiments/copilot-cli/README.md), [profile](../../experiments/copilot-cli/harness.json), [protocol](../method.md), `agents/a2-janitor/spec.md`, and public [T002 contract](../../tasks/T002-repo-janitor/task.md). The solving agent must not read hidden `tasks/*/check/`; contracts are not edited.

Execute blocks sequentially in Bash, investigating errors before proceeding:

```bash
npm run lab:new -- --lab LAB18 --session my-session
LAB_DIR='experiments/copilot-cli/measurements/LAB18-my-session'
HARNESS_VERSION='1.0.86'
IMAGE_REF='harness-lab/copilot-cli:1.0.86'
PROVIDER_ID='copilot'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

`.env` requires **`COPILOT_GITHUB_TOKEN`**, a supported token with Copilot access; research for the pinned version specifies a fine-grained PAT with Copilot Requests permission, while classic PATs are unsupported. Do not expose its value or copy it into the report; do not mount `.env` in the container. Before an API call, record the selected configuration, T002 limits, `timeout=900 s`, `budget-mode=observed`, one main attempt, and independent evaluator. Record subscription type without account identifiers or secrets.

## Procedure

1. **Build the image and preserve its identity.** Use pinned npm package 1.0.86. Building requires network for packages, but no key or model call; an existing verified image may be used without rebuilding.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/copilot-cli \
     > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Check native cache without network or credentials.** The CLI extracts a native addon; `noexec /tmp` without a separate executable tmpfs blocks even `--version`. Keep the main `/tmp` as `noexec`, allocate a separate 512 MiB `/tmp/harness-native`, and point `TMPDIR`/`XDG_CACHE_HOME` there. This is a setting of the existing profile, not permission to execute lab files.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --tmpfs /tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777 \
       --env HOME=/tmp --env TMPDIR=/tmp/harness-native \
       --env XDG_CACHE_HOME=/tmp/harness-native --env COPILOT_HOME=/tmp/copilot \
       --env COPILOT_AUTO_UPDATE=false --env CI=true --workdir /tmp \
       "$IMAGE_ID" copilot "$FLAG" \
       > "$LAB_DIR/raw/copilot-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/copilot-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/copilot-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/copilot-cli/adapter.test.mjs \
     > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Check both files and exit codes: version must be 1.0.86 and help must complete successfully. After `break`, smoke testing is incomplete; do not begin the API stage. Do not copy the README's earlier arm64 cache measurement of ≈157.5 MiB into your report as your own. 512 MiB is the tmpfs maximum capacity, not preallocated or measured episode memory.

3. **Examine the adapter contract.** Find `--no-ask-user`, `--no-custom-instructions`, `--disable-builtin-mcps`, `--no-remote-export`, disabled updates, and prompt passing as one argv element in the [adapter](../../experiments/copilot-cli/adapter.mjs) and tests. Explain why `--allow-all` is acceptable only with an external boundary. Do not add GitHub MCP, BYOK, GHE.com, or remote execution to this assignment: these are new conditions and profiles.

4. **Choose an explicit selector and prepare a new T002.** The `gpt-5.4` example appears in tests and the pinned adapter README. Use it only if available in your Copilot account; otherwise replace it with another supported explicit selector before `new-run` and record the selection source. `auto`, `default`, and `latest` are forbidden. A Copilot selector name does not prove the same snapshot as another provider's direct API.

   ```bash
   MODEL_ID='gpt-5.4'
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Save the returned ID in the lab manifest and this variable:

   ```bash
   RUN_ID='<ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Confirm `prepared` state before execution. The profile allows only `github.com`, `api.github.com`, `api.githubcopilot.com`, `api.individual.githubcopilot.com`, `api.business.githubcopilot.com`, and `api.enterprise.githubcopilot.com`. Completeness of this list for your authenticated CLI remains a testable hypothesis, not grounds for a wildcard.

5. **Execute a real episode.** This is the first stage using the model and credentials.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   `observed` means the task's USD cap is not enforced. `--max-autopilot-continues` is not used as a substitute for a model-turn limit; the external timeout is the enforced boundary. Preserve the reason for authorization errors or denied egress. A profile change requires new preparation and a new run ID; do not expand networking in a sealed attempt. Do not pass the token in diagnostic command arguments.

6. **Check the trace and unknown metrics.** Save a record summary:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   Find `session.start`, `assistant.turn_start` / `assistant.turn_end` pairs, and a `type: result` terminator with numeric `exitCode` in raw JSONL. A complete set of pairs yields measurable main-agent turns; duplicate IDs are not summed. This version's stdout formatter filters `assistant.usage` and `session.shutdown`; the current parser leaves token totals and observed model unknown. Premium requests/AI credits cannot be converted to USD without a separate justified measurement; USD remains `null` with a reason in the run record. A `result` and successful exit code do not yet check the T002 solution.

7. **Complete independent judging.** Create a template for `awaiting_review`; for `aborted`, preserve the error and create a new attempt if needed. Do not turn an unfinished/interrupted record into success by editing it.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Under the [shared procedure](harness-workflow.md), an independent evaluator performs the T002 hidden check outside the agent container and fills `result`, `evaluator`, and `check_output` with check version and observations; `human_notes` is optional. `result` accepts `pass`, `fail`, or `partial`; generated hashes stay unchanged. The record remains `awaiting_review` until independent evaluation exists.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   The lab minimum is a real `completed` record with any substantively justified verdict. Record actual IDs, observability, egress, and selector limitations in `experiments/copilot-cli/NOTES.md`. A new component requires a ledger row; absent token totals do not permit invented measurements.

8. **Extend the study according to a predefined plan.** For a triple, create three new T002 attempts through steps 4–7. The initial main episode remains a pilot; preserve version, image IDs, selector, provider, task inputs, timeout, and observed budget. Analyze every started outcome:

   ```bash
   SERIES_RUN_IDS='<three new run IDs separated by commas without spaces>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   For T001, use one recorded discovery-run archive. If none exists, perform separate live discovery under the [workflow](harness-workflow.md); the archive must contain HTTP bodies/statuses, not only URLs.

   ```bash
   SOURCE_ARCHIVE='<path to discovery run trace/sources.jsonl>'
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<new T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Execute with step 5 and evaluate with step 7, but T001 uses `rubric` with its designated checking script. Prepare a separate T003 audit:

   ```bash
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Perform step 5 and external `rubric` evaluation. Different harnesses give T003 different input configurations. For ablation, create a new T002 as in step 4 and prepare `--variant without-spec`, then execute and evaluate. Check that custom instructions do not reintroduce the specification; Docker and gateway remain. Study the effect with three baseline and three without-spec attempts under [LAB10](LAB10-ablation.md).

## Results tables

| Run ID | Task / variant | CLI version / image ID | Copilot selector | Status | External verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Metric | Value | Unit | Measurement or reason for `null` | Evidence |
| --- | --- | --- | --- | --- |
| Main-agent turns | — | turns | — | — |
| Input/output tokens | — | tokens | — | — |
| Premium requests / AI credits | — | As labeled by the service | — | — |
| Run cost | — | USD | — | — |
| Time | — | s | — | — |
| Observed model ID | — | ID | — | — |

| Check | Condition before execution | Observation | Evidence / limitation |
| --- | --- | --- | --- |
| Native cache smoke | Separate 512 MiB executable tmpfs, network disabled | — | — |
| Turn pairs | Complete unique main-agent pairs | — | — |
| Egress | Only domains in the pinned profile | — | — |
| T002 | Independent substantive evaluation | — | — |

## Deliverables

- LAB18 lab manifest/report with the advance protocol, tables, and review answers.
- Version, architecture, image IDs, offline help/version/tests, and native tmpfs parameters; no token or `.env`.
- References to all created run records, immutable inputs/trace/artifacts, T002 `trace/change.patch`, and external evaluations.
- Compare JSON for exact IDs, NOTES, and ledger additions if needed; a separate explanation of selector identity and the AI credits/USD boundary.

## Completion criteria

- [ ] 1.0.86 confirmed offline; native cache works while main `/tmp` remains noexec.
- [ ] At least one real T002 is `completed` with an independent verdict; errors and aborted attempts are not hidden.
- [ ] Explicit selector, provider, immutable images, observed budget, and timeout 900 s recorded.
- [ ] Selector not declared an exact model snapshot, AI credits not substituted for USD, missing tokens not replaced with zeros.
- [ ] Turns supported by complete-pair evidence, or remain unknown with a reason.
- [ ] `npm run check` passes; offline smoke and real results are separate; additional series have their own IDs.

## Review questions

1. How does local Copilot CLI differ from the cloud Copilot coding agent?
2. Why does the same selector string in Copilot and another API not guarantee identical weights?
3. Why does shared `/tmp` remain noexec although an executable native cache is needed?
4. Which events are needed for a reliable turn count? What should be done with an unclosed pair?
5. Why are premium requests not the USD cost of a particular attempt?
6. What must be checked before expanding egress after a network rejection, and why is a new record required?

## Sources

- [README](../../experiments/copilot-cli/README.md), [NOTES](../../experiments/copilot-cli/NOTES.md), [profile](../../experiments/copilot-cli/harness.json), [Dockerfile](../../experiments/copilot-cli/Dockerfile), [adapter](../../experiments/copilot-cli/adapter.mjs), [tests](../../experiments/copilot-cli/adapter.test.mjs).
- [Protocol](../method.md), [evaluation workflow](harness-workflow.md), [ledger L014](../harness-ledger.md), [LAB09](LAB09-agent-campaign.md), [LAB10](LAB10-ablation.md).
- Primary sources used by the repository snapshot from 2026-09-20: [programmatic CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference), [authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), [network allowlist](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference). Performing the assignment checks pinned version 1.0.86, not current `latest`.
