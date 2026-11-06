# LAB04. Comparing llama.cpp Vulkan and HIP/ROCm

## Profile

| Field | Value |
| --- | --- |
| Estimated time | 2–4 hours after obtaining weights and dependencies; large models may take longer |
| Prerequisites | LAB02 and LAB03 completed; target Linux; pinned GGUF and llama.cpp commit; Vulkan and HIP build dependencies installed |
| Readiness status | Commands prepared; both hardware branches require smoke tests |
| Outcome | Paired backend comparison using one model and one commit |

## Objective

Measure Vulkan and HIP/ROCm differences on Radeon 8060S while keeping weights, engine version, and parameters identical. Both branches are required; a missing branch is recorded as a blocker, not as evidence that the other is superior.

## Hypothesis

The same GGUF can run with full GPU offload in both llama.cpp builds. Under an identical workload, the backend may affect prefill/decode speed and memory; the direction and magnitude of the effect are unknown before measurement.

## Preparation

- Obtain the local GGUF, the list of all shards with SHA-256 values, and the model card from LAB03. That lab does not prepare llama.cpp sources.
- Select one specific llama.cpp commit based on support for the selected model's architecture/quant in its documentation and change history. Record the full 40-hex-character SHA and selection date in the report. A release number or the word `master` alone does not replace a SHA. For the first comparison, both builds use that same commit, while the model-specific template is pinned separately.
- Obtain the profile and permitted budgets from LAB02. Start with a small control candidate rather than a model at the limit.
- Ensure that `cmake`, a compiler, Vulkan headers/shader compiler, and the HIP SDK are already installed. Do not install them automatically after a build error.
- Run all commands from the repository root. Replace `/absolute/...` values with actual absolute paths; do not use a floating `master` as the build identifier.

## Procedure

1. Create a separate archive and specify the inputs:

   ```sh
   npm run lab:new -- --lab LAB04 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB04-my-session'
   export LAB03_DIR='experiments/local-models/measurements/LAB03-my-session'
   export LLAMA_SOURCE='/absolute/path/to/pinned/llama.cpp'
   export LLAMA_COMMIT='<replace-with-40-character-commit-sha>'
   export LOCAL_GGUF='/absolute/path/to/model.gguf'
   test "$(uname -s)" = Linux
   test -f "$LOCAL_GGUF"
   python3 - <<'PY'
   import os, re
   assert re.fullmatch(r'[0-9a-f]{40}', os.environ['LLAMA_COMMIT']), 'set full lowercase commit SHA'
   PY
   test "$(git -C "$LLAMA_SOURCE" rev-parse HEAD)" = "$LLAMA_COMMIT"
   git -C "$LLAMA_SOURCE" rev-parse HEAD > "$LAB_DIR/raw/llama-commit.txt"
   git -C "$LLAMA_SOURCE" status --porcelain > "$LAB_DIR/raw/llama-status.txt"
   cmake --version > "$LAB_DIR/raw/cmake-version.txt"
   hipconfig --full > "$LAB_DIR/raw/hipconfig.txt" 2>&1
   vulkaninfo --summary > "$LAB_DIR/raw/vulkan-summary.txt" 2>&1
   cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
   cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
   sha256sum --check "$LAB_DIR/raw/weights.sha256" \
     > "$LAB_DIR/raw/verification-before.txt"
   ```

   The commands assume an **already prepared separate checkout** at `LLAMA_SOURCE`: the selected commit must match `HEAD`, and `git status --porcelain` must be empty. If the checkout does not exist, first obtain the sources separately, for example with the commands below, then repeat the step 1 checks. For cloning, `LLAMA_SOURCE` must be a new directory, not an existing user directory:

   ```sh
   git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE"
   git -C "$LLAMA_SOURCE" checkout --detach "$LLAMA_COMMIT"
   ```

   If using local patches, save the diff and apply it identically to both builds; this is a separate variant relative to the clean pin. `weights.sha256` from LAB03 contains all shards with absolute paths; a JSON manifest is not input for `sha256sum --check`. Stop on a nonzero exit code. Hashing reads the weights and warms the filesystem cache; account for this in the cache state.

