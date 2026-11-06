# LAB14. Antigravity CLI: Gemini API, an autonomous episode, and observability limits

## Profile

| Field | Value |
| --- | --- |
| Previous lab | [LAB01](LAB01-reproducibility.md) |
| Harness | `antigravity-cli`, official `agy` **1.2.7** |
| Main route | Cloud `google` / Gemini API; no local bridge required |
| Agent and task | `a2-janitor` / T002 |
| Minimum | Offline smoke test and one real T002 with independent evaluation |
| Extension | Three new T002 attempts, T001 replay, T003, specification ablation |
| Time | Estimate: 2–4 hours excluding provider queues; not a measured result |
| Initial status | `not-run`: commands are assignments; results still need to be obtained |

## Objective

Run T002 through the native `agy` loop, preserving reproducible inputs and an external verdict. Check which information is actually available from Antigravity stream-json, without substituting a CLI setting for the response's model identity.

## Hypothesis

Pinned Antigravity CLI with an explicit Gemini API model ID will execute an autonomous T002 through the allowed gateway and return a result suitable for independent evaluation. The final `result` will provide output tokens, but the current adapter will not confirm USD, internal model turns, input/cache, or the actual response model ID. Task success and telemetry completeness are checked separately.

## Preparation

You need Node.js ≥22, Bash, Git, Docker, and Gemini API access. Run the coordinator as a regular user from the lab root. Perform your own smoke tests for a separate Linux x64 machine: the repository's saved verification on 2026-09-20 concerned Linux arm64. ROCm/Vulkan are not involved here; the provider serves the model.

Read the [adapter README](../../experiments/antigravity-cli/README.md), [profile](../../experiments/antigravity-cli/harness.json), [protocol](../method.md), `agents/a2-janitor/spec.md`, and the public [T002 contract](../../tasks/T002-repo-janitor/task.md). Do not read `tasks/*/check/` or modify the task contract or sealed inputs.

Execute blocks sequentially in Bash; investigate an error before proceeding. Creating a report does not create an experimental run:

```bash
npm run lab:new -- --lab LAB14 --session my-session
LAB_DIR='experiments/antigravity-cli/measurements/LAB14-my-session'
HARNESS_VERSION='1.2.7'
IMAGE_REF='harness-lab/antigravity-cli:1.2.7'
PROVIDER_ID='google'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Before the API call, record the hypothesis, T002 limits, timeout **900 s**, `budget-mode=observed`, one main attempt, and the independent evaluator's name in the report. `.env` requires only **`GEMINI_API_KEY`** from the selected profile; do not print its value, copy it into the report, or pass it through `docker --env-file`. The coordinator reads `.env` itself. `settings.json` specifies `modelProvider: gemini`; this is Antigravity CLI, not the Gemini CLI package or an interactive Antigravity subscription.

## Procedure

1. **Build the pinned image and gateway.** Building downloads system packages and the official archive but does not call a model. Existing images may be used if their IDs are preserved. The installer verifies SHA-512 against the local version 1.2.7 manifest; do not substitute a `latest` installation.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/antigravity-cli \
     > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Check the CLI without an API or keys.** Preserve version/help output, then run the synthetic adapter tests. There is no repository or `.env` mount and no network access here. `--version` must show 1.2.7; a mismatch requires stopping before the episode.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --env HOME=/tmp --workdir /tmp \
       "$IMAGE_ID" agy "$FLAG" \
       > "$LAB_DIR/raw/agy-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/agy-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/agy-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/antigravity-cli/adapter.test.mjs \
     > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Check every smoke-test exit code and file contents; absence of the second file after `break` means incomplete smoke testing. Find final-aggregate, repeated-`step_update`, incomplete-trace, and unsupported-USD-cap cases in the tests. Explain why Antigravity's `num_turns` is not copied into `loop.turns`: here it counts user requests, not internal model calls.

3. **Pin the model and create T002.** Choose an explicit available ID in your Gemini API account before creating the record. `google/gemini-2.5-pro` is used in the adapter's synthetic test; this does not confirm availability in your account. Replace the placeholder below. The profile permits a `google/` prefix; the adapter passes the CLI the ID without it. Do not use `auto`, `latest`, or `default`.

   ```bash
   MODEL_ID='<explicit available Gemini API model ID>'
   npm run new-run -- --harness antigravity-cli \
     --harness-version "$HARNESS_VERSION" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Copy the returned ID into the report manifest and variable. Only this new record is used below:

   ```bash
   RUN_ID='<ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Confirm that the record became `prepared`. The snapshot pins `settings.json`, the runtime wrapper, and an explicit `google` profile. The runtime creates a temporary HOME and copies Gemini API settings there; host authorization files are not connected. The profile's allowed API domain is `generativelanguage.googleapis.com`.

4. **Execute one real attempt.** Run this command after preparing the key and agreeing on the evaluation protocol; this is the lab's first stage that calls a model.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   `observed` does not enforce the contract's USD cap. `agy` also has no confirmed internal-turn limit; the external timeout supplies the enforced boundary. The adapter uses `--output-format stream-json`, disables slash expansion, explicitly passes `--print-timeout 0`, and bypasses interactive permissions inside Docker. Bypassing permissions is not isolation by itself.

5. **Check state and metric provenance.** Save a summary without credentials:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   Establish from the record and raw trace whether a final `event: result` occurred, which `result.status` was received, and whether valid `usage.output_tokens` exist. Do not sum the cumulative total with `step_update`. `init.model` is a setting; do not replace the current `observed_id=null` with it. `tokens_in`, USD, and model turns remain unknown with reasons. If networking/authorization fails, preserve the rejection; do not expand the allowlist with a wildcard or change the profile after `prepare`. A fix creates a new configuration and run.

6. **Obtain an independent evaluation.** Only `awaiting_review` permits the following sequence. Preserve `aborted` with its reason; without a completed real attempt, the minimum lab remains incomplete. Exit 0 is not `pass`.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Give unchanged results to an external evaluator using the [judging procedure](harness-workflow.md). For T002, they execute the hidden check outside the agent container and fill `result` (`pass`, `fail`, or `partial`), `evaluator`, `check_output` with check version and observations, and optionally `human_notes`. Generated hashes remain unchanged. The task-solving agent does not receive the hidden check. The state remains `awaiting_review` while no evaluator is available.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   After importing the substantive evaluation, expect `completed`; a negative verdict is also a valid lab result. `judge-run` checks integrity but does not make the substantive decision itself. Add actual run IDs and observations to `experiments/antigravity-cli/NOTES.md`; adding a component requires a ledger row in the same change.

7. **Perform the selected extension.** Treat the main episode as a pilot. For a series, create **three new** T002 attempts through steps 3–6, assigning their order beforehand; preserve one image ID/model/provider/timeout/budget policy. Do not replace started failures with successful retries.

   ```bash
   SERIES_RUN_IDS='<three new run IDs separated by commas without spaces>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   For T001, create a new record and prepare it using one discovery-run archive containing page bodies/statuses and a shared date. If no archive exists, first perform separate live discovery using the [shared procedure](harness-workflow.md); exclude it from the controlled replay series.

   ```bash
   SOURCE_ARCHIVE='<path to recorded discovery run trace/sources.jsonl>'
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run new-run -- --harness antigravity-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<new T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Execute with step 4 and evaluate with step 6, but T001 uses `rubric` and its designated checking script. For T003, run separately:

   ```bash
   npm run new-run -- --harness antigravity-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Repeat execution and external evaluation with `rubric`. T003 contains the selected harness's configuration, so its results across harnesses do not have identical inputs. For ablation, repeat T002 creation from step 3 with a new ID and prepare `--variant without-spec`, then perform steps 4–6. Full effect testing requires three baseline and three without-spec attempts under [LAB10](LAB10-ablation.md); Docker, gateway, and hidden check remain unchanged.

