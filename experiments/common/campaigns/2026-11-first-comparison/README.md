# First comparison campaign: preparation plan

This directory drafts two controlled campaigns for preregistration after
qualification. It contains no experimental results and does not authorize API
activation or paid execution. [`plan.json`](plan.json) is the proposed slot
register and readiness checklist. Exact model IDs are selected below; account
access, evaluator, and final input fingerprints remain unresolved. Verified image IDs and offline
evidence are recorded separately; neither series is frozen. No real run records
are created by this plan.

## Historical offline preparation on 2026-11-06

- [Host evidence](host-preflight.json): mise 2026.11.3, Node 24.13.1,
  Python 3.12.12, and npm 11.8.0. All 198 enabled Node tests, 26 Python tests,
  and repository checks passed in the pinned environment.
- [Docker evidence](docker-preflight.json): Colima is running; all five existing
  harness images match their package pins and contain Node 24.13.1. The installed
  Codex CLI exposes the flags used by its adapter. Image IDs are recorded in the
  historical Docker evidence; the 2026-11-07 refresh below supersedes those image IDs.
- The two separately enabled Docker tests passed: the container boundary test
  and Pi's synthetic tool round-trip, cancellation, and timeout test.
  mini-SWE-agent's native SDK/shell initialization also passed without network.
- [Preparation evidence](preparation-preflight.json) records temporary slot
  preparation and input-comparability checks, not real task executions.

The ignored `mise.local.toml` selects `DOCKER_CONTEXT=colima` only in this
checkout. Shell configuration and global runtime defaults were not changed.
From the repository root, use:

```bash
~/.local/bin/mise exec -- node --version
~/.local/bin/mise exec -- docker context show
~/.local/bin/mise run verify
```

Live model/account qualification, credentials, independent evaluator qualification,
and paid-execution authorization remain launch gates. No provider API was called and no real
run record was created during offline preparation. Colima is left running for
the next preparation step; temporary smoke containers were removed.

## Scope

| Cohort | Harnesses | T002 pilots | New comparison slots | Total |
| --- | --- | --- | --- | --- |
| Anthropic | Claude Code, Pi, OpenCode | 3 | 18: 3 harnesses × 2 tasks × 3 repeats | 21 |
| OpenAI | Codex, Pi, mini-SWE-agent | 3 | 18: 3 harnesses × 2 tasks × 3 repeats | 21 |
| Total | Five distinct harnesses; Pi in both cohorts | 6 | 36 | 42 |

The OpenAI cohort provides a second controlled comparison. Each cohort requests one
exact, unprefixed model ID; offline checks are recorded below and live support is
still pending qualification. Providers and models
differ between cohorts; do not merge them into a causal five-harness ranking.
Pi's Anthropic ID must exist in its pinned SDK registry. For OpenAI, Pi may retain
a dated snapshot ID using known family metadata; mini-SWE-agent also needs
compatible installed LiteLLM model/pricing support. Availability requires separate
verification, not an assumption from the host Codex application.

Each 18-run series excludes three qualifying pilots required by
[LAB09](../../../../docs/labs/LAB09-agent-campaign.md). Historical local runs do not
qualify these cloud deployments. A pilot may fail the task and still qualify the
lifecycle if execution and independent evaluation are valid. Installation,
protocol, identity-mismatch, or evidence failures need resolution before the main
series. Pilots never count toward comparison triples.

## Conditions and ordering

### Selected models and pilot budget

The refreshed selections for future pilots and comparisons are:

| Cohort | Exact published model ID | Standard input / output USD per million tokens | Pilot target |
| --- | --- | --- | --- |
| Anthropic | `claude-sonnet-5-5` | 2 / 10 | 3 × USD 2 = USD 6 |
| OpenAI | `gpt-6.1-sol` | 2 / 10 | 3 × USD 2 = USD 6 |

List prices checked on 2026-11-07: [Sonnet5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview),
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol). These are the published IDs;
no dated snapshot or permanent alias stability is assumed. Sol requests above 272K input tokens
use 2× input/cache and 1.5× output rates for the entire request. Reasoning output is billable.

[Current model selection](model-selection.json) links six passing lab entrypoint fixtures,
exact immutable Linux/arm64 images and the [budget recalculation](../../model-refresh-2026-11/pilot-budget.json).
Pass each image ID explicitly; existing default tags refer to earlier environments.
Claude Code is 2.1.319; Codex is 0.167.0. Pi 0.73.1 has explicit model metadata and a
hash-guarded Sonnet compatibility delta. mini 2.4.6 uses its native Responses model
for Sol with LiteLLM 1.108.1. OpenCode remains 1.18.29 with explicit metadata/medium
variant; 1.19.5 failed the offline process-exit gate. All six cases sent medium effort;
this does not equalize prompts, turn definitions, output ceilings or inference behavior.

The six pilots retain a USD 12 target (USD 2 each, USD 6 per provider), no reserve,
and no execution authorization. At 500K aggregate input + 30K output per pilot, with
every request at most 272K input and no caching, arithmetic cost is USD 1.30 per model
or USD 7.80 for six pilots. Illustrative 30% extra Sonnet tokens for the same text makes
that USD 8.97; neither scenario is a forecast. One Sol request with500K input + 30K
output costs USD 2.45 and exceeds the target. Long-context use needs reassessment.