2. Build the two backends from this checkout in **different** directories. This builds software; it does not install system packages:

   ```sh
   (
   set -eu
   cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-vulkan" \
     -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release \
     > "$LAB_DIR/raw/configure-vulkan.log" 2>&1
   cmake --build "$LAB_DIR/build-vulkan" --config Release -j 8 \
     > "$LAB_DIR/raw/build-vulkan.log" 2>&1

   HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
     cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-hip" \
     -DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_BUILD_TYPE=Release \
     > "$LAB_DIR/raw/configure-hip.log" 2>&1
   cmake --build "$LAB_DIR/build-hip" --config Release -j 8 \
     > "$LAB_DIR/raw/build-hip.log" 2>&1
   )
   ```

   Check the exit code after each command before proceeding. Preserve the full error. Do not add `HSA_OVERRIDE_GFX_VERSION` or substitute another target architecture to make the baseline pass.

3. Record the resulting binaries and confirm that flags match the pinned `--help`:

   ```sh
   for backend in vulkan hip; do
     binary="$LAB_DIR/build-$backend/bin/llama-bench"
     "$binary" --help > "$LAB_DIR/raw/$backend-bench-help.txt" 2>&1
     "$binary" --list-devices > "$LAB_DIR/raw/$backend-devices.txt" 2>&1
     "$LAB_DIR/build-$backend/bin/llama-server" --version \
       > "$LAB_DIR/raw/$backend-version.txt" 2>&1
     sha256sum "$binary" "$LAB_DIR/build-$backend/bin/llama-server" \
       > "$LAB_DIR/raw/$backend-binaries.sha256"
     cp "$LAB_DIR/build-$backend/CMakeCache.txt" "$LAB_DIR/raw/$backend-CMakeCache.txt"
   done
   ```

   Check `-fa on`, `-ctk/-ctv`, `-d`, `-r`, and `-o json`. If the syntax differs, adapt the command using the selected commit's documentation and preserve it. If there are several devices, select one and record the selection flag from help. Automatic selection is allowed only after confirming Radeon 8060S in both branches.

4. Perform one warmup per branch, excluded from the final statistics. Preserve warmup logs:

   ```sh
   (
   set -eu
   for backend in vulkan hip; do
     "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
       -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
       -p 512 -n 128 -r 1 -o json \
       > "$LAB_DIR/raw/$backend-warmup.json" \
       2> "$LAB_DIR/raw/$backend-warmup.log"
   done
   )
   ```

   Find the actual GPU layer count, backend, and allocations in the logs. `-ngl 999` is a request, not proof of full offload. CPU tokenization/sampling is allowed; model weights/layers falling back to CPU constitute a separate configuration. Stop the branch on OOM, GPU reset, invalid data, or budget violation. Do not silently reduce KV precision, context, or offload.

5. Perform three paired repetitions, alternating the order `Vulkan → HIP`, `HIP → Vulkan`, `Vulkan → HIP`. For each backend, measure pp2048 and tg128 at a depth of 4096. Do not run the branches simultaneously:

   ```sh
   (
   set -eu
   test -x /usr/bin/time
   for repeat in 1 2 3; do
     if [ "$repeat" = 2 ]; then set -- hip vulkan; else set -- vulkan hip; fi
     for backend do
       prefix="$LAB_DIR/raw/$backend-r$repeat"
       free -b > "$prefix-memory-before.txt"
       cat /proc/vmstat > "$prefix-vmstat-before.txt"
       /usr/bin/time -v -o "$prefix-pp-process.txt" \
         "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
         -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
         -p 2048 -n 0 -r 1 -o json \
         > "$prefix-pp.json" 2> "$prefix-pp.log"
       /usr/bin/time -v -o "$prefix-tg-process.txt" \
         "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
         -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
         -p 0 -n 128 -d 4096 -r 1 -o json \
         > "$prefix-tg.json" 2> "$prefix-tg.log"
       cat /proc/vmstat > "$prefix-vmstat-after.txt"
       free -b > "$prefix-memory-after.txt"
     done
   done
   )
   ```

   The subshell stops on a nonzero exit code. Preserve failures; do not count partial JSON as a successful measurement. A successful exit code still requires checking offload and allocations in the logs. `/usr/bin/time` is GNU time, not the shell keyword. If it is unavailable, record a blocker for process RSS/wall metrics or prepare a measurement tool separately.

