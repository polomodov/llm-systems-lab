# mini-SWE-agent

Learning track: [LAB16 — mini-SWE-agent: a minimal native loop and the cost of observability](../../docs/labs/LAB16-mini-swe-agent.md). Includes an offline smoke test, real T002, independent evaluation, and investigation of `mini.yaml`, step limits, and trajectory completeness.

Status: **SDK adapter implemented; build and offline initialization checked on 2026-09-20; real episodes unverified**. Pinned: `mini-swe-agent==2.4.6`, Python 3.12.12, and Node.js 24.13.1 for the shared entrypoint. Uses the original `DefaultAgent`, `LitellmModel`, `LocalEnvironment`, and built-in `mini.yaml` with native bash tool calling. Ledger component: L012.

## Execution

```bash
docker build -t harness-lab/mini-swe-agent:2.4.6 \
  -f experiments/mini-swe-agent/Dockerfile experiments/mini-swe-agent
npm run new-run -- --harness mini-swe-agent --agent a2-janitor --task T002
RUN_ID='<ID from new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/mini-swe-agent:2.4.6 \
  --model '<exact model ID>' --budget-mode observed
```

Select OpenAI with `prepare-run --provider openai`; the adapter passes `openai/<ID>` or `anthropic/<ID>` to LiteLLM. The selected profile reads `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` from `.env`. The adapter adds the provider prefix; an exact ID alone suffices for `--model`. Use one built image ID per series: pinning the main package is not a lockfile for every dependency.

## Conditions and accounting

- The original `DefaultAgent.run()` executes the full loop. A subclass overrides only `add_messages` for the JSONL trace; tool execution, termination, and format-error recovery remain upstream.
- `step_limit` is the native `n_calls` limit. Built-in `cost_limit` is checked **after** spending and may be exceeded, so the adapter rejects hard USD and requires `--budget-mode observed`. In this mode, `cost_limit=0`; the external wall-clock timeout remains active.
- `mini.yaml` contains a repository repair workflow. This harness property also applies to T001/T003; it is fixed by the package version, not a hidden replacement of the shared agent specification. The configuration is included in the final trajectory.
- Individual `mini_message` events preserve original messages; `lab_mini_result.trajectory` contains the full `serialize()` result. `turns` comes from `model_stats.api_calls`, including failed attempts. Token/cost totals are reported only when response usage exists for each such call. Cost is a LiteLLM estimate; an unknown price raises an upstream error rather than inventing a zero.
- `response.model` allows an observed ID to be recorded and multiple models to be detected. `LITELLM_LOCAL_MODEL_COST_MAP=True` uses the installed package’s table without fetching price updates. CLI onboarding and the operator’s home credentials are not used.

## Verification without an API

`node --test experiments/mini-swe-agent/adapter.test.mjs` checks provider selection, limits, and complete/truncated traces. `run.py --help` imports the SDK; `--smoke` creates a native agent/model/environment and executes a harmless `printf` through `LocalEnvironment` without calling the model:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/mini-swe-agent,dst=/control,readonly" \
  --entrypoint python harness-lab/mini-swe-agent:2.4.6 /control/run.py --smoke
```

The offline smoke test also passed with proxy environment variables; `/tmp` does not need executable permission. The version comes from installed Python-package metadata.

Primary sources at the tag: [DefaultAgent and step/cost limits](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/agents/default.py), [LiteLLM: raw response, usage, and cost](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/models/litellm_model.py), [mini.yaml](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/config/mini.yaml), [LocalEnvironment](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/environments/local.py). Availability of a particular model ID and episode outcomes require a separate registered run.

## Sol 6.1 revision

For exact `openai/gpt-6.1-sol`, the lab entrypoint uses mini's native `LitellmResponseModel`, with Responses tool calling, explicit medium effort and no incompatible sampling options. Other models keep their existing model class. LiteLLM 1.108.1 and MCP 2.2.0 are pinned; the refreshed immutable image has a checked dependency closure. The parser accepts Responses usage without inventing missing totals. [Offline lab/native evidence](../common/model-refresh-2026-11/README.md) passes; fixture cost is synthetic and live billing/account access remain unverified.
