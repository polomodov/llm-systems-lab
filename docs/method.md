# Experiment protocol

## Objective and unit of comparison

Measure what each harness needs to execute the same independent specification on the same episode. Account for instructions, constraints and built-in capabilities. A harness name alone does not explain a result: record the model, its settings, CLI version, environment image and task conditions.

| Aspect | What to record |
| --- | --- |
| Loop and stopping | Turns, stop reason, USD/time limits, actual cost |
| Context and memory | Prompt/spec/config snapshot, ablation variant, availability of compaction counts |
| Tools and environment | Adapter, immutable image ID, cwd, network and mounts |
| Evaluation | Independent judge, method, check version and evidence hash |
| Orchestration | Presence and observability of subagents; unknown does not mean zero |
| Observability | Original CLI stream, measured fields, reasons for missing metrics |
| Trust and boundaries | Restricted workspace, external coordinator, task-specific network |

## Replayable episode

A task contains a public `task.md` contract, a machine-readable `task.json` descriptor, a safe `setup.sh` and a hidden check. The descriptor defines the agent, workspace kind (`repo` — a Git project in `sample/` with a working branch and a patch against the seed commit; `files` — a read-only directory with writes limited to `artifacts/`), evaluation method, required artifacts, additional network domains and setup arguments. The coordinator does not branch on task IDs. Coordinator fixes do not change contracts. Setup requires a separate empty directory. Preparation captures sources, initial files and their hashes, date and Git revision; a dirty working tree is marked explicitly, and coordinator code is included in the snapshot.

The agent does not receive a mount of the original lab repository, hidden checks, metadata or the original `.env`. Regex hooks and `chmod` under the same user are not sufficient boundaries. Docker isolation and the gateway remain in every ablation variant. Details and credential-isolation limits are in `experiments/common/README.md`.

T002 has a reproducible Git commit. The internal `.git/index` contains file timestamps, so the full snapshot verifies its integrity, while comparison grouping excludes `.git/` and uses the initial commit separately. T003 copies allowlisted sources and configuration for the selected harness; different configurations are different inputs and are not compared as an identical episode.

For T001, live source retrieval creates a research archive, but pages can change between runs. A controlled series uses one saved `trace/sources.jsonl` through `prepare-run --source-archive`. The GET gateway returns the stored HTTP status, URL and body, allowing seed URLs and depth-1 links. New fetches are forbidden during replay; missing responses produce an unavailable source, not an invented fact. A URL-list snapshot without page bodies is not complete replay. `npm run capture-sources` captures seed URLs without an agent run. Depth-1 links are excluded and read as unavailable during replay, as recorded in the archive manifest.

## Lifecycle and measurements

`planned → prepared → running → awaiting_review → completed`; failed or interrupted execution becomes `aborted`. A `running` record whose coordinator died (SIGKILL or host failure) is changed to `aborted` by `npm run reconcile`, with reason `coordinator_lost`. Containers are located using names in `trace/runtime.json`, their logs are saved with the credential redacted, and execution never resumes automatically. CLI exit 0 advances only to awaiting_review. Independent evaluation advances to completed with pass/fail/partial. Templates and unfinished attempts are not presented as results.

Every attempt gets a new run ID. Never overwrite an old record with a new execution. Zero is valid only as an observed measurement. Unknown cost, tokens, turns, approvals, compactions and subagents are recorded as `null`, with reasons in `metrics_unavailable`. `tokens_in` includes ordinary input and cache read/write; the raw trace allows its definition to be examined. CLI cost is a harness-reported measurement, not an independent billing reconciliation.

Task budgets belong to the contract: the runner reads turn and USD limits from the sealed `task.md` and has no defaults of its own. A contract without a budget stops execution. The Claude adapter passes max-turns and max-budget-usd; the behavior of a particular version still requires a real run. The shared runner forcibly stops the container on timeout. The other eight adapters do not establish a hard USD cap; execution requires explicit `--budget-mode observed`. Turns are limited only where a native capability exists; otherwise launch records `turns=null` and the external timeout is the only enforced loop limit. Such research attempts state their deviation from the contract and are grouped separately. The loop's USD value is a target budget; execution.budget_policy describes enforcement.

## Model identity and comparability

Specify an exact available model ID; floating aliases are forbidden. Record the requested ID separately from the ID observed in the assistant response. An observed model switch aborts execution. The absence of an observed ID does not prove the provider selected the requested model; the report shows the fraction of verified identifiers.

`model.lock` is a fact about a specific configuration, not an assumption based on a brand. Eight adapters accept an explicit ID or supported selector; Amp chooses its underlying model through a managed mode. For Amp, record `model.selection=managed`, selector `managed:<mode>` and `model.lock=true`. Provider and selection method are comparison conditions. `harness.mode` distinguishes native SDKs from CLIs; native project loops are not replaced with a shared agent.

Report grouping preserves task, agent, inputs, requested model/managed selector, provider, model selection, model lock, ablation, budget policy, limits, network and evaluation method. Each group shows separate harness/version/image entries. Live T001 sources are marked live; such a group cannot establish the effect of the harness alone. Comparisons involving different models or images require separate interpretation, not a shared ranking.

Start with single runs, then preregister series of three. `pass@3` means at least one pass; `pass^3` means three passes. The CLI forms non-overlapping triples in run-ID order and reports one or two remaining attempts separately. Select the intended IDs explicitly for a scientific series, without selecting only successes. Started aborted attempts remain in the denominator; pre-start failures and unfinished records are listed separately.

