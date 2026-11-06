# LAB07. Ollama, LM Studio, and Lemonade

## Profile

- Time: 3–6 hours plus installation of the selected applications/runtimes.
- Prerequisites: [LAB05](LAB05-context-tools.md) submitted; verified GGUF, hash manifest, working backend, and HTTP driver preserved. The optional Lemonade/vLLM branch requires [LAB06](LAB06-engines.md).
- Readiness: Linux CLI and import/configuration paths are documented as of 2026-09-21; all hardware results remain to be obtained. Installed application versions and selected runtimes must pass their own smoke tests.
- Minimum: one control GGUF and **two services of your choice**, each using one backend that already passed LAB04. The third service, Vulkan/ROCm pairs, a second control GGUF, and Lemonade/vLLM are extensions. Leave untested branches `not-run`; do not promise verification of the entire matrix.

## Objective

Check whether one artifact and a working tool protocol are preserved when moving from direct llama-server to different local services, and identify changes in runtime, template, parser, and memory settings.

## Hypothesis

“Two selected services import the same control GGUF bytes, use the declared GPU backend, and pass identical chat/streaming/tool fixtures with pinned settings.” Matching weights do not imply matching prompts or kernels; those conditions are checked separately.

## Preparation

```bash
npm run lab:new -- --lab LAB07 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB07-my-session"
export LAB03_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB05_DIR="$PWD/experiments/local-models/measurements/LAB05-my-session"
cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
cp "$LAB03_DIR/raw/verification.json" "$LAB_DIR/raw/source-verification.json"
cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
cp "$LAB05_DIR/raw/http_probe.py" "$LAB_DIR/raw/http_probe.py"
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/source-recheck.txt"
```

Set `GGUF` to the absolute path of the single `qwen35-9b` control file from LAB03. It does not need a special split import. When extending to a split GGUF, verify all shards again and use the import method specifically supported by that version, without concatenation.

Before execution, choose two services, the backend, context 8192, concurrency 1, output budget 2048, and the thinking/sampling mode from LAB05 in the report. Start with one server and one model in memory; after stopping it, confirm the runner has released the GPU. Preserve the direct-server baseline from LAB05 separately. These applications are serving wrappers: Ollama has its own llama.cpp integration, LM Studio selects a runtime package, and Lemonade launches a recipe. Three application names do not mean three independent sets of GPU kernels.

## Procedure

1. **Pin the application and runtime before the first request.** If an application is missing, install its Linux version using the official instructions in the sources, choosing a release compatible with your OS. Record the installer URL, version, date, archive/package SHA-256, and installation commands in `raw/install-notes.md`. Exclude installation from inference time. Do not update the application, models, or runtime during the series.

   ```bash
   ollama --version > "$LAB_DIR/raw/ollama-version.txt" 2>&1
   lms --version > "$LAB_DIR/raw/lms-version.txt" 2>&1
   lemonade --version > "$LAB_DIR/raw/lemonade-version.txt" 2>&1
   lemond --help > "$LAB_DIR/raw/lemond-help.txt" 2>&1
   ```

   Run only the selected applications' commands. A missing command means `not-run: runtime-not-installed`, not a model error. A specific Ollama candidate is [v0.34.2](https://github.com/ollama/ollama/releases/tag/v0.34.2); AMD Linux requires the main package and ROCm runtime from the same release. For Lemonade, use [v11.9.0](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0). Record LM Studio GUI and `lms` versions separately; select the runtime in step 3 rather than inventing a `gfx1151` package name. Another already installed version may be studied, but its results apply specifically to that version.

