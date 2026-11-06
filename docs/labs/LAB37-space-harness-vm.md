# LAB37. Pi and OpenHands in SPACE microVMs

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisites | [LAB36](LAB36-space-deploy-smoke.md) on the chosen machine; [LAB15](LAB15-pi.md) and [LAB17](LAB17-openhands.md) at least through offline smoke and one Docker T002 pilot |
| Harnesses | `pi` (`@mariozechner/pi-coding-agent@0.73.1`), `openhands` (`openhands-sdk==1.49.2`); this repository's images |
| Isolation | SPACE Firecracker microVM instead of the runner's Docker container; `sandbox.kind = "vm"` in `run.json` |
| Minimum | SPACE templates from both images, offline `--smoke` for both harnesses inside the VM, SPACE runner backend, one T002 per harness with an independent judge |
| Extensions | Three repetitions per harness; T001 replay; agent in a VM with a local model on machine A through the [LAB08](LAB08-local-bridge.md) bridge |
| Time | Allow 1–2 engineering days plus runs; agent execution ≤900 s per attempt |
| Readiness | `implementation-required`: `scripts/run.mjs` currently has only a Docker backend |
| Initial state | Experiment `not-run`; educational manifest `not-started` |

## Objective

Execute the same A2/T002 episode as LAB15 and LAB17, with Firecracker VM isolation, and record the components added to the harness and runner. The agent remains the same: the SPACE template is built from the same OCI image used by the runner in Docker.

## Hypothesis

1. Both harnesses pass their own `--smoke` inside a SPACE VM without changes to `experiments/pi/run.mjs` or `experiments/openhands/run.py`.
2. A real episode needs only three new runner components: uploading sealed inputs to the VM, egress to the selected provider API, and downloading trace/workspace. Each gets a row in the [ledger](../harness-ledger.md).
3. The VM T002 verdict matches the Docker pilot for the same harness and model; wall-clock differences are explained by environment startup time.

One attempt cannot establish point 3: it is an observation, not a comparison. Comparison requires repetitions (extension) and [LAB09](LAB09-agent-campaign.md) rules.

## Preparation

