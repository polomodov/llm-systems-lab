# LAB08. Local provider bridge and reproducible inference records

## Profile

| Field | Value |
| --- | --- |
| Lab type | Engineering: design, implement, and verify an integration; not just run measurements |
| Time | Estimate: 12–20 hours of development and verification after the server is ready; SDK incompatibility work is accounted for separately |
| Prerequisites | LAB01 and either LAB05 (Ryzen/Linux) or LAB32 (Apple/macOS); machine profile, pinned weights, and working protocol smoke tests |
| Readiness | Pi/T002 bridge and metadata implemented for native llama.cpp Metal/macOS and ROCm/Linux. The [Ryzen pilot](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-ryzen-linux-bridge/report.md) has independent verdicts, but its aggregate report is blocked under preregistration; the [Apple pilot](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-native-requalification-20261010/report.md) awaits evaluation. Other adapters are **pending** |
| Minimum scope | One backend, one model, one Pi or mini-SWE-agent adapter, a synthetic matrix, and one real T002 pilot |
| Extension | Connect the remaining primary local harnesses: Pi, mini-SWE-agent, OpenCode, OpenHands |

## Objective

Connect an isolated agent container to a trusted local inference service while preserving denial of access to the rest of the network and experiment reproducibility. The record must distinguish identical model aliases backed by different weights, engines, contexts, and settings.

## Hypothesis

A dedicated route to one inference endpoint allows the selected harness's native tool loop to run without expanding the agent's network permissions. If a material inference condition changes, the coordinator either refuses to run the sealed configuration or creates a new comparison group; the previous model alias must not hide the change.

Falsification criteria: access to another address/port, administrative API, or cloud fallback; a lost tool-result; two different weights configurations entering one group; missing usage reported as zero.

## Preparation

For Apple, the inference server runs natively on macOS; the container contains only the agent harness. Connecting Docker Desktop to the host endpoint must be designed and tested separately: container `127.0.0.1` is not the Mac's loopback, and the name `host.docker.internal` alone provides no isolation. The bridge must allow only the pinned endpoint and pass the same B01–B10 matrix. Do not expose the server to the LAN instead of performing this check. An MLX server alias and MLX artifact manifest require the same identity controls as GGUF. Until the bridge is accepted, Apple agent series remain `pending/blocked`.

Create the lab directory from the repository root:

```bash
npm run lab:new -- --lab LAB08 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB08-my-session'
npm run harnesses
npm test
npm run check
```

Choose your testbed's catalog; the machine is not selected automatically:

```bash
# Entry through LAB05: Ryzen / Linux
npm run local:engines -- --hardware ryzen-ai-max-395-128gb-linux
# Entry through LAB32: Apple / macOS
npm run local:engines -- --hardware apple-m5-max-128gb-macos
```

Record the selected hardware ID and reference the admitted protocol-smoke condition in the report: LAB05 for Ryzen or LAB32 for Apple. Partial context admission does not extend to other contexts or reasoning settings.

`report.md`, `measurements.tsv`, the draft `manifest.json`, and `raw/` belong to the educational lab. A real agent attempt receives a separate `results/runs/<run-id>/run.json`. The lab report does not replace it.

Read `scripts/lib/harnesses.mjs`, `scripts/prepare-run.mjs`, `scripts/run.mjs`, `experiments/common/egress.mjs`, `results/schema.json`, `scripts/lib/records.mjs`, and `scripts/compare.mjs`. Do not open hidden checks or modify `tasks/*/task.md` contracts. Prepare one available model from LAB05 (Ryzen) or LAB32 (Apple), with pinned artifacts and passing chat/tool/cancel/overflow/recovery checks for the exact selected deployment; the server must have no built-in shell/tools and no mount of the original lab repository.

## Procedure

1. **Describe the original restriction and current implementation.** In the report, reference the verified Git commit and code locations: a cloud profile contains `connect_domains`, CONNECT permits pinned domains on 443, and the public resolver rejects private/reserved IPs. The local provider uses a separate bridge and a versioned `local_inference` fingerprint. Record the selected model, harness, and server. The `prepare-run --provider local --local-deployment ...` and `run --provider local` interface is described in the [Pi README](../../experiments/pi/README.md); it is limited to Pi/T002 and controlled native llama.cpp on Metal/macOS or ROCm/Linux, starting its own pinned server. Do not bypass this boundary by substituting a LAN address for a cloud domain.