2. **Ollama branch: import and backend.** Start a separate foreground server on an available loopback port. `OLLAMA_MODELS` specifies separate storage; check disk space accounting for a weights copy. For ROCm:

   ```bash
   mkdir -p "$LAB_DIR/raw/ollama-models"
   export LAB_OLLAMA_CONFIG=ollama-rocm-8k
   OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS="$LAB_DIR/raw/ollama-models" OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_DEBUG=1 OLLAMA_VULKAN=0 ollama serve > "$LAB_DIR/raw/$LAB_OLLAMA_CONFIG-server.log" 2>&1
   ```

   Ensure the environment does not retain `ROCR_VISIBLE_DEVICES=-1` from an earlier experiment. In another terminal with the same `LAB_DIR` and `GGUF`, create a Modelfile and import without requantization:

   ```bash
   python3 - "$GGUF" "$LAB_DIR/raw/Modelfile" <<'PY'
   import pathlib, sys
   model = pathlib.Path(sys.argv[1]).resolve()
   assert model.is_file() and "\n" not in str(model) and '"' not in str(model)
   pathlib.Path(sys.argv[2]).write_text(
       f'FROM "{model}"\nPARAMETER num_ctx 8192\nPARAMETER num_predict 2048\n')
   PY
   OLLAMA_HOST=127.0.0.1:11435 ollama create lab-model -f "$LAB_DIR/raw/Modelfile" > "$LAB_DIR/raw/ollama-import.txt" 2>&1
   OLLAMA_HOST=127.0.0.1:11435 ollama show --modelfile lab-model > "$LAB_DIR/raw/ollama-effective-modelfile.txt"
   ```

   Compare the `FROM` path in the effective Modelfile with the local blob and compute its `sha256sum`: for a single GGUF it must match the source. Do not execute the `FROM` line as shell code. Save the template, stop tokens, parameters, and actual context from the runner log. The example source Modelfile does not set its own template; differences between the service's automatic template and LAB05 remain part of the configuration under study.

   Perform step 5 with URL `http://127.0.0.1:11435` and model `lab-model`. The log must explicitly show ROCm/gfx1151 and layer placement; disabling Vulkan alone does not prove this. CPU fallback → `fail` for the ROCm hypothesis, even if the text is correct.

   For an additional Vulkan configuration, stop the foreground process **created here**, wait for memory release, set `LAB_OLLAMA_CONFIG=ollama-vulkan-8k`, and repeat serve with `OLLAMA_VULKAN=1 ROCR_VISIBLE_DEVICES=-1`; set `GGML_VK_VISIBLE_DEVICES` from the detected Vulkan device index. Save the new `$LAB_OLLAMA_CONFIG-server.log` separately from ROCm. This is a diagnostic way to exclude HIP discovery; the actual selection still needs log confirmation. If CPU is selected again, do not call the probe Vulkan. Preserve the artifact hash and Modelfile; give the backend and configuration a new name.

3. **LM Studio branch: application and runtime are separate.** Prepare local LM Studio/`lms`, then:

   ```bash
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes-before.txt"
   lms runtime get
   lms runtime select
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes-selected.txt"
   lms import "$GGUF" --copy --user-repo lab/qwen35-9b --yes > "$LAB_DIR/raw/lms-import.txt" 2>&1
   lms ls > "$LAB_DIR/raw/lms-models.txt"
   ```

   In the interactive selection, record the exact runtime ID/version and Vulkan or ROCm backend. Skip `get` if the required package is already installed. Linux ROCm is documented, but the exact package/device stack still requires verification on 395. Import moves the file by default, so `--copy` matters; afterward, find the destination in the output and verify its bytes/SHA-256. Do not replace import with downloading a similarly named model from the LM Studio catalog.

   Select the exact `model_key` from `lms ls` and save it in `LMS_MODEL_KEY`, then:

   ```bash
   lms load "$LMS_MODEL_KEY" --estimate-only --gpu max --context-length 8192 > "$LAB_DIR/raw/lms-estimate.txt"
   lms load "$LMS_MODEL_KEY" --gpu max --context-length 8192 --identifier lab-model > "$LAB_DIR/raw/lms-load.txt" 2>&1
   lms ps > "$LAB_DIR/raw/lms-loaded.txt"
   lms server start --port 1235 --bind 127.0.0.1 > "$LAB_DIR/raw/lms-server-start.txt" 2>&1
   lms log stream > "$LAB_DIR/raw/lms-prompt-log.txt" 2>&1
   ```

   The last command runs in the foreground in a separate terminal. Confirm in the runtime log that `--gpu max` actually offloads to the intended device. Perform step 5 with URL `http://127.0.0.1:1235`. Save effective load/inference settings from the application: flash attention, KV dtype, context, seed/sampling, and template. `--estimate-only` is an LM Studio estimate, not a RAM measurement.

   Native tool parsing and default tool fallback are different conditions. Fallback may append instructions and transform messages; preserve the actual model input for public fixtures from `lms log stream` and identify the mode. If the mode cannot be established, record `unverified` and do not claim equal prompts. After the experiment, stop your log stream and unload with `lms unload lab-model`; stop the lab server you created with `lms server stop`. A second backend is a newly selected runtime and a separate configuration.

