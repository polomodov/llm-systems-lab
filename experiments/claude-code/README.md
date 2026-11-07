# Claude Code: lab adapter

Step-by-step assignment with its own report, Docker smoke test, real T002, usage audit, and independent evaluation: [LAB11 — Claude Code](../../docs/labs/LAB11-claude-code.md).

The adapter is implemented; actual results appear only in `results/runs/`. CLI documentation was checked on **2026-09-20**; each image’s compatibility is verified separately. The local version on the operator’s machine does not determine the run version.

An infrastructure check ran on 2026-09-20 using Docker Engine 29.5.2 / Linux arm64: historical version `2.1.83 (Claude Code)` built with `--ignore-scripts`, and CLI help opened with networking disabled. No keys or provider requests were used. Its historical image ID was `sha256:4d9080ac1909d7e8c49056f0f2ae881e13926c5fc37f398c463bcb42d6117761`; it does not identify the current runtime.

Current pin: **2.1.319**, independently checked on 2026-11-07. This release needs its native-binary postinstall during image preparation; `--ignore-scripts` does not qualify it. The [refresh evidence](../common/model-refresh-2026-11/README.md) records new immutable images, exact versions and synthetic Messages tool loops. Live API/model access remains unverified.

```bash
docker build --build-arg HARNESS_VERSION=2.1.319 -t harness-lab/claude-code:2.1.319 -f experiments/claude-code/Dockerfile experiments/claude-code
docker run --rm --network none harness-lab/claude-code:2.1.319 claude --version
docker run --rm --network none harness-lab/claude-code:2.1.319 claude --help
```

Rebuilding may produce a different image ID; retain the selected immutable image for a run series.

## Execution

First build the image with a pinned CLI version using the [root instructions](../../README.md). The orchestrator reads the provider key from `.env`; the file itself is not copied to the workspace. Select an exact model ID available through the API in use.

```bash
npm run new-run -- --harness claude-code --agent a1-dossier --task T001
RUN_ID='<identifier printed by new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/claude-code:2.1.319 --model '<exact model ID>'
npm run judge-run -- --run "$RUN_ID" --evaluation '<independent evaluation JSON>'
npm run check
```

`judge-run` imports an external evaluation after execution. Successful CLI termination alone does not mean `pass`. The evaluator operates outside the agent container; hidden-check criteria must not be added to the prompt.

## What the adapter adds

`adapter.mjs` builds an argument array for execution without a shell: `claude -p`, an explicit model, `--output-format stream-json --verbose`, and `--max-turns` / `--max-budget-usd` limits. Permissions are set with `--permission-mode dontAsk` and `/control/settings.json`; standard settings sources are disabled using `--setting-sources ''`. `DISABLE_AUTOUPDATER=1` disables background updates. Sources: [CLI](https://code.claude.com/docs/en/cli-reference), [environment variables](https://code.claude.com/docs/en/env-vars).

`settings.example.json` is input for container preparation. The orchestrator creates the filesystem boundary: the agent receives the workspace, but not the repository directory containing hidden checks, result metadata, and `.env`. Tool configuration operates inside this boundary; hidden checks are not mounted in the container.

The orchestrator sets the proxy through `HTTP_PROXY` / `HTTPS_PROXY`. The CLI supports these variables according to its [network documentation](https://code.claude.com/docs/en/network-config). Network access rules are enforced separately from tool rules.

## Result accounting

The parser extracts the last final `result`; it supports JSONL, a message array, and a single JSON value. Format source: the [official SDK parser](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/message_parser.py).

- `turns` — `num_turns`, `cost_usd` — `total_cost_usd`.
- `tokens_in` includes ordinary input and prompt-cache reads and writes. `tokens_out` comes from output tokens. If complete `modelUsage` is available, its sum across models is used; `usage` is not added again.
- The main response model is checked using `assistant.message.model`; requested and observed models are different evidence. A missing observed ID does not confirm model selection.
- Missing values are not replaced with zeros. Reasons are saved in `metrics_unavailable`; truncation without a final message produces `trace_incomplete`.

The CLI reports cost. This is not an independent billing reconciliation. The first real run should confirm auxiliary-request completeness and limit behavior for the particular version. [Official SDK usage types](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py).

Parser verification without a model or API:

```bash
node --test experiments/claude-code/adapter.test.mjs
```

Record component rationale and removal plans in the [ledger](../../docs/harness-ledger.md), and observations in `NOTES.md` with the run ID.
