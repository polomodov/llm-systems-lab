# Pi (pi-mono)

Learning track: [LAB15 — Pi: upstream SDK loop, events, and reproducible T002](../../docs/labs/LAB15-pi.md). Includes an offline smoke test, a real episode, independent evaluation, and native-event accounting exercises.

Status: **SDK adapter implemented; build and offline initialization checked on 2026-09-20; Pi/local/T002 has two independently evaluated failures and one pass on Ryzen (2026-10-12–15); cloud episodes unverified**. Pinned: `@mariozechner/pi-coding-agent@0.73.1`, Node.js 24.13.1. Uses the original `createAgentSession`: Pi’s system prompt, tools, and loop. `run.mjs` only configures the session, passes the prompt, saves events, and stops the loop at the turn boundary. Ledger component: L011.

## Execution

```bash
docker build -t harness-lab/pi:0.73.1 -f experiments/pi/Dockerfile experiments/pi
npm run new-run -- --harness pi --agent a2-janitor --task T002
RUN_ID='<ID from new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/pi:0.73.1 \
  --model '<exact model ID>' --budget-mode observed
```

For OpenAI, select `prepare-run --provider openai`. The selected provider’s key is read only from `.env`: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. The shared coordinator isolates the container, saves the snapshot, and supplies `/control/run.mjs`; no local SDK launch on the operator’s machine is needed. The image pins the main package; the final image ID fixes the transitive dependencies resolved during build. Use one image per series.

## Conditions and accounting

- `budget-mode observed` is required: the SDK does not guarantee a hard USD limit.
- Turns are limited through native `agent.abort()` after `turn_end`, before the next model turn begins. Automatic compaction and retry are disabled to avoid calls outside this counter. HTTP retries inside the provider are not separate turns.
- The model is selected by exact ID in the SDK catalog. For OpenAI, the catalog may contain only a family name: for IDs with a `YYYY-MM-DD` suffix, the adapter takes the family’s transport/context/pricing metadata but sends the **original exact snapshot ID**. An unknown family causes an error; there is no fallback to another model. Family prices are SDK estimates, not the provider’s bill.
- The trace contains original SDK events and one `lab_pi_result`. Only completed assistant `message_end` events are summed; duplicates in `turn_end` are excluded. Input tokens include cache reads/writes. Unknown totals are not replaced with zeros after a truncated trace or incomplete usage.
- Pi message `model` fields are populated from the supplied configuration, so they **do not prove** the actual provider-response ID: `observed_id=null`. No subagents were added; host user plugins are not mounted. Comparison with a different compaction configuration requires a separate series.

## Verification without an API

`node --test experiments/pi/adapter.test.mjs` checks arguments, USD-cap rejection, snapshot IDs, and complete/truncated traces. `run.mjs --help` imports the SDK; `--smoke` creates a real session and checks native bash with `printf`, without `prompt()` or model calls:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/pi,dst=/control,readonly" \
  --entrypoint node harness-lab/pi:0.73.1 /control/run.mjs --smoke
```

In this version, `pi --version` writes to stderr. The coordinator therefore obtains the installed package version through `node -p`, as specified in `harness.json`. The offline check also passed with `HTTP_PROXY`, `HTTPS_PROXY`, and `NODE_USE_ENV_PROXY=1`; no separate executable cache mount is needed.

Primary sources checked against the tag: [SDK](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/coding-agent/docs/sdk.md), [JSON events](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/coding-agent/docs/json.md), [subscription and abort](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/agent/src/agent.ts), [Anthropic model/usage mapping](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/ai/src/providers/anthropic.ts). After changing versions, repeat the build, offline smoke test, and event-format checks. Task success is established only by a real registered episode and an independent verdict.

<a id="local-provider-bridge"></a>

## Local provider bridge — first LAB08 implementation

Pi now supports provider `local` / GGUF / controlled native llama.cpp Metal on macOS and ROCm on Linux. [LAB15 Ryzen](measurements/LAB15-local-ryzen/report.md) contains evaluated T002 runs; the summary report is blocked on repeat preregistration. The Apple deployment example below is retained; its pilot awaits independent evaluation. This is a separate engineering track; existing cloud providers are unchanged. A complete deployment manifest v1, passing LAB32 conditions, and current-file verification are prerequisites. Original manifest example: [LAB08 deployment](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/raw/deployment.json). Absolute paths refer to this test machine; substituting a different endpoint or alias after preparation is forbidden.

```sh
npm run new-run -- --harness pi --agent a2-janitor --task T002 --provider local --model lab-model
RUN_ID='<actual ID of a new record>'
npm run prepare-run -- --run "$RUN_ID" --provider local \
  --local-deployment experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/raw/deployment.json
npm run run -- --run "$RUN_ID" --provider local --model lab-model \
  --image harness-lab/pi:0.73.1 --proxy-image node:24.13.1-bookworm-slim \
  --budget-mode observed --timeout 900
```

The runner starts its own native server on the Mac loopback interface after checking weights, executables, and all bundled dylib hashes, and stops only that server. Resource and AC guards apply. The sealed supervisor checks PID/props/template/context and files before and after every HTTP request. A changed manifest or runtime identity causes rejection; there is no cloud fallback. Connecting to an arbitrary already-running server is not yet supported.

The agent container has only an internal Docker network, 2 GiB RAM, and the existing mounts/permissions. The trusted broker has a second Docker bridge network to publish the host control port only on loopback; it forwards no CONNECT requests and creates no upstream sockets. The host worker initiates a reverse control connection with a one-time capability and forwards only POST `/v1/chat/completions` to the pinned endpoint. GET `/health` is accessible to the agent; `/props`, `/slots`, `/models`, LAN/cloud, and the control API without the capability are forbidden. T001/T003 are not yet admitted through the local provider; the public source gateway/replay is retained for cloud.

Pi uses its own `createAgentSession` and native tools. SDK API: `openai-completions`; provider: `local`. This is a compatibility protocol, with no OpenAI calls. The public dummy marker `harness-local-dummy` is required by ModelRegistry and is not forwarded upstream; `.env` is unnecessary. Real server authentication is unsupported in this variant. The SDK requires numeric prices, so zero placeholders are not treated as cost: `run.json` records cost=null with a reason. Tokens come from primary HTTP usage; if absent, SDK zeros are rejected.

The first bridge buffers SSE until finish/DONE; tool-call events are preserved, but the stream does not reflect actual TTFT. Request limit: 1 MiB; response: 4 MiB; one concurrent request; upstream deadline: 300 s; automatic retries/compaction disabled. Cancelling the client connection closes its own upstream request. `awaiting_review` is not a pass; import independent evaluation through the existing judge-run.

Checks: `npm test`, `npm run test:docker`, `npm run test:local-docker` (requires both pinned images), and `npm run check`. Results, original rejections, and pilot status are in the [LAB08 report](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/report.md). Components L024/L025 have status “proposed”; their quality contribution and transfer to other adapters/platforms have not been established.

After the first real pilot, wall-clock deadline checking and rejection on resource-timeline gaps >15 s or backward clock movement were added. Software/Docker regressions passed; a new [Apple qualification](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-native-requalification-20261010/report.md) was performed, and its 16K pilot remains awaiting_review. The [Ryzen continuation](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-ryzen-linux-bridge/report.md) has evaluated fail/pass outcomes under different conditions. Guards apply when the host resumes and do not promise termination while it is fully suspended. Two real aborted attempts are retained in LAB08.
