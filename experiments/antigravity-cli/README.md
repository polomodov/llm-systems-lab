# Google Antigravity CLI

Practical assignment: [LAB14 — Antigravity CLI, Gemini API, and observability](../../docs/labs/LAB14-antigravity-cli.md). Includes an offline smoke test, full T002 with external judging, and additional series.

An adapter for the official binary CLI **`agy` 1.2.7** is implemented. This is a separate Antigravity product; the Gemini CLI package is not used. The image was checked on 2026-09-20 on Linux/arm64 without credentials or network access. Actual Gemini API episode execution remains **unverified**. The [original checks](smoke/2026-09-20.json) concern infrastructure.

```bash
docker build --build-arg HARNESS_VERSION=1.2.7 \
  -t harness-lab/antigravity-cli:1.2.7 experiments/antigravity-cli
```

The installer uses a [release snapshot](releases/1.2.7.json), pinned URLs, and Linux arm64/x64 SHA-512 values from official release manifests. The build does not request `latest`; add a verified manifest before selecting a new version. The x64 archive is pinned but has not been run locally.

`.env` must contain `GEMINI_API_KEY`. `settings.json` sets `modelProvider: gemini`: according to the documentation, requests go directly to the Gemini API. The runtime copies this file to a temporary HOME inside the container; host credentials are not mounted. Select `--harness antigravity-cli` and provider `google` for preparation; execution requires an exact available model ID, an image, and `--budget-mode observed`. The shared lifecycle is described in the [root instructions](../../README.md).

The adapter uses `--output-format stream-json`, an explicit model, and skips interactive permissions inside the outer container. Slash-command expansion is disabled. `--print-timeout 0` delegates the time limit to the shared runner. The interface does not verify USD or internal-turn limits; mandatory values are rejected, and the absence of limits in research mode is recorded.

The parser uses only the last final `result`; cumulative counters are not added to `step_update`. USD and model turns are unknown: `num_turns` counts user requests. `tokens_out` comes from final usage. Cache/input semantics need confirmation in a real run, so `tokens_in` remains unknown. `init.model` reflects configuration, not independent evidence of the response model: `observed_id=null`.

Primary sources: [installation and Gemini API key](https://antigravity.google/docs/cli/install/), [headless protocol](https://antigravity.google/docs/cli/headless/), [official installer](https://antigravity.google/cli/install.sh). Specific flags were checked against `agy --help` inside the image. Retesting requires unit/smoke tests, credential/network verification, and a recorded episode with external evaluation; component row: **L010**.
