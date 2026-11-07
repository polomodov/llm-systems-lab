# Harness matrix

Each of the nine harnesses has a dedicated [LAB11–19 exercise](labs/README.md) covering builds, smoke tests, a model episode and independent evaluation. The cloud learning route does not require a local provider bridge.

Integration status as of **2026-09-20**. All nine harnesses are connected to shared preparation, Docker execution, trace recording and independent evaluation. Installation and offline smoke tests verify infrastructure; task success with a real provider remains **unverified** until completed records exist in `results/runs/`.

| Harness | Verified pin | Interface | Provider / `.env` variable | Model selection | Limits |
| --- | --- | --- | --- | --- | --- |
| [Claude Code](../experiments/claude-code/README.md) | 2.1.319 | CLI JSONL | Anthropic / `ANTHROPIC_API_KEY` | Explicit ID | Turns and USD through CLI |
| [OpenCode](../experiments/opencode/README.md) | 1.18.29 | CLI JSONL | Anthropic / `ANTHROPIC_API_KEY` | Explicit ID | Steps advisory; USD observed |
| [Codex](../experiments/codex/README.md) | 0.167.0 | `codex exec --json` | OpenAI / `CODEX_API_KEY` | Explicit ID | Internal turns and USD unavailable |
| [Antigravity CLI](../experiments/antigravity-cli/README.md) | 1.2.7 | `agy` headless JSONL | Google / `GEMINI_API_KEY` | Explicit ID through direct Gemini API | Internal turns and USD unavailable |
| [Pi](../experiments/pi/README.md) | 0.73.1 | Native SDK `createAgentSession` | Anthropic or OpenAI / corresponding API key | Explicit ID | Turn limit; USD observed |
| [mini-SWE-agent](../experiments/mini-swe-agent/README.md) | 2.4.6 | Native SDK `DefaultAgent` | Anthropic or OpenAI / corresponding API key | Explicit ID | Native step limit; USD observed |
| [OpenHands](../experiments/openhands/README.md) | SDK/tools 1.49.2 | Native SDK `Conversation` | Anthropic or OpenAI / corresponding API key | Explicit ID | Native iteration limit; USD observed |
| [Copilot CLI](../experiments/copilot-cli/README.md) | 1.0.86 | Headless CLI JSONL | Copilot / `COPILOT_GITHUB_TOKEN` | Explicit supported selector; underlying ID may be unknown | USD and model-turn cap unavailable |
| [Amp](../experiments/amp/README.md) | 0.0.1789920039-gafe14b | CLI stream JSONL | Amp / `AMP_API_KEY` | `managed:low`, `managed:medium`, `managed:high`, `managed:ultra` | USD and model-turn cap unavailable |

## What a verified pin means

The version pin in `experiments/<harness>/harness.json` is the sole source of truth. `npm run check` compares it with Dockerfile `ARG`/`RUN test`, the `harness-lab/<id>:<pin>` tag in the root README, this table and the harness README. A mismatch anywhere is a failed check, not silent drift. At execution time, `run.mjs` compares the sealed profile's pin with the version reported by the image and aborts before starting the agent if they differ.

The evidence class for the image itself varies; this table does not make those classes equivalent:

- All nine have a recorded verified local image ID: `claude-code`, `opencode`, `amp` and `copilot-cli` in their READMEs; `antigravity-cli`, `codex`, `pi`, `mini-swe-agent` and `openhands` in NOTES.
- Only two have machine-readable offline smoke records: `antigravity-cli` and `codex` (`experiments/<harness>/smoke/2026-09-20.json`). The others have textual notes.
- As of this integration snapshot, none had a real-model run.

On 2026-09-21, on the operator's machine (Docker Engine 29.5.2, darwin/arm64 host), the version command in each of the nine built images returned its exact pin. This is our installation check without keys or provider requests, not a task result.

Image installation uses `--ignore-scripts` by default. Exceptions are documented in their Dockerfiles: `claude-code`2.1.319 (native binary installation, verified offline on 2026-11-07), `opencode` (postinstall selects a platform binary), `amp` (postinstall places a native binary) and `pi` (its dependency tree includes `koffi`, which builds a native binding through an install script).

