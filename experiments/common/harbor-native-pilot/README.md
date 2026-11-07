# Native Harbor adapter pilot preparation

Status: **offline preparation passed; paid execution is disabled**.
This is a separate six-slot infrastructure pilot using Harbor 0.25.0 at commit
`ff2a1ef48070a8df374669138e4d4db79b77f013`. The current campaigns, historical
results, original Harbor experiment and laboratory harness profiles are unchanged.
[plan.json](plan.json) remains `execution_authorized=false`, `launchable=false`.

## Preparation and evidence

| Blocker | Prepared result | Evidence |
| --- | --- | --- |
| Runtime images | Five dedicated agent images and one separate verifier, bound to immutable local image IDs; exact versions, UID 1000 and package inventories checked | [Runtime lock](runtime-lock.json), [runtime probes](runtime-evidence.json), [package inventories](runtime-inventories.json) |
| Pi metadata/defaults | Exact dated mini model definition in native HOME; 400k context, 128k output, 0.75/4.5 input/output and 0.075 cache-read prices per million; retry and compaction disabled | [Model definition](runtime/pi/models.json), [settings](runtime/pi/settings.json), native registry/settings probes |
| mini environment | Genuine uv 0.13.7 tool installation of mini 2.4.6, Python 3.12.12 and LiteLLM 1.108.1; missing MCP dependency closure pinned; imports and `pip check` pass | [Dockerfile](images/mini.Dockerfile), [wheel lock](runtime/wheels.lock.json), runtime evidence |
| Native setup/tool/trace path | All six slots complete native setup, task-tool execution, submission and official ATIF-v1.7 validation against a local fixture | [Lifecycle evidence](native-smoke-evidence.json) |
| Independent grading | Real Harbor Trial controls on the mini image with the common separate verifier and task policy | [Control evidence](control-evidence.json) |
| Record/accounting bridge | Separate task registration, sealed prepared records and data-only evidence import; unknown metrics and billing stay null | [Accounting guide](ACCOUNTING.md), [accounting.py](accounting.py) |

The original source/version inspection remains in [offline-checks.json](offline-checks.json).
[Anthropic](anthropic-source-evidence.json), [OpenAI](openai-source-evidence.json)
and [Pi](pi-source-evidence.json) source audits explain the earlier compatibility
findings. Their proposed remedies are superseded by the runtime and lifecycle
evidence above; they are not evidence of live provider access.

Images use dedicated `harbor-native-pilot/*` tags. The lock, packages and records
use image IDs, not mutable tags. These are **local Linux/arm64 image IDs**, not
registry-pullable manifest digests. Retain or export these images before moving
hosts. Existing base dependencies are frozen by image identity and inventory;
this does not claim bit-reproducible rebuilds from package indexes. Public wheel
downloads are a separate, hash-checked preparation step. Image builds and runtime
checks use Docker network `none`, and no model credentials are supplied.

mini's real uv environment exposes the immutable base's packages through
`system-site-packages`; the application wheel, additional dependency closure and
full resulting package set are recorded. Pi has a small, explicit fixed-Node shim
for Harbor's expected nvm source path. It selects and checks Node 24.13.1 without
installing NVM or fabricating version output. All images have Node; only mini's
agent image also has Python. This is not a general coding-environment comparison.

## What the offline checks establish

The native smoke uses Harbor's actual `AgentFactory`, `setup`, `run` and
`populate_context_post_run`, with the actual pinned CLIs. Its Docker exec adapter
is a test fixture, not a full Harbor Trial. A deterministic server runs inside
each container on loopback; Docker network `none` and a host Python socket guard
exclude provider access. Fake authentication and synthetic token fields are
protocol fixtures, never model measurements or billing. Native setup requires
root CHOWN/DAC_OVERRIDE/FOWNER capabilities; the task tool is UID 1000 with no
effective capabilities. Root filesystems are disposable writable layers.

