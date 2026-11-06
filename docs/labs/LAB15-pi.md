# LAB15. Pi: native SDK loop, events, and reproducible T002

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | Completed [LAB01](LAB01-reproducibility.md) |
| Harness | `pi`, `mode=sdk`; `@mariozechner/pi-coding-agent@0.73.1`, Node.js `24.13.1` |
| Minimum | Build, offline smoke test, event analysis, and one real A2/T002 attempt with an independent judge |
| Time | Estimate: 2–4 operator hours plus build and waiting for a judge; agent execution limited to 900 s |
| Mode | Cloud `anthropic` or `openai`; exact available model ID; `baseline`, USD `observed` |
| Extensions | Three preassigned repetitions, T001 replay, T003, `without-spec` |
| Initial state | Experiment `not-run`; created lab manifest `not-started` |

## Objective

Run a native Pi session on the shared episode and demonstrate from the trace that the adapter preserves the native loop and does not count a message twice. Obtain independent evaluation, distinguishing fix quality from successful SDK startup and metric completeness.

## Hypothesis

With model, image, and inputs pinned, Pi's standard tools and the shared agent spec are sufficient to perform T002 without extra extensions. Testing conditions: one recorded attempt, an independent `pass`/`fail`/`partial`, and a list of tools actually used and unavailable metrics. `fail` refutes the sufficiency of this configuration in this attempt; one `pass` does not establish result stability.

Check accounting separately: `message_end` provides usage for a completed assistant message, and repeating that message in `turn_end` must not increase tokens. The `model` field in Pi events comes from configuration and does not confirm the provider response's model.

## Preparation

Work from the repository root as a regular user with Node.js ≥22 and Docker Engine available. The commands below are assignments to perform; publication of the lab does not mean you have already executed them. Create a report and record conditions before calling a model:

```bash
npm run lab:new -- --lab LAB15 --session my-session
LAB_DIR='experiments/pi/measurements/LAB15-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<exact available ID of the selected provider>'
IMAGE_TAG='harness-lab/pi:0.73.1'
```

Replace `MODEL_ID` with a snapshot available to your account; `latest` or a family name instead of an exact model is unsuitable. For OpenAI, change `PROVIDER_ID` to `openai` **before** `new-run` and preparation. The model argument has no `anthropic/` or `openai/` prefix: the provider is passed separately. Credential names in the root `.env` are `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Do not expose values or copy `.env` into the report. The coordinator passes only the selected profile's key; it is available to processes inside the agent container, which does not fully isolate the secret from the agent's bash tool.

Read the [profile](../../experiments/pi/harness.json), [adapter](../../experiments/pi/adapter.mjs), [runtime](../../experiments/pi/run.mjs), [shared protocol](../method.md), and [independent evaluation workflow](harness-workflow.md). Local connection to Ryzen is a separate extension after implementing and accepting [LAB08](LAB08-local-bridge.md) for Pi. This lab's cloud minimum does not depend on the bridge.

## Procedure

1. **Record the configuration.** Save Git revision, working-tree status, Node/Docker versions, selected provider/model, the T002 USD 2 target, native 30-turn limit, and timeout 900 s. State explicitly in `report.md`: `observed` does not stop expenditure at USD 2; this is a research deviation from the contractual hard cap.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/pi/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Check each step's exit code before proceeding. Tests use synthetic events, not APIs or actual hidden checks.

2. **Build and freeze the image; check the SDK offline.** Building downloads dependencies; the main package is pinned, while the resulting image ID fixes transitive versions. Do not rebuild the image between series repetitions. The shared gateway needs a separate Node.js image:

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/pi/Dockerfile experiments/pi > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/pi,dst=/control,readonly" \
     --entrypoint node "$IMAGE_ID" /control/run.mjs --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint node "$IMAGE_ID" -p \
     "require('/opt/pi/node_modules/@mariozechner/pi-coding-agent/package.json').version" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Expected smoke indication: session and native bash initialized, `printf sdk-ready` executed, no model called. The version must be `0.73.1`; this version's `pi --version` writes to stderr, so package metadata is used. Record the actual result rather than copying the expectation into the observation table.

3. **Examine native-loop boundaries.** Find `createAgentSession`, `session.prompt`, the `turn_end` handler, and `agent.abort()` in `run.mjs`. Diagram “prompt → response → tools → turn_end → continue/abort” in the report. Note that automatic compaction and retry are disabled. The limit applies at Pi's turn boundary; transport HTTP retries are not universal agent turns. User plugins and host home are not loaded. Pi creates the system prompt and tools; the adapter does not implement its own agent loop.

4. **Create and prepare a separate T002.** Save the returned run ID in the report. Do not reuse the prepared teaching record from LAB01:

   ```bash
   npm run new-run -- --harness pi --harness-version 0.73.1 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Confirm `prepared` state and that `inputs/control/harness.json` contains the selected provider, unchanged runtime, and its allowed API domains. Check the manifest and seed commit as in LAB01. Do not edit sealed inputs or open `tasks/*/check/` while solving the episode.

5. **Execute the native session and read the coordinator result.** Only this step calls the model:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   `awaiting_review` means execution ended, not T002 success. Preserve the reason for `aborted`; a new attempt requires a new ID. If the selected snapshot is absent from Pi's catalog, the OpenAI fallback may take transport/context/pricing from a known family while preserving the exact requested snapshot ID; an unknown family produces an error rather than a model substitution. Availability of a specific ID remains `unverified` before the real run.

