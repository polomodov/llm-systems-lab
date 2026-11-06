# LAB06. vLLM, SGLang, and Transformers on ROCm

## Profile

- Time: 4–8 hours plus checkpoint/container downloads and the SGLang build.
- Prerequisites: [LAB03](LAB03-artifacts.md) and [LAB05](LAB05-context-tools.md) submitted; Linux on Ryzen AI Max+ 395, working AMD kernel driver, access to `/dev/kfd` and the DRM render node, Docker, Git, Python 3.11+, and free disk space for large images and a BF16 checkpoint.
- Readiness: commands are based on sources checked on 2026-09-21. **Hardware execution in this lab has not yet occurred.** Documented support does not guarantee that a particular image/kernel/model combination works.
- Minimum: one native Qwen3.5-9B checkpoint; one configuration each of vLLM, SGLang, and direct Transformers `generate`. Start with 4096 tokens/one sequence; servers that pass proceed to 8192 and the HTTP/tools checks from LAB05. Other models, quants, 16K/32K, and tuning are extensions.

## Objective

Test three executions of one pinned native checkpoint on ROCm/gfx1151 and distinguish hardware-stack, model, kernel, and OpenAI-compatible server errors.

## Hypothesis

“One BF16 Qwen3.5-9B checkpoint loads on gfx1151 in each of three pinned runtimes and produces the correct control response; server implementations also complete an allowed tool round trip.” This tests availability and compatibility, not equal speed or numerically identical logits.

## Preparation

```bash
npm run lab:new -- --lab LAB06 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB06-my-session"
export LAB03_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB05_DIR="$PWD/experiments/local-models/measurements/LAB05-my-session"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
cp "$LAB03_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/fetch_artifact.py"
cp "$LAB05_DIR/raw/http_probe.py" "$LAB_DIR/raw/http_probe.py"
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
docker version > "$LAB_DIR/raw/docker-version.txt"
```

Substitute your own session IDs. `http_probe.py` is the saved public HTTP/SSE driver from LAB05, not an agent harness. Check the hardware profile and budgets from LAB02; all engines run **sequentially**, unloading the previous one. The research coordinator uses Docker with GPU devices; this is not a sandbox for model-generated code.

## Procedure

