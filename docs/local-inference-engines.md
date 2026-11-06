# Inference-engine comparison plan for Ryzen AI Max+ 395

**Apple track (2026-10-07):** [LAB28–35 and M5 Max profiles](../experiments/local-models/apple/README.md). Both `local:plan` and `local:engines` accept `--hardware apple-m5-max-128gb-macos`; without the flag, Ryzen remains selected. Apple uses Metal/MLX and a separate five-profile catalog. Its GPU budget is unknown: effective budget/headroom is `null`, with status `hardware-memory-required`; set a numerical budget after measuring it. MLX stays `artifact-required`, and wrappers with unknown memory stay `engine-memory-required`. The original Ryzen/Linux plan follows.

Practical exercises: [LAB04 — backends](labs/LAB04-backends.md), [LAB06 — engines](labs/LAB06-engines.md), [LAB07 — services](labs/LAB07-serving.md). The [course](labs/README.md) provides the overall route and templates.

Addition dated **2026-09-21** to the [local-model campaign](local-models.md). Target: Ryzen AI Max+ 395 / Radeon 8060S (`gfx1151`), 128 GB UMA, Linux. **ROCm is a fully required research branch alongside Vulkan.** Max+ 395 support is explicitly listed in the [AMD matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html); AMD also publishes a [vLLM image for gfx1151](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedryz/linux/llm/build-docker-image.html). These are documented execution paths, not our hardware measurements.

## Factors to separate

| Layer | Examples | What changes in the experiment |
| --- | --- | --- |
| Model and artifact | Qwen3.6, GGUF Q5, safetensors BF16/MXFP4/AWQ | Weights, precision, template, actual memory |
| Engine | llama.cpp, vLLM, SGLang, Transformers/PyTorch | Kernels, attention, batching, scheduler/cache |
| GPU backend | Vulkan or HIP/ROCm | Compiler, GPU libraries, ICD/runtime, memory allocation |
| Service above the engine | Ollama, LM Studio, Lemonade | API, loading/unloading, templates, limits, overhead |
| Agent harness | Pi, OpenCode, mini-SWE-agent, OpenHands | Tools and autonomous loop |

