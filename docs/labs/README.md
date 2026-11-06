# Laboratory course: models, engines, and agent harnesses

Assignment version: **2026-10-07**. The local inference testbeds are **Ryzen AI Max+ 395 / 128 GB / Linux** and **Apple M5 Max / 128 GB / macOS**. The course examines how the model, GPU backend, inference engine, and agent harness affect the solution of the same tasks. Its output is your reports and reproducible data, not a predetermined winner.

There are **53 labs**: ten general and local labs, nine separate labs covering every implemented harness, nine labs on quality, resilience, and system evolution, eight Apple labs, seven SPACE labs, five Kubernetes and GPU labs, and five AWS and Terraform labs. The three infrastructure tracks, LAB36–52, have been **frozen** since 2026-11-05 (see below); 36 labs are active. Each has an objective, hypothesis, prerequisites, step-by-step procedure, empty tables, submission bundle, completion criteria, and review questions. The general [research protocol](../method.md) remains in force. The [model catalog](../local-model-candidates.md) and [engine matrix](../local-inference-engines.md) serve as references for the assignments.

<a id="execution-status-as-of-2026-10-22"></a>

## Execution status as of 2026-10-22

As of 2026-10-22, there were 97 `LABxx-session` bundles for 18 labs; the remaining 34 had no bundles. On 2026-11-05, all local model bundles were moved out of the tree into the [archive](../../experiments/local-models/measurements/README.md): the links below point to permalinks at the last commit containing the measurements; contents and statuses were unchanged. Separate smoke/preflight manifests outside this format are not included. `catalog.json` and `npm run labs` describe **execution prerequisites** (`readiness`), while the table below describes actual results. A single `completed` session does not automatically satisfy a lab's entire minimum; `ready_for_review` means only that the bundle is complete. All bundles have `reviewer_decision=null`: no formal acceptance review was assigned. After reconciliation, all 97 pass `lab:check --mode submission`: 45 have status `completed`, and 52 are `blocked`. These are session counts, not counts of completed labs.

