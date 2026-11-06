# Shared experiment infrastructure

The coordinator executes the code in this directory, not the task agent.

- `entrypoint.mjs` starts the pinned adapter and forwards its original event stream to the coordinator.
- `egress.mjs` is the only route out of the internal Docker network. CONNECT is allowed only to the model API and, for T002, the npm registry. For T001, the GET gateway permits initial URLs and depth-1 links; private addresses are forbidden, responses are limited to 4 MiB, and the total archive to 64 MiB.
- Source snapshots are saved outside the agent mount. `prepare-run --source-archive ...` forbids new downloads and replays saved responses.

The agent container does not receive the lab source repository, `.env`, Docker socket, log, run.json, or hidden checks. For T001/T003, the working directory is read-only and `artifacts/` is writable. For T002, the entire separate workspace is writable. The root filesystem is read-only, the user is unprivileged, capabilities are dropped, and CPU/RAM/PID/time limits are set. Amp/Copilot with native_cache=true additionally receive a separate 512 MiB executable tmpfs at /tmp/harness-native for their native CLI libraries. Host credentials are not mounted.

Only the selected provider credentials from `.env`, listed in sealed harness.json, are passed to the harness environment; other keys are not passed. This does not protect the key from the agent’s bash inside the same container: strong credential isolation requires a separate API broker. Outbound API requests are restricted by an allowlist; exact key values are redacted from raw CLI responses before recording. Do not use real secrets as task data. Components and limitations are recorded in `docs/harness-ledger.md`.

The gateway constrains the network route and source retrieval method; it is not universal protection against every side channel and does not verify the truth of agent claims. T003 receives a configuration copy, not hidden checks; audited scripts remain untrusted data.
