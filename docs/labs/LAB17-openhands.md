# LAB17. OpenHands SDK: Conversation, native tools, and independent evaluation

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | Completed [LAB01](LAB01-reproducibility.md) |
| Harness | `openhands`, `mode=sdk`; `openhands-sdk==1.49.2`, `openhands-tools==1.49.2` |
| Environment | Python `3.12.12`, Node.js `24.13.1`; native terminal with tmux in the shared Docker container |
| Minimum | Build, native offline smoke test, event/metric analysis, one real A2/T002 with an independent judge |
| Time | Estimate: 2–4 operator hours plus build/judge; agent execution ≤900 s |
| Conditions | Cloud `anthropic` or `openai`, exact model ID, baseline, USD observed |
| Extensions | Three preassigned repetitions, T001 replay, T003, and spec ablation |
| Initial state | Experiment `not-run`; lab manifest `not-started` |

## Objective

Run an episode through OpenHands' native `Agent` and `Conversation.run()` with native terminal/file editor, and study the boundary between a Conversation iteration, a completed LLM response, and external timeout. Obtain a verified task result in the shared lab environment while preserving the SDK's own loop.

## Hypothesis

An OpenHands configuration with native `TerminalTool`/`FileEditorTool` and the shared A2 specification can perform T002 without a browser, MCP, delegation, or separate runtime server. Test with an independent `pass`/`fail`/`partial` for one real attempt, preserved tool events, and a list of any additional components needed. This concerns the given episode, not universal sufficiency of the tool set.

Measurement requirement: `turns` reflects completed LLM responses from complete `token_usages`; `max_iteration_per_run` and tool-call count do not substitute for this metric. Configured SDK model fields do not count as observed provider identity.

## Preparation

Run commands from the repository root as a regular user with Node.js ≥22 and Docker Engine. Create the report before execution:

```bash
npm run lab:new -- --lab LAB17 --session my-session
LAB_DIR='experiments/openhands/measurements/LAB17-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<exact available ID of the selected provider>'
IMAGE_TAG='harness-lab/openhands:1.49.2'
```

For OpenAI, change provider to `openai` before creating the record. Replace the placeholder with an exact available model ID, not `latest` or a floating alias. Do not add a provider prefix to `--model`: the adapter passes `anthropic/<ID>` or `openai/<ID>` to the SDK itself. The root `.env` must contain the appropriate `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`; key values do not belong in commands or reports. `.env` is not mounted, but the selected provider's credential is available to processes inside the agent container, a known boundary of the shared infrastructure.

Read the [OpenHands README](../../experiments/openhands/README.md), [profile](../../experiments/openhands/harness.json), [runtime](../../experiments/openhands/run.py), [adapter](../../experiments/openhands/adapter.mjs), [method](../method.md), and [shared evaluation workflow](harness-workflow.md). This lab studies **SDK 1.49.2**; the legacy CLI/runtime image is another deployment. A local Ryzen provider still requires implementation and acceptance of [LAB08](LAB08-local-bridge.md); the cloud minimum already uses an existing route.

## Procedure

1. **Preserve the conditions.** Record T002/A2, baseline variant, provider/model, and working-tree revision. The T002 target is USD 2, but the SDK profile uses `observed` because no hard USD cap is implemented. Record native `max_iteration_per_run=30` separately from external timeout 900 s; iterations do not promise to limit provider HTTP retries.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/openhands/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Start each phase only after checking the previous phase's exit code. These adapter tests are synthetic: they contain no real API calls or hidden checks.

2. **Build the SDK profile and check the native terminal without a model.** Record both image IDs; identical tags after rebuilding do not guarantee identical transitive dependencies.

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/openhands/Dockerfile experiments/openhands > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/openhands,dst=/control,readonly" \
     --entrypoint python "$IMAGE_ID" /control/run.py --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint python "$IMAGE_ID" -c \
     "from importlib.metadata import version; print('sdk='+version('openhands-sdk')); print('tools='+version('openhands-tools'))" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Both versions should be `1.49.2`. The smoke test creates a Conversation, sends a local user event for initialization, and calls the native terminal with `printf sdk-ready`; neither `conversation.run()` nor the model is called. It checks terminal operation and tool initialization with `/tmp noexec`. This profile requires neither a separate executable cache nor a second OpenHands container. Record the actual result in the table, not the expected text.

3. **Diagram execution.** From `run.py`, show `LLM → Agent(native tools) → Conversation → send_message → run → callback/final metrics`. Identify where workspace, iteration limit, and `persistence_dir=None` are set. The workspace operates inside the shared container; Docker socket, host home, and hidden checks are not passed into it. The coordinator saves events in the host trace; temporary tool caches remain in `/tmp`.

   List the explicitly connected `TerminalTool`/`FileEditorTool` in the report; the SDK adds standard Finish/Think tools. Browser, MCP, delegation, and condenser are not added to this profile. Note tmux's role and differences from the legacy OpenHands server environment. Do not attribute absent functions to the adapter based on the product name alone.