2. **Record the integration contract before coding.** In `report.md`, describe the endpoint configuration: trusted address, port, transport, allowed methods/paths, identity alias, request/response limits, and timeout. Choose the minimum API for the specific adapter; chat completions, for example, do not automatically authorize all of `/v1/`. Availability checking must use a separately allowed route. Define behavior for redirects, streaming disconnects, address changes, and unknown models. Require rejection with diagnostics, not switching to another model or the cloud.

3. **Design the network boundary.** The model server runs outside the 2 GiB task container and is accessible only through the trusted bridge. The agent container retains its own isolated Docker network, workspace mounts, unprivileged user, and external timeout. The bridge forwards requests only to the fixed endpoint; the agent cannot supply an arbitrary target URL or Host to select an upstream. Do not allow the entire LAN, host networking, Docker socket, administrative server routes, or direct device access from the task container. Preserve the existing T001 source GET gateway and its public SSRF filter.

4. **Add a minimal provider profile and adapter.** Implement a separate local policy in the validator, prepare snapshot, gateway, and one selected adapter. Use the native Pi/mini-SWE-agent agent loop; do not replace it with a shared loop. For Pi, check streaming tool-call → tool-result → final; for mini-SWE-agent, also check the native textual action protocol. Pin context/output limits, chat template, and reasoning/sampling. If the server requires a secret, its source is `.env` and the selected profile; do not include its value in snapshots, manifests, or logs. Document separately whether a dummy auth marker is needed.

5. **Extend the data, not just the URL.** Design and implement versioned schema fields, their validation, and immutability after prepare. The names below are data requirements, not existing `run.json` fields. Do not add them manually to old records.

   | Data group | Required content |
   | --- | --- |
   | Model identity | Official repository and revision; exact files, bytes, and verified SHA-256 values; quant/format; requested alias and observed identity with supporting evidence |
   | Engine | Engine/version/commit, Vulkan, ROCm, or Metal GPU backend, build flags, serving wrapper/version, image digest for container execution |
   | Input protocol | Tokenizer/chat-template hash; context/output budgets; sampling, seed if supported, reasoning; tools/action protocol format |
   | Memory and execution | KV/state dtype, batch/ubatch, offload/GPU layers, slot count; hardware-profile hash, driver, and power mode |
   | Provenance | Sealed deployment manifest and its hash; confirmation of the configuration actually running, absence of cloud fallback |
   | Metrics | Measured values and units; separate reasons for unknown tokens, memory, energy, and cost |

6. **Connect the data to prepare/run/compare.** Prepare saves the configuration and fingerprint. Run verifies the server against the pinned configuration before agent startup and handles detected identity changes during execution. One `/models` response with the same alias does not prove unchanged weights: a verifiable deployment manifest or equivalent evidence from a controlled process is needed. Compare includes material fields in the conditions key, preserving cloud/local and engine/backend distinctions. For GGUF and safetensors with different quantizations, the comparison concerns the deployment as a whole, not the pure engine effect. Old cloud records continue to validate.

7. **Run synthetic acceptance tests.** Create a mock inference server and test responses without real keys or hidden tasks. Give each case a test ID, expected result, and raw-output reference. Minimum matrix:

   | ID | Intervention | Acceptance criterion |
   | --- | --- | --- |
   | B01 | Allowed request and native tool/action round trip | Final answer obtained, events and tool-result preserved without loss |
   | B02 | Same host, different port; another LAN IP; IPv6 address outside the allowlist | Rejected before connecting to a forbidden upstream; verified with a mock-server counter |
   | B03 | Host/target substitution, redirect, administrative path | No switch to another destination and no administrative action executed |
   | B04 | Cloud endpoint request after a local error | Rejected; no calls to the cloud mock endpoint |
   | B05 | Oversized response, invalid JSON, 4xx/5xx, interrupted stream | Bounded log size, explicit error; client exit 0 does not turn an error into success |
   | B06 | Timeout and cancellation | Agent container and temporary resources removed; shared model-server process not killed without a separate reason |
   | B07 | Same alias, different weights/template/context/backend | Run rejected or a separate condition created; data not merged under the previous alias |
   | B08 | Usage absent | `null` with a reason; cost and tokens do not become 0 |
   | B09 | Modified sealed manifest, secret in trace/artifact | Integrity rejection or designed protection; the secret value did not enter the archive |
   | B10 | Old cloud run and T001 replay | Backward compatibility; private-source URLs remain forbidden, no live fallback during replay |