## Local models as distinct conditions

In the local campaign, the inference backend is separate from the agent harness: preserve the same server, artifact hash, quantization, template, context/KV, sampling/reasoning and hardware profile between harnesses. A Vulkan/HIP, offload or quantization change creates a new condition group. A nominal model ID and GPU name are insufficient. Weight size and memory calculations are plans, not measurements. TDP is not power consumption; electricity cost and inference fees are accounted for separately.

The [inference-engine matrix](local-inference-engines.md) records kernel engine, GPU backend and serving application separately. To estimate an engine's effect, keep weights/quantization/template fixed; otherwise compare complete deployments. GGUF estimates cannot be transferred to native safetensors without a new artifact. `artifact-required`/`engine-memory-required` indicate missing planning data, not task results. Different engines' built-in benchmarks are not equivalent HTTP-latency instruments.

The [local-model plan](local-models.md) defines resource probes, selection and repeats. Versioned `local_inference` is integrated into schema/prepare/compare and a separate Pi/T002 bridge; current qualification and limits are described below and in LAB08 reports. Other local harnesses require integration; cloud profiles are not a local route. Backend microbenchmarks are stored separately from agent-run records and cannot count as task success. T003 retains the limitation that different harnesses have different inputs.

## Independent judge

The operator runs the hidden check outside the agent container. T002 uses hidden-check; T001/T003 use rubric, with both a script and rubric considered for T001. Fix the evaluation protocol before execution. An evaluation contains run ID, result, evaluator, check_output and hashes of two manifests: final artifacts and workspace. evaluation-template creates these hashes; the evaluator supplies the decision.

judge-run verifies input/output integrity and required artifacts but does not replace substantive judgment. Evaluation cannot change result bytes. `check` and `compare` recheck integrity after completion. Transfer the entire inputs/trace/artifacts archive together with run.json; retain empty trace directories using `.gitkeep`. Workspace is git-ignored and optional after evaluation: if present, it is fully checked; if absent, the archive and final-manifest hash are checked, and check/compare explicitly report the missing live tree. For an archived `prepared` record, sealed inputs and their bound initial-workspace inventory are checked. `check` explicitly reports a missing live tree, and status stays `prepared/pending`. A present tree with changes or symlinks is rejected. Execution through `run` still requires the full workspace and verifies it against the initial snapshot: successful archive validation does not authorize execution without the tree. Infrastructure tests use synthetic fixtures and do not read hidden checks.

## Evidence classes

- **Verifiable fact** — a linked primary source or a measurement with a run ID.
- **Product snapshot** — a documented state at a particular date; vendor-favorable numbers are labeled as vendor claims.
- **Author's forecast** — an expectation with a verification criterion.
- **Management heuristic** — guidance, not a standard.
- **Author's inference** — an explicit chain from facts to interpretation.

Infrastructure smoke is not an autonomous-agent result. Before real runs exist, do not claim that one harness is better than another or that an added component improves success.

## Ablation and observation records

Baseline passes both specification and contract. `without-spec` removes specification text from the prompt while retaining boundaries. This variant does not delete naturally present files in the T003 repository under audit. Other ablations are not yet implemented; each addition requires a separately recorded variant and ledger row.

After each series, complete `experiments/<harness>/NOTES.md`: run IDs, conditions, required additions, blocked actions and removable components. The ledger records the component, assumption or boundary, evidence, date/model, retest trigger and ownership mode. A confirmed status requires actual completed before/after runs. If removing a component leaves the outcome unchanged, it becomes a removal candidate; ablation never removes safety boundaries.

### Versioned local configuration (LAB08)

The local provider is limited to Pi / T002 / controlled native llama.cpp: Metal/macOS and ROCm/Linux. Ryzen has independent fail/pass verdicts; the Apple pilot awaits evaluation. Implementation status does not replace lab-report acceptance: the consolidated Ryzen bundle is blocked because repeats were registered retrospectively (reconciliation on 2026-10-22). Prepare accepts `--local-deployment` and seals the manifest into inputs. The additional `local_inference` record field has its own `schema_version=1`, `deployment_sha256`, canonical `fingerprint`, full `deployment` and an `observed` proof of the controlled process. Old cloud schema_version=1 records remain valid without this field; old runs are not manually migrated.

The fingerprint includes weights/revision/bytes/hashes/quantization, tokenizer/template, engine/backend/build pins, hardware/OS/power and the complete protocol/context/output/KV/cache/tools configuration. Compare adds it to conditions only for local runs. The observed alias is based on the owned PID, file checks before Popen and props/template checks before and after requests, not SDK metadata. Primary HTTP usage is separate from the SDK trace; absent usage is null with a reason. Zero SDK prices do not prove zero hardware/electricity cost.

The bridge preserves the agent's internal network. A trusted dual-network broker exposes only the host control listener on loopback and does not implement CONNECT. The native host-worker selects the single sealed loopback endpoint. The first implementation buffers SSE until finish/DONE: tool round trips can be checked, but TTFT is unknown. The shared source gateway and T001 replay are unchanged for cloud runs; local T001/T003 require separate acceptance.

### Language migration

The English publication translates current specifications, contracts and generated prompts. This changes input bytes and potentially model behavior, so it is a new condition rather than a relabeling of previous experiments. Original sealed Russian inputs remain unchanged and readable. Comparison groups use actual input hashes; see [archive provenance](publication.md).
