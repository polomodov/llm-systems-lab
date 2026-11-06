# LAB13. Codex CLI: autonomous exec and observability boundaries

## Profile

| Field | Value |
| --- | --- |
| Harness | `codex`, CLI `@openai/codex@0.155.1`, `codex exec --json` mode |
| Prerequisite | [LAB01](LAB01-reproducibility.md); Node.js ≥22, Git, Bash, Docker Engine; regular coordinator user |
| Main route | OpenAI API, `CODEX_API_KEY` from `.env`; no local provider bridge |
| Minimum scope | Parser/command tests, offline image smoke test, one A2/T002 baseline with an independent judge |
| Extensions | Three repetitions, `without-spec`, T001 frozen replay, T003 configuration audit |
| Time | Estimate: 2–3 operator hours plus build/judging; individual execution timeout 900 s |
| Readiness | CLI `0.155.1` passed offline installation verification on 2026-09-20 on Linux/arm64; your smoke tests and real episode remain `not-run` until performed |

## Objective

Run the independent A2 agent through Codex CLI in a controlled container, obtain an external evaluation of the fix, and explain the separation of internal CLI settings, external isolation, and final accounting. Check why a user `turn` is not the number of internal model turns and why a correct model argument does not confirm the provider response ID.

## Hypothesis

Codex `0.155.1` with an explicit available OpenAI model ID, disabled external settings, and a baseline prompt can prepare a T002 result for independent checking. A correctly completed JSONL stream reports usage but does not provide sufficient evidence to populate USD, internal turns, or observed model ID.

Record task-success criteria separately from accounting-correctness criteria before execution. Nonzero tokens do not prove substantive success, and unknown cost does not mean free execution.

## Preparation

Run commands from the lab repository root. Choose `my-session` once; a new report needs a new name. Replace all angle-bracketed placeholders below before execution. On a nonzero exit code, preserve the error and stop dependent steps: an existing old image or file does not prove that the current command succeeded.

