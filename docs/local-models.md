# Local-model research

**Apple track (2026-10-07):** [LAB28–35 and M5 Max profiles](../experiments/local-models/apple/README.md). Both `local:plan` and `local:engines` accept `--hardware apple-m5-max-128gb-macos`; without the flag, Ryzen remains selected. Apple uses Metal/MLX and a separate five-profile catalog. Its GPU budget is unknown: effective budget/headroom is `null`, with status `hardware-memory-required`; set a numerical budget after measuring it. MLX stays `artifact-required`, and wrappers with unknown memory stay `engine-memory-required`. The original Ryzen/Linux plan follows.

Step-by-step execution is organized as the [local LAB01–10 route](labs/README.md); the same course includes LAB11–19 for every harness and additional LAB20–27 exercises. The next Ryzen measurements are [quality across quantizations](labs/LAB25-quantization-quality.md) after local integration, and [concurrent load](labs/LAB26-concurrent-load.md) on a working server. The extended-series research plan is below; each lab specifies its own minimum scope.

Plan dated **2026-09-20**, expanded to multiple inference engines on **2026-09-21**, for the owner's specified **Ryzen AI Max+ 395, 128 GB shared memory, Linux**. The objective is to find practical local models for our autonomous agents, then measure what each harness needs with the same model. Generation speed alone does not determine agent quality.