1. **Pin a new artifact and recalculate memory.** The GGUF from LAB03 cannot replace a BF16 native checkpoint. The selected model is the official `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. Its safetensors alone occupy **19 306 310 880 bytes**, about **17.982 GiB**; runtime, cache, and temporary buffers are additional. Save metadata and a manifest without downloading weights:

   ```bash
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, sys, urllib.request
   out = pathlib.Path(sys.argv[1]) / "raw"
   repo = "Qwen/Qwen3.5-9B"
   rev = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
   url = f"https://huggingface.co/api/models/{repo}/revision/{rev}?blobs=true"
   with urllib.request.urlopen(url, timeout=60) as response:
       metadata = json.load(response)
   assert metadata["sha"] == rev
   (out / "native-publisher-metadata.json").write_text(json.dumps(metadata, indent=2))
   files = []
   for item in metadata["siblings"]:
       name = item["rfilename"]
       if name.endswith((".safetensors", ".json", ".txt", ".jinja")) or name == "LICENSE":
           files.append({"path": name, "bytes": item["size"],
                         "sha256": item.get("lfs", {}).get("sha256"),
                         "git_blob_id": item.get("blobId")})
   manifest = {"model_id": repo, "quantization": "BF16 native checkpoint",
               "artifact": {"repository": repo, "revision": rev, "files": files,
                            "total_bytes": sum(f["bytes"] for f in files)}}
   (out / "native-artifact.json").write_text(json.dumps(manifest, indent=2) + "\n")
   print(manifest["artifact"]["total_bytes"])
   PY
   ```

   Check `config.json`/quantization metadata and ensure there is no unexpected architecture substitution. HF may not publish SHA-256 for small Git files: the saved `git_blob_id` and locally computed SHA are different fields. After checking disk space and the budget, download and verify files with the LAB03 script:

   ```bash
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/native-artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/native-download.json"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/native-artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/native-verification.json"
   export NATIVE_MODEL_DIR="$LAB_STORAGE/Qwen/Qwen3.5-9B/c202236235762e1c871ad0ccb60c8ee5ba337b9a"
   ```

   Mount the same directory read-only in all three runtimes. `HF_HUB_OFFLINE=1` prevents silently downloading another revision. Missing files → `no-artifact`, not an invented size of 0. FP8/AWQ/GPTQ/MXFP4 and dequantized gpt-oss are new artifacts: support for each particular kernel on gfx1151 is checked separately. Native BF16 for large MoEs is not admitted simply because that family's GGUF fit.

2. **Prepare pinned runtimes.** For vLLM, use the published ROCm image v0.29.0 by digest rather than a mutable `latest`:

   ```bash
   export VLLM_IMAGE='vllm/vllm-openai-rocm@sha256:e5e47f6aaab675c252c381f0dac237b31b10d87bb74d092b07fb4065efd7f5a1'
   docker pull "$VLLM_IMAGE" > "$LAB_DIR/raw/vllm-pull.txt" 2>&1
   docker image inspect "$VLLM_IMAGE" > "$LAB_DIR/raw/vllm-image.json"
   ```

   Upstream lists gfx1151 and ROCm ≥7.0.2 for Ryzen AI; the container does not replace the host kernel driver. Do not install arbitrary newer Torch/Triton versions over the image. Record image incompatibility with this device as `fail` with a log.

   SGLang v0.5.20 has a dedicated gfx1151 Dockerfile. A generic MI300/CDNA image is not equivalent. Build from the pinned commit:

   ```bash
   git clone --filter=blob:none --no-checkout https://github.com/sgl-project/sglang "$LAB_DIR/raw/sglang-src"
   git -C "$LAB_DIR/raw/sglang-src" checkout --detach 94602c9c2b7cbdb8efd5c52802dac6a1c180089e
   git -C "$LAB_DIR/raw/sglang-src" rev-parse HEAD > "$LAB_DIR/raw/sglang-commit.txt"
   docker build --progress=plain -f "$LAB_DIR/raw/sglang-src/docker/rocm-gfx1151.Dockerfile" -t lab-sglang:gfx1151-94602c9 "$LAB_DIR/raw/sglang-src" > "$LAB_DIR/raw/sglang-build.txt" 2>&1
   export SGLANG_IMAGE="$(docker image inspect --format '{{.Id}}' lab-sglang:gfx1151-94602c9)"
   docker image inspect "$SGLANG_IMAGE" > "$LAB_DIR/raw/sglang-image.json"
   ```

   The Dockerfile pins an AMD base image with ROCm 7.2.4/PyTorch 2.9.1 and applies wave32/gfx1151 patches; `SGLANG_USE_AITER=0` and Triton attention matter. The original PR author tested Qwen3.5-9B on 395/8060S **in WSL2**. This lab tests native Linux; that is an additional condition, not validation already performed. The Dockerfile resolves some build dependencies during the build: a commit does not guarantee bit-for-bit identical rebuilt images. Preserve the package freeze and use the resulting image ID for the entire series; if needed, archive the image with `docker image save` and hash the archive.

3. **Check the GPU before loading the model.** In Bash, specify the render node from LAB02 rather than choosing it by assumption:

   ```bash
   set -euo pipefail
   export LAB_RENDER=/dev/dri/renderD128
   test -c "$LAB_RENDER"
   test -c /dev/kfd
   export GPU_PROBE_DIR="$LAB_DIR/raw/gpu-probe-01"
   mkdir "$GPU_PROBE_DIR"
   GPU_ARGS=(--device=/dev/kfd --device=/dev/dri --group-add "$(stat -c '%g' /dev/kfd)" --group-add "$(stat -c '%g' "$LAB_RENDER")" --security-opt seccomp=unconfined --ipc=host)
   for RUNTIME in vllm sglang; do
     if [ "$RUNTIME" = vllm ]; then LAB_IMAGE="$VLLM_IMAGE"; else LAB_IMAGE="$SGLANG_IMAGE"; fi
     if docker run --rm "${GPU_ARGS[@]}" --entrypoint python3 "$LAB_IMAGE" -c 'import json,torch; assert torch.version.hip; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); print(json.dumps({"torch":torch.__version__,"hip":torch.version.hip,"device":p.name,"arch":p.gcnArchName,"total_memory":p.total_memory})); assert "gfx1151" in p.gcnArchName' > "$GPU_PROBE_DIR/$RUNTIME-gpu.json" 2> "$GPU_PROBE_DIR/$RUNTIME-gpu.stderr"; then
       printf '0\n' > "$GPU_PROBE_DIR/$RUNTIME-exit.txt"
     else
       LAB_PROBE_EXIT=$?
       printf '%s\n' "$LAB_PROBE_EXIT" > "$GPU_PROBE_DIR/$RUNTIME-exit.txt"
       printf 'GPU probe failed: %s; stop before loading models.\n' "$RUNTIME" >&2
       exit "$LAB_PROBE_EXIT"
     fi
     docker run --rm --entrypoint python3 "$LAB_IMAGE" -m pip freeze > "$GPU_PROBE_DIR/$RUNTIME-packages.txt"
     printf '%s\n' "$LAB_IMAGE" > "$GPU_PROBE_DIR/$RUNTIME-ready-image.txt"
   done
   ```

   Run the block in a separate Bash session: a nonzero probe explicitly exits it before model loading, preserving the original exit code. `ready-image.txt` appears only after a successful check of that image. A repeated probe gets a new directory, such as `gpu-probe-02`; the preceding `mkdir` deliberately prevents overwriting. Do not use an old marker after a driver or image change. Copy the current `GPU_PROBE_DIR`, image variables, and `GPU_ARGS` array into the launch terminals; Bash arrays are not exported automatically. PyTorch normally uses the `torch.cuda` name on ROCm as well. API availability does not prove support for all model kernels. Measure free memory and observe the peak using LAB02/05 tools, including page cache and temporary loading costs. The `0.5` fraction below is an initial limit; vLLM and SGLang use **different** mechanisms, not the same byte count. First compare it with the capacity reported by the runtime and the OS budget.

4. **Start vLLM.** Save the image's `--help` before execution. The command uses a minimal context, one sequence, BF16, disabled prefix caching and CUDA/HIP graphs, and explicit Qwen3.5 parsers:

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/vllm-ready-image.txt")" = "$VLLM_IMAGE"
   export LAB_CONTEXT=4096
   export LAB_CONFIG=vllm-c4096-eager-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   mkdir "$SERVER_EVIDENCE"
   docker run --rm --entrypoint vllm "$VLLM_IMAGE" serve --help > "$SERVER_EVIDENCE/help.txt" 2>&1
   docker run --rm --name lab06-vllm "${GPU_ARGS[@]}" -p 127.0.0.1:8000:8000 -v "$NATIVE_MODEL_DIR:/model:ro" -e HF_HUB_OFFLINE=1 "$VLLM_IMAGE" --model /model --served-model-name lab-model --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len "$LAB_CONTEXT" --max-num-seqs 1 --gpu-memory-utilization 0.5 --enforce-eager --no-enable-prefix-caching --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder > "$SERVER_EVIDENCE/server.log" 2>&1
   ```

   This is a foreground command in a separate terminal. `LAB_CONFIG` includes engine/context and a unique start number; choose the next number even when restarting identical settings. `mkdir` without `-p` stops the block if an archive is reused. In another terminal, set the same `LAB_CONFIG`/`SERVER_EVIDENCE`, check `/v1/models`, and then run the control request in step 7. Watch compile errors, the attention backend, and actual offload/residency. After measuring, stop **this** container with `docker stop lab06-vllm` and record memory release. Do not replace `--model` with a network alias if the local path fails.

