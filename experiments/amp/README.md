# Amp: lab adapter

Practical assignment: [LAB19 — Amp, managed mode, and independent evaluation](../../docs/labs/LAB19-amp.md). Includes a native-cache smoke test, full T002 with external judging, and additional series.

A local CLI adapter is implemented with explicitly identified managed model routing. Verified version: `@ampcode/cli@0.0.1789920039-gafe14b`, checked on **2026-09-20**. No actual model episodes have been run yet.

## Build and run

```bash
docker build --build-arg HARNESS_VERSION=0.0.1789920039-gafe14b -t harness-lab/amp:0.0.1789920039-gafe14b experiments/amp
docker run --rm --network none harness-lab/amp:0.0.1789920039-gafe14b amp --help
npm run new-run -- --harness amp --harness-version 0.0.1789920039-gafe14b --provider amp --model managed:medium --agent a1-dossier --task T001
RUN_ID='<identifier from new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/amp:0.0.1789920039-gafe14b --model managed:medium --budget-mode observed
npm run evaluation-template -- --run "$RUN_ID"
```

The coordinator reads `AMP_API_KEY` from `.env`. Use an access token from Amp settings, not a short-lived interactive-login session token. Without a key, the CLI starts a login flow even in execute mode; the coordinator must stop such a launch before starting the container. [Execute mode and authentication](https://ampcode.com/docs/cli/execute-mode).

The profile accepts only `managed:low`, `managed:medium`, `managed:high`, and `managed:ultra`. These values were checked against the pinned version’s `--help`. The coordinator passes the unprefixed mode name to the adapter; the CLI receives `--mode` and `--executor local`. Models, system instructions, tools, and subagents depend on Amp routing. Do not record the mode name as an observed model ID or treat such an episode as a comparison of one fixed model across harnesses. [Amp modes](https://ampcode.com/docs/the-dial), [models and subagents](https://ampcode.com/docs/models-and-subagents).

## Experimental conditions

`settings.json` is loaded from `/control/amp-settings.json`: it permits commands inside the outer container boundary and disables updates, remote thread creation, and external skill directories. Separate flags disable IDE context, notifications, and the remote terminal, and set private visibility. Workspace and service settings may affect Amp; their actual contents and whether all account-connected plugins/MCP are disabled remain **unverified** until the first episode. [Configuration](https://ampcode.com/docs/cli/settings), [settings schema](https://ampcode.com/cli-settings.schema.json).

`amp.proxy=http://egress:8080` routes service requests through the shared gateway. `AMP_URL` is pinned to `https://ampcode.com/`, and only the exact domain `ampcode.com` is allowed; both settings were confirmed by the installed CLI’s help. Completeness of the network list for an authenticated local episode is **unverified**. Add addresses only after checking a primary source and network trace, not through a wildcard. Installation uses the npm registry; packages download during image build, separately from the episode network.

The package requires `postinstall`, which places the native binary from the package of the same version. Bun extracts a native addon into a temporary directory: with `noexec /tmp`, even `--version` fails to load it. The `native_cache` profile enables only a separate executable tmpfs at `/tmp/harness-native`, capped at 512 MiB, and sets `TMPDIR` / `XDG_CACHE_HOME`; the main `/tmp` remains `noexec`. During offline `--version`, the cache occupied 2672 KiB (about 2.6 MiB), and peak cgroup memory was about 153.8 MiB. Tested limits: 512 MiB `/tmp`, 512 MiB native tmpfs, and 2 GiB container memory. This measures CLI startup, not memory for a real episode; tmpfs consumes memory as it fills. This does not expose lab data to the agent.

This adapter has no hard USD or turn-count limits, so `--budget-mode observed` is required. The coordinator enforces the timeout. Managed routing and an observed budget must be included when grouping comparisons.

## Trace and validation

The parser reads the [official stream-json schema](https://ampcode.com/docs/cli/streaming-json). Final `result.num_turns` supplies turns; `result.usage`, if returned, supplies tokens. Input is counted only when the complete set of input/cache buckets is available; assistant usage is not added again. The documented result example lacks usage, so unknown metrics are allowed with an explanation. The schema does not establish the actual routed model IDs or cost in USD; these fields remain unknown. `error_max_turns` / `error_during_execution` errors are distinguished from truncation.

```bash
node --test experiments/amp/adapter.test.mjs
```

On Docker Engine `29.5.2`, Linux arm64, the build, `--version`, help, and recognition of adapter arguments were checked without network access or keys. The version check passes with a read-only root, UID `1000`, `cap-drop ALL`, `no-new-privileges`, and a separate native tmpfs. Image: `sha256:31b165957d2ed53eb0fee4474e7dedb347b31aa3acc146a103c0aad5b3c8be49`. No model call was made; these checks are not an experimental run. Component rationale: [L015 in the ledger](../../docs/harness-ledger.md).