6. **Check events and arithmetic.** Read only the host trace saved by the coordinator. The summary below prints event types, not complete message text:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/pi-events-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const counts = {};
   for (const e of events) if (typeof e?.type === 'string') counts[e.type] = (counts[e.type] ?? 0) + 1;
   const messages = events.filter(e => e?.type === 'message_end' && e.message?.role === 'assistant');
   console.log(JSON.stringify({ counts, final:events.findLast(e => e?.type === 'lab_pi_result') ?? null,
     assistant_usage:messages.map(e => ({ stopReason:e.message.stopReason, usage:e.message.usage ?? null })) }, null, 2));
   NODE
   ```

   Compare native `turns`/`compactions` with `lab_pi_result`; input tokens are the sum of `input + cacheRead + cacheWrite` for completed assistant `message_end` events; output tokens are `output`. `turn_end` does not add a second usage copy. Cost is an SDK estimate; preserve `null` and a reason for incomplete usage/truncated traces. `model.observed_id=null` is correct here even when `message.model` exists: a field populated from the request is not an observation of the response.

7. **Obtain an independent verdict.** For `awaiting_review`, generate a template and pass it to the evaluator with unchanged artifacts and manifests, following the [shared workflow](harness-workflow.md):

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The evaluator performs the T002 hidden check outside the agent container, filling `result`, `evaluator`, and `check_output` while preserving generated hashes. Do not run the next command before their decision. The agent report and CLI exit 0 do not replace the check.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

8. **Write the conclusion and choose an extension.** Add the run ID to the report manifest and observations to [NOTES](../../experiments/pi/NOTES.md). The minimum does not require `pass`: a substantive, independently evaluated `fail`/`partial` is a completed experiment. `aborted` is diagnostic material; to meet the minimum, fix the cause and obtain a new evaluated attempt while preserving the old one. For three repetitions, preassign three new slots without selecting successful outcomes. Run T001 with one frozen source archive, T003 as an audit of Pi inputs, and `without-spec` as a separate paired series under [LAB10](LAB10-ablation.md). For T001/T003, Pi's built-in tools and system prompt remain properties of the same configuration. The [shared workflow](harness-workflow.md) describes how to create these records.

## Results tables

Measurements remain empty before execution; `not-run` is a plan state, not a recorded attempt's verdict.

| Check | Plan | Actual observation | Evidence path |
| --- | --- | --- | --- |
| Package/image ID | Pi 0.73.1 / immutable ID | — | — |
| Native smoke | Session + bash without an API | — | — |
| Identity | Exact request; observed separately | — | — |
| Usage | Only completed `message_end` events | — | — |
| Limit | 30 native turns; 900 s; USD observed | — | — |

| Slot | Run ID | Requested / observed ID | Native turns | Tokens in / out | USD / source | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Pi component | Why needed | Event/code supporting its role | Measurement or limitation |
| --- | --- | --- | --- |
| Native session/tools | — | — | — |
| Abort on `turn_end` | — | — | — |
| Compaction/retry disabled | — | — | — |

## Deliverables

`report.md`, completed lab manifest, tables with evidence paths, build/version/smoke/test logs, Pi event analysis, a reference to the complete `results/runs/<run-id>/`, and independent evaluation. Submit inputs/trace/artifacts with `run.json`; a final-answer screenshot alone is insufficient. Identify unknown metrics and reasons, the USD boundary, and the conclusion about the native configuration's sufficiency. Secrets and `.env` are excluded from the submission.

## Completion criteria

- [ ] Version, image IDs, provider, exact model, variant, native limit, USD policy, and timeout pinned.
- [ ] Offline tests/smoke passed or diagnosed; preparation does not reveal hidden checks.
- [ ] At least one real T002 attempt is `completed` with an independent `pass`/`fail`/`partial`; other started attempts are preserved.
- [ ] `message_end` accounting without duplicate `turn_end` counting demonstrated; `observed_id=null` explained.
- [ ] Report, raw evidence, answers, and NOTES agree; `npm run check` passes.

If the model/judge is unavailable, submit a `blocked` report with completed steps and the reason. This is an honest interim result, not completion of the lab minimum.

## Review questions

1. Why do `message_end` and `turn_end` not represent two paid responses?
2. What does `agent.abort()` limit, and which calls cannot be treated as equivalent turns across harnesses?
3. Why is the `model` field in a Pi message insufficient for `observed_id`?
4. How does disabled compaction affect interpretation of a long series?
5. Why does an identical package version not replace an immutable image ID?
6. How does an independent `fail` differ from `aborted` and successful offline smoke testing?

## Sources

Versions and commands in this lab come from pinned repository files: [Pi README](../../experiments/pi/README.md), [Dockerfile](../../experiments/pi/Dockerfile), [harness.json](../../experiments/pi/harness.json), [runtime](../../experiments/pi/run.mjs), [adapter tests](../../experiments/pi/adapter.test.mjs), [method](../method.md), [ledger L011](../harness-ledger.md), and [shared infrastructure](../../experiments/common/README.md). The lab does not claim compatibility with other SDK versions; a version change requires a new configuration, smoke tests, and event verification.