- A machine with accepted LAB36 and a working SPACE cluster. Use the same SPACE commit as the LAB36 report, or a new one with baseline smoke repeated.
- Built `harness-lab/pi:0.73.1` and `harness-lab/openhands:1.49.2` images and their image IDs from LAB15/LAB17.
- Read in SPACE: `docs/native-template-runtime.md`, `templates/firecracker/recipes/oci-python-smoke.toml` (template over an OCI-image seed), `docs/using-api.md`, `docs/egress-profiles.md`, and the LLM agent example `examples/llm_agent.py` (draft PR polomodov/SPACE#1) as a command-session + SSE example.
- Read here: `scripts/run.mjs` (how the Docker backend mounts `/control`, configures network/limits and collects traces), [method](../method.md), [evaluation workflow](harness-workflow.md).

```bash
npm run lab:new -- --lab LAB37 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB37-ryzen-01'
```

The runner still reads provider secrets only from `.env`. A key entering the VM is a known boundary of this lab; [LAB41](LAB41-space-network-secrets.md) addresses it.

## Procedure

1. **Deliver the image to SPACE.** Establish where your installation's SPACE template builder obtains the OCI image (public registry, loopback registry, import into a Kind node). This is `unverified`: record the verified method and commands. Deliver the image by digest, not tag.

2. **Template recipes.** Create `experiments/space/recipes/pi.toml` and `openhands.toml` based on `oci-python-smoke.toml`: `from = "oci-image"`, `base = "seed"`, `image = <ref@digest>`, explicit `vcpu`, `memory_mib`, `disk_size_mb`. The `run` step checks package version as in `harness.json` (`node -p` for Pi, `importlib.metadata` for OpenHands). Note that the template ignores OCI `CMD`/`ENTRYPOINT`. Build, publish and record the template content hash.

3. **Offline smoke in the VM.** Create a sandbox from each template without egress, upload `experiments/<harness>/` to `/control` and execute a command session:

   - Pi: `node /control/run.mjs --smoke`
   - OpenHands: `python /control/run.py --smoke`

   Save stdout/stderr and exit code. Record differences from Docker smoke (`/tmp noexec`, read-only rootfs, uid 1000 versus the seed's `user` uid 2000): which SPACE reproduces and which it does not.

4. **Runner backend.** Add `--sandbox space` selection to `scripts/run.mjs` (Docker remains the default). Minimum contract:
   - create a sandbox from a template tied to the profile image ID; record the template content hash in `run.json`;
   - upload sealed inputs and `/control`, invoke the profile entry point with the same arguments as Docker;
   - stream stdout to `trace/stdout.jsonl`, enforce timeout and turn limit from the task contract;
   - retrieve the workspace for the judge, delete the sandbox in `finally`;
   - run the hidden check on the host after retrieval; it never enters the VM;
   - `sandbox.kind = "vm"`, `sandbox.network` reflects actual policy.

   Add offline tests with a fake SPACE API (as in `scripts/tests/test_llm_agent_example.py` in the SPACE PR). Each component gets a ledger row in the same change.

5. **Egress.** A real episode requires VM access to the provider API. At minimum, allow only the provider domain (see `docs/egress-profiles.md`); if your installation does not support profiles, record actual VM networking and mark it as a limitation. Full validation is in LAB41.

6. **Real T002 runs.** One attempt per harness, using the same provider/model as the Docker pilot:

   ```bash
   npm run new-run -- --harness pi --harness-version 0.73.1 --agent a2-janitor --task T002 \
     --provider anthropic --model "$MODEL_ID"
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   npm run run -- --run "$RUN_ID" --sandbox space --template "$PI_TEMPLATE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   `--sandbox`/`--template` flags exist after step 4; record the actual interface from the implementation. Then perform independent evaluation according to [harness-workflow](harness-workflow.md). Repeat for OpenHands.

7. **Comparison with the Docker pilot.** Complete the table: verdict, turns, tokens, cost, wall-clock, time to the first agent command and environment creation/deletion time.

## Results tables

**Templates**

| Harness | Image ID | Ref@digest | Template content hash | vCPU / MiB / disk | Build, s | Code |
| --- | --- | --- | --- | --- | --- | --- |
| pi | | | | | | |
| openhands | | | | | | |

**Offline smoke**

| Harness | Environment | Code | Key output | Differences from Docker |
| --- | --- | --- | --- | --- |
| pi | Docker (LAB15) | | | — |
| pi | SPACE VM | | | |
| openhands | Docker (LAB17) | | | — |
| openhands | SPACE VM | | | |

**T002 episodes**

| Run ID | Harness | Environment | Judge verdict | Turns | Tokens in/out | USD | Wall-clock, s | Environment startup, s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | pi | Docker | | | | | | |
| | pi | SPACE | | | | | | |
| | openhands | Docker | | | | | | |
| | openhands | SPACE | | | | | | |

**Added components** — links to ledger rows.

## Deliverables

- Report, template recipes in `experiments/space/recipes/`, runner changes with tests, ledger rows.
- Raw: template builds, VM smoke logs, `run.json` and traces for both episodes, judge verdicts.
- Description of image delivery to SPACE with verified commands.

## Completion criteria

- Both offline VM smoke tests have saved exit codes and output.
- `npm test` and `npm run check` pass; the Docker backend without `--sandbox` behaves as before.
- Each harness has a `run.json` with `sandbox.kind = "vm"` and an independent verdict (any of pass, fail or partial).
- Hidden checks never entered the VM; backend code and traces demonstrate this.
- Every added component is in the ledger with a retest condition.

## Review questions

1. Which Docker-backend assumptions (`--network none`, `--read-only`, `/tmp noexec`, uid) do not transfer directly to a VM, and how did you address each?
2. Which trace fields distinguish a SPACE failure from an agent failure?
3. What is lost if a template is built from a tag rather than a digest?
4. Where is the provider-key trust boundary in this design, and how will LAB41 change it?
5. Which component seems unnecessary after the run, and what would removing it reveal?

## Sources

- This repository: [LAB15](LAB15-pi.md), [LAB17](LAB17-openhands.md), `experiments/pi/README.md`, `experiments/openhands/README.md`, `scripts/run.mjs`, [ledger](../harness-ledger.md).
- SPACE: `docs/native-template-runtime.md`, `templates/firecracker/recipes/oci-python-smoke.toml`, `docs/using-api.md`, `docs/egress-profiles.md`, `examples/first_sandbox.py`.
- SPACE PR #1 (`polomodov/SPACE`): `examples/llm_agent.py` and its offline tests.