ROCm is a software stack; HIP is the GPU API it uses. They are not two independent inference engines. Ollama includes a pinned, patched llama.cpp integration; record its actual runner rather than assuming upstream equivalence. [Ollama integration source](https://github.com/ollama/ollama/blob/6383a0fa9cbf97494b847226e189f6e36b401a08/llama/README.md). LM Studio uses separate runtime packages, and Lemonade can launch different engines. Their results are not independent repeats of the same kernel implementation.

## Matrix and order

[engines.json](../experiments/local-models/engines.json) contains **12 profiles**, including backend pairs. `documented` describes sources, `conditional` means the exact stack/device has not been fully checked, and `experimental` identifies an explicitly experimental upstream path. All three require hardware smoke; none means “verified in the lab.”

| Queue / CLI profiles | Engine or service | Weights and status | First experiment |
| --- | --- | --- | --- |
| P1 `llama-cpp-vulkan`, `llama-cpp-rocm` | llama.cpp, two equal backend branches | The same GGUF and commit; documented Linux build paths | Resource checks for all 12 candidates, starting with Qwen3.5-9B; then 8K/16K/32K |
| P2 `vllm-rocm` | vLLM | Documented gfx1151; its own checkpoint/quantization, not automatic GGUF transfer | Qwen3.5-9B, gpt-oss-20b and Qwen3.6-35B, only after kernel/format checks |
| P2 `sglang-rocm` | SGLang | New dedicated gfx1151 build; native Linux remains conditional until smoke | The same three model families, using independently supported artifacts |
| P2 `transformers-rocm` | Transformers + PyTorch | Documented AMD Torch; reference `generate`, no ready agent API | The same three small/medium models if BF16/supported quantization fits |
| P3 `ollama-rocm`, `ollama-vulkan` | Ollama | Linux ROCm explicitly includes 395; Vulkan is also documented | Two qualified control GGUFs; import original shards and pin server settings |
| P3 `lm-studio-vulkan`, `lm-studio-rocm` | LM Studio / llama.cpp | Both Linux backends documented; verify the exact gfx1151 runtime | Two control GGUFs; record application and runtime-package versions separately |
| P3 `lemonade-vulkan`, `lemonade-rocm` | Lemonade / llama.cpp | Recipe and binary can be pinned | Two control GGUFs; direct server and service on the same binary hash where possible |
| P3 `lemonade-vllm-rocm` | Lemonade / vLLM | Upstream experimental; gfx1151 validation | Two previously qualified native checkpoints from the vLLM branch |

### Versions and primary-source limitations

**llama.cpp.** Build Vulkan and HIP from one immutable commit; commands are in the [Linux runbook](local-model-runtime.md). Archived AMD b8407/ROCm 7.2.1 is a diagnostic reference, but a new model architecture may need a newer commit. Current Vulkan and old HIP cannot be treated as a backend-only change. [Upstream build](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

**vLLM.** The stable GPU guide lists Ryzen AI MAX/AI 300 and `gfx1151`/`gfx1150`; [v0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0) is a version candidate at the research date. AMD also documents the historical `rocm7.2.1_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.16.0` stack. Do not combine a newer server tag with dependencies from an old example. Select a complete compatible image, retain its digest and Torch/Triton/ROCm versions, and verify GPU/kernel dispatch. Study GGUF separately if needed; it does not imply support for every architecture. [GPU installation](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/), [AMD example](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedryz/linux/llm/build-docker-image.html).

**SGLang.** [v0.5.20](https://github.com/sgl-project/sglang/releases/tag/v0.5.20) includes a [dedicated gfx1151 Docker image](https://github.com/sgl-project/sglang/pull/33939). The PR author tested 395/8060S under WSL2, not our native Linux machine: context 4096, concurrency 1, a separate wave32 build, Triton attention and AITER dispatch disabled. Do not select a generic CDNA/MI300 image. Retain the specific gfx1151 image digest; repeat the original short smoke first, then 8K/16K/32K. CDNA MXFP4 support does not prove RDNA 3.5 support: for gpt-oss, first select a supported native/dequantized variant, record its new quantization and recalculate memory. [SGLang AMD GPU guide](https://docs.sglang.io/docs/hardware-platforms/amd_gpu).

**Transformers/PyTorch.** The reference helps distinguish checkpoint/template defects from serving-integration defects. AMD publishes separate [device-specific Torch packages](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html); select a tested Torch/ROCm pair instead of independently choosing each package's latest version. The reference does not enter agent-API comparisons until a reproducible server adapter exists. Pin chat templates and tool messages following [Transformers documentation](https://huggingface.co/docs/transformers/chat_extras). AMD separately describes [older PyTorch performance limitations on Ryzen AI Max](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html); record BLAS preference and workarounds as explicit settings, not hidden acceleration for one participant.

**Ollama.** The [hardware documentation](https://docs.ollama.com/gpu) explicitly includes Ryzen 395 and ROCm v7; Vulkan is enabled when its backend is available. Confirm actual selection in logs. Import an [exact GGUF](https://docs.ollama.com/import) without requantization, retaining manifest, Modelfile, template and `num_ctx`. [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) is not the full API: in particular, verify stateful Responses limitations for the specific harness. Auto backend selection, CPU fallback and automatic context are not acceptable unknown conditions within a series.

**LM Studio.** [Linux ROCm is described in a release](https://lmstudio.ai/blog/lmstudio-v0.3.19), and [Vulkan/Linux in the SDK announcement](https://lmstudio.ai/blog/introducing-lmstudio-sdk); neither is exact-395 certification. Record [`lms runtime ls/get/select`](https://lmstudio.ai/docs/cli/runtime/runtime) output. [`lms import`](https://lmstudio.ai/docs/cli/local-models/import) moves its source file by default; use copying/hard links for the experiment and verify the hash. Native and fallback tools differ: fallback changes messages and prompts, making it a separate component that needs a ledger entry. [Tool use](https://lmstudio.ai/docs/developer/openai-compat/tools).

**Lemonade.** Pin [recipe, backend and binary](https://lemonade-server.ai/docs/guide/configuration/) and [local extra models](https://lemonade-server.ai/docs/guide/configuration/custom-models/), without automatic latest/pull during a series. `llamacpp:rocm` stable/nightly may ship its own build and runtime. The [vLLM recipe](https://lemonade-server.ai/docs/guide/configuration/vllm/) is a separate experimental path with architecture-specific packages, checkpoints and launch parameters. Measure JIT/initial loading separately; internal backend-only `/metrics` remains accessible to the coordinator, not the agent.

## Memory: GGUF cannot stand in for a native checkpoint

The existing `models.json` pins **specific GGUF artifacts**. Their 7–71 GiB sizes do not describe BF16, FP8, GPTQ, AWQ or expanded MXFP4 memory in another engine. Even the same “4-bit” label does not imply matching weights or kernels. Safetensors is a file container, not a precision designation.

For vLLM/SGLang/Transformers and Lemonade-vLLM, the planner returns `artifact-required`, `quantization=null` and unknown weights/total/headroom. Next, choose a supported artifact, pin revision/shards/bytes/hash/quantization configuration and recalculate resident memory. This does not mean “unsupported model”; the planning data is incomplete. Do not silently convert GGUF to BF16 or load a full 120B BF16 checkpoint under the same alias.

For GGUF-importing services, weight size is known but extra runtime/scheduler reserve is not: `engine-memory-required`. The old 6 GiB reserve remains **a llama.cpp hypothesis only**, not a measurement of every engine. Measure KV preallocation, compile workspace, prefix cache and `max_num_seqs`/equivalent settings separately. Use the shared physical UMA budget and retain the OS reserve; `gpu_memory_utilization`/`mem_fraction_static` percentages do not mean equal byte counts across engines.

## Comparison procedure

1. **Two llama.cpp baseline backends.** Up to 12 models × 2 backends × 3 contexts × 3 repeats = **216 resource-measurement sets**, stopping progression after earlier-level failures. Each set includes pp/tg, memory and HTTP smoke; these are not 216 agent attempts. Fill the entire context rather than merely configuring its size.
2. **Independent ROCm engines.** Test vLLM/SGLang on three selected families: up to 3 × 2 × 3 × 3 = **54 sets**. SGLang first gets the separate upstream-PR 4K installation smoke, excluded from the 8K comparison. Transformers reference: up to 3 × one 8K context × 3 = **9 sets**. Record unavailable quantization/architecture/fit as an incompatible cell; do not imply every combination is ready.
3. **Serving layers.** Six GGUF profiles (Ollama, LM Studio, Lemonade × ROCm/Vulkan) on two controls at 16K, three repeats: up to **36 sets**. Lemonade-vLLM is separate: up to **6 sets**, after direct vLLM. Before this stage, record the control models and selection rationale; prefer Qwen3.5-9B and gpt-oss-20b if import/protocol is qualified.
4. **Engine effect on agents.** Up to 3 finalists × 2 qualified engine deployments × T001/T002 × 3 repeats on reference Pi = **36 new attempts**, at most 9 hours at a 900-second timeout, plus setup/evaluation. This is a separate series; runtime smoke does not replace task verdicts. With only one qualified engine for a model, no pair exists and no engine effect is estimated.
5. **Agent-harness effect.** Retain the main plan: pin one qualified engine deployment for each of 3 models, then 4 harnesses × 2 tasks × 3 repeats = **72 attempts**. T003 adds up to 36 separate audits with the existing different-input limitation. Keep the engine fixed to estimate the harness-only effect.

This order does not multiply all 12 models by all 12 profiles and every harness in a real series. The full planner table describes the research space; these stages define a bounded queue. Times are individual execution limits, not a forecast for completing the campaign. Downloads, compilation/JIT and external judging are estimated separately.

Use **one external HTTP workload driver** for engine comparisons: matching texts/prompts, output budget, tool schema, sampling, slot count and cache state. Built-in `llama-bench`, `vllm bench` and SGLang benchmarks use different definitions; retain them as diagnostics, not a combined tokens/s ranking. Record TTFT, prefill, decode, total wall-clock time, actual output/reasoning tokens, usage coverage and errors separately. Cross-model tokens/s comparisons must account for different tokenizers.

The primary workload is one sequential agent, concurrency **1**, with prefix cache disabled or explicitly aligned; if it cannot be disabled, use a different group. A separate throughput experiment at concurrency 2/4 on two small models may follow a memory gate. It is excluded from the counts above and does not determine the single-agent winner. Separate warmup, cold JIT, warm prefix cache and service idle time; alternate backend/engine order using a saved seed.

Matching weight hashes, quantization recipes, templates and parameters allow engine/backend-effect estimates. When native quantization differs from GGUF, the conclusion concerns the **complete model configuration**, not the engine alone. For llama.cpp-based services, overhead comparisons require matching actual binary hashes; otherwise also record fork/patch/version differences.

## What to retain and implement before execution

Add engine/version/commit/image digest; backend and actually selected kernels; PyTorch/Triton/AITER/ROCm/ICD; quantization loader; attention implementation; template/parser; KV dtype/allocation; batch/ubatch/max sequences; prefix cache; compile/graph mode; serving-application/runtime versions; and the full effective configuration to the hardware/weight profile. Empty fields remain unknown with reasons. A matching `model` alias does not automatically bind these conditions.

The planned `results/schema.json`, prepare-snapshot and compare extension must account for **all these layers**. At the time of this plan, `run --provider local` and a universal engine launcher were not implemented. `local:engines` and `local:plan --engine ...` only read catalogs. A separate model service receives GPU devices; agent containers retain their existing boundaries, narrow local proxy and independent evaluator.

```bash
npm run local:engines
npm run local:plan -- --engine llama-cpp-rocm --context 16384
npm run local:plan -- --engine vllm-rocm --model gpt-oss-20b
npm run local:plan -- --engine all --format json
```

Without `--engine`, the original GGUF calculation remains the planner's compatibility mode. These commands do not install ROCm, download weights, start servers or create background jobs.

`ik_llama.cpp` is excluded from the GPU series: its author identifies CPU/CUDA as fully supported, not ROCm/Vulkan. A possible CPU AVX-512 experiment would be a separate control. [Pinned README](https://github.com/ikawrakow/ik_llama.cpp/blob/9cba2e3874df6f598fd339c4c6c7d5fc2b44645b/README.md). NPU/ONNX/FastFlowLM, multi-GPU and cloud endpoints are outside this GPU campaign and require separate artifacts and conditions.
