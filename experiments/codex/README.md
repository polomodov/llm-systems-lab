# OpenAI Codex CLI

Step-by-step assignment covering `exec`, external isolation, a real T002, and JSONL analysis: [LAB13 — Codex CLI](../../docs/labs/LAB13-codex.md).

The `codex exec --json` adapter is implemented. Version **0.167.0** was built and checked on 2026-09-20 on Linux/arm64 without credentials or network access. Actual provider-backed episode execution remains **unverified**. The [original checks](smoke/2026-09-20.json) are not agent runs.

```bash
docker build --build-arg HARNESS_VERSION=0.167.0 \
  -t harness-lab/codex:0.167.0 experiments/codex
```

`.env` must contain `CODEX_API_KEY`; the coordinator passes only the selected key. Host `auth.json`, user settings, and sessions are not mounted. Select `--harness codex` and provider `openai` for preparation; specify an exact available model ID, image, and `--budget-mode observed` for execution. Shared commands are in the [root instructions](../../README.md).

The adapter explicitly selects the model and `approval_policy=never`, disables built-in web search and subagents, and disables loading user config/rules. The internal sandbox is disabled using the documented `danger-full-access`; the lab’s outer container enforces file, process, and network boundaries.

The CLI has no verified flags for limiting internal turns or USD. The adapter rejects such mandatory limits. Research mode records the absence of these limits; the external timeout remains hard.

The parser reads only a valid completed stream. `turn.completed.usage.input_tokens` already includes cache; `cached_input_tokens` is not added a second time. USD and internal model turns remain unknown. `thread.started` supplies the session ID, but JSONL does not establish the model ID in the provider response: `observed_id=null`. An error or truncated stream does not become successful completion.

Primary sources: [OpenAI Docs — non-interactive mode](https://developers.openai.com/codex/noninteractive), [config reference](https://developers.openai.com/codex/config-reference). Installation package: `@openai/codex@0.167.0`. Specific flags were also checked against `codex exec --help` inside the image. On upgrade, repeat the smoke test and parser tests, then perform a recorded episode; component row: **L009**.