4. **Lemonade branch: a custom llama.cpp binary and exact GGUF.** For the strictest comparison, use the `bin` directory of the working ROCm or Vulkan build from LAB04. It must contain `llama-server` and required libraries, and its direct launch must already have passed LAB05. Set `LAB_LLAMA_BIN` to an absolute path and `LAB_BACKEND=rocm` or `vulkan`. Create separate config/cache directories without changing the system service:

   ```bash
   export LAB_BACKEND=rocm
   mkdir -p "$LAB_DIR/raw/lemonade-config" "$LAB_DIR/raw/lemonade-cache"
   python3 - "$LAB_DIR" "$GGUF" "$LAB_LLAMA_BIN" "$LAB_BACKEND" <<'PY'
   import json, pathlib, sys
   lab, gguf, binary, backend = sys.argv[1:]
   assert backend in {"rocm", "vulkan"}
   assert (pathlib.Path(binary) / "llama-server").is_file()
   assert pathlib.Path(gguf).is_file()
   config = {"host": "127.0.0.1", "port": 13315, "ctx_size": 8192,
       "max_loaded_models": 1, "broadcast": False, "offline": True,
       "auto_check_model_updates": False, "auto_update_models": False,
       "no_fetch_executables": True,
       "extra_models_dir": str(pathlib.Path(gguf).resolve().parent),
       "llamacpp": {"backend": backend, backend + "_bin": str(pathlib.Path(binary).resolve())}}
   pathlib.Path(lab, "raw/lemonade-config/config.json").write_text(json.dumps(config, indent=2))
   PY
   sha256sum "$LAB_LLAMA_BIN/llama-server" > "$LAB_DIR/raw/lemonade-backend-hash.txt"
   lemond "$LAB_DIR/raw/lemonade-cache" "$LAB_DIR/raw/lemonade-config" --port 13315 --host 127.0.0.1 --no-broadcast > "$LAB_DIR/raw/lemonade-server.log" 2>&1
   ```

   `extra_models_dir` is scanned for local GGUF files; for the minimum, the parent directory should contain only the selected control, otherwise explicitly check the list. In a separate terminal, save `curl --fail-with-body http://127.0.0.1:13315/v1/models` to `raw/lemonade-models.json`. Identify the imported name in the list and use **`extra.NAME`** as the model ID in step 5. The canonical prefix distinguishes an imported file from a matching built-in/user alias. The request initiates loading itself; do not run `pull` for this experiment.

   The log must show the intended recipe, absolute binary path, GGUF path, context, GPU backend, and child command. Also preserve the inherited library environment used in the direct LAB04 run: an identical executable without identical libraries does not guarantee an identical runtime. If the custom binary is incompatible with Lemonade, preserve `fail`; switching to a built-in binary is a separate deployment configuration with its own binary hash. After the probe, stop only the `lemond` instance you created and check for remaining model runners belonging to it.

