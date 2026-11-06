# LAB19. Amp: managed mode, its own agent loop, and independent evaluation

## Profile

| Field | Value |
| --- | --- |
| Previous lab | [LAB01](LAB01-reproducibility.md) |
| Harness | `amp`, package `@ampcode/cli` **0.0.1789920039-gafe14b** |
| Main route | Cloud provider `amp`, selector `managed:medium`; no local bridge required |
| Agent and task | `a2-janitor` / T002 |
| Minimum | Offline smoke test with native cache and one real T002 with independent evaluation |
| Extension | Three new T002 attempts, other managed modes, T001 replay, T003, ablation |
| Time | Estimate: 2–4 hours, not a measured duration |
| Initial status | `not-run`: describes a procedure for future execution |

## Objective

Run an autonomous task through Amp, preserving its managed selection of models, tools, and subagents. Obtain an external verdict, examine available telemetry, and conclude about this deployment without inventing a fixed model ID.

## Hypothesis

Pinned Amp with `managed:medium` and `--executor local` will perform T002 within the container boundary and return a final stream-json result for external evaluation. Success or failure can be established independently of the unknown underlying model; such a run cannot establish differences in the harness itself with one fixed model. Tokens are measurable only when complete final usage exists.

## Preparation

You need Node.js ≥22, Bash, Git, Docker, and an available Amp account. Run the coordinator as a regular user from the repository root. `--executor local` specifies where tools execute; it **does not mean a local LLM** and does not use your Ryzen's ROCm/Vulkan. Perform Linux x64 verification yourself: existing smoke tests ran on Linux arm64.

Read the [Amp README](../../experiments/amp/README.md), [settings](../../experiments/amp/settings.json), [profile](../../experiments/amp/harness.json), [protocol](../method.md), `agents/a2-janitor/spec.md`, and public [T002 contract](../../tasks/T002-repo-janitor/task.md). The solving agent does not read `tasks/*/check/`; task contracts remain unchanged.

Execute blocks sequentially in Bash, stopping to investigate any error before the next stage:

```bash
npm run lab:new -- --lab LAB19 --session my-session
LAB_DIR='experiments/amp/measurements/LAB19-my-session'
HARNESS_VERSION='0.0.1789920039-gafe14b'
IMAGE_REF='harness-lab/amp:0.0.1789920039-gafe14b'
PROVIDER_ID='amp'
MODEL_ID='managed:medium'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

`.env` needs **`AMP_API_KEY`**, an access token from Amp settings, not a short-lived interactive-login session token. Do not expose the value or copy `.env` into the report or a container mount. Before calling the model, preserve T002 limits, `timeout=900 s`, `budget-mode=observed`, one main attempt, selected managed mode, and independent evaluator. Record applicable workspace/account settings without secrets: complete disabling of service-connected plugins/MCP remains `unverified` before the first episode.

## Procedure

1. **Build the pinned image.** Amp requires normal npm `postinstall` for the same version's native binary; do not replace the Dockerfile with an `--ignore-scripts` installation. Building downloads packages but does not call a model. An existing image may be used without rebuilding if its ID is preserved.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/amp > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Check the CLI without network, a key, or execute mode.** Bun extracts a native addon into a temporary directory. A separate executable tmpfs is needed even for `--version`; the main `/tmp` remains noexec.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --tmpfs /tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777 \
       --env HOME=/tmp --env TMPDIR=/tmp/harness-native \
       --env XDG_CACHE_HOME=/tmp/harness-native --workdir /tmp \
       "$IMAGE_ID" amp "$FLAG" \
       > "$LAB_DIR/raw/amp-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/amp-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/amp-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/amp/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Check both files and exit codes: the version must include the pinned ID, and help must list `low`, `medium`, `high`, `ultra`, local executor, and stream-json. After `break`, smoke testing is incomplete. Missing a key in execute mode triggers a login flow; do not use it as an offline check in this lab. The coordinator checks credentials separately before starting the real container. The README's earlier native-cache measurement of ≈2.6 MiB is neither a measurement on your machine nor agent memory consumption.

3. **Check managed policy and configuration.** The profile accepts only `managed:low`, `managed:medium`, `managed:high`, and `managed:ultra`. The prefix stays in the record, while the CLI receives `--mode medium` and `--executor local`. `smart`/`rush` modes do not apply to this version. `model.selection=managed` and `model.lock=true` pin the selected mode, not model weights.

   In [settings](../../experiments/amp/settings.json), find the proxy, disabled updates, remote thread creation, and external skill directories. In the [adapter](../../experiments/amp/adapter.mjs), find private visibility, disabled IDE context, and remote-control terminal. Explain which account-side settings these still do not prove. `AMP_URL` is pinned to `https://ampcode.com/`, and the profile permits exactly `ampcode.com`; verify allowlist completeness for an authenticated episode using a real trace.

