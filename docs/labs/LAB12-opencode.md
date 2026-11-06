# LAB12. OpenCode: configuration layers, steps, and unknown cost

## Profile

| Field | Value |
| --- | --- |
| Harness | `opencode`, CLI v1 `opencode-ai@1.18.29` |
| Prerequisite | [LAB01](LAB01-reproducibility.md), Node.js ≥22, Git, Bash, Docker Engine, unprivileged coordinator user |
| Main route | Anthropic API, `ANTHROPIC_API_KEY` from `.env`; ready cloud adapter, no local bridge |
| Minimum scope | Parser/config tests, build and offline CLI smoke test, one real A2/T002 baseline with an external judge |
| Extensions | Three repetitions, `without-spec`, T001 with a frozen archive, T003, design of verified session export |
| Time | Estimate: 2–3 operator hours plus build/evaluation; execution timeout 900 s |
| Readiness | CLI `1.18.29` passed installation smoke tests on 2026-09-20 on Linux/arm64; actual execution and your measurements remain `not-run` until performed |

## Objective

Execute T002 through the OpenCode build agent and trace how the sealed permissions file combines with runtime configuration for the main and small models and the `steps` limit. Establish which JSONL fields support conclusions about completion and which do not provide reliable final usage.

## Hypothesis

OpenCode `1.18.29` with a fixed Anthropic model ID, build agent, and allowed tools can produce a T002 result ready for evaluation. However, the `step_finish` stream alone does not prove the session's complete cost or model-turn count: missing observability must remain an unknown in the result.

Before execution, define what would falsify the first part of the hypothesis and which observations would resolve the second. Do not equate missing metrics with zero expenditure or failure of the substantive task.

## Preparation

Work from the repository root in one shell session. `my-session` is the chosen report name; use another for a repeated lab. Replace every angle-bracketed value with actual data before execution. On a nonzero exit code, preserve the error and stop dependent steps: an old image tag or file does not confirm success of the current command.

