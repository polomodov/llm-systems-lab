# Local-model candidates for Ryzen AI Max+ 395, 128 GB

Source snapshot: **2026-09-20**. The objective is to test autonomous-task quality on existing lab tasks, time cost and required harness support on Linux. This is a research plan and test queue: weights had not been downloaded, local models had not been run, and performance on the user's machine was **unverified** at this snapshot.

The machine-readable catalog is [`experiments/local-models/models.json`](../experiments/local-models/models.json). Each candidate records its official ID, source-model revision, GGUF publisher, artifact revision, all required shards, byte sizes and published SHA-256 values. Those hashes came from the Hugging Face API, not local download verification. Verify local-file checksums before execution.

## Shortlist and order

P1 is the first pass, P2 extends it after successful runtime/tool checks, and P3 provides control comparisons. Priority is not a quality ranking. Twelve models from four families allow the same tasks to probe model size, architecture and generation effects.

Parameter counts are billions: **total** first, then **active per token**, as stated in the model card. Dense models have the same value for both. A MoE with 3B active parameters does not need only 3B of weights in memory: ordinary execution loads the full selected quantization. Here `hybrid-*` combines Gated DeltaNet with full attention; `dense`/`moe` does not rule out sliding-window attention.

**GB = 10⁹ bytes; GiB = 2³⁰ bytes.** GiB values are rounded up to 0.1. These are text-execution weight-file totals, excluding a separate vision projector, draft model, KV cache, compute buffers and OS. A GGUF published by Unsloth or ggml-org is that publisher's artifact, not automatically an official quantization by the base-model author.

