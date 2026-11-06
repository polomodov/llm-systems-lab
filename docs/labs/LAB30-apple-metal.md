# LAB30. llama.cpp on Apple Metal

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Backend measurement / `target-machine` |
| Time | 2–4 hours plus build time |
| Prerequisites | LAB28, LAB29; native arm64 CMake/Clang and GGUF |
| Minimum | One pinned build, GPU smoke test, separate warmup and three prefill/decode repetitions |

## Objective

Establish a reproducible Metal baseline and confirm which operations actually run on the GPU.

## Hypothesis

The selected GGUF runs in pinned llama.cpp on M5 Max with measured memory headroom and no unplanned CPU fallback. This makes no speed claim before measurement.

## Preparation

```sh
npm run lab:new -- --lab LAB30 --session apple-metal
export LAB_DIR='experiments/local-models/measurements/LAB30-apple-metal'
export LLAMA_SRC='/absolute/path/to/llama.cpp-checkout'
export LLAMA_BUILD='/absolute/path/to/new-metal-build'
export LOCAL_GGUF='/absolute/path/to/pinned-model.gguf'
export LLAMA_COMMIT='<full commit from the protocol>'
```

Prepare the checkout at the selected commit. A comparison with Ryzen requires the same commit. The build directory must be new; source, build and weights are not included in evidence. The [shared protocol](../../experiments/local-models/apple/README.md) is mandatory.

## Procedure

1. Pin source, toolchain and parameters, then build natively. Stop if the SHA differs or the checkout is dirty:

   ```sh
   test "$(git -C "$LLAMA_SRC" rev-parse HEAD)" = "$LLAMA_COMMIT" && \
     test -z "$(git -C "$LLAMA_SRC" status --porcelain)" && \
     test ! -e "$LLAMA_BUILD"
   ```

   Only after the check succeeds:

   ```sh
   git -C "$LLAMA_SRC" rev-parse HEAD > "$LAB_DIR/raw/source-commit.txt"
   cmake --version > "$LAB_DIR/raw/cmake-version.txt"
   xcrun clang --version > "$LAB_DIR/raw/clang-version.txt"
   cmake -S "$LLAMA_SRC" -B "$LLAMA_BUILD" -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_OSX_ARCHITECTURES=arm64 -DGGML_METAL=ON \
     > "$LAB_DIR/raw/configure.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/configure-exit.txt"
   ```

   Build after exit 0; on error, record a blocker:

   ```sh
   cmake --build "$LLAMA_BUILD" --config Release -j 8 \
     --target llama-bench llama-server > "$LAB_DIR/raw/build.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/build-exit.txt"
   export LLAMA_BIN="$LLAMA_BUILD/bin"
   cp "$LLAMA_BUILD/CMakeCache.txt" "$LAB_DIR/raw/CMakeCache.txt"
   file "$LLAMA_BIN/llama-bench" > "$LAB_DIR/raw/binary-arch.txt"
   shasum -a 256 "$LLAMA_BIN/llama-bench" "$LLAMA_BIN/llama-server" \
     > "$LAB_DIR/raw/binaries.sha256"
   "$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
   "$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   ```

   Also pin linked runtime libraries/build flags. A binary hash alone does not describe dynamic dependencies.

2. Check flags against the saved help; collect the LAB28 initial memory snapshot and start a memory time series. Run a small smoke test/warmup:

   ```sh
   "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -p 512 -n 128 -r 1 -o json > "$LAB_DIR/raw/warmup.json" \
     2> "$LAB_DIR/raw/warmup-device.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/warmup-exit.txt"
   ```

   Require exit 0 and logs showing the Metal device, actual offloaded layers and allocations. CPU housekeeping operations are normal; claim full GPU offload only with log evidence. If the model does not support `-ngl 999` or the log does not confirm GPU use, report a blocker or a separately described partial-offload variant.

3. After a successful smoke test, run once each for `REPEAT=1`, `2`, `3`, checking every result before continuing. Save the three raw repetitions separately; stdout contains PP/TG, stderr contains macOS time and backend output:

   ```sh
   export REPEAT=1
   /usr/bin/time -l "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -p 512 -n 128 -r 1 -o json > "$LAB_DIR/raw/r$REPEAT-bench.json" \
     2> "$LAB_DIR/raw/r$REPEAT-process.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/r$REPEAT-exit.txt"
   ```

   Each CLI invocation starts a new process; describe the built-in benchmark warmup and file cache. `/usr/bin/time` measures the entire process; PP/TG in JSON measure individual benchmark kernels. Do not present wall time as decode throughput or warm HTTP request time.

4. Save `raw/runtime-manifest.json`: SHA, macOS/SDK/compiler, binary/library hashes, build flags, exact commands, model manifest, threads/batch/defaults, observed GPU/offload. Link the hardware profile and memory snapshots. If a measured working GPU budget is available, recalculate with `local:plan --gpu-budget-gib`; this is operator input, not automatic calibration.

5. Compare repetitions: median and min/max PP/TG, process RSS, runtime allocations, swap delta and errors. Proceed to LAB32 for HTTP/context tests; CPU-versus-Metal or different thread counts require separate additional series.

## Results tables

| Repetition | PP tokens/s | TG tokens/s | Wall s | Max RSS bytes | Runtime allocations | Swap delta | Exit / evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

## Deliverables

Report/TSV/manifest, source/build/toolchain evidence, runtime manifest, hashes and the full warmup/three-repetition set with memory and exit codes. Weight and build archives are not required.

## Completion criteria

- [ ] Pin and native arm64 build confirmed.
- [ ] Actual Metal/offload established from logs.
- [ ] Separate warmup and three repetitions, or saved failures/blockers.
- [ ] PP, TG, process wall time and memory kept distinct.
- [ ] Submission checked against the shared protocol.

## Review questions

1. Why does a Metal build not prove GPU execution of a request?
2. How do PP, TG and process wall time differ?
3. Why is the same commit required for a Ryzen comparison?
4. How does shared memory affect RSS interpretation?

## Sources

- [llama.cpp: Metal build](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- [llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench).
- [LAB28](LAB28-apple-hardware.md), [LAB29](LAB29-apple-artifacts.md), pinned help and source commit.
