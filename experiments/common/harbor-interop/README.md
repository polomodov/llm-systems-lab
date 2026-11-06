# Harbor interoperability experiment

This is a local infrastructure experiment, separate from the registered lab
campaigns. It exports one historical Pi run for inspection and exercises a
synthetic task with a separate verifier. It does not execute a model, qualify a
campaign harness, reproduce the historical task, or produce a Harbor-Index score.

Evidence is recorded in [`export-results.json`](export-results.json) and
[`synthetic-results.json`](synthetic-results.json). The source run and campaign
files were byte-for-byte unchanged across 161 protected files. Harbor's official
ATIF validator and local browser inspection accepted the export.

## Pinned environment

[`lock.json`](lock.json) pins Harbor 0.25.0 at commit
`ff2a1ef48070a8df374669138e4d4db79b77f013`, its upstream Python and viewer dependency
locks, Python 3.12.12, Node 24.13.1, uv 0.13.7 and Bun 1.4.4. The checkout,
environments, frontend build and exports stay in ignored directories here.
The bootstrap uses the upstream frozen Bun lock because the npm lock in this
revision fails `npm ci` on missing platform-specific optional dependencies.

From the repository root:

```bash
~/.local/bin/mise exec -- python experiments/common/harbor-interop/bootstrap.py
~/.local/bin/mise exec -- python experiments/common/harbor-interop/setup-docker-plugins.py
```

Setup downloads public dependencies and builds the viewer. The Docker plugin
helper installs SHA-256-verified Buildx and Compose binaries only under this
experiment; it does not change global Docker configuration. Its binaries are
qualified for macOS arm64. Other hosts need their own qualified plugins. The
synthetic runner uses a private HOME and Docker configuration and accepts only a
local Unix Docker socket; no host credentials are forwarded. Harbor telemetry
is disabled.

## Historical export and viewer

```bash
experiments/common/harbor-interop/.venv/bin/python \
  experiments/common/harbor-interop/export-run.py \
  --run-dir results/runs/2026-10-15-pi-a2-janitor-t002-repo-janitor \
  --jobs-dir experiments/common/harbor-interop/output/jobs

experiments/common/harbor-interop/.venv/bin/python \
  experiments/common/harbor-interop/view.py --port 8765
```

Open <http://127.0.0.1:8765>. Select the derived job, its Rollouts tab, then the
historical trial. Existing exports are never overwritten; use another jobs
directory for an additional export and pass it to `view.py --jobs`.

The qualified source is Pi SDK 0.73.1, completed with a binary historical verdict.
Other harnesses, trace formats, partial verdicts and unfinished runs are rejected.
Terminal `message_end` events become ATIF messages; tool results join their
matching calls. Incremental events remain in the copied raw trace and are not
counted twice. Original Russian inputs remain in their source language.

The export has **29 ATIF steps, 28 assistant messages and 27 linked tool calls and
results**. Authoritative totals remain **172,863 input tokens, 5,225 output tokens,
and unknown cost (`null`)**. Requested `local/lab-model` is displayed as the model;
the original observed identity and its evidence remain separate metadata. The
reward of 1 represents the original recorded pass, not a new verifier decision.
Source copies, manifest/evaluation/artifact hash checks, and per-file SHA-256
provenance accompany the export. The absent historical workspace is not rebuilt.

Keep these viewer interpretation limits in mind:

- ATIF steps and lab turns have different definitions. The original loop record
  and missing-metric explanations remain in `extra` metadata.
- The original recorded execution time is 851 seconds. The source execution
  timestamps span 856.492 seconds, while the trial extends through the recorded
  evaluation time. Harbor can display that full interval as 15m 42s alongside
  its timing chart. It is not a replacement for `loop.wall_clock_s`.
- The authoritative aggregate cache count is unavailable. Harbor's generic
  chart label “Uncached Input” must not be interpreted as a new cache measurement.
- Per-message SDK usage and authoritative aggregate run usage remain separate;
  SDK placeholder prices are not monetary measurements.

