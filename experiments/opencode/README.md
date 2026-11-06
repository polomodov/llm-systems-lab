# OpenCode: lab adapter

Step-by-step assignment covering configuration layers, a real T002, unknown metrics, and independent evaluation: [LAB12 — OpenCode](../../docs/labs/LAB12-opencode.md).

The adapter supports the CLI v1 interface, checked on **2026-09-20**. Product documentation does not verify a particular image; actual execution and its version must be included in a run record.

An infrastructure check ran on 2026-09-20 using Docker Engine 29.5.2 / Linux arm64: the image built, `opencode --version` returned `1.18.29`, and `opencode run --help` succeeded with network access disabled. The package contains `postinstall`; the Dockerfile runs it inside the image. No keys were passed and no model requests were made.

```bash
docker build --build-arg HARNESS_VERSION=1.18.29 -t harness-lab/opencode:1.18.29 -f experiments/opencode/Dockerfile experiments/opencode
docker run --rm --network none harness-lab/opencode:1.18.29 opencode --version
docker run --rm --network none harness-lab/opencode:1.18.29 opencode run --help
```

Verified local image ID: `sha256:d94ef97e160c572b519c2bc03c8b8939a010326ed4907e9989167c0285bb8228`. This checks installation, not a successful agent episode. Use one image for a repeat series; rebuilding system packages can change its ID.

## Execution and budget limits

The adapter does not yet have a verified hard OpenCode cost limit. A normal run with `hard` policy is rejected before calling the model. A research run must explicitly select `--budget-mode observed`; this departs from the task’s mandatory budget and must not be mixed with comparable `hard` runs.

The [root instructions](../../README.md) describe building an image with a pinned version. Anthropic is supported, with the orchestrator passing its key from `.env`.

```bash
npm run new-run -- --harness opencode --agent a1-dossier --task T001
RUN_ID='<identifier printed by new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/opencode:1.18.29 --model '<exact model ID>' --budget-mode observed
npm run judge-run -- --run "$RUN_ID" --evaluation '<independent evaluation JSON>'
npm run check
```

`observed` does not guarantee a final cost: the current adapter explicitly marks it unavailable. A timeout and step limit do not replace a dollar limit. Artifact suitability is evaluated separately after execution.

## Command and configuration

`adapter.mjs` invokes `opencode run --model anthropic/<ID> --agent build --format json`; the prompt is passed as one argument without a shell. Configuration is selected with `OPENCODE_CONFIG=/control/opencode.json`; auto-updates are disabled with `OPENCODE_DISABLE_AUTOUPDATE=true`. [CLI v1](https://opencode.ai/docs/cli/).

In `OPENCODE_CONFIG_CONTENT`, the adapter sets the main and small model IDs and `agent.build.steps`. This runtime layer overrides the settings file. [Configuration precedence](https://opencode.ai/docs/config/). On reaching `steps`, OpenCode asks the model to finish with a text answer; this limits agent actions and is not equivalent to Claude Code’s `max-turns`. [Agent max steps](https://opencode.ai/docs/agents/#max-steps).

`opencode.json` sets `read`, `edit`, `bash`, and other permissions. This configuration controls tools inside the container. Hidden checks are isolated by keeping the repository directory out of its mounts. [Permissions documentation](https://opencode.ai/docs/permissions/).

The orchestrator configures networking. OpenCode supports `HTTP_PROXY` and `HTTPS_PROXY`; exclude the local server using `NO_PROXY=localhost,127.0.0.1`. [Network documentation](https://opencode.ai/docs/network/).

## Trace and unknown metrics

JSONL is saved in full. The adapter extracts the session ID and observed stop reason, but does not present a sum of `step_finish` events as a trustworthy session total. The stream may lack a terminal event; complete accounting of auxiliary requests is also unverified. `turns`, cost, and tokens remain unknown with explanations in `metrics_unavailable`. [CLI source](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/cli/cmd/run.ts), [missing-event report](https://github.com/anomalyco/opencode/issues/26855).

The next integration step is a verified export from the same isolated session, tests for the specific version, and verification of model, cost, and usage. In CLI v1, the command is `opencode export <sessionID>`; do not copy `opencode session export` from v2 documentation. Automatic export is not implemented yet.

```bash
node --test experiments/opencode/adapter.test.mjs
```

Record component changes in the [ledger](../../docs/harness-ledger.md) and results in `NOTES.md` with the run ID. Compare conditions with the shared `npm run compare -- --runs <run-id-1>,<run-id-2>` command; preserve research deviations in the report.