5. **Start SGLang.** All dependencies are already in the built image. Save its help and start the same model:

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/sglang-ready-image.txt")" = "$SGLANG_IMAGE"
   export LAB_CONTEXT=4096
   export LAB_CONFIG=sglang-c4096-graph1-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   mkdir "$SERVER_EVIDENCE"
   docker run --rm --entrypoint python3 "$SGLANG_IMAGE" -m sglang.launch_server --help > "$SERVER_EVIDENCE/help.txt" 2>&1
   docker run --rm --name lab06-sglang "${GPU_ARGS[@]}" -p 127.0.0.1:30000:30000 -v "$NATIVE_MODEL_DIR:/model:ro" -e HF_HUB_OFFLINE=1 -e SGLANG_USE_AITER=0 "$SGLANG_IMAGE" python3 -m sglang.launch_server --model-path /model --served-model-name lab-model --host 0.0.0.0 --port 30000 --dtype bfloat16 --attention-backend triton --context-length "$LAB_CONTEXT" --mem-fraction-static 0.5 --max-running-requests 1 --cuda-graph-max-bs-decode 1 --disable-radix-cache --reasoning-parser qwen3 --tool-call-parser qwen3_coder > "$SERVER_EVIDENCE/server.log" 2>&1
   ```

   First reproduce a configuration close to the PR, with graph decode batch 1; this differs from eager vLLM and is recorded in the comparison. A graph-capture error permits a separate diagnostic run with `--disable-cuda-graph`, after checking the flag in the saved help; this is a **new configuration**. After the HTTP probe, stop only `lab06-sglang`. Do not add WSL `/dev/dxg` or WSL library mounts to the native Linux command.

6. **Run the reference directly through Transformers.** Use the same SGLang image for its already compatible ROCm/Torch/Transformers, but do not invoke the SGLang server. This provides a separate execution path sharing libraries, not an independent implementation of all kernels. Save the following as `$LAB_DIR/raw/reference.py`:

   ```python
   import json, pathlib, time, torch, transformers
   from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

   assert torch.version.hip and torch.cuda.is_available()
   assert "gfx1151" in torch.cuda.get_device_properties(0).gcnArchName
   request = json.loads(pathlib.Path("/evidence/raw/chat-request.json").read_text())
   tokenizer = AutoTokenizer.from_pretrained("/model", local_files_only=True)
   # Explicit BF16, SDPA, and the full checkpoint; this probe has no vision inputs.
   model = Qwen3_5ForConditionalGeneration.from_pretrained(
       "/model", dtype=torch.bfloat16, attn_implementation="sdpa",
       local_files_only=True).to("cuda:0").eval()
   template = tokenizer.apply_chat_template(
       request["messages"], tokenize=False, add_generation_prompt=True,
       enable_thinking=False)
   pathlib.Path("/evidence/raw/reference-prompt.txt").write_text(template)
   inputs = tokenizer(template, return_tensors="pt", add_special_tokens=False).to("cuda:0")
   assert inputs.input_ids.shape[1] + request["max_tokens"] <= 4096
   torch.cuda.reset_peak_memory_stats()
   torch.cuda.synchronize()
   start = time.perf_counter()
   with torch.inference_mode():
       outputs = model.generate(**inputs, max_new_tokens=request["max_tokens"], do_sample=False)
   torch.cuda.synchronize()
   elapsed = time.perf_counter() - start
   generated = outputs[0, inputs.input_ids.shape[1]:]
   print(json.dumps({"torch": torch.__version__, "hip": torch.version.hip,
       "transformers": transformers.__version__, "thinking": False,
       "sampling": "greedy", "input_tokens": inputs.input_ids.shape[1],
       "output_tokens": generated.numel(), "generate_seconds": elapsed,
       "peak_allocated_bytes_after_load": torch.cuda.max_memory_allocated(),
       "peak_reserved_bytes_after_load": torch.cuda.max_memory_reserved(),
       "final": tokenizer.decode(generated, skip_special_tokens=True)}, ensure_ascii=False))
   ```

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/sglang-ready-image.txt")" = "$SGLANG_IMAGE"
   docker run --rm "${GPU_ARGS[@]}" -v "$NATIVE_MODEL_DIR:/model:ro" -v "$LAB_DIR:/evidence" -e HF_HUB_OFFLINE=1 "$SGLANG_IMAGE" python3 /evidence/raw/reference.py > "$LAB_DIR/raw/reference-result.json" 2> "$LAB_DIR/raw/reference.stderr"
   ```

   CPU loading and `.to()` may temporarily hold additional copies: observe external peak RAM separately; it is not included in the two post-load Torch counters. Fast DeltaNet extensions may be missing; preserve fallback and warnings without silently installing `latest`. Greedy/non-thinking are diagnostic reference conditions. They do not replace the author's sampling settings for a quality benchmark. There is no HTTP, TTFT, or tool execution here; these fields are `not-applicable`, not zeros.