[`view.py`](view.py) serves the upstream UI but retains only local inspection
routes. Launch, LLM summaries, uploads, authentication, remote sources, editor
streaming, inferred pricing and all writes are unavailable. Some upstream UI
buttons remain visible; their endpoints are disabled. The export is data only,
with a non-runnable task path and verification disabled in its viewer envelopes.

## Synthetic task and isolated verification

[`task/`](task/) is a new package containing a small normalization instruction,
input data, a reference shell solution, and an independent expected-result
fixture. It does not read or modify any existing lab task or hidden check.

The agent image contains only public inputs. A separately built verifier image
owns the expected output and evaluator. Only the declared `result.json` artifact
crosses the boundary. The reference solution must pass; no-op, incorrect output,
and forged verifier files/reward in the agent container must fail.

The actual controls produced the following outcomes, with no Harbor exceptions:

| Control | Reward | Interpretation |
| --- | --- | --- |
| Reference solution (`oracle`) | 1 | Correct artifact accepted |
| No output (`nop`) | 0 | Missing output rejected |
| Incorrect output | 0 | Incorrect artifact rejected |
| Forged local tests, fixture and reward | 0 | Agent-side tampering did not alter the separate verifier |

Harbor mounts a verifier-log directory into the agent, then clears it before
grading. The tampering control deliberately writes a fake reward there; the
separate verifier still rejects its incorrect artifact. This is evidence for
the tested boundary, not a claim that no shared writable path exists.

```bash
experiments/common/harbor-interop/.venv/bin/python \
  experiments/common/harbor-interop/synthetic_controls.py \
  --docker-host "unix://$HOME/.colima/default/docker.sock" \
  --docker-plugin-dir "$PWD/experiments/common/harbor-interop/.cache/docker-plugins"
```

The command uses Harbor's built-in `oracle` and `nop` agents, plus deterministic
no-model controls. It never configures a provider, paid judge, cloud sandbox, or
model. It creates raw Harbor infrastructure trials under
`.cache/synthetic-runs/` and a compact `synthetic-results.json` report. These are
not autonomous-agent results and do not create lab `results/runs` entries.
The runner requires the same durable task-lock digest, directory checksum and
component hashes before and after every control. Python bytecode is excluded
from Harbor packaging and the verifier Docker build. The initial diagnostic
series had one directory-checksum change caused by bytecode; its durable task
digest was identical across all four controls. The final package was verified
again after adding these exclusions.

Both sides select Harbor's native `no-network` policy. Its Docker implementation
uses a transparent egress sidecar; the policy still permits resolver DNS and
ICMP. It is not Docker `network_mode=none`. A TCP handshake can reach the local
proxy, so a handshake alone cannot prove external access or denial. The control
report records the actual application-level probes and their scope.

## Validation and adoption decision

```bash
experiments/common/harbor-interop/.venv/bin/python -m unittest discover \
  -s experiments/common/harbor-interop -p 'test_*.py' -v
~/.local/bin/mise exec -- npm run check
```

The mapping tests cover duplicate/incomplete events, tool-call linkage, unknown
metrics, unsafe evidence paths, source tampering, overwrite rejection and Harbor
schema/scanner compatibility. Verifier tests cover correct, missing, incorrect,
invalid JSON, oversized and symlink artifacts. Viewer tests verify
that local reads work while launch, summaries, upload and deletion are blocked.
Nine unit tests pass (the artifact test includes seven cases); the additional
test verifies that generated bytecode cannot change the task checksum. Raw diagnostic
attempts remain under the ignored cache, including the earlier TCP-only probe;
they are not model results or selectively replaced campaign attempts.

This proves a narrow interoperability path. It does not establish native
configuration parity, complete accounting for other harnesses, or the security
of arbitrary Harbor tasks. Keep the existing campaign coordinator and frozen
conditions. A future extension can qualify another trace format or a single
external deterministic task before considering orchestration migration.

Sources: [task format](https://docs.harborframework.com/tasks/overview),
[separate verifier](https://docs.harborframework.com/tasks/separate-verifier),
[ATIF](https://docs.harborframework.com/agents/atif),
[pinned source](https://github.com/harbor-framework/harbor/tree/ff2a1ef48070a8df374669138e4d4db79b77f013).