4. **Prepare a new T002.** Do not supply Amp with an exact third-party model ID: the current adapter does not select it.

   ```bash
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Save the actual ID in the report manifest and variable:

   ```bash
   RUN_ID='<ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Confirm `prepared` state. Prompt/spec, settings, adapter, and provider profile are sealed. Configuration cannot change within an already prepared attempt. The agent sees the task workspace, not the original lab or hidden check.

5. **Execute a real episode.** Requests to the service begin here with the prepared key:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   This adapter has no hard USD cap or native turn limit. `observed` is a research deviation from the contract's USD limit; external timeout is enforced. Preserve any service/egress errors; do not add wildcards or change settings in a sealed attempt. New settings, another mode, or a profile fix require a new run ID.

6. **Analyze the aggregate and unknown metrics.** Save a safe record summary:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   In the raw trace, find final `type: result`, its `subtype`, `is_error`, `num_turns`, and `usage` if present. The adapter accepts input tokens only with the complete `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` set, and output only with valid `output_tokens`. Do not add individual assistant-event usage to the total again. Missing fields remain `null` with reasons. The current schema does not confirm USD or underlying model ID; do not copy managed mode into `observed_id`. Separately check `error_max_turns`, `error_during_execution`, and interrupted streams.

7. **Obtain an external verdict.** Normal handoff to an evaluator starts from `awaiting_review`. `aborted` remains a failed attempt; retry always creates a new record. If no evaluator is available yet, do not mark the lab completed.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Following the [workflow](harness-workflow.md), the evaluator checks T002 using the hidden check outside the agent container without changing results. They fill `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` with check version and observations, and optionally `human_notes`; generated hashes remain unchanged. `judge-run` imports their decision and checks integrity rather than judging the task itself.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   Include `completed` with any justified verdict, all previous errors, and limitations of model identity and metrics in the report. Update `experiments/amp/NOTES.md` with actual run IDs. New components receive a ledger row in the same change; one successful attempt does not prove a component's usefulness without a before/after comparison.