6. **Before step 5**, in a separate terminal at the repository root, set `LAB_DIR` from step 1 again and run `vmstat -w 1 > "$LAB_DIR/raw/vmstat-series.txt"`. Stop collection after the series with Ctrl-C. Use available GPU/temperature telemetry from LAB02; mark missing sensors as `null`. Do not add process RSS, GPU allocation, and page cache without analyzing UMA overlap. Use `pswpin/pswpout` before/after and the `vmstat` log to assess swapping; describe isolated noise separately from sustained swap-in/out.

7. Separate timings and cache states. Each `llama-bench` starts a new process; this does not guarantee a cold SSD/filesystem cache. Its built-in warmup is excluded from t/s, while `/usr/bin/time` includes the entire process. Record “process cold / filesystem warm or unknown” and the separately measured pp/tg phase. Do not call process wall time model-loading time. A separate cold-load series requires a newly declared scenario; the global page cache is not cleared here.

8. Transfer the three individual JSON results into `measurements.tsv`; calculate median/min/max for matching modes. For each mode, provide `median_HIP / median_Vulkan` if both branches completed under identical conditions. With different quant, FA, or offload settings, the ratio cannot be interpreted as a pure backend effect. Complete the report and manifest, then repeat the weights SHA and commit checks.

## Results tables

| Backend | Commit / binary SHA | GPU / target | Layers on GPU / total | Quant / KV / FA | Admission |
| --- | --- | --- | --- | --- | --- |
| Vulkan | | | | | |
| HIP/ROCm | | | | | |

| Backend | Repetition | pp2048, tokens/s | tg128 @ depth4096, tokens/s | Max RSS, KiB | Swap delta | Status / raw prefix |
| --- | --- | --- | --- | --- | --- | --- |
| Vulkan | 1 | | | | | |
| HIP | 1 | | | | | |
| Vulkan | 2 | | | | | |
| HIP | 2 | | | | | |
| Vulkan | 3 | | | | | |
| HIP | 3 | | | | | |

| Mode | Vulkan median [min; max] | HIP median [min; max] | HIP/Vulkan | Limits of the conclusion |
| --- | --- | --- | --- | --- |
| pp2048 | | | | |
| tg128 @ depth4096 | | | | |

## Deliverables

- `report.md`, `measurements.tsv`, and `manifest.json` with dependencies on LAB02/03.
- `raw/llama-commit.txt`, checkout status/patch, manifest, and SHA verification results for all shards.
- Configure/build logs, `*-CMakeCache.txt`, `*-binaries.sha256`, versions/help/device inventories for both branches.
- All `*-warmup.*`, `*-r[1-3]-pp.*`, `*-r[1-3]-tg.*`, process metrics, and memory/swap observations; do not remove unsuccessful attempts.
- Recorded launch arguments and power mode; a comparison table without invented zeros.

## Completion criteria

- [ ] Both branches were built from one commit and use identical weights SHA values.
- [ ] Radeon 8060S, actual offload, and identical settings are confirmed.
- [ ] Warmup and three paired repetitions are preserved, or a specific blocker is recorded.
- [ ] Cold process, filesystem cache, and the measured phase are described separately.
- [ ] Swap and budgets were checked; no concealed fallback occurred.
- [ ] The conclusion is limited to the tested model/context and is not an agent ranking.

## Review questions

1. Why does comparing different commits prevent isolating the Vulkan/HIP effect?
2. Why is tg128 with an empty context insufficient to assess an agent workload?
3. What is included in process wall time and excluded from `llama-bench` t/s?
4. How can you distinguish a successful launch from full GPU offload?
5. What must be recalculated when changing KV from f16 to q8_0?

## Sources

- [llama.cpp: Vulkan and HIP builds](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- [llama-bench: pp/tg modes, context depth, warmup, and output](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md).
- [AMD: archived llama.cpp b8407 / ROCm 7.2.1 package](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/advanced/advancedryz/linux/llm/llamacpp.html).
- [Lab course](README.md), [machine profile](LAB02-hardware.md), [engine matrix](../local-inference-engines.md).