A [candidate catalog](local-model-candidates.md), [Linux runbook](local-model-runtime.md) and `npm run local:plan` command are available. Reconciliation on 2026-10-22 found LAB02–06/26 measurements and independently evaluated Pi/local/T002 runs (two fail, one pass). The [lab status overview](labs/README.md#execution-status-as-of-2026-10-22) distinguishes these observations from report acceptance and remaining series. File sizes and developer claims are kept separate from our measurements; power consumption is unverified.

**Vulkan and HIP/ROCm are equally required branches.** The [engine matrix](local-inference-engines.md) adds vLLM, SGLang, Transformers/PyTorch, Ollama, LM Studio and Lemonade; subsequent sections account for that extension. Services built on llama.cpp are evaluated separately from independent kernel engines. A GGUF catalog does not define another engine's native checkpoint size.

## Memory and the meaning of “fits”

128 GB is shared CPU/GPU memory; do not add the GPU allocation to it. The vendor describes up to 96 GB for graphics, but that is not the measured Linux heap of this machine. Before preflight, use conservative assumptions: **119.2 GiB total memory**, **89.4 GiB GPU budget**, and **16 GiB OS/harness reserve**. Planner units are GiB (2³⁰ bytes); interpret 128/96 GB as decimal for the initial lower estimate. Replace these assumptions with actual values after checking `/proc/meminfo` and Vulkan/ROCm. Sources and limitations are in [hardware.json](../experiments/local-models/hardware.json) and the runbook.

Queue estimate:

```text
budget = min(usable_RAM_GiB − OS_reserve_GiB, safe_GPU_budget_GiB)
estimate = weights_GiB + runtime_reserve_GiB + KV_or_state_reserve_GiB
headroom = budget − estimate
```

Initial runtime reserve is 6 GiB; KV/state reserves are 4/8/16 GiB for 8/16/32K context. This is a **queue-planning heuristic**, not an architecture-specific formula. Dense attention, sliding windows, MLA and hybrid recurrent state need different calculations. MoE weights include all experts, not just active parameters. Check peak loading, prefill and generation separately: GGUF size on disk is insufficient.

Admit a candidate to a series only if loading and filling the selected context finish without OOM, budget violations or persistent swap-in/out. The agreed OS reserve must remain available, and logs must confirm all required GPU allocations. CPU offload, mmap and partial GPU offload are allowed only as separate, explicitly described variants, never as silent rescue of the primary configuration.

## Campaign order and scope

This is a sequence of work sessions, not a promised completion date. Execution on the machine is strictly sequential: one model server, one slot, one agent attempt. Sort the catalog by priority, then weight size; test large conditional candidates after the small control. There is no need to download all weights in advance: download pinned artifacts sequentially, checking free SSD space including the downloader's temporary cache.

| Stage | Work | Scope / limit | Gate |
| --- | --- | --- | --- |
| 0. Machine profile | CPU, BIOS, Linux/kernel, RAM, GPU heap, Vulkan/ROCm, power mode, SSD | One session; roughly 1–2 hours excluding driver installation | Measured budgets, versions and initial state recorded |
| 1. Backend and protocol | Small control; pinned llama.cpp Vulkan **and HIP/ROCm** on one commit/artifact; streaming, tools, reasoning | Roughly 2–4 hours once the stack is ready; record incompatibility rather than silently dropping a branch | Valid responses and tool round trip; no hidden backend/model substitution |
| 2. Resource screening | All candidates: 8K → 16K → 32K on both llama.cpp backends; then independent ROCm engines and serving layers from the matrix | Up to **216** baseline sets (12 × 2 × 3 × 3); additional bounded series follow the matrix, not a full Cartesian product | Stable fit at 16K; evaluate 32K and each new engine separately |
| 3. Agent pilot | Each qualified model on A2/T002 using Pi as the reference harness | One new attempt each, 900-second timeout; 15 minutes is a limit, not a speed forecast | Trace and independent verdict obtained; all failures recorded |
| 3b. Engine effect | Up to 3 finalists × 2 qualified engine deployments × T001/T002 × 3 repeats in Pi | Up to **36** new attempts, at most **9 hours** of timeout budgets, separate from the main series | Artifacts and quantization accounted for; different quantizations mean deployment comparisons |
| 4. Main series | Up to 3 finalists × 4 harnesses × T001/T002 × 3 repeats | Up to **72** agent attempts, at most **18 hours** of execution timeouts, plus setup/evaluation | Comparable conditions and complete triples without selecting only successes |
| 5. Audit and ablations | T003 for the same 3 × 4 × 3; then one ablation for the best pair | Up to **36** audits (9 hours of timeout budgets); first T002 ablation adds 3 attempts | Interpret audit separately; establish component effects only through before/after comparisons |

Stages 0–2 can precede agent integration. **Stages 3–5, including 3b, depend on the local-provider bridge and extended result records** described below. Do not run them using existing cloud profiles with network restrictions disabled. Before the main series, select and pin one engine deployment per model, then keep it fixed across all four harnesses.

Use the same 900-second limit for compared agent configurations; task turn and contract limits remain in force. If the best local models consistently time out, preregister a separate 1800-second group for every participant in a new series; do not extend individual failed attempts. Change only one factor at a time for Q4/Q6/Q8, 16K/32K context, f16/q8 KV, reasoning on/off and Vulkan/HIP ablations.

Within a model series, alternate harnesses in a saved, preregistered order rather than finishing all repeats of one harness before another. Record the order seed, power mode, warm/cold state and cooling pauses. Measure large-model loading separately from agent-attempt duration; preserve the entire order and every failure.

## Model selection without confounding factors

The first wave contains the small control and catalog priority 1. The second is priority 2, including large MoEs and a dense control. Priority 3 covers resource boundaries and generation comparisons. Actual memory takes precedence over nominal 30B/70B/120B classes. Huge models at extremely low bitrates and SSD expert streaming are outside the main series; they are separate tradeoff studies.

Before the pilot, exclude only technically incompatible configurations (OOM, protocol or unavailable backend); retain low speed as a result. Resource preflight failures or inability to load are not agent-task failures. An agent run that starts and ends in a timeout or error remains a failed attempt in its series.

Select up to 3 finalists in a preregistered order: independent T002 result (`pass`, then `partial`, then `fail`), then shorter execution time, then lower peak shared-memory use. Do not award a win on an unknown metric when coverage is incomplete. One pilot is a weak screening signal; conclusions apply only to finalists, not a global ranking of all models. Also retain a quality/time/memory frontier so a large slow finalist does not displace a practical fast option.

Use sampling parameters from each model card and pin them per model; they remain identical across harnesses for that model. Thinking/reasoning effort, maximum output and chat template are conditions. Context means the complete input + output budget: baseline 16384, reserving up to 4096 output tokens, including reasoning if the server counts it as output. Check the actual effective input budget in the API and harness. Prioritizing model-card guidance does not mean forcing `temperature=0` on every model.

## Harnesses and required integration

The primary local-series candidates are **Pi, mini-SWE-agent, OpenCode and OpenHands**. Pi/T002 already has a local provider for native llama.cpp ROCm/Linux and Metal/macOS. mini-SWE-agent, OpenCode and OpenHands remain integration plans; their local series are not qualified.

| Harness | Basis | Verification before inclusion |
| --- | --- | --- |
| Pi | [Custom models / OpenAI-compatible](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md) | Custom model registry, exact endpoint, roles, streaming tool calls and native turn bound |
| mini-SWE-agent | [Local models](https://mini-swe-agent.com/latest/models/local_models/) | API base, DefaultAgent's own text action protocol, unknown cost without an invented rate |
| OpenCode | [Custom provider](https://opencode.ai/docs/providers/#custom-provider) | OpenAI-compatible provider, explicit context/output, usage and native tools |
| OpenHands | [LLM in the SDK](https://github.com/OpenHands/software-agent-sdk) | Pinned SDK base-URL parameter, streaming/tools and actual iteration limit |

Codex is an additional branch only after local API/protocol checks on the pinned version. Claude Code, Antigravity, Copilot and Amp are excluded from the main local plan without a separately documented and verified route. A model's presence in a cloud catalog does not imply that requests can be sent to a self-hosted server.

Technical-readiness plan, completed **before** stage 3:

1. A trusted local inference service outside the task workspace, without shell/tools or a mount of the repository containing hidden checks. The agent retains its own Docker sandbox; its 2 GiB limit must not constrain the model server.
2. A narrow proxy route to one pinned server address/port. Current `egress.mjs` deliberately forbids private addresses. A separate local-endpoint policy must deny the rest of the LAN and administrative APIs; retain the shared SSRF/public-source filter. Inference must not use cloud fallback.
3. Each adapter needs an explicit local provider, endpoint, model alias, context/output and protocol. If the endpoint uses a secret, obtain it from `.env` through the selected profile. A dummy auth marker is not a paid API key.
4. Support local identity/metadata in `results/schema.json`, validation, prepare snapshots and compare. Pi already implements versioned `local_inference`; use the same verifiable contract when extending other adapters, rather than manually adding arbitrary fields to `run.json`. The comparison key must include weight hashes, quantization, template, backend commit, context, KV dtype, sampling, reasoning and hardware profile.
5. Synthetic bridge integration tests: successful tool round trip, rejection of another IP/port, oversized/error responses, timeout and cleanup, alias/weight changes and unknown usage. Then perform one real pilot with independent evaluation, adding a ledger row for each new component.

## Measurements and records

For the backend stage, save: Linux/BIOS/driver snapshot; llama.cpp commit and build flags; GPU device/heap; weight repository/revision, all shard names, bytes and SHA-256; tokenizer/chat-template hash; model alias; quantization; context, batch/ubatch, KV/state dtype, GPU layers/offload, slot count; sampling/reasoning; load time; TTFT; prompt/decode tokens/s; peak RAM and device allocations; swap delta; wall-clock time; errors and raw logs. Do not double-count shared RAM and GPU allocations. Separate prefill from decode, and cold starts from warm execution. A maximum-context measurement must actually fill the context, not merely start an empty server.

Also record two repeats of each of five protocol cases: ordinary text, streaming, tool-call → tool-result → final, errors/unknown tools, and long context. Separate reasoning from the final answer where the architecture uses it. For mini-SWE-agent, also check its native text action protocol; a harness using that protocol need not use JSON function calling.

Agent attempts remain in `results/runs/<run-id>/` under the main [protocol](method.md). Backend probes are stored separately in `experiments/local-models/measurements/<probe-id>/` with their own `metadata.json` and raw logs; they are not completed tasks or `run.json` records. Planned profiles are not measurements. Existing bundles are listed in the [lab status overview](labs/README.md#execution-status-as-of-2026-10-22); missing acceptance or preregistration remains an explicit limitation.

Electricity: if a meter is available, record whole-system joules/Wh, idle baseline and the measurement method. TDP does not replace measured watts. No provider fee does not make a local run free: account separately for inference fee (0 only with verified local-only execution), kWh, a user-specified electricity rate and, if needed, depreciation. Unknown quantities are `null` with a reason.

Use one frozen source archive for T001; otherwise web data changes at the same time. Current T003 setup includes the selected harness configuration, so different harnesses produce different inputs; do not include that audit in a causal cross-harness comparison. The first 72 T001/T002 attempts form the comparison; the 36 T003 attempts are separate diagnostics. Do not read hidden checks while developing an adapter; the evaluator works outside the agent container.

## Readiness and next actions

- [x] Record the owner's machine and Linux target; prepare a dated shortlist with sources.
- [x] Provide a reproducible queue estimate without downloading models: `npm run local:plan`.
- [x] Add 12 engine/backend profiles and a separate engine-comparison series: `npm run local:engines`, `npm run local:plan -- --engine all`.
- [ ] Preflight on the actual Ryzen and a measured hardware profile.
- [ ] Pin weights/licenses/template and backend builds; first cold/warm smoke.
- [ ] Local provider bridge, metadata schema, isolation tests and compare keys.
- [ ] Resource probes, pilot, independent evaluation and finalist triples.

Start at stage 0 on the Ryzen itself, then use the catalog's small control. Do not assign speed, verdicts or completion dates before measurement. Revisit the catalog before downloads, when a new model appears, when the backend/driver changes and after the first results. A weight update always creates a new series configuration.