```bash
npm run lab:new -- --lab LAB13 --session my-session
LAB_DIR='experiments/codex/measurements/LAB13-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Read [A2](../../agents/a2-janitor/spec.md), [public T002](../../tasks/T002-repo-janitor/task.md), the [profile](../../experiments/codex/harness.json), [adapter](../../experiments/codex/adapter.mjs), [shared infrastructure](../../experiments/common/README.md), and [independent evaluation workflow](harness-workflow.md). Do not open `tasks/*/check/` or modify task contracts. Arrange the external evaluator and `hidden-check` method before execution.

Prepare specifically `CODEX_API_KEY` in `.env`. Other harnesses use `OPENAI_API_KEY`; it does not replace this profile's credential. If `.env` is absent, create it from `.env.example`; do not overwrite an existing file. Do not print the key in the terminal/report or run `source .env`: the coordinator parses it. Home-directory `auth.json`, settings, and sessions are not mounted; access in the host Codex application does not confirm API access inside the lab container.

Choose an exact available OpenAI API model ID and record how availability was confirmed. `latest`, `auto`, and `default` are unsuitable. The profile does not catalog models available to the account: a valid CLI string does not prove access or observed identity. This adapter supports only provider `openai` and API domain `api.openai.com`.

## Procedure

1. **Check the adapter without an API.**

   ```bash
   node --test experiments/codex/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Record the exit code. Explain five test scenarios: literal prompt as one argv element; rejection of unsupported provider/USD/turn caps; `input_tokens` already including cached input; malformed/failed trace not yielding complete usage; and valid explicit zero usage. These fixtures are not T002 episodes.

2. **Build and pin the CLI.** Building and fetching the proxy image require network access, but version/help run without network or keys. Do not update the package during the series.

   ```bash
   docker build --build-arg HARNESS_VERSION=0.155.1 \
     -t harness-lab/codex:0.155.1 \
     -f experiments/codex/Dockerfile experiments/codex \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/codex:0.155.1)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" codex --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" codex exec --help > "$LAB_DIR/raw/exec-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Verify `0.155.1`, architecture, image ID, and proxy ID. The historical [smoke test](../../experiments/codex/smoke/2026-09-20.json) illustrates evidence structure, not a result from your machine. A fresh build may receive another ID because of the base image/system packages; freeze one image for all repetitions.

3. **Examine the actual Codex command.** Fill in the settings/boundaries table from the adapter and saved help. Pinned settings are `exec --json`, explicit model, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--skip-git-repo-check`, `approval_policy="never"`, `web_search="disabled"`, and `agents.enabled=false`. Sources/smoke tests confirm that a flag exists and is passed; record behavior in the real episode separately.

   The internal sandbox runs in `danger-full-access`. In this lab, the external Docker container and gateway enforce file/process/network boundaries; lacking an internal sandbox does not expose the host rootfs to the agent. Do not run the adapter-generated command directly on the host workspace. User credentials/config/rules are not inherited; the coordinator prompt supplies the A2 specification.

   The current adapter supports no native turn cap or USD cap. With `observed`, the runner passes `turns=null` and `budget=null`; timeout 900 remains enforced. One `turn.completed` may include an internal tool loop, so it cannot be counted as one model turn.

4. **Register a new T002.** Record the model, baseline, image IDs, `observed`, timeout 900, and selected judge in the report manifest. The native CLI does not enforce T002's budget of up to 30 turns or $2 on this route; record the deviation beforehand.

   ```bash
   MODEL_ID='<exact available OpenAI model ID>'
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a2-janitor --task T002 --provider openai --model "$MODEL_ID"
   RUN_ID='<ID printed by new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai
   ```

   Add the returned ID to the report. Check `inputs/manifest.json`: provider openai, harness codex, baseline, seed commit, and allowed inputs. `.env` and hidden checks are absent from the snapshot. Do not manually edit sealed files or the workspace after prepare.

5. **Execute the cloud episode.** It spends funds from the selected API account; this adapter does not cap USD.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider openai --timeout 900 --budget-mode observed
   ```

   Check `run.json`, `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch`, and `artifacts/report.md`. If the state is `aborted`, record the reason; a retry gets a new ID. If it is `awaiting_review`, proceed to external evaluation. Tokens, exit 0, or “done” text do not replace a verdict.

6. **Check usage and stream completeness.** Find `thread.started`, `turn.started`, the terminal event, and `turn.completed.usage`. Compare `input_tokens`/`output_tokens` with `loop.tokens_in`/`loop.tokens_out`. `cached_input_tokens` is part of input, not an additional term. If the final JSONL section is truncated or termination is erroneous, the parser must not declare usage complete.

   Separately explain `loop.turns=null`, `loop.cost_usd=null`, and `model.observed_id=null`. `thread_id` identifies the CLI session, not the underlying model. The requested model is recorded, but the stream does not confirm the provider response's ID. Preserve reasons in `metrics_unavailable`; do not manually populate fields from assumptions or another run's cost.

7. **Conduct independent judging.** Only for `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The external evaluator applies the T002 hidden check using the [procedure](harness-workflow.md), filling `result`, `evaluator`, `check_output`, and optional notes; generated hashes remain unchanged. Agent results remain unchanged. Then:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `completed` may have `pass`, `fail`, or `partial`: all three are measurement results. Judge does not automatically create a substantive verdict or turn aborted into completed. Without an external evaluator, the work remains `awaiting_review` and does not meet the minimum.

8. **Extension: three repetitions and prompt ablation.** Before the series, assign three baseline and three without-spec attempts, preserving provider/model/image/proxy/timeout and inputs. Alternate variants, creating a new run from step 4 for each. For without-spec, replace baseline prepare with:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider openai
   ```

   Perform steps 5–7 for every assigned attempt. The minimum T002 serves as a pilot and admission to LAB09; comparison baseline/without-spec triples always contain new attempts. Do not replace aborted attempts with successful retries. Compare all IDs:

   ```bash
   SERIES_RUN_IDS='<all assigned run IDs separated by commas>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   Show outcomes, time, and token completeness; cost and internal turns remain unknown. `--ignore-rules` applies to both variants; without-spec removes A2 text from the coordinator prompt, not the external Docker boundary. See [LAB10](LAB10-ablation.md) for details.

9. **Extension: sources and audit.** Create discovery T001 separately:

   ```bash
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a1-dossier --task T001 --provider openai --model "$MODEL_ID"
   RUN_ID='<new discovery ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai --as-of "$AS_OF_DATE"
   ```

   Perform steps 5–7 with `rubric`; the evaluator also applies T001's designated source check. Codex's built-in web search remains disabled; tools and the lab gateway provide access to allowed sources. Preserve `trace/sources.jsonl` with URLs, bodies, and statuses. Create a new T001 with the same `new-run` command, assign its new ID, and prepare replay:

   ```bash
   SOURCE_ARCHIVE='<path to discovery run trace/sources.jsonl>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Perform steps 5–7; all controlled T001 attempts use one archive and date, with discovery accounted for separately. For T003:

   ```bash
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a3-ledger-auditor --task T003 --provider openai --model "$MODEL_ID"
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai
   ```

   Obtain `ledger.md`, `ablation-plan.md`, and an external rubric evaluation through steps 5–7. Distinguish the adapter's actual command from broader Codex capabilities. T003 configuration inputs differ across harnesses and require separate interpretation.

10. **Conclude about the deployment.** Record IDs, conditions, successes/errors, and unknown metrics in `experiments/codex/NOTES.md`. Installation smoke tests, parser tests, and real tasks are different evidence. A new component needs a ledger row; the existing adapter is L009 in the [ledger](../harness-ledger.md). Do not retroactively add restored user rules or other capabilities to the baseline.

## Results tables

| Setting | Actual value/argv | Layer: CLI or Docker/gateway | Evidence | Limitation |
| --- | --- | --- | --- | --- |
| Model, rules/config, sandbox, approvals, web, agents, timeout | Fill in | Fill in | Source + your smoke/run | Fill in |

| Slot before execution | Task/variant | Run ID | Status/verdict | Terminal event | Wall-clock, s |
| --- | --- | --- | --- | --- | --- |
| Fill in | T002/baseline | After new-run | After run/judge | From trace | From record |

| Metric | Value or `null` | Definition | Evidence | Reason for absence |
| --- | --- | --- | --- | --- |
| Input/cache/output, turns, USD, model identity | After execution | No double-counted cache | Record field/event | Fill in |

| Extension | IDs of all assigned attempts | Outcomes | Changed condition | Limit of the conclusion |
| --- | --- | --- | --- | --- |
| Triples/without-spec/replay/T003 | If executed | All outcomes | Fill in | Fill in |

## Deliverables

- Manifest and report with a pre-run hypothesis, tables, all run IDs, and answers to questions.
- Parser tests, build/version/help evidence, immutable image/proxy IDs, and architecture.
- At least one real independently evaluated T002: patch, report, raw trace, and evaluation with unchanged manifests; previous failures are not hidden.
- Explanation of the external boundary and unknown USD/turns/model identity, NOTES entry; extension results only if executed.

## Completion criteria

- [ ] CLI `0.155.1` and immutable IDs verified in your environment; parser tests pass.
- [ ] Interaction of `danger-full-access` with the external container and disabled user rules/config explained.
- [ ] One T002 has `completed` and an independent `pass`, `fail`, or `partial`; aborted/awaiting_review are not called a completed minimum.
- [ ] Main run used `observed`, timeout 900; absence of native USD/turn caps explicitly stated.
- [ ] Cache not double-counted, `turn.completed` not called an internal-turn count, requested ID distinguished from observed.
- [ ] All attempts preserved, no secrets/hidden checks/manual result correction; `npm run check` passes.

## Review questions

1. Why can `CODEX_API_KEY` not be replaced with another OpenAI adapter's variable without changing the profile?
2. Why does `danger-full-access` in this experiment not mean full host access?
3. How does `turn.completed` differ from the complete model-turn count?
4. How would double-counting cached input distort the comparison?
5. Why are `thread_id` and requested model insufficient for an observed model ID?
6. Which limits remain with `observed`, and which are absent?
7. What exactly does without-spec remove when user rules are already disabled?
8. How does T001 obtain sources with built-in web search disabled?

## Sources

- [Codex README](../../experiments/codex/README.md), [profile](../../experiments/codex/harness.json), [adapter](../../experiments/codex/adapter.mjs), [tests](../../experiments/codex/adapter.test.mjs), [Dockerfile](../../experiments/codex/Dockerfile), [historical offline smoke test](../../experiments/codex/smoke/2026-09-20.json).
- [Protocol](../method.md), [external infrastructure](../../experiments/common/README.md), [independent judge](harness-workflow.md), [LAB10](LAB10-ablation.md).
- Commands come from the pinned `0.155.1` adapter, not the current Codex application's capabilities; confirm selected API-model availability when performing the lab.
