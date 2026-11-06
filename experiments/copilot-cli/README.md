# GitHub Copilot CLI: lab adapter

Practical assignment: [LAB18 — Copilot CLI, model selector, and AI credits](../../docs/labs/LAB18-copilot-cli.md). Includes a native-cache smoke test, full T002 with external judging, and additional series.

A local CLI adapter implements the shared preparation, container execution, external evaluation, and comparison lifecycle. Verified version: `@github/copilot@1.0.86`, checked on **2026-09-20**. No actual model runs have been performed yet; this adapter does not launch the cloud Copilot coding agent.

## Build and run

```bash
docker build --build-arg HARNESS_VERSION=1.0.86 -t harness-lab/copilot-cli:1.0.86 experiments/copilot-cli
docker run --rm --network none harness-lab/copilot-cli:1.0.86 copilot --help
npm run new-run -- --harness copilot-cli --harness-version 1.0.86 --provider copilot --model gpt-5.4 --agent a1-dossier --task T001
RUN_ID='<identifier from new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/copilot-cli:1.0.86 --model gpt-5.4 --budget-mode observed
npm run evaluation-template -- --run "$RUN_ID"
```

`gpt-5.4` is an example identifier in the Copilot catalog; availability depends on the subscription. The selected name is recorded as a request to the service. It does not establish an exact weights version or equivalence to a model available through another provider’s direct API. `auto` is forbidden. [Model selection and non-interactive mode](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference).

The coordinator reads only `COPILOT_GITHUB_TOKEN` from `.env`; the file is not passed to the agent. A supported GitHub token with Copilot access is required, for example a fine-grained PAT with the Copilot Requests permission; classic PATs are unsupported. [Authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli).

## Experimental conditions

The command uses `--prompt`, JSONL, automatic tool permission inside the outer container, and `--no-ask-user`. Auto-updates, repository instruction loading, built-in GitHub MCP, remote control, and remote export are disabled. The specification arrives through the shared prompt, so the `without-spec` variant cannot regain it through local instructions. The full argv is preserved in the adapter snapshot. [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).

The CLI counts AI credits / premium requests, but these numbers must not be recorded as USD. There is no hard USD limit; `--budget-mode observed` is required. `--max-autopilot-continues` limits autopilot continuations, not model turns; the adapter does not substitute it for `turns`. The external timeout applies independently.

`harness.json` allows HTTPS CONNECT only to `github.com`, `api.github.com`, `api.githubcopilot.com`, and the three plan-specific addresses `api.individual.githubcopilot.com`, `api.business.githubcopilot.com`, and `api.enterprise.githubcopilot.com`. CLI support for `HTTP_PROXY` / `HTTPS_PROXY` was verified with `copilot help environment`. The addresses match the [official network access list](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference) and [GitHub’s plan-based routing](https://github.blog/changelog/2026-03-02-network-configuration-changes-for-copilot-coding-agent-now-in-effect/). Completeness for an authenticated CLI episode is **unverified**: inspect the network trace on the first run; do not automatically open a wildcard. GHE.com and BYOK require separate profiles.

The CLI unpacks a native addon into its cache. The profile therefore enables a separate executable tmpfs at `/tmp/harness-native`, capped at 512 MiB; `TMPDIR` and `XDG_CACHE_HOME` point there, while the main `/tmp` remains `noexec`. This is required even for the version check. During offline `--version` on Linux arm64, the cache occupied 161284 KiB (about 157.5 MiB); 128 MiB is insufficient. Native tmpfs limits of 256 and 512 MiB were tested with a 512 MiB `/tmp` and 2 GiB container memory; 512 MiB leaves startup headroom. Peak cgroup memory with 256 MiB was about 381.6 MiB. This measures CLI startup, not real episode memory usage. Hidden checks and lab files remain absent from the container.

## Trace and validation

The JSONL formatter and filter in the installed `1.0.86` package’s `app.js` were checked: `assistant.usage` and `session.shutdown` are excluded from stdout. The final message contains `type: result`, `sessionId`, a numeric `exitCode`, and premium-request/time statistics. The parser uses this terminator, not Claude’s identically named schema. Observed model ID, token totals, and USD remain unknown. Complete `assistant.turn_start` / `assistant.turn_end` pairs between `session.start` and `result` supply the main agent’s turn count; duplicate IDs are not counted again. The event schema is documented in the [official SDK](https://github.com/github/copilot-sdk/blob/main/nodejs/src/generated/session-events.ts).

```bash
node --test experiments/copilot-cli/adapter.test.mjs
```

On Docker Engine `29.5.2`, Linux arm64, the build, `--version`, help, adapter arguments, and missing-key rejection were checked without network access. Native cache was checked with `--read-only`, UID `1000`, `cap-drop ALL`, and `no-new-privileges`. Image: `sha256:17da822b2853ced41f6986f0f27f10c9e66dd64498bc1cb8be8f612cb5925474`. This is an infrastructure check without an API request, not a task result. Component rationale: [L014 in the ledger](../../docs/harness-ledger.md).