5. **Run common probes for each selected configuration.** The example is for Ollama; for other services replace the URL, configuration ID, and model ID using the previous steps:

   ```bash
   export LAB_URL=http://127.0.0.1:11435
   export LAB_CONFIG=ollama-rocm
   export LAB_CASE=smoke-8k-cold-r1
   export LAB_MODEL_ID=lab-model
   python3 - "$LAB_DIR" "$LAB_MODEL_ID" "$LAB_CONFIG" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / "raw"
   for kind in ["chat", "tool"]:
       request = json.loads((raw / f"{kind}-request.json").read_text())
       request["model"] = sys.argv[2]
       (raw / f"{sys.argv[3]}-{kind}-request.json").write_text(json.dumps(request, ensure_ascii=False))
   PY
   curl --fail-with-body --silent --show-error "$LAB_URL/v1/models" > "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-api-models.json"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/$LAB_CONFIG-chat-request.json" --out "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-chat"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/$LAB_CONFIG-tool-request.json" --out "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-tool" --follow-tool
   ```

   Repeat the streaming variant and full round trip from LAB05. Success means final `LAB_READY`; an allowed tool with argument `alpha`, a matching call ID, and final `LAB_VALUE_42`. HTTP 200, text resembling JSON, or `finish_reason=length` alone do not mean success. Preserve rejected/ignored parameters and the distinction between reasoning and final output. Ollama's OpenAI API context is set through the Modelfile; the presence of Chat Completions does not prove every Responses capability or support for a particular agent harness.

   For each passing configuration, obtain one cold and three warm repetitions. For each case/request type, indicate whether the model was already loaded: a tool request sent after chat is not a cold load. For example, after the first chat set `LAB_CASE=smoke-8k-warm-r1` and repeat only the chat command, then use `smoke-8k-warm-r2` and `smoke-8k-warm-r3`. For streaming, use `LAB_CASE=stream-8k-warm-r1` and the corresponding saved request. Explicitly record cache mode, model keep-alive, loading time, prefix reuse, and concurrency. For a second backend/context, create a separate raw subdirectory before execution and direct every command, request file, and server log there; do not overwrite the original log. Perform a genuine near-limit 8K probe and memory observation using the LAB05 method; a short fixture does not become 8K merely because of a server flag. Do not transplant llama.cpp-specific `/tokenize` and `/apply-template` to these services: use the saved long-fixture JSON from LAB05, replace `model`, verify actual input tokens/template and absence of truncation using this service's usage/logs, and leave an output reserve. If tokenization/truncation cannot be confirmed, near-limit fit remains `unverified`; if no request was executed, use `not-run: tokenizer-accounting-unavailable`. Short HTTP/tools probes remain results in their own right.

6. **Compare the service with the direct baseline.** Compare manifests by layer: weights → binary/runtime → backend → template/parser → effective generation settings → API. Only when these conditions match can a latency difference be studied as a serving-wrapper effect. Otherwise, call the result a deployment comparison and list the differences. In particular, LM Studio fallback tools and Ollama's patched runner do not disappear from the description merely because the GGUF matches. A component subsequently added to an agent harness requires a ledger row and a separate LAB08, not a new flag for a nonexistent `local` provider.

7. **Extension: Lemonade/vLLM after LAB06.** First save the Lemonade version and its `backend_versions.json`, per-arch pin, and recipe/model-family defaults. This is an experimental ROCm path tested by its author on gfx1151; it uses its own relocatable vLLM/Torch/Triton bundle. Check kernel/CWSR prerequisites in the official instructions. Create a separate instance/config for this branch: the `offline`/`no_fetch_executables` restrictions from step 4 deliberately prevent installation. During preparation, permit downloading only the selected release with a specific `vllm.rocm_bin`, then run `lemonade --host 127.0.0.1 --port 13315 --no-discovery backends install vllm:rocm` for **your own** instance and record the actual downloaded tag/hash and architecture. Restore offline/no-fetch after installation for the series.

   The selected native checkpoint must have a new manifest and verified shards from LAB06. Registering a `user.*` recipe with only an HF name and no immutable revision does not prove checkpoint equality. Check local snapshot/cache resolution in your version and the actual child `--model`; if a pinned artifact path cannot be ensured, leave the paired comparison as `no-artifact`. Do not substitute a built-in FP16 or FP8 model. Recalculate BF16/FP16/native-quant memory separately from GGUF.

   Run chat/tools and compare child arguments with direct vLLM. The service manages model, served name, host/port, context, and some cache/graph flags, and adds family parser settings. You cannot simply paste the entire LAB06 command into `vllm.args`. Preserve the health/backend URL only in coordinator evidence; the child's direct `/metrics` is not a public capability of the shared API. This branch is outside the minimum required work; an unprepared bundle/exact artifact leaves an explicit `not-run`/`no-artifact`.

