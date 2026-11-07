# llm-systems-lab

A lab for reproducible experiments with LLM systems: local models, inference engines, hardware, serving and autonomous agents. Agent comparisons run the same agents on the same tasks in different harnesses. We measure success, cost and time, as well as the instructions, constraints and tools each harness needed. We then remove optional components and replay the episode.

## What works today

- A shared `new-run → prepare-run → run → judge-run → compare` lifecycle.
- Adapters for **all nine harnesses**: Claude Code, OpenCode, Codex, Antigravity CLI, Pi, mini-SWE-agent, OpenHands, Copilot CLI and Amp. CLI/SDK versions are pinned; `npm run harnesses` lists their parameters and limits.
- Six task types: A1/T001 — a dossier from web sources; A2/T002 — fix failing `npm test`; A3/T003 — audit harness configuration; A4/T004 — implement a feature from a specification with hidden tests; A5/T005 — normalize three messy data exports without a repository; A6/T006 — fix three HTTP server security defects with exploit tests. Each task's `task.json` defines its conditions; only T002 has evaluated runs so far.
- Docker isolates the agent from hidden checks, `.env` and result metadata. Outbound access goes through a separate gateway.
- Input snapshots with SHA-256, original traces, reasons for unknown metrics, and independent evaluation bound to the actual outputs.
- Comparisons only within matching conditions; `pass@3` and `pass^3` over complete triples. Specification ablation through `--variant without-spec`.