Each slot checks an unchanged input, a real task tool operation, correct output,
terminal native success, exact requested wire model, official declared ATIF
schema and container removal. Raw native logs, commands, input plan/runtime
snapshots and hash manifests stay under ignored `.cache/native-smoke/`.
The committed summary binds these artifacts and the slot configuration. Later
gate/run-ID bookkeeping may change the full plan hash; its frozen snapshot and
configuration digest preserve the tested conditions.

The boundary suite separately uses real Harbor `Trial` and Docker environments,
with four controls: oracle **1**, missing output **0**, wrong output **0**, and
input/reward tampering **0**. It uses mini's image as the representative runtime;
all five images also have runtime probes and all six slots have native lifecycle
checks. Only `/app/output/result.json` crosses into the separate verifier.
The verifier runs as UID 1000, cannot alter its fixture, and sees no agent input,
solution or tamper marker. Harbor copies the public input after startup with host file ownership. The
tamper control replaces it through writable `/app` and forges the shared reward;
independent grading still fails.
Harbor clears the shared verifier-log directory before grading: it is not an
unwritable shared path.

Effective sidecar policies/rules and image labels are recorded. The sidecar's
upstream base is digest-pinned in the pinned Harbor source; its observed built
image ID is captured separately from the six task images. Harbor `no-network`
denies controlled TCP but permits DNS/ICMP. It is not Docker network `none`.
The suite checks blocked HTTPS; it does not contact a provider or run an online
positive control. Native lifecycle testing and full Trial boundary controls are
complementary; a full native-agent Trial with a real provider remains unverified.

## Recorded native differences

- **Claude:** `dontAsk` needs explicit `Bash,Read,Write` allowed tools. The offline
  tool call was denied without that pilot-only setting. Native turn/USD controls
  remain different from other harnesses; no universal hard cap is claimed.
- **Codex:** native sessions, rollout conversion and `unified_exec` differ from the
  lab's ephemeral execution. The pilot disables web search and subagents and uses
  a private HOME/CODEX_HOME.
- **OpenCode:** the pinned binary supports Harbor's auto-approval switch. An extra
  title request uses the same exact Anthropic model at low effort; the two task
  fixture requests use medium effort. Auxiliary work belongs in later accounting.
- **Pi:** the native CLI differs from the lab SDK, including its turn-limit
  extension. Pi writes its version to stderr, which Harbor's detector misses;
  native ATIF says `unknown`. An independent exact-version gate checks both
  streams. The fixture's custom base URL creates a `harbor-endpoint` provider with
  different generated metadata/settings; direct-provider metadata and settings
  are checked separately through native imports. No MCP bridge is enabled.
- **mini:** native `InteractiveAgent` differs from lab SDK `DefaultAgent`. This
  pilot explicitly uses Responses (`litellm_response`): LiteLLM routed the chosen
  GPT snapshot to Responses even under the earlier Chat Completions proposal.
  Native retries are set to one attempt; step limit is 8 and cost target is USD2.
  Limits and estimates are not settled provider billing.

Harbor `skip_install` only warns about version mismatches. Our independent gate
must match the exact observed version and immutable image before later admission.
All five names are registered, but **none is live-model-qualified by mocks**.
The wider lab remains deferred: OpenHands SDK, Antigravity and Copilot need their
own environment/condition qualification; Amp has no registered native integration.

## Frozen task, records and proposed live slots

The task has its own `harbor-native-normalize` / `harbor-native-normalizer`
registration under [task/](task/registration.json). It copies the original public
input and evaluator/expected fixture bytes. Only the new public instruction's
network-boundary sentence changes; a later authorized model API is distinguished
from task network needs. The Node oracle, runtime policies and budget contract
are new. Existing `tasks/*/task.md` and hidden campaign checks are untouched.

[package-lock.json](package-lock.json) binds twelve packages: six prepared
provider-allowlist packages and six offline variants. They have identical public
semantics and verifier bytes, but distinct runtime/policy digests. Setup and the
verifier deny controlled TCP; a prepared agent phase allows only its selected
API hostname. A package is not an execution authorization or launch command.