7. **Run identical server probes and analyze differences.** For each working server, set the URL without `/v1`, save `/v1/models`, and apply the LAB05 driver:

   ```bash
   set -euo pipefail
   export LAB_URL=http://127.0.0.1:8000
   export LAB_ENGINE=vllm
   export LAB_CONFIG=vllm-c4096-eager-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   export LAB_REPEAT=1
   test -d "$SERVER_EVIDENCE"
   export PROBE_EVIDENCE="$SERVER_EVIDENCE/protocol-r$LAB_REPEAT"
   mkdir "$PROBE_EVIDENCE"
   curl --fail-with-body --silent --show-error "$LAB_URL/v1/models" > "$PROBE_EVIDENCE/models.json"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/chat-request.json" --out "$PROBE_EVIDENCE/chat"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/tool-request.json" --out "$PROBE_EVIDENCE/tool" --follow-tool
   ```

   For SGLang, change the URL to `http://127.0.0.1:30000`, the name to `sglang`, and `LAB_CONFIG` to the ID of the server actually running. Increase `LAB_REPEAT` for the next repetition: existing directories are not reused. Then create streaming JSON variants and repeat the full round trip from LAB05, saving results under separate `$PROBE_EVIDENCE/chat-stream` and `$PROBE_EVIDENCE/tool-stream` prefixes; do not use its hardcoded `8080` URL. Label the first chat after startup separately from subsequent requests; a tool request after chat is no longer the server's first request. Save the actual request body, thinking/sampling settings, parser, template hash, finish reason, and final content. When comparing with the reference, explicitly identify differences in modes; for a matched series, first set identical thinking/sampling using a method supported by each version, and save new JSON files.

   After successful 4K smoke tests, increase only `LAB_CONTEXT` to 8192 and set a new `LAB_CONFIG` in the launch step, such as `vllm-c8192-eager-01`. Stop the previous server before starting the new one. Set the new `SERVER_EVIDENCE` in the client terminal; before other inference requests, perform one first request and three repetitions:

   ```bash
   set -euo pipefail
   test -d "$SERVER_EVIDENCE"
   for SAMPLE in cold-r1 warm-r1 warm-r2 warm-r3; do
     SAMPLE_DIR="$SERVER_EVIDENCE/$SAMPLE"
     mkdir "$SAMPLE_DIR"
     python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/chat-request.json" --out "$SAMPLE_DIR/chat"
   done
   ```

   Here, cold means the first inference request after starting a new server process, not a guaranteed empty OS page cache. Then run protocol cases with new repetition directories. On error the block stops, preserving original files; mark subsequent requests `not-run` until deciding on another attempt. In this minimum lab, 8K means a server setting and short protocol smoke test, **not confirmation that a full 8K input fits**. Do not compare JIT cold with warm, HTTP wall time with pure `generate_seconds`, or a preallocated pool with Torch allocated memory. The three runtimes need not produce bit-for-bit identical text.

   **Separate extension: near-limit input.** The LAB05 generator uses llama.cpp-specific `/apply-template` and `/tokenize` on port 8080; it is not a ready-made command for vLLM/SGLang. Before this extension, independently verify counting through the tokenizer of the same native model revision and the selected server's actual template, with identical special tokens, thinking, and tools. Save the template hash, rendered prompt, and token count; compare the count with `usage.prompt_tokens` on a short request. Once they match, prepare a new long request with an explicit output reserve, separate configuration/repetition prefixes, and a check for no truncation. If the effective template or count cannot be reproduced, mark near-limit as `blocked/not-run`; the previous llama.cpp counter does not prove this deployment's capacity. This extension is outside the LAB06 minimum.