| Labs | Actual status | Evidence and remaining work |
| --- | --- | --- |
| LAB01 | Preparation minimum completed | [Apple preparation](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB01-apple-prerequisite-20261007/report.md); no model was run |
| LAB02 | Observations preserved; both reports `blocked` | [First inventory](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB02-first-pass/report.md), [after ROCm](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB02-after-rocm/report.md): the original protocol before observations is unconfirmed; attempt registers were reconstructed retrospectively |
| LAB03 | Some artifact checks completed; original Qwen9 selection `blocked` | [Qwen9](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB03-qwen35-9b/report.md) has no confirmed preregistration; the [new GPT-OSS preregistration session](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB03-gpt-oss-120b-prereg/report.md) retains its own status |
| LAB04–06 | Minimums completed in the configurations studied | [Vulkan/HIP](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB04-qwen35-9b-prebuilt/report.md), [context/tools](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB05-qwen35-9b-hip-prebuilt/report.md), [vLLM/SGLang/reference](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB06-qwen35-9b-rocm-prereg/report.md). Different toolchains and eager/graph modes limit comparisons |
| LAB07 | No report | Ryzen services have not been studied in a separate lab |
| LAB08 | Pi/T002 bridge implemented; reports `blocked` | [Ryzen](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-ryzen-linux-bridge/report.md): two `fail` results, then `pass`; part of the attempt register is retrospective. [Apple](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-native-requalification-20261010/report.md): pilot `awaiting-review`; the [October 12 repeat](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-provider-bridge-20261012/report.md) was stopped by the resource guard before chat; no new T002 was run. Other local adapters have not been qualified |
| LAB09–10 | No reports | No comparative agent campaign or ablation has been conducted |
| LAB11–14, LAB16–19 | No reports | Adapters and instructions exist; the labs have no evaluated episodes of their own |
| LAB15 | Local practical minimum executed; summary report `blocked` | [Pi/Ryzen](../../experiments/pi/measurements/LAB15-local-ryzen/report.md): actual verdicts are preserved; the repeat and follow-up were not recorded in the original plan. The cloud track was not executed |
| LAB20 | `blocked`: minimum not met | [Two passes by one model](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB20-offline/report.md) do not replace two independent people |
| LAB21–25, LAB27 | No reports | LAB21–24 require engineering extensions; LAB25/27 await their own comparative series |
| LAB26 | Minimum completed | [Ryzen c1/c2/c4](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB26-ryzen-qwen35-9b/report.md): a queue for one server slot, with no evidence of parallel GPU speedup |
| LAB28–31 | Minimums completed for the selected deployments | [Inventory](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB28-apple-first-20261007/report.md), [artifacts](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB29-apple-qwen35-9b-20261007/report.md), [Metal](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB30-apple-qwen35-9b-metal-20261007/report.md), [MLX](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB31-apple-qwen35-9b-mlx-20261007/report.md) |
| LAB32 | Partial qualification | [MLX 8K/16K/32K](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB32-apple-mlx-identity-repeat-20261010/report.md): input budgets; hard cap/overflow and physical GPU resource release are unconfirmed. The full sequential Metal chain remains incomplete |
| LAB33 | All nine sessions `blocked` | [SDK cancel](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB33-apple-sdk-framing-20261010/report.md): the third measured repeat was interrupted by the memory guard; HTTP cancellation was not performed. In the [lifecycle session](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB33-apple-lifecycle-20261008/report.md), two original `.log` files are missing and recorded as unavailable |
| LAB34 | Minimum completed for one GPU slot | [Short matrix and 35.51 minutes](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB34-apple-sustained-resume-20261009/report.md); simultaneous 2/4 GPU slots are not qualified |
| LAB35 | All sessions `blocked`; Apple sub-experiment executed | [Tensor repeat](https://github.com/polomodov/llm-systems-lab/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB35-apple-tensor-pinned-20261009/report.md) is preserved as executed attempts; there is no fresh comparable Ryzen pair or agent series |
| LAB36–42 | **Frozen on 2026-11-05**; no measurements or track implementation | [SPACE](../../experiments/space/README.md) |
| LAB43–47 | **Frozen on 2026-11-05**; no measurements or track implementation | [Kubernetes/GPU](../../experiments/k8s-gpu/README.md) |
| LAB48–52 | **Frozen on 2026-11-05**; no measurements or track implementation | [AWS/Terraform](../../experiments/aws/README.md) |
| LAB53 | Manual dated 2026-10-31; no reports | The replay/analyze tool has been checked offline; it has not been run on the testbed |

The agent register contains 11 records: 3 `completed` (2 `fail`, 1 `pass`), 6 `aborted`, 1 `awaiting_review`, and 1 `prepared`. All evaluated results are Pi/local/T002. `compare` forms no complete group of three with identical conditions: the October 15 success cannot be combined with the two October 12 failures after the bridge changed. These data establish neither a harness ranking nor the effect of a component change.

The October 22 reconciliation involved no new runs and no changes to run verdicts. Old protocols and primary data were not supplemented; accounting corrections are described in the corresponding reports. `blocked` preserves useful measurements and honestly identifies an unmet qualification requirement. Further execution requires a separate preregistered session, not changing the dates of an old one.

## Apple M5 Max track

The [Apple profiles and general protocol](../../experiments/local-models/apple/README.md) describe native macOS, memory, evidence capture, and the CLI. Main path: **01 → 28 → 29 → 30 or 31 → 32 → 33/34 → 35**. Complete both 30/31 to compare engines; one is enough for a standalone protocol smoke test.

| Lab | Output | Prerequisites |
| --- | --- | --- |
| [LAB28. Apple M5 Max inventory and unified memory](LAB28-apple-hardware.md) | Inventory, Metal recommendation, RAM/swap | 01; Mac |
| [LAB29. Pinning GGUF and MLX artifacts](LAB29-apple-artifacts.md) | Separate GGUF/MLX manifests and hashes | 28 |
| [LAB30. llama.cpp on Apple Metal](LAB30-apple-metal.md) | Pinned Metal build and PP/TG baseline | 28, 29 |
| [LAB31. Native MLX-LM inference](LAB31-apple-mlx.md) | MLX runtime and memory measurements | 28, 29 |
| [LAB32. Context, streaming, and tools on Mac](LAB32-apple-context-tools.md) | 8K/16K/32K, tools/SSE, cancellation, and recovery | 29 and one of 30/31 |
| [LAB33. Ollama and LM Studio on Apple Silicon](LAB33-apple-serving.md) | Ollama and LM Studio: runtime identity/API | 32 |
| [LAB34. Concurrent load and Mac stability](LAB34-apple-load.md) | 1/2/4 requests and 30 minutes of stability | 32; 33 when using a wrapper |
| [LAB35. Apple versus Ryzen on identical tasks](LAB35-apple-ryzen-comparison.md) | Shared GGUF/episodes on Apple and Ryzen | 04, 08, 09, 32, 34; full bridge acceptance and the agent series remain incomplete |

The catalog stores common mandatory dependencies in `prerequisites` and "at least one" alternatives in the optional `prerequisites_any`. LAB08 accepts LAB05 **or** LAB32: Mac does not require completion of the Linux labs. The CLI displays alternatives; `lab:new` still only creates a draft and does not check actual completion. LAB35 includes comparison with Ryzen and therefore requires its baseline.

All new reports use the existing path `experiments/local-models/measurements/LABxx-session/`. LAB35 has `implementation-required`: an HTTP smoke test does not replace the provider bridge and real run records. The manuals contain no prefilled results. Compatibility of a specific M5 Max/runtime/model combination remains `unverified` until a smoke test.

<a id="infrastructure-branch-freeze"></a>
<a id="frozen-infrastructure-tracks"></a>

## Infrastructure branch freeze

On 2026-11-05, the SPACE (LAB36–42), Kubernetes and GPU (LAB43–47), and AWS and Terraform (LAB48–52) tracks were set to `frozen` in `catalog.json`. Reason: none of the 17 labs has measurements or an implementation, and their scope diluted the focus of the harness lab. The manuals were retained unchanged apart from a banner at the top; `npm run labs` displays `frozen`, and `lab:new` refuses these labs. Each lab's planned readiness is preserved in `frozen.planned_readiness` in case the track is unfrozen.

The next step for these tracks is a separate teaching repository: move `docs/labs/LAB36–52*.md`, the `experiments/space/`, `experiments/k8s-gpu/`, and `experiments/aws/` directories, and the corresponding catalog entries there. Unfreezing them within this lab requires at least one measured session and a decision recorded here.

<a id="space-track"></a>

## SPACE track

[SPACE](https://github.com/polomodov/SPACE) is an open sandbox platform built on Firecracker microVMs (a fork of `perplexityai/SPACE`). This track tests it as an agent execution environment. Testbeds: **A** — Ryzen AI Max+ 395 / 128 GB / Linux (the same as in LAB02); **B** — HONOR MagicBook X16 laptop, Ryzen 7 PRO 8845HS / 32 GB / Ubuntu. Sessions are named after the testbed: `ryzen-01`, `honor-01`. Main path: **01 → 36 → 37 → 41 → 42**; complete LAB38–40 after 36 in any order. The [SPACE directory](../../experiments/space/README.md) stores recipes, scripts, and reports.

| Lab | Output | Prerequisites |
| --- | --- | --- |
| [LAB36. Host inventory, Kind deployment, and smoke test](LAB36-space-deploy-smoke.md) | Testbed inventory, bring-up time/memory/disk, smoke verdicts on two machines | 01; Linux x86_64 with KVM |
| [LAB37. Pi and OpenHands in SPACE microVMs](LAB37-space-harness-vm.md) | Templates from harness images, offline smoke in a VM, runner backend, T002 with run records | 36, 15, 17; backend implementation required |
| [LAB38. Tool layer](LAB38-space-tool-layer.md) | Exec/files server on top of SPACE for two harnesses, per-call overhead | 36; implementation required |
| [LAB39. State layer: suspend/restore and fork](LAB39-space-state-layer.md) | Episode checkpoint, restore verification, three attempts from a fork | 36 and one of 37/38 |
| [LAB40. Latency and pools](LAB40-space-latency-pools.md) | Time to first command: cold, pool, base snapshot, restore | 36 |
| [LAB41. Network and secrets](LAB41-space-network-secrets.md) | Egress only to the provider API, probe table, key outside the VM (extension) | 37 |
| [LAB42. Campaigns on SPACE](LAB42-space-campaign.md) | Docker versus SPACE series, concurrency, and testbed B's limit | 09, 37, 41 |

Reports for this track are created in `experiments/space/measurements/LABxx-session/`: the catalog's `area` field routes labs that are not tied to one harness there. LAB37–39 and 41–42 have `implementation-required`: the current runner executes agents only in Docker. SPACE compatibility with each testbed remains `unverified` until LAB36. The SPACE installer installs packages, privileged containers, and nft rules; on testbed A, do not run it alongside LAB04–07 measurement series.

<a id="kubernetes-and-gpu-track"></a>

## Kubernetes and GPU track

This track teaches GPU workload orchestration in Kubernetes: how a GPU reaches a pod, how the scheduler divides a shared fleet, how an inference engine replica behaves under load, how to route LLM requests, and how to scale serving in the cloud. The testbeds are the same: **A** — Ryzen AI Max+ 395 / 128 GB / Linux with Radeon 8060S (`gfx1151`), single-node k3s; **B** — HONOR MagicBook X16 / 32 GB / Ubuntu, Kind with fake GPUs; LAB47 runs in a training AWS account. Main path: **02 → 05 → 43 → 06 → 45 → 46 → 47**; LAB44 only requires LAB01 and can be done in parallel. The [track directory](../../experiments/k8s-gpu/README.md) stores manifests, load generators, Terraform, and reports.

| Lab | Output | Prerequisites |
| --- | --- | --- |
| [LAB43. GPU in a pod: k3s and the AMD device plugin](LAB43-k8s-gpu-pod.md) | Verified driver → device plugin → pod chain, k8s inference overhead | 02, 05; testbed A |
| [LAB44. Scheduling on a fake GPU fleet](LAB44-k8s-gpu-scheduling.md) | DRA claims, Kueue quotas with strict limits and with a cohort, DDP recovery after pod loss | 01; testbed B |
| [LAB45. vLLM in Kubernetes and replica capacity](LAB45-k8s-gpu-vllm-capacity.md) | TTFT/ITL curves, prefix caching benefit, capacity under an SLO | 06, 43; testbed A |
| [LAB46. Inference-aware routing and cold start](LAB46-k8s-gpu-inference-routing.md) | Round-robin versus endpoint picker, cold-start stages | 44, 45; testbeds A and B |
| [LAB47. EKS, Karpenter, and KEDA](LAB47-k8s-gpu-eks-autoscaling.md) | Stages of bringing up a GPU replica in the cloud, cost per million tokens, clean teardown | 45, 49; AWS account |

Reports for this track are created in `experiments/k8s-gpu/measurements/LABxx-session/` through the catalog's `area` field. Sessions are named after the testbed: `ryzen-01`, `honor-01`, `aws-01`. Support for the `gfx1151` APU in the AMD device plugin remains `unverified` until LAB43. NVIDIA-specific mechanisms (MIG, time-slicing, NCCL across multiple GPUs) cannot be tested on these testbeds; LAB47 provides only one cloud GPU. On testbed A, do not run k3s or Kind alongside LAB04–07 series or a deployed SPACE instance.

<a id="aws-and-terraform-track"></a>

## AWS and Terraform track

This track covers the cloud requirements for an AI infrastructure lead: an account with cost controls, networking and IAM, infrastructure code with tests and CI, cold start, and reliable GPU serving. Everything is created with Terraform in a training AWS account and deleted in the same session. Path: **01 → 48 → 49 → 50**, then **45 → 47** from the Kubernetes and GPU track (LAB47 uses the VPC from LAB49 and optionally the GPU pool module from LAB50), then **51** and **52** in any order. LAB48–50 do not require a GPU; request a G-instance quota at the beginning of LAB48. The [track directory](../../experiments/aws/README.md) stores Terraform and reports.

| Lab | Output | Prerequisites |
| --- | --- | --- |
| [LAB48. Training AWS account as code](LAB48-aws-account-baseline.md) | Remote state with locking, budget, a role instead of root keys, drift, and a residual-resource check script | 01; AWS account |
| [LAB49. Networking and IAM for a GPU platform](LAB49-aws-network-iam.md) | Cost and speed of downloading weights through NAT and endpoints, least privilege | 48 |
| [LAB50. Terraform as a team product](LAB50-aws-terraform-ci.md) | GPU pool module with tests, share of errors caught by each tool, CI with OIDC | 49; repository with Actions |
| [LAB51. GPU replica cold start in AWS](LAB51-aws-gpu-cold-start.md) | Benefit and cost of ECR, weights from S3, and preloading, broken down by stage | 47 |
| [LAB52. GPU serving reliability in AWS](LAB52-aws-gpu-reliability.md) | Errors and TTFT during Spot interruption with and without protection, alerts, runbook | 47; Spot quota |

Reports for this track are created in `experiments/aws/measurements/LABxx-session/`, with sessions `aws-01`, `aws-02`. Terraform for LAB48–50 lives in `experiments/aws/terraform/`; cluster changes for LAB51–52 build on the LAB47 code in `experiments/k8s-gpu/terraform/`. AWS prices are vendor claims with an access date; session costs come from Billing without the account ID.

## Ryzen track and general labs

| Lab | What you will obtain | Previous labs | Execution environment / readiness |
| --- | --- | --- | --- |
| [LAB01. Reproducible episode](LAB01-reproducibility.md) | Prepared task record, verified snapshots and boundaries | — | Already available on a machine with Node/Git/Bash; Docker for the additional check |
| [LAB02. Ryzen inventory and memory](LAB02-hardware.md) | Hardware inventory, measured RAM/heap, and planned budget | 01 | On the Ryzen/Linux machine itself; no BIOS or driver changes |
| [LAB03. Models and artifacts](LAB03-artifacts.md) | Selected weights, immutable revision, shard list, and verified hashes | 01, 02 | On Ryzen; SSD/access to published weights required |
| [LAB04. Vulkan versus HIP/ROCm](LAB04-backends.md) | Comparison of two backends in the same llama.cpp | 02, 03 | On Ryzen with the GPU stack and build dependencies prepared |
| [LAB05. Context and tools](LAB05-context-tools.md) | 8K/16K/32K boundaries, HTTP/tool round trip, and memory | 04 | On a running local server |
| [LAB06. Independent engines](LAB06-engines.md) | vLLM/SGLang and a Transformers control on ROCm | 03, 05 | Separate compatible images/weights; support statuses must be checked |
| [LAB07. Serving applications](LAB07-serving.md) | Ollama/LM Studio/Lemonade overhead and APIs | 05; also 06 for the vLLM recipe | After installing the selected services |
| [LAB08. Local integration](LAB08-local-bridge.md) | Implemented and verified bridge, metadata, and comparison conditions | 01 and one of 05/32 | Pi/T002 native llama.cpp is implemented on Ryzen/ROCm and Apple/Metal; qualification depends on the report and deployment; other adapters require implementation |
| [LAB09. Agent campaigns](LAB09-agent-campaign.md) | Pilot, independent verdicts, and harness comparison | 01 and selected LAB11–19; also 08 for local | Cloud comparison is available now; local comparison after LAB08 |
| [LAB10. Ablations and conclusions](LAB10-ablation.md) | Paired series, repeat analysis, and a justified ledger entry | 09 | Under the same pinned conditions as the agent series |

LAB01 can be completed before gaining access to Ryzen. LAB02–07 do not require a local-provider bridge and do not run task agents. The minimum Pi/T002 path in LAB08 can use the existing `local` provider; porting to other harnesses requires an engineering extension. Implementation and actual acceptance are different: see the status table above. LAB09–10 use the existing record lifecycle; their cloud path is available without LAB08.

## Separate labs for each harness

All nine labs start after LAB01 and use the current adapter's cloud provider. They require Docker, an available model/mode in the selected account, and an independent evaluator. The catalog status `available` means that the commands are implemented; it does not promise keys, a subscription, or a successful model run. This path does not require a GPU.

| Lab | What is studied beyond the common launch | Provider for the main path |
| --- | --- | --- |
| [LAB11. Claude Code](LAB11-claude-code.md) | CLI, permissions, limits, final usage/cache | Anthropic |
| [LAB12. OpenCode](LAB12-opencode.md) | JSONL events, explicit model, and incomplete accounting | Anthropic |
| [LAB13. Codex](LAB13-codex.md) | Autonomous exec, external sandbox, meaning of turn.completed | OpenAI |
| [LAB14. Antigravity CLI](LAB14-antigravity-cli.md) | agy headless, Google API, configuration, and terminal result | Google |
| [LAB15. Pi](LAB15-pi.md) | SDK createAgentSession, native tools, and message usage | Anthropic or OpenAI |
| [LAB16. mini-SWE-agent](LAB16-mini-swe-agent.md) | DefaultAgent, step limit, trajectory, and cost | Anthropic or OpenAI |
| [LAB17. OpenHands](LAB17-openhands.md) | Conversation, tools, iterations, and SDK metrics | Anthropic or OpenAI |
| [LAB18. Copilot CLI](LAB18-copilot-cli.md) | Model selector, subscription metrics, and native cache | Copilot |
| [LAB19. Amp](LAB19-amp.md) | Managed mode, unknown underlying model, and native cache | Amp |

Each lab has its own commands for installing the pinned image, running smoke tests and T002, evaluation, and trace analysis; the shared [evidence workflow](harness-workflow.md) explains states, independent evaluation, T001 replay, and T003. Each lab's minimum is one new evaluated T002 attempt and a report. Three repeats, T001/T003, and ablations are described as extensions and follow-up work.

**Path through all harnesses:** LAB01 → LAB11–19 in any order → cloud variant of LAB09 → LAB10. Pilots from individual labs can be used to qualify for LAB09; comparative attempts are created afresh. If an account for one system is unavailable, record a blocker for that specific lab and continue with the others; the entire path remains incomplete.

**Local path:** LAB01 → LAB02–05 → LAB06 and LAB07; then LAB08 and the local variants of LAB09–10. Before integrating each harness, complete the corresponding LAB11–19 at least through offline smoke. The full assignment set is prepared for both paths; the final data are produced by executing them.

## Quality, resilience, and upgrades

| Lab | Main experiment | Dependencies / readiness |
| --- | --- | --- |
| [LAB20. Evaluation calibration](LAB20-judge-calibration.md) | Two independent evaluators and anonymized answers; analysis of disagreements | 01; open teaching dataset, no API |
| [LAB21. Memory and context compression](LAB21-context-memory.md) | Full history, summary, and checkpoint in a multi-step episode | 09; implement and verify memory modes first |
| [LAB22. Tool design](LAB22-tool-design.md) | General and specialized interfaces with identical capabilities | 09; implement the variants and their observability first |
| [LAB23. Failure recovery](LAB23-failure-recovery.md) | Specified errors and retry policy in the full agent loop | 09; implement controlled failures and accounting first |
| [LAB24. One agent and delegation](LAB24-delegation.md) | Identical total budget, different ways of dividing work | 09; implement isolation and aggregate team accounting first |
| [LAB25. Quantization and quality](LAB25-quantization-quality.md) | Quantization variants of one model on real tasks | 08, 09; Ryzen and an accepted local bridge |
| [LAB26. Concurrent load](LAB26-concurrent-load.md) | 1/2/4 requests, latency, aggregate throughput, and memory | 05; Ryzen, a prepared server, and the HTTP driver included in the assignment |
| [LAB27. Regressions after an upgrade](LAB27-upgrade-regression.md) | Repeating episodes and ablations after changing one version | 09, 10; cloud path available; the new component requires qualification |
| [LAB53. Serving noise and agent decisions](LAB53-serving-noise.md) | Replaying recorded agent requests across server configurations, then 10+10 T002 attempts | 04, 08, 26; Ryzen, Pi, and the replay tool included in the assignment |

LAB21–24 are engineering assignments with qualification criteria before model comparison. Current adapters do not promise a universal choice of memory mode, tools, fault injection, or delegation. Their practice exercises can be completed in advance, but that does not satisfy the lab's main minimum. LAB25 also remains dependent on the engineering work in LAB08.

[Public multi-step episodes](episodes/README.md) include fixing multiple modules, migrating an interface, and analyzing conflicting sources. These are teaching fixtures with open checks, separate from registered T001–T003. Moving them into a comparative campaign requires a new task ID and qualification under the protocol; existing contracts do not change.

**Recommended next stage:** LAB20 and the first real pilot of a chosen harness → LAB09 → LAB08 and LAB25 for a local model. Then choose LAB21–24 based on the observed cause of failures. LAB26 can be completed earlier, after LAB05; LAB27 follows the first complete comparative series.

## Practice path without an API

[Practice mode](practice.md) replays recorded synthetic events locally, makes no network requests, and requires neither Docker nor Ryzen:

```bash
npm run lab:practice -- --scenario retry-429 --session first-pass
```

The exercise is created separately in `experiments/local-models/practice/`; it does not create `run.json`, evaluate a model, or fill in conclusions for the learner. Other scenarios include a valid tool round trip, an interrupted stream, and repeating an action after an ambiguous response. To report on the analysis, create a separate `lab:new` session with `evidence_class=synthetic`; the mode's instructions describe the format and how to transfer evidence.

## Getting started

Open the root of this repository. Commands for the Ryzen track target Bash/Linux; LAB28–34 target native macOS, and LAB35 uses both testbeds while accounting for their differences. LAB01 and coordinator commands are portable. Paths are relative to the root. Check `node --version` (≥22 required), `git --version`, and `bash --version`.

```bash
npm run labs
npm run lab:new -- --lab LAB01 --session first-pass
```

The second command creates a **new empty report bundle**:

```text
experiments/local-models/measurements/LAB01-first-pass/
  report.md
  manifest.json
  measurements.tsv
  raw/
```

Then open [LAB01](LAB01-reproducibility.md) and follow its steps. For another lab, replace `LAB01` with its ID. `--session` is your short English identifier, such as `baseline-01` or `rocm-02`; use only lowercase letters, digits, and hyphens. An existing directory is not overwritten. Repeating an experiment means a new session, not writing over previous results.

For LAB11–19, the helper selects the corresponding harness directory. For example:

```bash
npm run lab:new -- --lab LAB13 --session first-pass
```

creates `experiments/codex/measurements/LAB13-first-pass/` with the same files. Existing LAB01–10 paths remain in `experiments/local-models/measurements/`; this preserves links in existing reports, even if LAB09/10 uses a cloud model. The new teaching manifest's `harness_id` field is populated for individual harness labs; for general labs it is `null`.

The `lab:new` command does not install software, read `.env`, call models, or create `run.json`. It does not check actual completion of previous labs: you provide links to their reports and document satisfaction of the prerequisites. Here, `manifest.json` is the profile of a teaching report, **not the experimental run schema**. General LAB20–27 use the same `experiments/local-models/measurements/` directory, even for cloud or practice execution.

LAB04 build directories, LAB06 SGLang sources, and LAB07 Ollama weight copies are excluded from Git; original weights are stored outside the repository. Preserve raw evidence in the report archive: the shared `.gitignore` excludes `*.log`, so a normal Git commit alone does not transfer the entire evidence bundle.

## General execution rules

1. **Before measuring**, fill in the hypothesis, variable factor, constants, order, repeat count, and stop criterion. An experiment changed after it starts has a new configuration; preserve the explanation.
2. Complete the minimum variant of your lab first. The full matrix and large models are extensions after a successful small control. Hours in profiles are estimates of operator work, not guarantees of speed or completion time.
3. Reserve memory for the OS and runtime; the GPU and CPU share physical RAM. Do not assume that all 128 GB is available for weights or add RAM to the GPU heap. Treat Vulkan and HIP/ROCm equally; confirm the actual backend with a log.
4. Preserve commands, effective configuration, and raw output. Do not use a number in a comparison without units, context, precision, and conditions. `null`/empty means unknown with a reason; `0` means only a measured zero. Example tables in assignments remain empty until execution.
5. Do not execute arbitrary tools from a model's smoke response. LAB05–07 provide [open fixtures](fixtures/README.md) with a single permitted function. In LAB09–19, agent tools operate in a separate isolated environment.
6. Do not read hidden `tasks/*/check/` while solving tasks or developing adapters; do not modify `tasks/*/task.md`. The evaluator applies checks outside the agent container. API credentials come from `.env` through the harness; keys are not included in the report or raw logs.
7. Do not present an infrastructure smoke test, teaching report, or exit 0 as task success. An autonomous attempt requires a separate `results/runs/<run-id>/run.json` and an independent verdict.
8. If you cannot continue, preserve observations and the exact blocker. A report with status `blocked` or `in-progress` does not count as a completed minimum assignment. A rejected hypothesis or model failure can be a complete result if the method and submission bundle requirements are met.

## Writing the report

The [shared template](templates/report.md) is copied automatically. Insert the assignment's specific tables into `report.md`, document the procedure, and answer the questions. In `manifest.json`, specify the status (`not-started`, `in-progress`, `completed`, `blocked`), operator, links to inventories/artifacts, evidence, and run IDs. Links must point to preserved materials; leave fields that do not apply to the lab as `null` with an explanation in `unavailable`.

New reports use manifest v2: the evidence class `evidence_class`, a preserved preliminary protocol, and the complete `planned_attempts` register. The [report validation guide](report-validation.md) describes paths, attempt statuses, and migration from the old version. Check the draft and then the submission bundle:

```bash
npm run lab:check -- --report experiments/local-models/measurements/LAB01-first-pass
npm run lab:check -- --report experiments/local-models/measurements/LAB01-first-pass --mode submission
```

The second call returns an error until required data are filled in and omissions are explained. It checks links, the attempt register, metrics, and real run records; substantive acceptance remains the evaluator's responsibility.

In `measurements.tsv`, one row represents one numerical observation. Columns:

| Field | Meaning |
| --- | --- |
| observation_id / configuration_id | Unique row and the configuration linking it to the manifest/report |
| model_id / engine / backend / context_tokens / repeat | Observation conditions; leave non-applicable fields empty |
| metric / value / unit | Defined metric, measured value, unit |
| status | `measured`, `failed`, `not-run`, or `unavailable` |
| evidence_path / unavailable_reason | Path to raw evidence / reason the value is missing |

The mean, median/min/max, and comparisons are derived in the report from the original rows. If there were no numerical measurements (for example, only design work in LAB08), the file may contain just the header; explain this. TSV is not an import format for `compare`; the CLI compares only real run records.

## Course acceptance criteria

Each lab has its own checklist. When reviewing a bundle, also verify that:

- The report allows the actual configuration and experiment order to be reconstructed.
- All planned repeats, including errors, are present, or there are explained `not-run` entries.
- The hypothesis is compared with the data, and limitations of the conclusions are listed.
- Raw evidence, lab-specific tables, and answers to questions are included.
- Agent verdicts come from the evaluator, not automatically from a teaching template.
- `npm run check` passes; it checks assignment structure, a separate lab for each harness profile, catalogs, and run records; it **does not grant acceptance of a report**.

The path through all harnesses is complete after satisfying the criteria for LAB01, all nine LAB11–19, cloud LAB09, and LAB10. The local path is complete after satisfying the criteria for LAB01–10 under its conditions. The core course combines these 19 labs; the full course adds LAB20–27 and LAB53, the Apple track LAB28–35, the SPACE track LAB36–42, the Kubernetes and GPU track LAB43–47, and the AWS and Terraform track LAB48–52. Shared completed labs are not duplicated, but additional paths and configurations receive their own sessions and new attempts. Extended series within an individual lab are not part of its required minimum. Unmeasured metrics and engines that have not been integrated remain explicitly identified; there are no prefilled results.
