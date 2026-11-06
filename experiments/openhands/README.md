# OpenHands

Learning track: [LAB17 — OpenHands SDK: Conversation, native tools, and independent evaluation](../../docs/labs/LAB17-openhands.md). Includes an offline smoke test, real T002, and analysis of the differences between iterations, tool actions, and completed model responses.

Status: **SDK adapter implemented; build and offline initialization checked on 2026-09-20; real episodes unverified**. Pinned: `openhands-sdk==1.49.2`, `openhands-tools==1.49.2`, Python 3.12.12, and Node.js 24.13.1. This is an OpenHands SDK profile (`mode=sdk`), not a legacy CLI/runtime image. Ledger component: L013.

## Execution

```bash
docker build -t harness-lab/openhands:1.49.2 \
  -f experiments/openhands/Dockerfile experiments/openhands
npm run new-run -- --harness openhands --agent a2-janitor --task T002
RUN_ID='<ID from new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/openhands:1.49.2 \
  --model '<exact model ID>' --budget-mode observed
```

Select OpenAI with `prepare-run --provider openai`. The LLM receives `anthropic/<ID>` or `openai/<ID>`; the coordinator profile reads the key from `.env`. Keys are not written to arguments, runtime configuration, or the SDK trace. The version comes from installed `openhands-sdk` metadata. Retain one image ID per series; transitive versions are installed during build.

## Conditions and accounting

- `Agent` and `Conversation.run()` execute the original SDK loop. Native `TerminalTool` and `FileEditorTool` are registered; the SDK itself adds standard Finish/Think tools. Context, system prompt, and events retain their original forms.
- `LocalWorkspace` runs **inside** the shared isolated Docker container. The Docker socket, host home, hidden checks, and controlling `run.json` are not passed through. Packaged tmux supplies the standard terminal backend; no additional OpenHands container is launched.
- `max_iteration_per_run` limits the SDK loop. It is an iteration cap, not a guarantee on HTTP retries. Native `MaxIterationsReached` is retained as the reason for bounded termination. The external timeout limits wall-clock time.
- USD is recorded only in `--budget-mode observed`; hard mode is rejected before loading the key. Cost from `llm.metrics` is an SDK estimate. Missing prices or final usage sets are not replaced with invented zeros.
- The callback saves native events as `openhands_event`; final `lab_openhands_result` contains metrics, status, and conversation ID. Tokens are summed across `token_usages`; `turns` counts completed LLM responses, not tools. After an error, incomplete usage totals remain unknown.
- The SDK fills metric model fields from the request, so `observed_id=null`; those fields are not presented as a verified response model. Browser, MCP, delegation, and condenser were not added. Persistence is disabled: all events go to the host trace, while temporary tool caches remain in `/tmp`.

## Verification without an API

`node --test experiments/openhands/adapter.test.mjs` checks launch, providers, limits, and incomplete-metric handling. `run.py --help` imports the SDK; `--smoke` creates a `Conversation`, sends a local user event to initialize native tools, and checks the native terminal through `printf`, but **does not call `run()` or the model**:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/openhands,dst=/control,readonly" \
  --entrypoint python harness-lab/openhands:1.49.2 /control/run.py --smoke
```

The check also passed with proxy environment variables; SDK, terminal, and file editor initialize with `/tmp noexec`, with no separate executable cache required.

Primary sources at the tag: [basic SDK example](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/examples/01_standalone_sdk/01_hello_world.py), [metrics](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/examples/01_standalone_sdk/13_get_llm_metrics.py), [Conversation and iteration limits](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py), [TokenUsage format](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-sdk/openhands/sdk/llm/utils/metrics.py), [native terminal](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-tools/openhands/tools/terminal/definition.py). After upgrading, repeat the offline smoke test and metric checks; real episode success requires an external verdict.