## Results tables

| Service | App / CLI version | Runtime ID / binary hash | Backend / GPU evidence | Selected for minimum | Status / reason |
| --- | --- | --- | --- | --- | --- |
| Ollama | | | | | |
| LM Studio | | | | | |
| Lemonade / llama.cpp | | | | | |
| Lemonade / vLLM, extension | | | | | |

| Configuration | Source/imported SHA-256 | Template / tool mode | Context / cache / thinking / sampling | Differences from direct baseline |
| --- | --- | --- | --- | --- |
| | | | | |

| Configuration / repeat | Cold / warm | Chat / streaming / full tools | Wall / TTFT, s | Peak RAM / GPU, bytes | Evidence / verdict |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Deliverables

A report on two selected configurations, installation/runtime pins, source and imported file hashes, import commands, effective Modelfile/runtime/configuration, public model prompts, server/runner logs, raw HTTP/SSE, and memory observations. For every untested branch, give the reason and next specific step. State in the conclusion where wrapper overhead is comparable and where the entire deployment changes.

## Completion criteria

- [ ] Two services were examined using one artifact; each has a measurement or reproducible `fail` with evidence.
- [ ] The imported GGUF is verified by bytes/hash; downloading an alias does not substitute for provenance.
- [ ] App version, runtime version, and actual GPU backend are recorded separately.
- [ ] The full tool round trip and streaming are preserved; native/fallback parsing is stated explicitly.
- [ ] The direct baseline is compared under known conditions; missing metrics are not filled with zeros.
- [ ] Third/additional branches are marked `not-run` if not executed; Lemonade/vLLM did not inherit the GGUF memory estimate.

## Review questions

1. Why is comparing Ollama and LM Studio not equivalent to comparing two fully independent inference engines?
2. What must be checked after successfully importing a GGUF, beyond its appearance in the model list?
3. How does tool fallback change the question “did the harness help the model”?
4. Why do `--gpu max` or `OLLAMA_VULKAN=0` alone not prove the intended GPU path?
5. Under which conditions can a latency difference be attributed specifically to the serving wrapper?

## Sources

- Ollama: [Linux install](https://docs.ollama.com/linux), [GPU/gfx1151 and backend selection](https://docs.ollama.com/gpu), [GGUF import](https://docs.ollama.com/import), [Modelfile](https://docs.ollama.com/modelfile), [OpenAI API limits](https://docs.ollama.com/api/openai-compatibility).
- LM Studio: [Linux download](https://lmstudio.ai/download), [runtime CLI](https://lmstudio.ai/docs/cli/runtime/runtime), [import](https://lmstudio.ai/docs/cli/local-models/import), [load](https://lmstudio.ai/docs/cli/local-models/load), [server start](https://lmstudio.ai/docs/cli/serve/server-start), [native/default tools](https://lmstudio.ai/docs/developer/openai-compat/tools).
- Lemonade: [installation and supported platforms](https://lemonade-server.ai/docs/guide/install/), [CLI and instance selection](https://lemonade-server.ai/docs/guide/cli/), [configuration and custom binary](https://lemonade-server.ai/docs/guide/configuration/), [local extra models and canonical IDs](https://lemonade-server.ai/docs/guide/configuration/custom-models/), [experimental vLLM recipe and limitations](https://lemonade-server.ai/docs/guide/configuration/vllm/).
- [Engine and service matrix](../local-inference-engines.md), [shared fixtures](fixtures/README.md), [research method](../method.md).