| Queue | Model and primary source | Parameters, B total / active | Architecture | Selected GGUF and source | File size | Memory admission | Research question |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | 9 / 9 | hybrid-dense | [Q6_K](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5) | 7.46 GB / ≤7.0 GiB | `candidate` | Small control: speed and a lower quality baseline |
| P1 | [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 35 / 3 | hybrid-moe | [UD-Q5_K_M](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/tree/a483e9e6cbd595906af30beda3187c2663a1118c) | 26.46 GB / ≤24.7 GiB | `candidate` | Current MoE: agentic coding and reasoning preservation |
| P1 | [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) | 27 / 27 | hybrid-dense | [Q5_K_M](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/tree/82d411acf4a06cfb8d9b073a5211bf410bfc29bf) | 19.51 GB / ≤18.2 GiB | `candidate` | Dense quality control against MoE |
| P1 | [Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) | 80 / 3 | hybrid-moe | [Q5_K_M](https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF/tree/b82fb7382639d97b38fa7672e526c760c2fb358e) | 56.71 GB / ≤52.9 GiB | `candidate` | Coding-agent specialization; non-thinking |
| P1 | [gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b) | 21 / 3.6 | moe | [MXFP4](https://huggingface.co/ggml-org/gpt-oss-20b-GGUF/tree/ef9b12f2ff56c69cf32153a02784e7a3c88bf524) | 12.11 GB / ≤11.3 GiB | `candidate` | Independent compact family; Harmony and reasoning |
| P1 | [GLM-4.7-Flash](https://huggingface.co/zai-org/GLM-4.7-Flash) | 30 / 3 | moe | [Q8_0](https://huggingface.co/ggml-org/GLM-4.7-Flash-GGUF/tree/7559e96b7e324ab405897dc2b91492b0f376ad4a) | 31.84 GB / ≤29.7 GiB | `candidate` | Independent MoE with MLA; quality at Q8 |
| P2 | [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 30.5 / 3.3 | moe | [Q5_K_M](https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/tree/b17cb02dd882d5b6ab62fc777ad2995f19668350) | 21.73 GB / ≤20.3 GiB | `candidate` | Full-attention MoE against hybrid Coder-Next |
| P2 | [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b) | 117 / 5.1 | moe | [MXFP4](https://huggingface.co/ggml-org/gpt-oss-120b-GGUF/tree/238abdd290bb874b90a5da1b4549881b7d05c091) | 63.39 GB / ≤59.1 GiB | `conditional` | Scaling the same family to 117B |
| P2 | [Qwen3.5-122B-A10B](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) | 122 / 10 | hybrid-moe | [Q4_K_M](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF/tree/51eab4d59d53f573fb9206cb3ce613f1d0aa392b) | 76.54 GB / ≤71.3 GiB | `conditional` | Large hybrid MoE; practical size boundary |
| P2 | [gemma-4-31B-it](https://huggingface.co/google/gemma-4-31B-it) | 30.7 / 30.7 | dense | [Q5_K_M](https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/tree/c1ac76e99d5513b141e8adde7288b85c3f9c32ec) | 21.66 GB / ≤20.2 GiB | `candidate` | Independent dense family; native function calling |
| P3 | [Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) | 35 / 3 | hybrid-moe | [Q5_K_M](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/tree/bc014a17be43adabd7066b7a86075ff935c6a4e2) | 26.25 GB / ≤24.5 GiB | `candidate` | Paired Qwen3.5→3.6 generation control |
| P3 | [GLM-4.5-Air](https://huggingface.co/zai-org/GLM-4.5-Air) | 106 / 12 | moe | [Q4_K_M](https://huggingface.co/unsloth/GLM-4.5-Air-GGUF/tree/506d64aa8c5cfe9dbbf00bc7a15739438f83204d) | 72.98 GB / ≤68.0 GiB | `conditional` | Large alternative MoE with full attention |

`candidate` means weight size leaves meaningful headroom within 128 GB: it is **fit-estimate**, not `fit-verified`. `conditional` requires separate qualification using actual backend memory: files fit total capacity, but GPU-accessible memory, KV, working buffers and transient loading copies may change the outcome. No row guarantees acceptable speed.

For every row, the first pass is **8 192 → 16 384 → 32 768 tokens**, one model and one slot at a time. Advance only after the previous size succeeds with peak memory recorded. This is total context, including tool history, reasoning and the future answer. Do not automatically use native 128K/256K limits. Qwen's authors recommend long context for difficult reasoning; this pass therefore measures constrained local budgets, not maximum vendor scores. Finalists may receive separate 64K/128K trials after memory qualification. [Qwen guidance](https://huggingface.co/Qwen/Qwen3.5-9B#quickstart).

## Model weights and process memory are different quantities

Working estimate: `resident weights + KV/state cache + compute buffers + runtime/driver + OS/harness`. On UMA, CPU and iGPU use one physical memory pool; do not add their advertised capacities. GGUF size supports preliminary screening; allocator logs and system measurements determine final admission. mmap, CPU/GPU copies and shared pages can cause double-counting when simply adding process RSS.

For ordinary full-attention GQA with equal K/V dimensions, a one-slot FP16 cache estimate is:

```text
KV_bytes = 2 × full_attention_layers × kv_heads × head_dim × context_tokens × 2
```

The first `2` accounts for K and V; the last is FP16 bytes. Neither Q4/Q5/Q8 weight quantization nor active-expert count determines KV dtype. Multiple simultaneous sequences usually increase memory; cache-allocation strategy also depends on the backend.

Examples for **32 768 tokens, one slot, FP16 cache**, using official configurations and excluding allocator overhead:

| Model | Calculated KV component | Conditions and excluded components |
| --- | --- | --- |
| Qwen3.5-9B | 1.00 GiB | 8 attention layers, 4 KV heads × 256; Gated DeltaNet state is additional |
| Qwen3.6-27B | 2.00 GiB | 16 attention layers, 4 × 256; Gated DeltaNet state is additional |
| Qwen3.5/3.6-35B-A3B | 0.625 GiB | 10 attention layers, 2 × 256; Gated DeltaNet state is additional |
| Qwen3-Coder-Next / Qwen3.5-122B-A10B | 0.75 GiB | 12 attention layers, 2 × 256; Gated DeltaNet state is additional |
| Qwen3-Coder-30B-A3B-Instruct | 3.00 GiB | 48 full-attention layers, 4 × 128 |
| GLM-4.5-Air | 5.75 GiB | 46 full-attention layers, 8 × 128 |

These calculations use [Qwen3.5-9B config](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/config.json), [Qwen3.6-27B config](https://huggingface.co/Qwen/Qwen3.6-27B/blob/main/config.json), [Qwen3.6-35B config](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/blob/main/config.json), [Coder-Next config](https://huggingface.co/Qwen/Qwen3-Coder-Next/blob/main/config.json), [Qwen3.5-122B config](https://huggingface.co/Qwen/Qwen3.5-122B-A10B/blob/main/config.json), [Coder-30B config](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/blob/main/config.json) and [GLM-Air config](https://huggingface.co/zai-org/GLM-4.5-Air/blob/main/config.json). Model revisions are pinned in the catalog; these values are not lab measurements.

GLM-4.7-Flash requires a separate **MLA** implementation check: does the backend store compressed latent state or expanded K/V? The generic GQA formula is misleading here. gpt-oss alternates local/global attention; Gemma 4 also uses sliding/global attention and shared K/V. Obtain a runtime report of actual cache allocation. [GLM-Flash config](https://huggingface.co/zai-org/GLM-4.7-Flash/blob/main/config.json), [gpt-oss config](https://huggingface.co/openai/gpt-oss-120b/blob/main/config.json), [Gemma 4 config](https://huggingface.co/google/gemma-4-31B-it/blob/main/config.json).

## Conditions for a valid comparison

- **Qwen3-Coder-Next and Coder-30B** are non-thinking models. Do not invent a reasoning mode for them. For Qwen3.5/3.6, record thinking, history preservation and sampling separately. [Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next), [Coder-30B](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct).
- **gpt-oss** requires Harmony formatting. Check that server and harness preserve tool calls and separate channels correctly. MXFP4 is a specific weight format; verify support in the selected Linux GPU backend. Test reasoning `low/medium/high` separately without combining their results. The author's claim that 120b targets one 80 GB GPU does not verify Ryzen. [OpenAI model card](https://huggingface.co/openai/gpt-oss-20b).
- **GLM-4.7-Flash** needs tool-parser and cross-turn thinking-preservation checks. Initial Q8_0 leaves memory headroom and lets integration be checked first. Only then add Q5/Q4 as separate variants. [Z.ai model card](https://huggingface.co/zai-org/GLM-4.7-Flash).
- **Gemma 4 31B** is a dense model with a stated 30.7B parameters and native function calling. Verify chat template, system role, tool parser and thinking on the specific runtime. The first series' text tasks do not test vision. [Google model card](https://huggingface.co/google/gemma-4-31B-it).
- **Qwen3.6-35B UD-Q5_K_M and Qwen3.5-35B Q5_K_M** use different published quantization recipes. The initial comparison measures those artifacts, not the isolated generation effect. That conclusion requires an additional pass with a matching recipe, such as available Q8_0, and one runtime version.
- First qualify each model with a structured tool-call smoke: call a tool, return its result, make a second call and finish. A poor parser is not evidence of a poor model. After smoke, run the same lab tasks with an external verdict under the shared protocol.
- Run records need backend/version/commit, driver, memory parameters, model and GGUF SHA-256, chat template, parser, context, KV dtype, slots, offload, sampling, reasoning, actual tokens, time and peak memory. Compare different backend/quantization results separately. Do not copy marketing benchmark numbers into `results/runs/`.

## Excluded from the first series

Full BF16 large MoEs are not the target for 128 GB. For example, the official Qwen3.5-122B repository contains about 250 GB of files. Selected Q4 takes 76.54 GB. Even Q8_0 is about 129.87 GB before cache and OS. Q5_K_M (~91.52 GB / 85.3 GiB) leaves much less headroom and is only a conditional later ablation. [Original files](https://huggingface.co/Qwen/Qwen3.5-122B-A10B/tree/main), [GGUF artifacts](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF/tree/51eab4d59d53f573fb9206cb3ce613f1d0aa392b).

The name **GLM-4.7-Air** was not confirmed in the checked primary sources. The catalog includes the existing **GLM-4.7-Flash** and **GLM-4.5-Air** (106B total / 12B active according to the author's model card). [GLM-4.5-Air](https://huggingface.co/zai-org/GLM-4.5-Air). Hugging Face automatic parameter counts sometimes differ from author rounding; estimate memory from the selected artifact's files.

Qwen3.5-27B and additional 32B/70B dense models are excluded from the first series to keep the matrix bounded: Qwen3.6-27B already provides a dense control, while Gemma adds an independent family. Qwen3.5-35B remains for a paired generation comparison. Unidentified “uncensored,” merged and distilled community variants are excluded: first establish a reproducible baseline using official models.

All selected GGUFs total **436.62 GB (~406.63 GiB)** on disk before temporary files and results. They are not intended to be loaded into RAM simultaneously; download the next model or a small pool. Before downloading new revisions, update the catalog and repeat memory/tool smoke. Ryzen tokens/s, solution time and quality remain **unverified** until the plan is executed.