## Results tables

Fill in conditions before calling the API and results after observation. A dash means an empty field, not zero.

| Run ID | Variant/task | CLI version / image ID | Requested model / provider | Status | Independent verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Metric | Value | Unit | Observation or reason for `null` | Trace/record source |
| --- | --- | --- | --- | --- |
| Output tokens | — | tokens | — | — |
| Input/cache tokens | — | tokens | — | — |
| Internal turns | — | turns | — | — |
| Cost | — | USD | — | — |
| Time | — | s | — | — |
| Response model | — | ID | — | — |

| Check | Expectation set before execution | Actual observation | Evidence / limitation |
| --- | --- | --- | --- |
| Offline version/help | 1.2.7, no network or key | — | — |
| Final stream-json | Last valid result | — | — |
| Autonomous T002 | Result for external evaluation | — | — |

## Deliverables

- LAB14 manifest and report with the hypothesis, predefined conditions, completed tables, and answers to questions.
- Build/version/help/test evidence, image IDs, and architecture information; these are separate infrastructure results.
- Actual `results/runs/<run-id>/run.json`, inputs/trace/artifacts archive, and independent evaluation; for T002, also reference `trace/change.patch`.
- Compare JSON for explicitly selected IDs, NOTES, and a ledger update if components changed. Include neither `.env` nor key values.

## Completion criteria

- [ ] Version and architecture confirmed by your own offline smoke tests; unit tests pass.
- [ ] At least one real T002 completed the full lifecycle to `completed` with an independent verdict; all other attempts are also listed.
- [ ] Google API profile, requested model, immutable images, timeout 900 s, and observed budget preserved.
- [ ] Unknown input/cache, model turns, USD, and observed model not replaced by invented values.
- [ ] Aggregate double-counting excluded, container boundaries preserved, and `npm run check` passes.
- [ ] The report distinguishes smoke tests, CLI execution, and substantive task success; extensions are marked executed only with evidence.

## Review questions

1. How does Antigravity CLI with `modelProvider: gemini` differ from Gemini CLI and subscription login?
2. Why does `init.model` not confirm the underlying response model?
3. How does this trace's `num_turns` differ from model turns in other harnesses?
4. What happens to output tokens if `step_update` and the final aggregate are summed?
5. Which limits actually apply with `--print-timeout 0` and `--budget-mode observed`?
6. Can the lab be submitted with an independent `fail`, and why does that differ from unevaluated `aborted`?

## Sources

- [Adapter README and limitations](../../experiments/antigravity-cli/README.md), [NOTES](../../experiments/antigravity-cli/NOTES.md), [offline evidence from 2026-09-20](../../experiments/antigravity-cli/smoke/2026-09-20.json).
- [Profile](../../experiments/antigravity-cli/harness.json), [adapter](../../experiments/antigravity-cli/adapter.mjs), [tests](../../experiments/antigravity-cli/adapter.test.mjs), [runtime](../../experiments/antigravity-cli/run-cli.mjs), [release manifest](../../experiments/antigravity-cli/releases/1.2.7.json), [Dockerfile](../../experiments/antigravity-cli/Dockerfile).
- [Protocol](../method.md), [shared workflow](harness-workflow.md), [ledger L010](../harness-ledger.md), [LAB09](LAB09-agent-campaign.md), [LAB10](LAB10-ablation.md).
- Primary links pinned in the repository's research on 2026-09-20: [installation](https://antigravity.google/docs/cli/install/), [headless protocol](https://antigravity.google/docs/cli/headless/). This lab's properties are tied to the locally pinned version 1.2.7.