| Slot | Harness version | Proposed exact model |
| --- | --- | --- |
| HN-O01 | Codex 0.155.1 | `openai/gpt-5.4-mini-2026-03-17` |
| HN-A01 | Claude Code 2.1.83 | `anthropic/claude-sonnet-4-6` |
| HN-A02 | OpenCode 1.18.29 | `anthropic/claude-sonnet-4-6` |
| HN-A03 | Pi 0.73.1 | `anthropic/claude-sonnet-4-6` |
| HN-O02 | mini-SWE-agent 2.4.6 | `openai/gpt-5.4-mini-2026-03-17` |
| HN-O03 | Pi 0.73.1 | `openai/gpt-5.4-mini-2026-03-17` |

Six prepared lab records are listed in `plan.json`. They seal the package, exact
slot, runtime lock, plan, contract and specification. They have no execution
command/start time, observed model, usage, cost or verdict. Fixture trials are
not imported as completed live attempts. Core record/catalog changes accept
only this exact experiment registration, not arbitrary external task paths.

The bridge imports explicit raw-evidence references and independent attributable
billing; it is not an automated provider billing collector. Missing identity,
ATIF, measurements or settled billing leaves qualification inconclusive and
blocks the next slot. Started failures retain costs and cannot be silently
reused. A terminal import with unknown billing cannot currently be amended;
collect settled billing before final import or add an audited amendment later.

The separate **USD12 proposal** remains unauthorized: USD2 per attempt, USD6 per
provider, no reserve/retries, concurrency one, 180-second agent timeout and
60-second verifier timeout. Eight native turns/steps is a target with differing
semantics. In-flight requests can exceed observed budgets. No campaign allocation
is transferred. G5 still requires explicit authorization, credential handling
through `.env`, and live account/model access checks. There is no paid launcher
in this preparation and no automatic campaign promotion.

## Reproduce offline validation

Use the pinned Harbor Python environment from the existing interoperability
experiment and the local Colima daemon. From the repository root:

```sh
# Cached public wheels and local bases only; --fetch-wheels is an explicit
# separate download step if a hash-locked wheel is missing.
python3 experiments/common/harbor-native-pilot/build-images.py
experiments/common/harbor-interop/.venv/bin/python experiments/common/harbor-native-pilot/materialize.py
experiments/common/harbor-interop/.venv/bin/python experiments/common/harbor-native-pilot/offline_smoke.py --docker-host unix://$HOME/.colima/default/docker.sock
experiments/common/harbor-interop/.venv/bin/python experiments/common/harbor-native-pilot/verify_controls.py --docker-host unix://$HOME/.colima/default/docker.sock --docker-plugin-dir experiments/common/harbor-interop/.cache/docker-plugins
mise exec -- experiments/common/harbor-interop/.venv/bin/python -m unittest discover -s experiments/common/harbor-native-pilot -p 'test_*.py' -v
mise exec -- node --test experiments/common/harbor-native-pilot/mock-provider.test.mjs
mise exec -- experiments/common/harbor-interop/.venv/bin/python experiments/common/harbor-native-pilot/check_preparation.py
mise exec -- npm run check
```

Rebuilding can change runtime-lock timestamps or image IDs and invalidates sealed
records/evidence. Inspect existing preparation with `materialize.py --check` and
`check_preparation.py`; do not overwrite a prepared attempt to refresh its seals.
`verify_controls.py --all-images` repeats the same four controls on all five
images if an image-specific boundary concern warrants it.

The broader JavaScript suite runs on a git-visible source snapshot: local ignored
bootstrap/venv symlinks otherwise break two existing fixture-copy tests. That
snapshot has 198 passing tests and two intentionally skipped Docker tests; the
real Docker checks relevant to this experiment are recorded above. Final
validation and preservation evidence is in [preparation-evidence.json](preparation-evidence.json).
