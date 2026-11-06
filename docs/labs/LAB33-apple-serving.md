# LAB33. Ollama and LM Studio on Apple Silicon

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Serving applications / `target-machine` |
| Time | 3–5 hours plus installation |
| Prerequisites | LAB32; corresponding LAB29–31 manifests |
| Minimum | Ollama/Metal GGUF, LM Studio/Metal GGUF and LM Studio/MLX: smoke test each or provide blocker evidence |

## Objective

Check application API usability and correctness, distinguishing wrapper overhead from changes to the underlying inference runtime.

## Hypothesis

The application preserves the required tool/streaming protocol with pinned weights, runtime and settings. Overhead can be isolated only when the underlying engine and all material conditions match the direct baseline.

## Preparation

Install applications separately at pinned versions; do not update them during the series. Save application, CLI and runtime-package versions. The [shared protocol](../../experiments/local-models/apple/README.md) and LAB32 define context/repetitions.

```sh
npm run lab:new -- --lab LAB33 --session apple-serving
export LAB_DIR='experiments/local-models/measurements/LAB33-apple-serving'
ollama --version > "$LAB_DIR/raw/ollama-version.txt" 2>&1
ollama create --help > "$LAB_DIR/raw/ollama-create-help.txt" 2>&1
lms --help > "$LAB_DIR/raw/lms-help.txt" 2>&1
lms runtime --help > "$LAB_DIR/raw/lms-runtime-help.txt" 2>&1
lms import --help > "$LAB_DIR/raw/lms-import-help.txt" 2>&1
lms load --help > "$LAB_DIR/raw/lms-load-help.txt" 2>&1
lms server start --help > "$LAB_DIR/raw/lms-server-help.txt" 2>&1
```

Record a missing CLI/runtime as a blocker for that branch. Do not infer a version from the installer name or GUI alone.

## Procedure

1. Prepare separate `ollama-metal`, `lm-studio-metal`, `lm-studio-mlx` conditions and a direct baseline. For the first two, use **the same** GGUF hashes from LAB29; for the third, use a separate pinned MLX artifact. Import must not change original files or automatically update weights. For shard imports, check support in the selected version; the first shard without the others is not a model.

2. Ollama example for a supported single-file GGUF. Before writing `Modelfile`, ensure the path contains no quotes/newlines; substitute the already pinned absolute path:

   ```sh
   cat > "$LAB_DIR/raw/Modelfile" <<'MODEL'
   FROM /absolute/path/to/pinned-model.gguf
   PARAMETER num_ctx 8192
   MODEL
   ollama create lab-apple-gguf -f "$LAB_DIR/raw/Modelfile" \
     > "$LAB_DIR/raw/ollama-import.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/ollama-import-exit.txt"
   ollama show lab-apple-gguf --modelfile > "$LAB_DIR/raw/ollama-modelfile.txt" 2>&1
   ollama show lab-apple-gguf > "$LAB_DIR/raw/ollama-model.txt" 2>&1
   ```

   Import only after replacing the placeholder. Pin template/defaults and blob hashes; the same alias does not prove identity. Use one loopback server you own; for CLI startup, after stopping the application's background instance:

   ```sh
   OLLAMA_HOST=127.0.0.1:11434 ollama serve > "$LAB_DIR/raw/ollama-server.txt" 2>&1
   ```

   If the application already manages the server, do not start a second one—archive the existing logs. Confirm Metal, runner and offload from logs. If a different engine/artifact was actually selected, record a separate deployment condition; this GGUF profile does not prove applicability to an MLX runner.

3. LM Studio example (check the interface against pinned help):

   ```sh
   lms import "$LOCAL_GGUF" > "$LAB_DIR/raw/lms-import.txt" 2>&1
   lms ls > "$LAB_DIR/raw/lms-models.txt" 2>&1
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes.txt" 2>&1
   ```

   Record the actual model key from the list and the selected runtime package/version. Load only this model:

   ```sh
   export LMS_MODEL_KEY='<imported model key from lms ls>'
   lms load "$LMS_MODEL_KEY" --identifier lab-model --context-length 8192 \
     > "$LAB_DIR/raw/lms-load.txt" 2>&1
   lms server start --port 1234 > "$LAB_DIR/raw/lms-server-start.txt" 2>&1
   lms ps > "$LAB_DIR/raw/lms-loaded.txt" 2>&1
   ```

   Disable LAN access in server settings and check the actual listener; the interface depends on the version. Import/register the MLX variant using the method documented for the installed runtime: a GGUF CLI does not automatically support an MLX directory. Inability to preserve the exact revision/hash is a blocker. Save the selected runtime and loading logs for both LM Studio branches, unloading the previous model before the next.

4. Save `/v1/models` for each application, for example:

   ```sh
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:11434/v1/models \
     > "$LAB_DIR/raw/ollama-api-models.json"
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:1234/v1/models \
     > "$LAB_DIR/raw/lms-api-models.json"
   ```

   Send the request only to the current server. Make your own copies of the four LAB32 requests with the actual alias. At one admitted context size, run warmup + three repetitions of chat/tool × JSON/SSE, then one cancelled request and recovery. Save usage, final/IDs, raw SSE, TTFT and memory evidence. Native tool templates and fallback templates are separate conditions; do not hide fallback after a parser failure.

5. Repeat the same HTTP cases on direct llama-server/MLX-LM from LAB32 with matching prompt and settings. If the internal commit/build/tokenizer/quant differs or is unknown, frame the conclusion as a deployment comparison. Do not subtract TTFT for two different engines and call it “pure GUI overhead”.

6. Record each application's deployment manifest: app/CLI/runtime versions, weight hashes, template, context/slots, cache/loading policy, observed backend/runner and process. After completion, stop or unload only your own lab models using the application's standard controls.

## Results tables

| Deployment | App / CLI / runtime pin | Artifact hash | Backend confirmed | Protocol pass/attempts | Median TTFT / total s | Memory / failures |
| --- | --- | --- | --- | --- | --- | --- |
| Ollama GGUF | | | | | | |
| LM Studio GGUF | | | | | | |
| LM Studio MLX | | | | | | |

| Pair with direct baseline | Matching conditions | Differences / unknowns | Overhead or deployment comparison |
| --- | --- | --- | --- |
| | | | |

## Deliverables

Report/TSV/manifest, version/help, import/runtime/identity evidence, deployment manifests, requests and results for every repetition with memory. Import errors and unavailable branches remain in the attempt registry.

## Completion criteria

- [ ] Three branches checked or assigned a specific blocker.
- [ ] Exact weights and underlying runtime distinguished from GUI version.
- [ ] Tool/streaming cases have a warmup and three repetitions on admitted branches.
- [ ] No pure-overhead claim when underlying engines are unknown/different.
- [ ] Submission checked against the shared protocol.

## Review questions

1. Why is the GUI version not a pin for the inference engine?
2. When can importing the same file still change the input protocol?
3. What must be established to measure pure wrapper overhead?
4. How is the observed runner more useful than a model alias?

## Sources

- [Ollama import](https://docs.ollama.com/import), [GPU](https://docs.ollama.com/gpu), [API compatibility](https://docs.ollama.com/api/openai-compatibility).
- [LM Studio CLI](https://lmstudio.ai/docs/cli), [runtime](https://lmstudio.ai/docs/cli/runtime/runtime), [MLX engine](https://lmstudio.ai/blog/unified-mlx-engine).
