# LAB16. mini-SWE-agent: a minimal native loop and the cost of observability

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | Completed [LAB01](LAB01-reproducibility.md) |
| Harness | `mini-swe-agent`, `mode=sdk`; `mini-swe-agent==2.4.6`, Python `3.12.12`, Node.js `24.13.1` |
| Minimum | Build, offline smoke test, native trajectory analysis, and one real A2/T002 with independent evaluation |
| Time | Estimate: 2–4 operator hours plus build/judging; agent execution ≤900 s |
| Conditions | Cloud `anthropic` or `openai`, exact model ID, `baseline`, USD `observed` |
| Extensions | Three preassigned repetitions, T001 replay, T003 audit, paired spec ablation |
| Initial state | Experiment `not-run`; lab manifest after creation `not-started` |

## Objective

Study how the native `DefaultAgent` with `LitellmModel`, `LocalEnvironment`, and built-in `mini.yaml` executes the shared contract. Check trajectory completeness and show why the native step limit, API-attempt count, and cost cannot be combined into one universal counter.

## Hypothesis

The native mini-SWE-agent workflow and shared A2 specification are sufficient for T002, without additional fixing rules or a custom coordinator loop. The criterion is independent evaluation of one recorded attempt and a list of components actually involved. `LimitsExceeded` is a reason to evaluate the resulting artifact, not automatically declare success or an infrastructure error.

Measurement requirement to test: `model_stats.api_calls` reflects the number of attempts, including failed ones; tokens and cost are published as totals only when usage is present for all those calls. An incomplete trajectory must not become an inexpensive successful run.

## Preparation

From the repository root as a regular user with Node.js ≥22 and Docker Engine, create a report. Choose the provider and exact available model before preparing the episode:

```bash
npm run lab:new -- --lab LAB16 --session my-session
LAB_DIR='experiments/mini-swe-agent/measurements/LAB16-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<exact available ID of the selected provider>'
IMAGE_TAG='harness-lab/mini-swe-agent:2.4.6'
```

For OpenAI, set `PROVIDER_ID='openai'`. Replace the model placeholder; do not use floating aliases. The CLI requires an ID **without** `anthropic/`/`openai/`: the adapter adds the LiteLLM prefix. The required root `.env` key is `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Do not expose values, save `.env` in raw evidence, or execute it as a shell script. The selected provider's key is in the agent-container environment; the host `.env` file is not mounted, but this does not hide the key from processes inside the container.

Read the [README](../../experiments/mini-swe-agent/README.md), [harness.json](../../experiments/mini-swe-agent/harness.json), [run.py](../../experiments/mini-swe-agent/run.py), [adapter](../../experiments/mini-swe-agent/adapter.mjs), [method](../method.md), and [shared workflow](harness-workflow.md). Connect a local Ryzen model only after separate [LAB08](LAB08-local-bridge.md) acceptance for mini-SWE-agent. This lab uses the already implemented cloud route.

## Procedure

1. **Record the plan before execution.** Record T002/A2, baseline, provider/model, Git revision, and changed-tree status in the report. T002's target budget is USD 2, but this profile's `observed` mode does not enforce a hard cap. External timeout 900 s is mandatory. Native `step_limit=30` limits `n_calls`, while `cost_limit=0` disables the built-in after-the-fact cost stop; 0 here does not mean free inference.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/mini-swe-agent/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Proceed only after checking the current stage's exit code and evidence. Unit tests are synthetic and use neither a provider nor hidden checks.

2. **Build the image and run offline smoke tests.** Do not install the SDK on the host: the experiment runs inside the shared Docker container. The main package is pinned; one resulting image ID preserves transitive dependencies for the entire series.

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/mini-swe-agent/Dockerfile experiments/mini-swe-agent > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/mini-swe-agent,dst=/control,readonly" \
     --entrypoint python "$IMAGE_ID" /control/run.py --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint python "$IMAGE_ID" -c \
     "from importlib.metadata import version; print(version('mini-swe-agent'))" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Expected metadata is `2.4.6`. The smoke test constructs the real agent/model/environment and checks `printf sdk-ready` through `LocalEnvironment`; it calls neither `agent.run()` nor the model. Record actual output and status. Smoke success does not confirm model-ID availability, LiteLLM pricing, or T002 execution.

3. **Examine the native workflow components.** In `run.py`, find loading of `mini.yaml`, overrides of `step_limit`, `cost_limit`, and `output_path`, creation of `LitellmModel`/`LocalEnvironment`, and the `agent.run()` call. The `TracedAgent` subclass changes only `add_messages` to preserve events. State in the report who chooses commands, handles format errors, and ends the task: these actions remain in the native `DefaultAgent`, not a separate lab agent.

   Find the adapter's rejection of hard USD. Explain why a built-in check after expenditure is not a hard budget before a call. `LITELLM_LOCAL_MODEL_COST_MAP=True` uses the installed package's built-in pricing table; missing pricing may cause an upstream error. Record this limitation rather than replacing price with zero or substituting a model to obtain a successful row.

4. **Create a fresh record and seal inputs.** Do not reuse a run ID from LAB01 or another run:

   ```bash
   npm run new-run -- --harness mini-swe-agent --harness-version 2.4.6 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Check `prepared`, seed commit, selected provider, and API domains in `inputs/control/harness.json`/network policy. The container does not receive the original lab repository, its run records, or hidden checks. Do not modify the task contract or open `tasks/*/check/` while solving it. The snapshot must not be edited after preparation; changed conditions require a new record.

