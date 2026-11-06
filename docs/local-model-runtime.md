# Local inference: Ryzen AI Max+ 395, 128 GB, Linux

Research date: **2026-09-21**. This document preserves the original plan; “pending” and “unverified” below describe that dated planning snapshot, not the current implementation status. See the [current local-provider documentation](../experiments/pi/README.md#local-provider-bridge--first-lab08-implementation) for subsequent work. The user confirmed Linux. At the time of this research, the exact computer model, distribution, kernel, BIOS, power mode, and available GPU memory budget were **unverified**: the document was prepared from primary sources without access to the target machine. The commands below form a runbook for future measurements; runtime installation, weight downloads, and inference were not performed as part of this work.

The goal is first to establish which model configurations actually fit and preserve working tools, then compare them on autonomous tasks. Backend speed and agent quality are different measurements. Candidate planning and series order are in the [local-model study](local-models.md); the engine comparison scope is in the [inference-engine matrix](local-inference-engines.md). Command examples here cover two llama.cpp implementations: part of the overall campaign, not its entire scope.

## What primary sources establish

| Fact | Status and conditions |
| --- | --- |
| Ryzen AI Max+ 395: 16 cores / 32 threads, Radeon 8060S with 40 CUs, up to 128 GB LPDDR5x-8000 | AMD specification; the actual OEM configuration still needs verification. [Processor specifications](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html) |
| Up to 96 GB for graphics with 128 GB RAM | AMD claim about Variable Graphics Memory. Configuration instructions concern Windows/Adrenalin; this is neither a measured Linux heap nor 96 GB of additional memory. [AMD VGM FAQ](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html) |
| `gfx1151` / RDNA 3.5 for the Ryzen AI Max 300 family | Documented by AMD. The public matrix consulted was titled ROCm **10.0.0**, dated 2026-08-19; for Ryzen, it listed Ubuntu 26.04 / GA 7.0 and Ubuntu 24.04.4 / OEM 6.17. This is a matrix for a specific stack, not a promise of support for every Linux system. [ROCm matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html) |
| Max+ 395 was also supported in ROCm 7.2.1 | The archived matrix lists the processor and Ubuntu 24.04.4. Do not call an old `latest` section the current version of the whole platform. [Versioned 7.2.1 matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html) |
| ROCm 7.14.1 is a published release; 7.9–7.13 belonged to the preview line | Release notes are dated 2026-09-02. Record the installed-package branch and its matrix separately from moving `latest` documentation. [7.14.1 release notes](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html) |
| AMD publishes a llama.cpp b8407 / ROCm 7.2.1 / gfx115X / Ubuntu 24.04 package | A historical vendor-verified diagnostic option. New model architectures may require newer llama.cpp. [AMD llama.cpp binaries](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/advanced/advancedryz/linux/llm/llamacpp.html) |

Documented hardware support does not establish the performance of a specific quantization, Flash Attention, KV cache, or tool calling. For example, AMD separately noted reduced performance of some LLMs on Max+ 395 in ROCm 7.2.1. [Limitations of that version](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/limitations/limitationsryz.html)

## Mandatory llama.cpp pair: HIP/ROCm and Vulkan

**Both tracks are mandatory baseline conditions:** llama.cpp + HIP/ROCm targeting `gfx1151`, and llama.cpp + Vulkan. AMD documents ROCm on Ryzen AI Max+ 395; there is no basis for treating it as a fallback or a less suitable choice in advance. Measurements determine which backend is faster and more stable for a specific context and quantization. `llama.cpp` documents both Linux builds. [Upstream instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

For both tracks, check OS/kernel/driver and pass a smoke test; record any unavailable track as a specific infrastructure blocker. Use one llama.cpp commit and identical GGUF, context, KV precision, batch, thread count, and sampling. Record ROCm components and Vulkan ICD with versions. Comparing a newer Vulkan build with AMD b8407 changes both backend and engine version; it may be retained as exploratory work, but the difference cannot be attributed solely to HIP.

vLLM, SGLang, PyTorch/Transformers, Ollama, and LM Studio are considered in the overall campaign through the [engine matrix](local-inference-engines.md); do not exclude them merely because a Vulkan alternative exists. Runtime engine, weight format, backend, and serving wrapper are separate factors. AMD engine support does not imply support for every quantization and architecture on `gfx1151`.

For an unsupported stack, do not substitute the architecture with `HSA_OVERRIDE_GFX_VERSION` in the baseline. If such a track is needed, give it a separate configuration and experimental status. The NPU is a separate study. Windows and WSL are outside the user-confirmed Linux configuration; somebody else’s WSL smoke test does not replace native Linux verification.

## Preflight on the target machine

First capture state without changing BIOS, kernel cmdline, GPU memory, drivers, or power profile. Record OEM model and firmware, power connection, current power profile, graphical desktop, and background workloads. Mark missing utilities unavailable; do not turn diagnosis into implicit installation.

Example of read-only collection into a new Linux series directory:

```sh
set -eu
mkdir -p experiments/local-models/measurements
LOCAL_EVIDENCE=$(mktemp -d experiments/local-models/measurements/preflight.XXXXXX)
date -u +%FT%TZ > "$LOCAL_EVIDENCE/time.txt"
cat /etc/os-release > "$LOCAL_EVIDENCE/os-release.txt"
uname -a > "$LOCAL_EVIDENCE/kernel.txt"
lscpu > "$LOCAL_EVIDENCE/cpu.txt"
cat /proc/meminfo > "$LOCAL_EVIDENCE/meminfo.txt"
free -b > "$LOCAL_EVIDENCE/memory-bytes.txt"
swapon --show --bytes > "$LOCAL_EVIDENCE/swap.txt"
df -B1 . > "$LOCAL_EVIDENCE/disk.txt"
if command -v lspci >/dev/null; then
  lspci -nnk > "$LOCAL_EVIDENCE/pci.txt"
fi
if command -v vulkaninfo >/dev/null; then
  vulkaninfo --summary > "$LOCAL_EVIDENCE/vulkan-summary.txt" 2>&1
  vulkaninfo > "$LOCAL_EVIDENCE/vulkan-full.txt" 2>&1
fi
if command -v rocminfo >/dev/null; then
  rocminfo > "$LOCAL_EVIDENCE/rocminfo.txt" 2>&1
fi
if command -v hipconfig >/dev/null; then
  hipconfig --full > "$LOCAL_EVIDENCE/hipconfig.txt" 2>&1
fi
```

Verify that Vulkan sees **Radeon 8060S**, not a software renderer. For HIP, check `gfx1151`. Save actual memory heaps/budgets and device availability in the same environment that will run inference; host and container may see different devices and libraries. Do not assume `/dev/dri/renderD128`: map the render node to the selected GPU. Machine serial numbers are unnecessary in the published archive.

AMD specifies separate KFD fixes for `gfx1151`: Ubuntu HWE from `6.17.0-19.19~24.04.2`, OEM from `6.14.0-1018`, and kernel `6.18.4` or newer for other distributions in the cited AMD prebuilt table. Also check backports and the specific release matrix. The TTM limit in `/sys/module/ttm/parameters/pages_limit` is measured in pages; AMD recommends a small BIOS carve-out and shared-memory use on Linux. This motivates measuring current state, not automatically changing it. [AMD RDNA3.5 system optimization](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html)

Count memory in bytes and display GiB separately (`bytes / 2^30`). Do not substitute the “128 GB” label for measured `MemTotal`. VRAM and GTT on this APU are not independent physical banks; simply adding them may double-count available RAM. Configuration admission requires all of the following:

1. The actual GPU budget covers resident weights, KV/state cache, and compute buffers with headroom.
2. The reserve specified by the shared series plan remains available for the OS, filesystem cache, and harness.
3. Sustained execution does not produce sustained swap, OOM, GPU reset, or hidden CPU fallback.

GGUF size is a lower reference, not peak memory. For MoE, account for **all** loaded experts, not only active parameters. For recurrent/hybrid models, do not apply a conventional KV formula without checking the architecture. Increasing context from 8K to 32K or adding a second slot requires measuring memory admission again.

## Pin the engine and weights

Before downloading the selected batch, obtain an immutable weights-repository revision, the full GGUF shard list, and their total size. After downloading, retain each file’s SHA-256. Record the source model, license, quantizer author, quantization method/type, tokenizer, and embedded chat template. Third-party GGUF does not become official merely because its source model is official.

For the runtime, save commit SHA, `--version`, `--help`, compiler/CMake versions, build flags, linked libraries, and binary hashes. When containerized, also retain the image digest and host GPU stack: the image does not pin the machine’s kernel or driver. Mutable `master`/`latest` source URLs below are for reading; execution always binds to a specific artifact.

After preparing a pinned checkout, build commands have the following form. They neither install dependencies nor download models:

```sh
cmake -S "$LLAMA_SOURCE" -B "$LLAMA_SOURCE/build-vulkan" \
  -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$LLAMA_SOURCE/build-vulkan" --config Release -j 8

HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -S "$LLAMA_SOURCE" -B "$LLAMA_SOURCE/build-hip" \
  -DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_BUILD_TYPE=Release
cmake --build "$LLAMA_SOURCE/build-hip" --config Release -j 8
```

`LLAMA_SOURCE` must point to an already verified checkout. Before running commands, check flags against documentation for the selected commit; keep builds in separate directories. The example targets AMD HIP SDK and does not require PyTorch. Flag source: [llama.cpp build.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

## Series A: memory and speed without a harness

Start with one small candidate, one slot, full GPU offload, and 8K context. Confirm actual backend, offloaded-layer count, and buffer sizes in logs. If some computation falls back to CPU, retain it as a separate variant, not mixed with full offload. Do not run two models concurrently.

Initial series settings are study conditions, not recommended “optimal” parameters: 8 CPU threads, batch 512, microbatch 256, KV `f16`, and Flash Attention explicitly `on`. Record FA/quant/model incompatibility as configuration failure; fallback `off` creates a separate configuration. A later separate ablation of KV `q8_0` is allowed after quality verification; do not silently substitute KV precision for a better-looking fit.

`llama-bench` measures prompt processing (`pp`), generation (`tg`), and combined mode (`pg`), and can fill context with `-d`. Its timing excludes tokenization and sampling. Save raw repeats, not just the mean. [llama-bench semantics](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)

After one warmup, perform 3 measured repeats of each selected case, as in the shared plan. A set for a given context includes several pp/tg modes but does not become multiple agent attempts. Example for an already downloaded `LOCAL_GGUF` and installed `LLAMA_BIN`; the output directory must be new:

```sh
"$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 512,2048,8192 -n 0 -r 3 -o json \
  > "$LOCAL_EVIDENCE/pp.json" 2> "$LOCAL_EVIDENCE/pp.log"

"$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 0 -n 128 -d 0,8192 -r 3 -o json \
  > "$LOCAL_EVIDENCE/tg.json" 2> "$LOCAL_EVIDENCE/tg.log"
```

Here, `8192` is the **depth before generation**, so actual capacity must be at least `8192 + 128`. Test 32K only after memory admission, with headroom for output tokens. `-fa` syntax has changed over time; use these commands only when pinned `--help` confirms `on`. Upstream usually performs its own warmup; retain help and record whether additional warmup was performed, excluding it from measured repeats.

In a parallel process, collect MemAvailable, swap-in/out, process RSS/PSS, available GPU telemetry, and temperature roughly every second. RSS is not total physical system usage with mmap/UMA: do not add RSS, page cache, and GPU allocation without checking overlap. Record peaks separately from available counters, with their sources. Unsupported GPU sensors are `null` with a reason. Measure energy with an external wall-plug meter if available; do not treat one APU’s software power as whole-machine consumption.

The report contains median/min/max and raw repeats, load time, pp/tg at specified depth, memory, and stability. Alternate Vulkan/HIP order between repeats/series; record power mode and background workloads. Account separately for cold process loading and warm filesystem cache; do not clear global page cache in the background without a separate plan.

## Series B: HTTP, templates, and tools

After memory admission, launch one `llama-server` on loopback only, with an explicit context and one slot. This is a **runtime smoke test**, not yet an agent run through the lab runner:

```sh
"$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" \
  --host 127.0.0.1 --port 8080 -ngl 999 -c 8192 -np 1 \
  -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on --jinja
```

Set the chat template and reasoning according to the model card. The server supports reasoning extraction and related settings, but `reasoning-format` alone neither enables nor disables thinking. Record effective settings and the visible response. For a model with mandatory reasoning, do not claim a generic flag disabled it. [Server API and parameters](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Test a tool round-trip on harmless synthetic fixtures: reading a fixed value, one function with JSON arguments, a tool result, and the subsequent final answer. For streaming, correctly assemble `tool_calls`, arguments, and `call_id` from delta events. Then test two sequential functions and rejection of an unknown tool. Do not execute arbitrary commands from a model’s smoke-test response.

A tool-aware template is mandatory; compatibility with an ordinary chat endpoint does not establish function calling. Save `/props`, template hash, request and response without secrets, and grammar/parser configuration. If a modified template/parser helps, it becomes a component requiring a harness-ledger row and separate comparison. [llama.cpp function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)

Measure HTTP TTFT (from request dispatch to the first meaningful token), complete-response time, and server tokens; exclude empty service events for streaming. Check output-length limits, request cancellation, context overflow, and slot release. Chat Completions, Responses API, and Anthropic-style API are different contracts; do not treat one as support for the others. To isolate the harness factor, retain one backend/model/template and identical sampling settings.

## Series C: harness integration — after the bridge

**Status in the original 2026-09-21 plan: pending.** At that point, `experiments/common/egress.mjs` blocked private IPs, and the runner had no ready universal `--provider local`. The `new-run → prepare-run → run` commands therefore could not be presented as already working local inference. Candidate planning did not remove this limitation. Subsequent bridge work is documented in the current harness documentation linked above.

The next infrastructure change must give the agent container access only to one trusted model endpoint. Do not open all localhost/host networking or give the agent GPU devices. The coordinator starts the backend; its weights mount is read-only, without the task repository, `.env`, hidden checks, workspace, or Docker socket. The backend itself has no execution tools or optional external downloads. The bridge permits only necessary inference routes; model loading/unloading, administrative operations, and arbitrary proxying are unavailable to the agent.

Before real tasks, verify the specific harness contract, recording of exact model identity (GGUF hashes + server alias), usage, stop reason, and every available budget control. If an adapter expects the Responses API, verify its operations separately. Mark a managed harness unsupported without a verified custom endpoint; do not replace its loop with your own agent.

Preserve T001 replay and T002 dependency-gateway network boundaries. A local backend is an explicit exception for one service, not general LAN access. Boundary tests must establish rejection of adjacent ports/private endpoints, redirect bypasses, and backend admin routes. A new bridge requires a ledger entry in the same change.

## Recording results and stop criteria

Before launching an agent, prepare the usual `run.json` and separately attach a backend manifest/trace as evidence; runtime configuration → run ID linkage is mandatory. Do not present a microbenchmark as a completed agent run or assign it a hidden-check pass. Standalone backend probes are allowed before the bridge: store them in `experiments/local-models/measurements/<probe-id>/` with `metadata.json` and raw logs. The original 2026-09-21 work prepared a **plan**, without measurements at that date. New local `run.json` fields required the schema extension described in the shared plan; do not bypass the validator manually.

The manifest needs: date, machine/OS/kernel/firmware, ICD or ROCm versions, llama.cpp SHA, binary/image hashes, GGUF shard hashes, quantization, effective chat template, context/slots/KV, offload, threads/batch, reasoning/sampling, seed, every launch argument, and route contract. Unverified fields remain `null` with reasons.

Stop a configuration on OOM, GPU reset, invalid/unstable tool calls, sustained swap, exceeded reserved memory, or repeatable data errors. Preserve the failure and reason; reducing context/quantization or using CPU offload creates a new variant, not a correction of the old result. No API billing does not mean zero total cost: energy and time are recorded separately; unknown cost is not replaced with zero.

At the original 2026-09-21 planning date, hardware smoke tests, specific-model suitability, and the Vulkan/HIP comparison on the user’s machine remained **unverified** until this protocol was executed.