Run sequentially only after authorization; reconcile attributable settled billing
before admitting another pilot. Unknown costs block admission. Stop on any pilot
above USD 2, provider allocation at USD 6 or total at USD 12. Both remaining allocations
must cover USD 2 before starting. These operator rules permit in-flight/delayed-billing
overshoot; they are not a hard cap. Failures consume spend. No automatic additional
attempts or budget transfers. Native HTTP retry charges belong to the same attempt.

Historical results and all eight previous campaign files are preserved under the
[refresh archive](../../model-refresh-2026-11/previous-campaign/). The adjacent old
provider preflight JSON files remain historical evidence only. Offline loopback fixtures
establish protocol compatibility, not account access, live model identity or billing.
The separate refreshed Harbor pilot has its own USD 12 target, making USD 24 across
12 proposed pilots; comparison execution remains separately unauthorized.

Use `baseline`, a 900-second external timeout, and **observed USD policy for every
harness**, including Claude Code. Both task contracts specify 30 turns and a USD 2
target. Claude Code, Pi, and mini-SWE-agent have native turn/call limits, OpenCode
uses advisory steps, and Codex has no verified native turn cap. These units are
not equivalent. The external timeout is enforced; USD 2 is not enforced under
observed policy.

The nominal target is USD 42 per cohort (3+18 slots), USD 84 total, excluding
additional qualification attempts. These are arithmetic targets, not price
forecasts or spending ceilings. The pilot policy is recorded in `pilot_budget`;
the main-series spending decision remains open.

The pilot-only phase follows `pilot_budget.slot_ids`: `A-P01`, `A-P02`, `A-P03`,
then `O-P01`, `O-P02`, `O-P03`. Skip all comparison slots during this phase.
After separate main-series authorization and each cohort's freeze gate, retain
`slots.order` among comparison slots: Anthropic's 18, then OpenAI's 18.
Harness order rotates with each repeat, so each harness occupies each position
once per task. Task order alternates by repeat. Run only one attempt at a time.
Each cohort has independent readiness gates and a separate comparison ID list.

T002 uses agent `a2-janitor`; T004 uses `a4-implementer`. Preserve the current
English inputs and a common initial workspace fingerprint per task. T002 permits
the npm registry; T004 needs no task network. Provider access remains restricted
to the corresponding profile. Use `DOCKER_CONTEXT=colima` for Docker and
coordinator commands on this host; the default endpoint is not usable. Freeze one
image per harness and one proxy image. Pi uses the same pinned image in both
cohorts; do not rebuild or change adapter/model/input conditions during a series.

## Launch gates

Before any pilot, record exact model selection and account-access evidence,
credential readiness through the existing `.env` path, immutable image IDs,
offline version/smoke evidence, source revision, evaluation readiness, spend/stop
policy, and authorization for API execution. Do not put credentials in this plan.
Anthropic uses `ANTHROPIC_API_KEY`; OpenAI uses `CODEX_API_KEY` for Codex and
`OPENAI_API_KEY` for Pi and mini-SWE-agent. Host authentication is not the harness
credential. No key activation is needed to finish this preparation plan.

Arrange an independent evaluator for **both T002 and T004**, outside the agent
container. Record the evaluator and procedure evidence without inspecting or
exposing hidden checks during preparation. `evaluation-template` preserves input
and artifact hashes; the evaluator supplies the verdict and check output.
`judge-run` validates and imports that evidence. It does not decide task success.

After valid pilots, freeze each cohort and create a fresh record for every main
slot using the existing lifecycle. Record returned IDs explicitly. `new-run --n`
selects an ID suffix; it does **not** create multiple runs. This model-selection
step creates no real records; account/live qualification, evaluator readiness,
and execution authorization remain open. No new orchestration component is
needed for this plan.

Keep all started failures. A retry gets a new qualification slot and ID; it never
replaces a failed comparison slot. Compare only each cohort's explicitly recorded
main IDs, excluding pilots. Report pending and pre-start failures separately;
never merge unlike conditions merely to obtain a triple.

## What the results can establish

Success and elapsed time are the common primary measurements. Report `pass@3`
(at least one pass) and `pass^3` (three passes), raw outcomes, and measured coverage.
Pi, OpenCode, and Codex currently do not establish the cloud response model ID.
Their requested model IDs are conditions, not proof of observed identity.
Claude Code and mini-SWE-agent can report observed response identities when the
trace contains them. OpenCode's complete turns/tokens/cost and Codex's internal
turns/USD cost remain unknown. Pi and mini-SWE-agent costs are library estimates;
Claude's is CLI-reported. Do not turn unknowns into zero or claim complete
cost/turn comparisons across every harness.

At each cohort's fixed endpoint, universal `pass^3` means these tasks are too easy
to distinguish its selected harnesses. No success calls for model and contract
diagnosis. Protocol or evaluation failure pauses expansion; preserve the attempt
and record the reason. Task success is not a reason to stop early or selectively
replace the preregistered sample.

References: [roadmap](../../../../docs/roadmap.md),
[method](../../../../docs/method.md),
[LAB09](../../../../docs/labs/LAB09-agent-campaign.md),
[Codex adapter](../../../codex/README.md),
[mini-SWE-agent adapter](../../../mini-swe-agent/README.md).