## Results tables

| Runtime / image ID | Torch / ROCm / Triton / Transformers | gfx1151 probe | Documented path | Local status and evidence |
| --- | --- | --- | --- | --- |
| vLLM | | | | |
| SGLang | | | | |
| Transformers reference | | | | |

| Configuration | Artifact revision / hash manifest | Context / concurrency | Dtype / cache / graphs / parser | Peak RAM / GPU, bytes | Status |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

| Configuration / repeat | Cold or warm | Chat final | Tools / streaming | Wall / TTFT, s | Output tokens / finish reason | Evidence / reason for absence |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

## Deliverables

A completed report, new native artifact manifest and file verification, image inspect/package freeze/build log, GPU probes, launch commands, server logs, raw HTTP/SSE and reference output, and a table of 4K and admitted 8K probes. In the conclusion, distinguish “support documented by the author”, “runtime built”, “model loaded”, “protocol passed”, and “performance measured”.

## Completion criteria

- [ ] The native checkpoint is pinned and its memory estimated independently of GGUF.
- [ ] Each of the three branches has an observation or `fail`/`not-run`/`no-artifact` with a specific reason.
- [ ] Actual gfx1151/ROCm is confirmed before claiming GPU execution; CPU fallback is not called ROCm success.
- [ ] For successfully loaded servers, chat and the full tool round trip, including streaming, are preserved.
- [ ] Changes to context, graph/cache, sampling, and kernel path are recorded as configuration conditions.
- [ ] No engine smoke test is presented as an agent run; connecting harnesses remains the task of LAB08.

