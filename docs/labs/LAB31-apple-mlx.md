# LAB31. Native MLX-LM inference

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Independent engine / `target-machine` |
| Time | 2–4 hours plus environment setup |
| Prerequisites | LAB28, LAB29; separate MLX artifact and native arm64 Python |
| Minimum | One model, pinned mlx/mlx-lm, warmup and three repetitions; comparison with LAB30 if available |

## Objective

Measure MLX as a standalone configuration and establish which differences from GGUF arise from the format and input protocol.

## Hypothesis

The MLX variant of the selected model runs on the GPU with sufficient memory headroom. Differences from llama.cpp are not attributed solely to the engine if quantization or templates differ.

## Preparation

Create an environment outside Git and pin versions compatible with the selected architecture. Choose version numbers from model documentation and record them before installation; `latest` is not a pin.

```sh
npm run lab:new -- --lab LAB31 --session apple-mlx
export LAB_DIR='experiments/local-models/measurements/LAB31-apple-mlx'
export MLX_ENV='/absolute/path/to/new-mlx-venv'
export LOCAL_MLX='/absolute/path/to/pinned-mlx-model'
export MLX_VERSION='<exact mlx version>'
export MLX_LM_VERSION='<exact mlx-lm version>'
python3 -m venv "$MLX_ENV"
"$MLX_ENV/bin/python" -m pip install "mlx==$MLX_VERSION" "mlx-lm==$MLX_LM_VERSION" \
  > "$LAB_DIR/raw/install.txt" 2>&1
printf '%s\n' "$?" > "$LAB_DIR/raw/install-exit.txt"
```

Stop on error. The [shared Apple protocol](../../experiments/local-models/apple/README.md) defines memory, repetitions and submission; LAB30 is not required for standalone MLX admission.

## Procedure

1. Save versions, architecture and GPU interface information:

   ```sh
   "$MLX_ENV/bin/python" -m pip freeze > "$LAB_DIR/raw/python-lock.txt"
   "$MLX_ENV/bin/python" -c 'import platform; print(platform.machine()); print(platform.python_version())' \
     > "$LAB_DIR/raw/python-platform.txt"
   "$MLX_ENV/bin/python" -m mlx_lm.generate --help > "$LAB_DIR/raw/generate-help.txt" 2>&1
   "$MLX_ENV/bin/python" -m mlx_lm.server --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   "$MLX_ENV/bin/python" - <<'PY' > "$LAB_DIR/raw/mlx-device.json" 2> "$LAB_DIR/raw/mlx-device-errors.txt"
   import json, mlx.core as mx
   info = mx.device_info() if hasattr(mx, 'device_info') else mx.metal.device_info()
   print(json.dumps(info, indent=2))
   PY
   ```

   API availability depends on the pin: an error is evidence, not a zero memory limit. Verify the selected GPU and follow recommended values; do not call `set_memory_limit` or tune wired limits in the baseline.

2. Prepare the same public prompt and reasoning/sampling settings according to the model card. Save the prompt, tokenizer/template hash and exact command. Example smoke test (check flags in pinned help):

   ```sh
   printf '%s\n' 'Explain three reasons to verify model weight hashes.' > "$LAB_DIR/raw/prompt.txt"
   "$MLX_ENV/bin/python" -m mlx_lm.generate --model "$LOCAL_MLX" \
     --prompt "$(cat "$LAB_DIR/raw/prompt.txt")" --max-tokens 128 --temp 0 --seed 1 \
     > "$LAB_DIR/raw/warmup.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/warmup-exit.txt"
   ```

   The model path must point to a pinned local artifact. Do not use a remote model alias that allows automatic weight changes. CPU fallback, an unsupported architecture or unexpectedly loading another model is a blocker.

3. After the smoke test, collect memory and start the LAB28 time series. Run the command once each for `REPEAT=1`, `2`, `3`; stop on errors/pressure:

   ```sh
   export REPEAT=1
   /usr/bin/time -l "$MLX_ENV/bin/python" -m mlx_lm.generate --model "$LOCAL_MLX" \
     --prompt "$(cat "$LAB_DIR/raw/prompt.txt")" --max-tokens 128 --temp 0 --seed 1 \
     > "$LAB_DIR/raw/r$REPEAT-generate.txt" 2> "$LAB_DIR/raw/r$REPEAT-process.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/r$REPEAT-exit.txt"
   ```

   Record actual generated tokens, prompt/generation throughput and runtime peak memory if the version reports them. Do not substitute the 128 cap for actual output. A missing metric is `null`. Each command creates a new process: this is a CLI repetition with warm file cache, not resident warm HTTP.

4. Start the server in a separate terminal with the same artifact/environment, saving its output:

   ```sh
   "$MLX_ENV/bin/python" -m mlx_lm.server --model "$LOCAL_MLX" --host 127.0.0.1 --port 8081 \
     > "$LAB_DIR/raw/server.txt" 2>&1
   ```

   In the working terminal, after readiness:

   ```sh
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:8081/v1/models \
     > "$LAB_DIR/raw/server-models.json"
   ```

   Record the actual model identifier accepted by the pinned server; an alias does not prove weight identity. Stop your server with Ctrl-C before starting another configuration. HTTP streaming/tools and long context are tested in LAB32.

5. Write `runtime-manifest.json`: Python/MLX/MLX-LM, lock, artifact manifest, device, flags/defaults, template/reasoning and observed allocations. Include a differences table for comparison with LAB30. Synthetic `llama-bench` PP/TG and an MLX chat prompt are not identical workloads: comparable HTTP measurements belong in LAB32/35.

## Results tables

| Repetition | Prompt tokens | Output tokens | Prompt tokens/s | Generate tokens/s | Runtime peak GiB | Process RSS bytes | Wall s / exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

| Difference from GGUF | Value | Can the engine effect be isolated? |
| --- | --- | --- |
| Source revision / quant / tokenizer / template / prompt | | |

## Deliverables

Report/TSV/manifest, lock and installation provenance, device info, artifact/runtime manifests, prompt and all output/time/memory evidence. Do not commit weights or the venv.

## Completion criteria

- [ ] Native arm64 and exact versions confirmed.
- [ ] MLX weights recorded separately from GGUF.
- [ ] Smoke test and three repetitions completed, or blocker documented.
- [ ] Actual output, memory and comparison limitations recorded.
- [ ] Submission checked with `lab:check --mode submission`.

## Review questions

1. Why does a fresh CLI command not measure a warm resident server?
2. Why do 4-bit MLX and Q4_K_M not control quantization as a single factor?
3. Which processes contribute to RSS, and which metrics does the runtime provide?
4. Why is `/v1/models` insufficient to prove deployment identity?

## Sources

- [MLX-LM](https://github.com/ml-explore/mlx-lm).
- [MLX device API](https://ml-explore.github.io/mlx/build/html/python/devices_and_streams.html).
- [MLX-LM server source](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py).