8. **Verify the integration in Docker.** After unit tests, run real network-isolation checks with mock endpoints. Save stdout/stderr and mock-server parameters in `raw/`. Run the standard checks:

   ```bash
   npm test
   npm run test:docker
   npm run check
   git diff --check
   ```

   Record additional commands for new tests exactly as implemented. Do not mark B01–B10 passed merely because a test file exists.

9. **Document the working CLI and run one pilot.** Only after implementation and the preceding checks, add an exact command with actually supported parameters to the adapter README. Run one T002 with `a2-janitor`, following the LAB09 lifecycle and independent evaluation. Record the actual run ID; preserve startup errors too. If engineering is incomplete, submit the report as `pending/blocked`, with the reason and last reproducible test; do not create a fictitious `completed` result.

10. **Add components to the ledger.** For every added boundary or adaptation, add an unused ID to `docs/harness-ledger.md` in the same change: component → assumption/boundary → actual tests/run ID → date/model → retest trigger → ownership → status. A working bridge does not yet prove its contribution to agent quality; “confirmed” status requires before/after measurements under the ledger rules. Record porting to the other three adapters as separate readiness rows and repeat protocol tests.

## Results tables

| Harness | Engine/backend | Artifact/template fingerprint | B01–B10 | Actual pilot run ID | Independent verdict | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| Fill in | Fill in | Fill in | Test references | Existing ID only, or absent | pass/fail/partial/aborted or no evaluation | ready/pending/blocked |

| Test ID | Command/fixture | Expected | Observed | Raw evidence | Fix and rerun |
| --- | --- | --- | --- | --- | --- |
| B01 | Fill in | Fill in | Not measured before execution | Fill in | Fill in |

## Deliverables

- `report.md`, `measurements.tsv`, completed lab-session manifest, and raw logs.
- Engineering implementation diff, schema/migration, documented CLI, acceptance tests, and their output.
- Boundary diagram: agent container → bridge → one inference service; list of allowed routes.
- References to ledger rows and the actual pilot record with external evaluation, if a pilot occurred.

## Completion criteria

- [ ] One selected adapter uses its native loop through the local bridge.
- [ ] B01–B10 are verified; forbidden destinations and cloud fallback are actually inaccessible.
- [ ] Manifest and compare distinguish weights, template, backend, and settings behind identical aliases.
- [ ] Metrics without observations remain unknown; old cloud records are valid.
- [ ] Engineering checks and `npm run check` pass.
- [ ] One real pilot has independent evaluation; an incomplete integration is submitted as an interim report, not a completed LAB08.
- [ ] New components are recorded in the ledger; readiness is not automatically attributed to other adapters.

## Review questions

1. Why is permitting `192.168.0.0/16` in the existing resolver insufficient for safe local integration?
2. How does confirming a model alias differ from confirming weights and a chat template?
3. Why must the model server not inherit the task container's 2 GiB limit?
4. Which fields should separate compare groups when moving from Vulkan to ROCm with the same weights?
5. What does a synthetic tool round trip prove, and what does it not prove about agent quality?
6. Under which observations may inference fee be recorded as 0, and when is even that quantity unknown?

## Sources

- [Protocol and local identity](../method.md), [local-model plan](../local-models.md), [engine matrix](../local-inference-engines.md).
- [Provider profiles](../../scripts/lib/harnesses.mjs), [prepare](../../scripts/prepare-run.mjs), [runner](../../scripts/run.mjs), [egress](../../experiments/common/egress.mjs).
- [Record schema](../../results/schema.json), [validator](../../scripts/lib/records.mjs), [compare](../../scripts/compare.mjs).
- [Component ledger](../harness-ledger.md), [LAB09: agent campaign](LAB09-agent-campaign.md), [LAB01 and LAB05 index](README.md).