4. **Create a new T002 record and seal inputs.** Copy the actual returned run ID into the report:

   ```bash
   npm run new-run -- --harness openhands --harness-version 1.49.2 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Check `prepared`, seed commit, selected profile/provider, and network policy. Do not change inputs, model/provider, or the task contract after preparation. The solving agent does not read `tasks/*/check/`; a separate party evaluates later. Any configuration change means preparing again with a new run ID.

5. **Run a real Conversation and check the lifecycle.** API calls begin at this step:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   Native `MaxIterationsReached` is preserved as a limit stop; it does not imply fix success and is not identical to timeout. Normal completion leads to `awaiting_review`; provider/infrastructure errors lead to `aborted`. Do not repeat `run` on the same record or manually change `aborted` to a successful state.

6. **Analyze events and metrics.** The summary extracts only necessary final fields from the saved trace:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/openhands-metrics-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const final = events.findLast(e => e?.type === 'lab_openhands_result');
   console.log(JSON.stringify({ native_events:events.filter(e => e?.type === 'openhands_event').length,
     stopReason:final?.stopReason ?? null, sessionId:final?.sessionId ?? null, error:final?.error ?? null,
     token_usages:final?.metrics?.token_usages ?? null, costs:final?.metrics?.costs ?? null,
     accumulated_cost:final?.metrics?.accumulated_cost ?? null }, null, 2));
   NODE
   ```

   Compare `openhands_event` with native terminal/file-editor calls and final `lab_openhands_result`. The completed-response count `token_usages.length`, for a complete successful set, defines reported turns; it is neither tool count nor the Conversation limit. Tokens are sums of `prompt_tokens`/`completion_tokens`. Price is reported only with a complete set of positive costs and valid `accumulated_cost`; missing price is not zero. If final contains `error` or metrics are incomplete, aggregate usage remains unknown with a reason.

   Record `model.observed_id=null`: the SDK populates model fields from the request, so they do not prove actual response identity. `sessionId` connects Conversation events but does not identify the model. Report the proportion of confirmed model IDs separately in comparisons; do not present request-only identity as observed model pinning.

7. **Obtain an independent evaluation.** Create a clean template only for `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Following the [shared workflow](harness-workflow.md), the external evaluator performs the T002 hidden check and fills `result`, `evaluator`, and `check_output`, preserving manifests/hashes. Do not run the next command before this decision. The agent answer and `finished` state are not independent verdicts.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

   `judge-run` verifies the evaluation's link to unchanged artifacts; the evaluator makes the substantive decision. Without them the record remains `awaiting_review`. An evaluated `fail`/`partial` is a valid lab result; a startup failure alone does not meet the minimum.

8. **Submit the analysis and extend the series if needed.** Record all run IDs in the report/manifest and [NOTES](../../experiments/openhands/NOTES.md). To study stability, preassign three new repetitions with unchanged models, images, and conditions. T001 requires one frozen source archive; T003 receives an OpenHands-specific snapshot and is analyzed as diagnostics of its own inputs. Compare `without-spec` in a paired series under [LAB10](LAB10-ablation.md), preserving Docker/gateway and native tool boundaries. Additional-task commands are in the [shared workflow](harness-workflow.md). Adding condenser/browser/delegation creates a separate changed configuration with a ledger entry, not a continuation of the original baseline under the same name.

## Results tables

| Check | Plan | Actual observation | Evidence path |
| --- | --- | --- | --- |
| SDK/tools versions | 1.49.2 / 1.49.2 | — | — |
| Agent/gateway images | Immutable IDs | — | — |
| Offline Conversation/tools | Native terminal without `run()` | — | — |
| Iteration / time / USD | 30 / 900 s / observed | — | — |
| Identity | Exact request; observed separately | — | — |

| Slot | Run ID | Native stop reason | Completed responses | Tokens in / out | USD / source | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Mechanism | What was observed | How this differs from reported turns | Evidence path |
| --- | --- | --- | --- |
| Conversation iteration limit | — | — | — |
| Terminal/file editor actions | — | — | — |
| `token_usages` | — | — | — |
| External timeout | — | — | — |

`not-run` here means a slot not yet executed. Do not copy it into `run.json` in place of a valid lifecycle/verdict or populate measurements with expected numbers.

## Deliverables

Report/manifest with a preregistered hypothesis and all run IDs, conditions/metrics tables, build/version/adapter-test/smoke evidence, a Conversation diagram and event analysis, the full archive of at least one evaluated T002, and an independent verdict. Explain request-only identity and all unknown usage/cost. Reflect additional-component changes in NOTES/ledger; exclude `.env` and keys from the submission.

## Completion criteria

- [ ] Both SDK/tools versions, image IDs, exact model/provider, and all limits recorded.
- [ ] Adapter tests and offline Conversation/native-terminal smoke tests performed.
- [ ] At least one real T002 completed with an independent `pass`/`fail`/`partial`; unsuccessful started attempts preserved.
- [ ] Iterations, tool actions, and completed responses distinguished; usage completeness and identity limitations explained.
- [ ] Report, evidence, NOTES, and review answers ready; `npm run check` passes.

If a blocker leaves only `aborted`/`awaiting_review`, record it in a `blocked` report. The educational minimum remains incomplete until a new evaluated attempt or independent judging of the existing result.

## Review questions

1. Why does this lab study an SDK profile rather than every way of running OpenHands?
2. How do iteration limit, tool actions, and `token_usages.length` relate?
3. How does `MaxIterationsReached` differ from timeout and substantive `fail`?
4. Why does `Conversation.send_message` in the offline smoke test not yet imply a model call?
5. What do `sessionId` and configured model fields confirm, and what do they not confirm?
6. Why does adding a condenser or delegation create a new comparison configuration?

## Sources

Pinned project files used: [OpenHands README](../../experiments/openhands/README.md), [Dockerfile](../../experiments/openhands/Dockerfile), [harness.json](../../experiments/openhands/harness.json), [run.py](../../experiments/openhands/run.py), [adapter](../../experiments/openhands/adapter.mjs), [adapter tests](../../experiments/openhands/adapter.test.mjs), [method](../method.md), [ledger L013](../harness-ledger.md), and [shared infrastructure](../../experiments/common/README.md). Specific model-ID availability and episode success remain `unverified` before a real run; version changes require separate revalidation.