8. **Perform the selected extension.** The main episode remains a pilot. For a triple, create three new T002 attempts through steps 4–7 with unchanged mode, images, task inputs, provider, timeout, and budget policy. Analyze all started outcomes.

   ```bash
   SERIES_RUN_IDS='<three new run IDs separated by commas without spaces>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   To study mode, preselect, for example, `managed:low` or `managed:high` and perform another separate triple with a new `MODEL_ID`; do not change mode inside records. This compares managed-service modes, including possible model and tool changes, not the isolated effect of one model or harness.

   T001 uses one recorded discovery-run archive with HTTP bodies/statuses and a shared date. If none exists yet, perform separate live discovery under the [workflow](harness-workflow.md); exclude it from the controlled replay series.

   ```bash
   SOURCE_ARCHIVE='<path to discovery run trace/sources.jsonl>'
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<new T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Execute with step 5 and evaluate with step 7 using T001's `rubric` method and designated checking script. Prepare a separate T003 audit:

   ```bash
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Repeat execution and external `rubric` evaluation. Different harnesses give T003 different configurations; these results do not imply one causal harness ranking. For ablation, create a new T002 as in step 4, prepare `--variant without-spec`, and repeat steps 5–7. The full scope is three baseline and three without-spec attempts under [LAB10](LAB10-ablation.md); Amp's service-side instructions remain part of the managed deployment, and Docker/gateway boundaries remain.

## Results tables

| Run ID | Task / variant | CLI version / image ID | Managed selector | Status | External verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Field | Value | Unit | Measurement or reason for `null` | Evidence |
| --- | --- | --- | --- | --- |
| Turns in final result | — | turns | — | — |
| Input + cache buckets | — | tokens | — | — |
| Output tokens | — | tokens | — | — |
| Cost | — | USD | — | — |
| Time | — | s | — | — |
| Underlying model ID | — | ID | — | — |

| Condition | What is pinned before execution | What was confirmed afterward | Limitation / evidence |
| --- | --- | --- | --- |
| Managed policy | Explicit supported mode | — | — |
| Native cache | Executable tmpfs 512 MiB, shared /tmp noexec | — | — |
| Account/workspace settings | Applicable configuration without secrets | — | — |
| API egress | ampcode.com through gateway | — | — |

## Deliverables

- LAB19 manifest/report with hypothesis, conditions, tables, and review answers.
- Build/help/version/unit evidence, architecture, and immutable image IDs; native-cache parameters separately.
- All actual run records, inputs/trace/artifacts, T002 `trace/change.patch`, independent evaluations, and compare JSON for exact IDs.
- NOTES, ledger additions if components changed, and an explanation of conclusions permitted by managed routing. Exclude secrets and `.env`.

## Completion criteria

- [ ] Pinned version and allowed modes confirmed offline without a login flow; unit tests pass.
- [ ] At least one real T002 is `completed` with an independent verdict; other attempts are not hidden.
- [ ] `managed:<mode>`, provider amp, immutable images, timeout 900 s, and observed budget recorded.
- [ ] `model.lock` not interpreted as pinning underlying weights; `--executor local` not interpreted as local inference.
- [ ] Usage accounted for only with sufficient evidence and without double-counting; USD and unknown model IDs not invented.
- [ ] NOTES reflects actual observations, `npm run check` passes, and extensions/unfinished stages are explicitly labeled.

## Review questions

1. What exactly does `model.lock=true` pin for Amp, and how does that differ from a model snapshot?
2. Why does `--executor local` not mean running the model on Ryzen?
3. Which cache buckets are needed for input totals, and why must assistant usage not be added to result?
4. Why does the coordinator check for `AMP_API_KEY` before execute mode?
5. Which variables change together with managed mode, and how does this limit comparison?
6. What can be concluded about the specification's usefulness after ablation if Amp's server-side instructions are unknown?

## Sources

- [README](../../experiments/amp/README.md), [NOTES](../../experiments/amp/NOTES.md), [profile](../../experiments/amp/harness.json), [settings](../../experiments/amp/settings.json), [Dockerfile](../../experiments/amp/Dockerfile), [adapter](../../experiments/amp/adapter.mjs), [tests](../../experiments/amp/adapter.test.mjs).
- [Protocol](../method.md), [workflow](harness-workflow.md), [ledger L015](../harness-ledger.md), [LAB09](LAB09-agent-campaign.md), [LAB10](LAB10-ablation.md).
- Primary links from repository research on 2026-09-20: [execute mode](https://ampcode.com/docs/cli/execute-mode), [modes](https://ampcode.com/docs/the-dial), [models and subagents](https://ampcode.com/docs/models-and-subagents), [stream-json](https://ampcode.com/docs/cli/streaming-json), [settings](https://ampcode.com/docs/cli/settings). This lab is tied to the pinned package version, not the changing service description.