5. **Run T002 and record the state.** Only this stage calls a real provider:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   A possible `Submitted` means native completion, while `LimitsExceeded` means stopping at a limit; neither replaces an independent verdict. Provider errors, timeout, or identity violations produce `aborted`. Do not overwrite it with a successful retry; every repeated execution gets a new ID.

6. **Analyze the trajectory and accounting completeness.** Obtain a short summary without duplicating entire message texts:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/mini-trajectory-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const trajectory = events.findLast(e => e?.type === 'lab_mini_result')?.trajectory;
   const responses = (trajectory?.messages ?? []).filter(m => m.role === 'assistant').map(m => m.extra?.response);
   console.log(JSON.stringify({ mini_message_events:events.filter(e => e?.type === 'mini_message').length,
     has_final:!!trajectory, exit_status:trajectory?.info?.exit_status ?? null,
     model_stats:trajectory?.info?.model_stats ?? null, assistant_responses:responses.length,
     responses:responses.map(r => ({ model:r?.model ?? null, usage:r?.usage ?? null })) }, null, 2));
   NODE
   ```

   Compare the number of response entries with `api_calls`; this is a usage-completeness condition, not a reason to hide failed calls. Sum `prompt_tokens`/`completion_tokens` only with complete coverage of attempts. `instance_cost` is a LiteLLM estimate. If the total is missing, record `null` and `metrics_unavailable`. `response.model` supplies observed identity; compare it with the requested ID, accounting for the added provider prefix. Multiple models or a mismatch require separate investigation. Do not count `mini_message` as additional expenditure independent of the final trajectory.

7. **Hand T002 to an independent evaluator.** For `awaiting_review`, create a JSON template:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Following the [shared workflow](harness-workflow.md), the evaluator performs the T002 hidden check outside the agent container, preserves manifests, and fills `result`, `evaluator`, and `check_output`. Apply the evaluation only after receiving the substantive decision:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

   `judge-run` links the evaluation to evidence hashes; it does not perform substantive judging in place of the evaluator. Without an evaluator, the record remains `awaiting_review`; without completed evidence, the lab remains incomplete.

8. **Complete the report and plan an extension.** Record run IDs, native events, unknown metrics, and limitations in the manifest, report, and [NOTES](../../experiments/mini-swe-agent/NOTES.md). Extending to three repetitions requires preassigned new slots and one image ID. For T001, use a frozen archive; for T003, evaluate mini-SWE-agent's own configuration, which differs from other harnesses' inputs. `mini.yaml` contains a repository-fixing workflow even for T001/T003: investigate this condition's effect rather than rewriting configuration between attempts while calling it baseline. Follow [LAB10](LAB10-ablation.md) for the paired `without-spec` series and change accounting; T001/T003 commands are in the [shared workflow](harness-workflow.md).

## Results tables

| Condition/check | Plan | Measured value | Evidence path |
| --- | --- | --- | --- |
| Package / image IDs | 2.4.6 / agent and gateway | — | — |
| Offline environment smoke | Shell without a model call | — | — |
| Native limit / USD | `step_limit=30` / observed | — | — |
| API calls / responses with usage | Complete coverage or reason for absence | — | — |
| Model identity | Requested and response separately | — | — |

| Slot | Run ID | Native exit status | API calls | Tokens in / out | USD / source | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Component | Role in episode | Evidence | Testable by removal |
| --- | --- | --- | --- |
| `DefaultAgent` and `mini.yaml` | — | — | — |
| `LocalEnvironment` | — | — | — |
| Traced `add_messages` | — | — | — |
| LiteLLM cost map | — | — | — |

All measurement cells remain empty before execution. `not-run` is not a valid substitute for a `run.json` verdict.

## Deliverables

Completed report/manifest/tables, adapter-test and offline-smoke output, versions and image IDs, final-trajectory analysis, references to complete archives of every started attempt, and independent evaluation of at least one T002. Explain unknown metrics, the native workflow used, and the USD-policy deviation. Do not copy secrets or present model output as the judge's conclusion.

## Completion criteria

- [ ] Versions, exact provider/model, image, and all conditions recorded before execution.
- [ ] Offline adapter tests and native environment smoke tests performed.
- [ ] One real T002 has `completed` and an independent `pass`, `fail`, or `partial`; all `aborted` attempts preserved.
- [ ] Native step/API counters, usage completeness, model identity, and LiteLLM pricing analyzed.
- [ ] Role of `mini.yaml` demonstrated, NOTES and answers completed, and `npm run check` passes.

Completion requires an evaluated experiment, not necessarily `pass`. Unavailable model/pricing/judge is recorded as the reason for a `blocked` lab report, preserving completed steps rather than inventing completion.

## Review questions

1. How do `step_limit`, `model_stats.api_calls`, and message count differ?
2. Why does a post-expenditure `cost_limit` not enforce a hard USD cap?
3. What does `cost_limit=0` mean in this adapter build?
4. Why does one failed call's missing usage prevent calling the sum of other calls complete?
5. What information does `response.model` add to the requested ID?
6. How can the `mini.yaml` workflow affect T001/T003, and why must this not be hidden in a comparison?

## Sources

Pinned project files: [mini-SWE-agent README](../../experiments/mini-swe-agent/README.md), [Dockerfile](../../experiments/mini-swe-agent/Dockerfile), [harness.json](../../experiments/mini-swe-agent/harness.json), [runtime](../../experiments/mini-swe-agent/run.py), [adapter](../../experiments/mini-swe-agent/adapter.mjs), [adapter tests](../../experiments/mini-swe-agent/adapter.test.mjs), [method](../method.md), [ledger L012](../harness-ledger.md), and [container boundaries](../../experiments/common/README.md). Account/model availability and complete actual usage remain `unverified` until a recorded run; this lab does not update the pinned SDK.