```bash
npm run lab:new -- --lab LAB12 --session my-session
LAB_DIR='experiments/opencode/measurements/LAB12-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Read [A2](../../agents/a2-janitor/spec.md), [public T002](../../tasks/T002-repo-janitor/task.md), the [profile](../../experiments/opencode/harness.json), [opencode.json](../../experiments/opencode/opencode.json), [adapter](../../experiments/opencode/adapter.mjs), and [independent evaluation procedure](harness-workflow.md). Do not open `tasks/*/check/` directories or edit task contracts. Arrange the external judge and `hidden-check` method beforehand.

The selected profile requires only `ANTHROPIC_API_KEY` in `.env`. If `.env` is absent, create it from `.env.example`; if present, edit it without overwriting other data. Do not save the value in the report/command. The orchestrator reads `.env` itself: do not run `source .env` or mount home-directory credentials. Processes inside the agent container receive the selected key; this mechanism's boundary is described in the [common README](../../experiments/common/README.md).

Choose an exact available Anthropic API model ID. The profile does not list models or prove account access; record how access was confirmed without secrets. This lab uses only provider `anthropic`, with allowed API host `api.anthropic.com`. Other providers in upstream OpenCode do not imply support in the current adapter.

## Procedure

1. **Check the parser and command construction without an API.**

   ```bash
   node --test experiments/opencode/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Record the exit code. Explain why an event with `cost: 0` and token counts in a synthetic `step_finish` leaves final fields unknown; why `error` overrides a previous finish; and why a mandatory USD-budget request is rejected. These fixtures create no real `run.json`.

2. **Build the fixed version and check the CLI offline.** The OpenCode Dockerfile runs package postinstall inside the image; do not copy `--ignore-scripts` instructions from another harness. Building and downloading the proxy image require network access; smoke tests receive no credentials.

   ```bash
   docker build --build-arg HARNESS_VERSION=1.18.29 \
     -t harness-lab/opencode:1.18.29 \
     -f experiments/opencode/Dockerfile experiments/opencode \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/opencode:1.18.29)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" opencode --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" opencode run --help > "$LAB_DIR/raw/run-help.txt"
   docker run --rm --network none "$IMAGE_REF" opencode export --help > "$LAB_DIR/raw/export-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Verify `1.18.29`, architecture, and immutable IDs. Saved help must match CLI v1: the export command here is `opencode export`, not an unverified command from another version. Export from a real session is not yet integrated into the runner.

3. **Examine two configuration layers.** Fill the table using current files without modifying them. `OPENCODE_CONFIG` points to `/control/opencode.json`, which sets default deny and allows `read`, `edit`, `glob`, `grep`, `list`, and `bash`. `OPENCODE_CONFIG_CONTENT` additionally sets `model`, `small_model`, and `agent.build.model` to the same `anthropic/<ID>`, while `agent.build.steps` receives the task limit. `OPENCODE_DISABLE_AUTOUPDATE=true` disables auto-update.

   State each layer's purpose: which capability is defined by the permissions file, which by the adapter, and which by Docker/gateway. `steps` asks OpenCode to finish the loop and is not a guaranteed count of complete model requests or a USD cap.

4. **Create and prepare the minimum T002.** Pin baseline, model, image IDs, `observed`, and timeout 900 in the report beforehand. The T002 contract specifies up to 30 turns or $2; here USD is not capped, and native steps are not a universal turn counter. Explicitly identify this research deviation.

   ```bash
   MODEL_ID='<exact available Anthropic model ID>'
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a2-janitor --task T002 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<ID printed by new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Add the ID to the report manifest and check harness/provider/variant/seed commit in `inputs/manifest.json`. The snapshot must not contain `.env` or hidden checks. Do not edit inputs after prepare; a configuration change means a new run.

5. **Execute a real attempt.** The command uses the selected paid API; this adapter has no confirmed hard USD cap.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   Check state and stopping reason in `run.json`. Preserve references to `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch`, and `artifacts/report.md`. `awaiting_review` does not mean pass. For `aborted`, do not fix results or rerun the same ID; add a diagnosis and make any retry a new attempt.

6. **Map OpenCode observability.** Find the session ID, `step_finish`, and errors in raw JSONL; identify the exact events supporting the stopping reason. Verify that `run.json` contains `null` with reasons for turns/cost/input/output, while `model.observed_id` remains unknown. `--model` and runtime config confirm the requested model, but the parser does not confirm the provider response's model.

   Do not manually sum `step_finish` into final run fields. Success in this part means explained limitations, not numbers in every cell. If data are needed for a future improvement, describe a verifiable export from the same session with complete accounting of main and auxiliary requests. A session inside the container is not automatically retained as an accessible host CLI session.

7. **Obtain external evaluation.** Only from `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The external evaluator applies the T002 hidden check using the [shared procedure](harness-workflow.md), filling `result`, `evaluator`, `check_output`, and optional notes without changing hashes or agent results. Then:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `pass`, `fail`, and `partial` are equally valid honestly completed measurements. `aborted` is not imported through judge; without an external evaluator the lab remains incomplete. Preserve all previous failed attempts in `run_ids`.

8. **Extension: repetitions and specification removal.** Preassign three baseline and three `without-spec` attempts with identical model, images, timeout, inputs, and judge; alternate variants. For every slot, run `new-run` from step 4 with a new ID; for without-spec, replace baseline prepare with:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider anthropic
   ```

   This prepares a new record. Perform steps 5–7 for all assigned slots. The minimum T002 serves as a pilot and admission to LAB09; comparison baseline/without-spec triples always contain new attempts. Preserve all started failures, then compare exact IDs:

   ```bash
   SERIES_RUN_IDS='<all assigned run IDs separated by commas>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   Show outcomes, `pass@3`/`pass^3`, and measured time; cost comparison is unavailable with the current parser. `without-spec` does not remove Docker, permissions, or gateway. See [LAB10](LAB10-ablation.md) for detailed interpretation and the ledger.

9. **Extension: T001 discovery/replay and T003.** Create a separate live T001:

   ```bash
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a1-dossier --task T001 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<new discovery ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic --as-of "$AS_OF_DATE"
   ```

   Perform steps 5–7 with `rubric`; T001 also uses the designated source check. The `trace/sources.jsonl` archive must contain bodies, statuses, and URLs. Create a new T001 using the same `new-run`, assign its new ID, and prepare replay:

   ```bash
   SOURCE_ARCHIVE='<path to discovery run trace/sources.jsonl>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Perform steps 5–7; the controlled series uses one archive and date, with discovery marked separately. For an OpenCode audit:

   ```bash
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a3-ledger-auditor --task T003 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   After execution, obtain a rubric evaluation of `ledger.md` and `ablation-plan.md`. T003 receives its own copy of the OpenCode configuration; other harnesses' inputs differ.

10. **State the result and next check.** Record actual IDs, problems, and necessary changes in `experiments/opencode/NOTES.md`. A `null` value alone does not require a new component. If proposing session export, describe a completeness test, a safe path for saving from the same session, and a new ledger component; metrics remain unknown until it is implemented and verified. The original adapter belongs to L008 in the [ledger](../harness-ledger.md).

## Results tables

| Layer/parameter | Source | Actual value | What it guarantees | What remains unverified |
| --- | --- | --- | --- | --- |
| permissions / model / small_model / steps / timeout | File or launch | Fill in | From code and observation | Fill in |

| Slot | Task/variant | Run ID | Status/verdict | Stop event | Wall-clock, s | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Assign before execution | T002/baseline | After new-run | After run/judge | Raw event | From record | Path |

| Metric | Value or `null` | Basis | Reason for absence | Required confirmation |
| --- | --- | --- | --- | --- |
| Model identity / turns / cost / tokens | After execution | Record field + trace | Preserve the exact reason | Do not substitute an assumption |

| Extension | IDs of all slots | Changed factor | Outcomes | Limit of the conclusion |
| --- | --- | --- | --- | --- |
| Triples/without-spec/replay/T003 | If executed | Fill in | All attempts | Fill in |

## Deliverables

- Manifest and report with a pre-run hypothesis, all run IDs, and completed tables.
- Parser tests, build/version/help evidence, image/proxy IDs, and your environment's architecture.
- One real T002 reaching `completed`, original traces, patch, report, and independent evaluation with unchanged hashes; errors separately.
- Configuration-layer and observability map, review-question answers, and NOTES; optional series and session-export plan only if the extension is selected.

## Completion criteria

- [ ] CLI `1.18.29`, parser tests, and image IDs are confirmed on your machine.
- [ ] The distinction between file config, runtime config, and external isolation is defined.
- [ ] Real T002 independently evaluated; verdict not inferred from exit 0.
- [ ] `observed` and timeout 900 used; `steps` described as advisory.
- [ ] Unknown usage/model identity preserved; `step_finish` not presented as complete session accounting.
- [ ] All attempts preserved, no secrets or hidden checks in the report, and `npm run check` passes.

## Review questions

1. Why does the adapter set `model`, `small_model`, and `agent.build.model` together?
2. How does OpenCode `steps` differ from Claude `max-turns` and external timeout?
3. Why does `cost: 0` in one event not make session cost zero?
4. What would need to be proven before safely adding session export to metric accounting?
5. Why is `hard` rejected, and why can `observed` still spend more than $2?
6. Does a requested model ID confirm the provider response's actual model?
7. Which boundary keeps hidden checks inaccessible when `bash` is allowed?

## Sources

- [OpenCode README](../../experiments/opencode/README.md), [profile](../../experiments/opencode/harness.json), [configuration](../../experiments/opencode/opencode.json), [adapter](../../experiments/opencode/adapter.mjs), [tests](../../experiments/opencode/adapter.test.mjs), [Dockerfile](../../experiments/opencode/Dockerfile).
- [Protocol](../method.md), [shared infrastructure](../../experiments/common/README.md), [independent judge](harness-workflow.md), [LAB10](LAB10-ablation.md).
- This lab describes pinned CLI v1 `1.18.29`; commands from another version and upstream capabilities do not count as implemented in this adapter without separate verification.