**Status as of 2026-10-22:** hardware measurements exist for Ryzen and Apple, along with 11 agent-run records. Three Pi/local/T002 runs have independent evaluations: two `fail` and one `pass`. Six other records are `aborted`, one is `awaiting_review`, and one is `prepared`. There are no complete triples under matching conditions or cross-harness comparisons yet. Actual coverage and acceptance limits are listed in the [lab status overview](docs/labs/README.md#execution-status-as-of-2026-10-22). Infrastructure checks do not replace agent-quality evaluation.

**2026-11-05:** local-model measurement bundles (about 150 MB including binary logs) were moved out of the working tree into a [commit-addressed archive](experiments/local-models/measurements/README.md); documentation uses permalinks. The `experiments/` tree shrank from 155 MB to 2 MB.

**2026-11-06:** the project moved to this public repository with sanitized history, MIT licensing and an English project interface. Original research artifacts retain their source language and sealed conditions; see [publication and archive provenance](docs/publication.md).

## Laboratory exercises

The [53-lab course](docs/labs/README.md) includes an exercise for each of the nine harnesses, reproducibility, model research on Ryzen, Vulkan/HIP, engines, services, agent comparisons and ablations. LAB20–27 add evaluation calibration, memory, tools, recovery, delegation, quantization, concurrent load and upgrade regressions. Each lab has step-by-step assignments, tables, deliverables and review questions. LAB28–35 cover Apple M5 Max / 128 GB / macOS: Metal, MLX, services, context/tools, load and comparison with Ryzen. LAB36–42 (the SPACE sandbox platform), LAB43–47 (Kubernetes and GPUs) and LAB48–52 (AWS and Terraform) have been **frozen** since 2026-11-05: they are manuals without measurements, awaiting extraction into a separate teaching repository, and accept no new sessions. LAB53 measures how much variation in agent decisions comes from the inference server itself.

```bash
npm run labs
npm run lab:new -- --lab LAB01 --session first-pass
```

`lab:new` creates a blank report bundle and preserves existing files. After LAB01 you can proceed directly to **LAB11–19 for all harnesses**, then the cloud comparison in LAB09 and ablation in LAB10. Harness-specific reports go in `experiments/<harness>/measurements/`; SPACE reports in `experiments/space/measurements/`; Kubernetes and GPU reports in `experiments/k8s-gpu/measurements/`; AWS and Terraform reports in `experiments/aws/measurements/`. LAB02–07 run on Ryzen. LAB08 implements a local Pi/T002 bridge for native llama.cpp. Ryzen/ROCm has evaluated pilots; Apple/Metal awaits evaluation. Other local adapters still require implementation and qualification.

For preparation without an API, use the [four synthetic exercises](docs/labs/practice.md) and [public multi-step episodes](docs/labs/episodes/README.md). They do not create experimental results. The [report completeness check](docs/labs/report-validation.md) accounts for every planned attempt, including failures and omissions:

```bash
npm run lab:practice -- --scenario retry-429 --session first-pass
npm run lab:check -- --report experiments/local-models/measurements/LAB01-first-pass
```

Add `--mode submission` to submit a completed report. LAB21–24 require engineering extensions; LAB25 requires accepted LAB08 results. Practice traces do not replace these qualifications or real model series.

## Local models

For **Ryzen AI Max+ 395 / 128 GB / Linux**, the repository provides a [research plan](docs/local-models.md), [catalog](docs/local-model-candidates.md), [Linux runbook](docs/local-model-runtime.md) and actual LAB02–06, 08 and 26 reports. `npm run local:plan` lists candidates; `npm run local:plan -- --context 32768` recalculates context headroom. The planner does not download or run weights. Actual Pi/T002 runs use a separate [local provider](experiments/pi/README.md#local-provider-bridge) and sealed configuration; observations from one deployment do not qualify the whole catalog.

The [engine matrix](docs/local-inference-engines.md) treats llama.cpp Vulkan/HIP, vLLM and SGLang on ROCm, Transformers reference, Ollama, LM Studio and Lemonade as equal research options. `npm run local:engines` lists 12 profiles; `npm run local:plan -- --engine all --format json` builds the research space. For native checkpoints rather than GGUF, and for unmeasured service overhead, the planner keeps memory unknown instead of promising a fit.

The second platform is [Apple M5 Max / 128 GB / macOS](experiments/local-models/apple/README.md). `npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine all` selects Apple; `npm run local:engines -- --hardware apple-m5-max-128gb-macos` lists five profiles. Without `--hardware`, Ryzen remains the default. Specific Metal/MLX deployments and loads have been measured; LAB32 is partially qualified, while LAB33 and the full LAB35 are incomplete. Apple's maximum GPU budget remains unknown; GGUF and MLX have separate manifests. The Apple LAB08 pilot has executed and awaits an independent verdict.

## Requirements and images

You need Git, Bash, [mise](https://mise.jdx.dev/getting-started.html) and a running Docker Engine. [mise.toml](mise.toml) defines the development and CI environment: Node.js 24.13.1 and Python 3.12.12 for offline checks. After installing mise, run from the repository root:

```bash
mise trust
mise install
mise run verify
```

`mise run` and `mise exec -- <command>` work without shell activation; for example, `mise exec -- npm run harnesses`. To use ordinary `node`, `python3` and `npm` commands, you can [activate mise in your shell](https://mise.jdx.dev/cli/activate.html). Existing npm scripts remain available; the coordinator's minimum supported version is Node.js 22.0.0. Secrets stay in `.env`, consumed only by the harness; mise does not load it.

Run the coordinator as an ordinary user, not root. It has no npm dependencies. Mise manages host tools; harness CLI versions remain in `experiments/<harness>/harness.json` and Dockerfile. Images use Node.js 24.13.1; CLI versions are set at build time. The original nine harness versions were checked without model requests on 2026-09-20; the [2026-11-07 refresh](experiments/common/model-refresh-2026-11/README.md) separately qualifies the current Claude/Codex pins and revised model environments. Two example images:

```bash
docker build --build-arg HARNESS_VERSION=2.1.319 \
  -t harness-lab/claude-code:2.1.319 \
  -f experiments/claude-code/Dockerfile experiments/claude-code

docker build --build-arg HARNESS_VERSION=1.18.29 \
  -t harness-lab/opencode:1.18.29 \
  -f experiments/opencode/Dockerfile experiments/opencode

docker pull node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
test -e .env || cp .env.example .env
```

Set the selected provider's key in `.env`; `.env.example` and `npm run harnesses` list the required variable names. The coordinator passes only credentials from the selected profile, does not execute shell substitutions, and does not inherit credentials from your home directory. For Pi, mini-SWE-agent and OpenHands, select the provider during preparation with `--provider anthropic` or `--provider openai`. Every record captures built image IDs; use one image for a series instead of rebuilding between repeats. `--proxy-image` selects another prepared Node.js image, whose ID is also recorded.

Other pinned images:

| `--harness` | Image/tag | `.env` key |
| --- | --- | --- |
| `codex` | `harness-lab/codex:0.167.0` | `CODEX_API_KEY` |
| `antigravity-cli` | `harness-lab/antigravity-cli:1.2.7` | `GEMINI_API_KEY` |
| `pi` | `harness-lab/pi:0.73.1` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| `mini-swe-agent` | `harness-lab/mini-swe-agent:2.4.6` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| `openhands` | `harness-lab/openhands:1.49.2` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| `copilot-cli` | `harness-lab/copilot-cli:1.0.86` | `COPILOT_GITHUB_TOKEN` |
| `amp` | `harness-lab/amp:0.0.1789920039-gafe14b` | `AMP_API_KEY` |

Build with `docker build --build-arg HARNESS_VERSION=<pin> -t harness-lab/<harness>:<pin> experiments/<harness>`. Details, primary sources and offline smoke results are in the [matrix](docs/harnesses.md) and each harness README. These tags were also built in the original operator's Docker environment.

## First run

Example for a local task without changing web sources:

```bash
npm run new-run -- --harness claude-code --agent a2-janitor --task T002
RUN_ID='<identifier printed by new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" \
  --image harness-lab/claude-code:2.1.319 \
  --model '<exact model ID in the Anthropic API>' --timeout 900
```

`new-run` never overwrites an existing run, including a repeated `--n`. `prepare-run` executes setup in a separate directory and seals the specification, contract, configuration, coordinator code and initial tree. `run` verifies that they have not changed, determines the CLI version inside the image and starts the agent. Turn and USD limits come from the task. Timeout is a hard external limit in seconds. Output artifacts are in `results/runs/$RUN_ID/artifacts/`; traces are in `trace/`.

Successful execution results in **awaiting_review**, not `pass`. A nonzero exit, timeout, model switch or coordinator error produces **aborted**. Every retry needs a new record so failed attempts are not lost. If the coordinator itself is killed with SIGKILL, the record stays `running` and containers stay alive. `npm run reconcile` without arguments lists those records and containers labeled `harness-lab=true`. `npm run reconcile -- --run "$RUN_ID"` removes the run containers and network named in `trace/runtime.json`, saves their logs to `trace/recovered-*.log` with the key redacted, and marks the run `aborted` with reason `coordinator_lost`. It refuses while the coordinator PID is alive. Runs are not resumed; a retry is a new record.

For the other eight harnesses, select the appropriate harness/image and add `--budget-mode observed`: a hard USD boundary has not been verified for them. This is a research run that deviates from the contract budget; reports separate it from `hard` mode. CLIs without native turn limits still have the external timeout; SDKs apply their own step limits. Unknown metrics are never replaced with zero.

Codex example:

```bash
npm run new-run -- --harness codex --agent a2-janitor --task T002 --provider openai
RUN_ID='<new identifier>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/codex:0.167.0 \
  --model '<available exact model ID>' --budget-mode observed
```

Amp does not select an exact underlying model: use `--model managed:low`, `managed:medium`, `managed:high` or `managed:ultra`. The record retains the managed selector and `model.lock=true`; these cannot be compared with an exact model as matching conditions. Other harnesses require an explicit model ID or supported selector; independent verification of the response model is recorded separately.

## Independent evaluation

The hidden script or rubric is applied **by the operator outside the agent container**. The coordinator neither reads hidden checks nor passes them to the model. Both evaluation methods use the same JSON format. T002 is marked `hidden-check` in advance, T001/T003 are marked `rubric`; the T001 evaluator considers both the script and rubric. Put the check/rubric version and observations in `check_output`, and the evaluator's name in `evaluator`.

Create a draft after execution:

```bash
node scripts/evaluation-template.mjs --run "$RUN_ID" \
  > "results/runs/$RUN_ID/evaluation.draft.json"
```

Fill in `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` and, if needed, `human_notes`. Do not change hashes: they bind the evaluation to the artifacts and final workspace. Required files are checked separately; an external judge performs the substantive evaluation.

```bash
npm run judge-run -- --run "$RUN_ID" \
  --evaluation "results/runs/$RUN_ID/evaluation.draft.json"
npm run check
npm run compare
npm run compare -- --out results/compare/latest.md
```

`compare` without arguments prints JSON. With `--out`, it writes a report inside the repository but outside `results/runs/`; a `.md` extension or `--format markdown` produces grouped tables using the same facts, without ranking different groups.

`judge-run` rejects changed inputs/outputs and evaluations from another record. Import changes the state to `completed`. The original evaluation JSON is saved in the trace. T002 also saves `trace/change.patch` against the initial commit; the working Git repository remains in the ignored workspace.

## Repeats, sources and ablation

Create three separate records with the same model, image, task, variant, budget and timeout. `compare` groups by conditions, reports metric coverage and forms non-overlapping triples in run-ID order. Two runs do not become `pass^3`; started but aborted executions remain failures. `planned`, `prepared`, `running` and `awaiting_review` are shown separately. Select specific records with `npm run compare -- --runs ID1,ID2,ID3`.

For T001, set the date using `prepare-run --as-of YYYY-MM-DD`. Live pages can change, so such a run collects an initial archive rather than establishing a controlled comparison. GET responses are saved in `trace/sources.jsonl` and delivered to the agent through the gateway. For a subsequent matching series:

```bash
npm run prepare-run -- --run "$RUN_ID" --as-of 2026-09-20 \
  --source-archive 'results/runs/<source-run>/trace/sources.jsonl'
```

All compared runs must use one archive. It is copied into the input snapshot; a page absent from the archive is not fetched again. Seed URLs and discovered depth-1 links are available. The model API remains online.

You can capture an archive without running an agent:

```bash
npm run capture-sources -- --task T001 --as-of 2026-11-05
```

The command runs the task's `setup.sh` in a temporary directory, fetches every seed URL from `sources.txt` using the same `fetchPublic` as the gateway, and writes `tasks/T001-dossier-from-sources/archive/sources-<date>.jsonl` with an adjacent manifest recording successes, failures and SHA-256. Existing archives are never overwritten. Depth-1 links are not archived, so replay treats them as unavailable. The captured archive represents pages at capture time, not at the requested cutoff date.

For ablation, create a new record and prepare it with `--variant without-spec`: the specification is excluded from the prompt, while the contract and mandatory boundaries remain. This does not delete specification files naturally present in the T003 repository being audited. Compare separate baseline/without-spec groups; record a component's effect in the ledger only after measuring it.

## Checks and repository map

```bash
mise run verify             # test, test:python, check in sequence
mise run test:docker
mise run test:local-docker
mise run compare -- --out results/compare/latest.md
```

Individual `mise run test`, `mise run test:python` and `mise run check` tasks call the same npm scripts. Ordinary tests do not use APIs or hidden checks. `test:python` runs Apple exporter regressions and all fixture tests, including concurrent load and serving noise, through a local HTTP mock. Docker smoke is a separate opt-in using a local proxy image and synthetic workload. `test:local-docker` additionally requires the Pi image version from `experiments/pi/harness.json`: it checks the real SDK, tool calls, broker, request cancellation and timeout without a model or GPU. For Colima, the temporary mount is created under the home directory; set `HARNESS_DOCKER_TMPDIR` to choose the general smoke location.

`npm run check` also compares each harness pin in four places (profile, Dockerfile, this page and harness README) and reads turn/USD limits from task contracts. Every `tasks/<id>/task.json` descriptor is validated: the agent and `setup.sh` must exist, and workspace kind, evaluation method, network domains and setup arguments must be valid. The pin is defined once in `experiments/<harness>/harness.json`: Dockerfile asserts it, and `run` compares it with the image-reported version, aborting before the agent starts if they differ.

### CI and report publication

The [workflow](.github/workflows/ci.yml) runs on PRs, pushes to `main`, manual dispatch and Mondays at 06:23 UTC. It has only `contents: read`, receives no model credentials and does not run agent experiments. New commits cancel outdated runs of the same PR; `main` checks are not canceled.

| Job | Conditions and output |
| --- | --- |
| `plan` | Selects harnesses from `harness.json` using the Git diff; initial and forced pushes check every harness without requiring old history. Other history-read failures stop the job. |
| `check` | Every event: the `default` environment from `mise.toml` and `node22` with Node 22.0.0 (the support floor), running `test` and `check`. The default environment also runs Python and `test:python` from the same mise configuration. |
| `docker` | On `main`, manual/scheduled runs and PRs changing container infrastructure or harnesses: a real boundary smoke test. |
| `images` | PR/push: changed harnesses; manual/scheduled: all nine. Pinned builds and offline installed-version checks; Pi also runs `test:local-docker`. Up to three builds at a time. |
| `compare` | After successful checks on a push to `main`: `results/compare/latest.md` in a `comparison-<commit>-<attempt>` artifact retained for 90 days, and in the job summary. The file is not committed automatically. |

Changes to `.github/`, `scripts/`, `tests/`, `experiments/common/`, npm or mise configuration rebuild every harness. Changes to a specific harness rebuild its image only. Documentation and `measurements/` do not require builds. `plan` fetches history with `filter: blob:none`: merge bases are available without downloading old binary measurements. Each job has a 5–30 minute timeout; test/build logs are retained for 14 days, including failed runs. All jobs install host tools through pinned `mise-action`; Python is enabled only in the primary `check`, and a separate `node22` cache accounts for the `MISE_NODE_VERSION` override. Base and proxy images are pinned by multi-architecture digest; Actions use full commit SHAs. Update them in separate, reviewable changes. A digest fixes the base image but does not make mutable apt/npm/pip registries reproducible archives: a full weekly build checks that installation still works.

The same build and smoke commands work locally without GitHub:

```bash
node .github/scripts/harness-ci.mjs build pi
node .github/scripts/harness-ci.mjs smoke pi
GITHUB_EVENT_NAME=workflow_dispatch node .github/scripts/harness-ci.mjs plan
```

Builds download public dependencies; smoke runs only `version_command` in a container without network access. `compare` uses recorded results and keeps different conditions separate. Successful CI is not itself a measurement of agent quality.

- `docs/method.md` — protocol and limits of interpretation.
- `docs/roadmap.md` — experiment extensions: campaigns, ablations, new tasks, boundaries and ordered steps.
- `docs/harnesses.md` — implemented adapters and candidates with primary sources.
- `docs/harness-ledger.md` — added components and the basis for ablation.
- `docs/local-models.md`, `experiments/local-models/` — research plan, catalog, memory estimates and actual Ryzen/Apple measurement reports.
- `agents/` and `tasks/` — independent specifications, immutable task contracts and machine-readable `task.json` descriptors (agent, workspace kind, branch, evaluation, artifacts, network).
- `experiments/<harness>/` — adapters, configurations, images and notes.
- `results/schema.json`, `scripts/` — record format and coordinator.

The credential boundary has limits: the API key is in the harness environment and accessible to processes inside its container. The host `.env` file is not mounted. Untrusted tasks that must hide the key even from the agent's bash require a separate credential broker. Evaluated Pi/local/T002 results do not establish the quality of other harnesses. Cloud episodes, completeness of some usage fields and availability of a particular model in an account remain **unverified**. Preparation and offline installation/SDK checks are recorded for all nine adapters; consult their READMEs and the matrix for verification.

Code license: [MIT](LICENSE), copyright © 2026 polomodov.
History sanitization, archive integrity and old-reference limits are documented in [publication and archive provenance](docs/publication.md).
