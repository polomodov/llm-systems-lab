# LAB41. Network and secrets: an agent VM with access only to the provider API

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisites | [LAB37](LAB37-space-harness-vm.md) (agent in a VM with real egress) |
| SPACE mechanisms | Operator egress profiles (`SPACE_EGRESS_PROFILES`, `X-Space-Egress-Profiles` header), sandbox network policies, credential manager (`crates/apps/credential/mgr`) |
| Minimum | A profile allowing only the provider domain; synthetic VM probes with a “probe → expected → actual” table; one T002 episode with this profile |
| Extensions | Provider key outside the VM: network-layer injection through the credential manager or a host proxy; repeat the episode |
| Time | Allow 1 day |
| Readiness | `implementation-required`: profile and probes are written during the lab; key injection outside the VM is `unverified` for local Kind |
| Initial state | Educational manifest: `not-started` |

## Objective

Restrict the agent VM so that only the selected provider API is reachable, and verify this with probes. In the extension, remove the provider key from the VM.

## Hypothesis

With a profile allowing only the provider domain, all VM probes to other destinations are rejected, while the T002 episode achieves the same verdict as LAB37. A single successful probe to a prohibited destination or a failed legitimate provider call falsifies the hypothesis.

## Preparation

- Read in SPACE: `docs/egress-profiles.md`, `docs/ecw-network-policy.md`, `docs/tls-interception-exemptions.md`, `infra/space/kind/README.md` (network credential injection section). Configure profiles identically at API and cluster-controller startup.
- Probes are synthetic and target only your own machine and reserved names (`example.test`, `192.0.2.0/24`). External targets, scanning others' networks and bypassing third-party protections are outside this lab.
- Cluster configuration changes apply to this machine's local Kind; do not touch shared or production clusters.

```bash
npm run lab:new -- --lab LAB41 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB41-ryzen-01'
```

## Procedure

1. **Profile.** In `experiments/space/egress/`, create a profile JSON with `allow` for the provider API domain; add `tls_interception_exemptions` for it if needed. Apply it to the local Kind API and cluster-controller; record the method and rollout.

2. **Probes.** A script invoked inside the VM prints JSON for each probe: HTTPS to the allowed domain; HTTPS to another domain; direct IP; DNS to a third-party resolver; link-local metadata address; host SPACE API (`8080`) and data plane (`8090`); neighboring sandbox; host address. Specify each expected outcome before execution.

3. **Run probes** without the profile (LAB37 baseline) and with it. Save raw output.

4. **Episode.** T002 with the same harness and model as LAB37, using the profile; `sandbox.network` in `run.json` describes actual policy.

5. **Extension: key outside the VM.** Check whether local Kind can inject the provider credential at the network layer (credential manager) without AWS; if not, implement a host proxy that adds the authorization header while the VM knows only its address. Repeat probes and the episode; verify that the key is absent from the VM environment, files and trace.

## Results tables

| Probe | Destination | Expected | Without profile | With profile | Raw |
| --- | --- | --- | --- | --- | --- |
| allow | Provider API | allowed | | | |
| other-domain | `example.test` | denied | | | |
| direct-ip | `192.0.2.1` | denied | | | |
| dns | third-party resolver | denied | | | |
| metadata | link-local | denied | | | |
| space-api | host API/data plane | denied | | | |
| neighbour | another sandbox | denied | | | |

| Run ID | Profile | Key in VM | Verdict | Turns | USD |
| --- | --- | --- | --- | --- | --- |

## Deliverables

- Profile and probe script in `experiments/space/egress/`, report with tables, raw probe output, episode `run.json` file(s).
- For the extension: description of the key path and verification of its absence from the VM.

## Completion criteria

- Every probe executed in both modes, with expected and actual outcomes.
- Every discrepancy analyzed: profile error, platform limitation or incorrect expectation.
- Episode using the profile has a record and independent verdict.

## Review questions

1. What does the agent see when a connection is prohibited, and how does that affect its behavior?
2. Why must profiles be configured identically on the API and cluster-controller?
3. How is network-layer key injection better than passing an environment variable into the VM, and what does it not address?
4. Which probes should be added for T001, where the agent needs source access?

## Sources

- SPACE: `docs/egress-profiles.md`, `docs/ecw-network-policy.md`, `docs/tls-interception-exemptions.md`, `infra/space/kind/README.md`, `space_smoke/scenarios/` (`network_policy.*`).
- This repository: `experiments/common/egress.mjs` (Docker runner egress), [LAB37](LAB37-space-harness-vm.md).