## Review questions

1. Why does safetensors not specify a particular precision, and why does GGUF size not describe this checkpoint?
2. Why does a successful `torch.cuda.is_available()` not prove MXFP4 kernel support on gfx1151?
3. How can the reference help distinguish a template/parser error from a model error?
4. What does an image digest pin, and what does a Dockerfile Git commit alone not pin?
5. Which differences in graphs, cache, and measurement points prevent direct tokens/s comparisons?

## Sources

- [vLLM: GPU/ROCm installation and gfx1151 support](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/), [v0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0), [pinned Docker tag metadata](https://hub.docker.com/v2/repositories/vllm/vllm-openai-rocm/tags/v0.29.0), [server arguments](https://docs.vllm.ai/en/stable/cli/serve/).
- [SGLang: pinned gfx1151 Dockerfile](https://github.com/sgl-project/sglang/blob/94602c9c2b7cbdb8efd5c52802dac6a1c180089e/docker/rocm-gfx1151.Dockerfile), [original PR and limits of the WSL2 verification](https://github.com/sgl-project/sglang/pull/33939), [server arguments](https://docs.sglang.io/docs/advanced_features/server_arguments).
- [Qwen3.5-9B: pinned checkpoint and parsers](https://huggingface.co/Qwen/Qwen3.5-9B/tree/c202236235762e1c871ad0ccb60c8ee5ba337b9a), [Transformers Qwen3.5](https://huggingface.co/docs/transformers/model_doc/qwen3_5).
- [AMD: PyTorch installation](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html), [native Linux Ryzen compatibility](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html).
- [Engine matrix and artifact limitations](../local-inference-engines.md), [shared fixtures](fixtures/README.md).