An external timeout applies in every case. Eight harnesses require an explicit `--budget-mode observed`; the absence of a mandatory USD cap is not hidden. These research attempts deviate from the task budget and are not grouped with the `hard` policy. Native SDK step/iteration semantics can differ: raw events are retained for interpretation, and different counters are not presented as one universal metric.

## Profiles and reproducibility

`experiments/<harness>/harness.json` defines the machine-readable configuration: version command, configuration/runtime files, providers, credential names, exact network domains, model policy and available limits. `npm run harnesses` displays these without reading keys.

Choose the provider with `new-run --provider ...` or `prepare-run --provider ...`; without an explicit choice, the default profile applies. The provider is saved in the snapshot and run.json. You cannot switch it at run time while retaining the old network policy. Only credentials named by the selected provider are passed into the container; neither the full `.env` file nor user settings are mounted.

SDK adapters use the respective projects' native loops, not a shared custom agent. `harness.mode=sdk` distinguishes them from CLIs. The library version is determined inside the specific Docker image. Images are built with a pin; retain one image ID for a series. Runtime files and the adapter are included in sealed inputs.

Copilot and Amp extract native modules at startup; these two profiles have `native_cache=true`. The coordinator creates a separate unprivileged, executable 512 MiB tmpfs at `/tmp/harness-native` and sets `TMPDIR`/`XDG_CACHE_HOME`; the root image stays read-only. This condition is recorded in the ledger and was checked offline under UID 1000. Other profiles do not receive this mount.

## Models and measurements

The requested model, `model.provider`, `model.selection`, `model.lock` and observed model are separate fields. Amp supplies a managed selector and `lock=true`; this does not promise a particular underlying model. Those series are not grouped with explicit model IDs. A Copilot selector also does not verify the exact response snapshot. Missing observations remain `null` with reasons.

CLIs and SDKs account for caching, auxiliary calls and cost differently. Parsers use only confirmed final values; absent fields are never replaced with zero. An erroneous or truncated terminal stream with exit 0 is considered aborted. `awaiting_review` follows finished execution; `pass` requires external evaluation.

T003 prepares an allowlisted snapshot for each of the nine harnesses. `/control` files appear under `.harness/control/`, alongside the original adapter, profile, runtime and shared coordinator boundaries. Hidden checks and secrets are excluded.

## Primary sources and verification

A [separate campaign](local-models.md) covers open local models on Ryzen AI Max+ 395 / 128 GB / Linux. The first integration candidates are Pi, mini-SWE-agent, OpenCode and OpenHands. The campaign plan itself is not a ready `local` provider: network-bridge adaptation, backend-setting snapshots and comparison conditions are still required. Upstream custom-API capability does not establish tested local-server support in the current adapter.

- Claude: [CLI reference](https://code.claude.com/docs/en/cli-reference), [official SDK types](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py).
- OpenCode: [CLI v1](https://opencode.ai/docs/cli/), [network](https://opencode.ai/docs/network/). Do not mix v1 and v2 commands.
- Codex: [non-interactive mode](https://developers.openai.com/codex/noninteractive), [config reference](https://developers.openai.com/codex/config-reference).
- Antigravity: [install](https://antigravity.google/docs/cli/install/), [headless](https://antigravity.google/docs/cli/headless/). The separate `agy` executable was checked; no assumption about a Gemini CLI rename is needed.
- Pi: [upstream coding agent](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).
- mini-SWE-agent: [upstream](https://github.com/SWE-agent/mini-swe-agent).
- OpenHands: [Software Agent SDK](https://github.com/OpenHands/software-agent-sdk).
- Copilot: [official CLI](https://github.com/github/copilot-cli).
- Amp: [manual](https://ampcode.com/manual).

Exact source versions, build commands, offline limitations and observations are listed in the corresponding README/NOTES. Installation checks do not create fictional agent-run records. Measurements require API access for the selected account, a real episode and an external verdict.
