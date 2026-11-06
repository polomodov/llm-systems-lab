# Overnight campaign repair plan (overnight-models-20261008)

Status: **completed** (branch `overnight-models-fixes`, driver
`experiments/local-models/campaign/overnight-fix.py`). Source: overnight run
`overnight-20261008-154949` (branch `overnight-models-20261008`, worktree
`/tmp/opencode/overnight-wt-20261008-154949`, driver `/tmp/opencode/overnight.py`).

Repair results are in section “8. Repair progress” at the end of this document.

## 1. Diagnosis

| # | Symptom | Cause | Evidence |
| --- | --- | --- | --- |
| 1 | LAB05 scored 4/8 for 4 models: `chat`/`tool` pass, `chat-stream`/`tool-stream` fail | Driver bug: `f.replace(".json","-stream-request.json")` creates `chat-request-stream-request.json` instead of `chat-stream-request.json`; the probe cannot find its request file | `raw/chat-request-stream-request.json` instead of `raw/chat-stream-request.json` |
| 2 | LAB03 `glm-47-flash`, `qwen3-coder-next` failed with `KeyError: 'bytes'` | The driver reads `files[0]["bytes"]`, but `fetch_artifact.py` writes `{"status":"no-artifact"}` without `bytes` for a missing file | `LAB03-*-overnight/raw/verification.json` |
| 3 | Downloads of `glm-47-flash` (14.9/31.8 GiB) and `qwen3-coder-next` (17.1/56.7 GiB) broke | `fetch_artifact.py` cannot resume; an interruption leaves `.part`, and another run does not continue it | `…/GLM-4.7-Flash-GGUF/**/*.part`, `…/Qwen3-Coder-Next-GGUF/**/*.part` |
| 4 | `gemma4-31b-it`: LAB04/05 cannot load the model | llama.cpp b8407 does not recognize the architecture: `unknown model architecture: 'gemma4'` | `LAB04-gemma4-31b-it-overnight/raw/vulkan-offload-proof.log` |
| 5 | Driver outside the repository, not versioned | Located at `/tmp/opencode/overnight.py` | — |

## 2. Already complete (do not change)

- LAB03 verified: `gpt-oss-20b`, `qwen36-27b`, `gemma4-31b-it`, `qwen3-coder-30b-a3b`, `qwen35-35b-a3b`.
- LAB04 completed: `gpt-oss-20b`, `qwen36-27b`, `qwen3-coder-30b-a3b`, `qwen35-35b-a3b` (offload proof + 3 paired repeats).
- LAB05 memory-fill benchmarks at 8/16/32K passed (exit 0) for the same 4 models; non-streaming `chat`/`tool` returned `LAB_READY`/`LAB_VALUE_42`.

## 3. Planned fixes (not yet implemented)

1. **LAB05 stream request.** In `overnight.py` (lab05), generate
   `chat-stream-request.json` / `tool-stream-request.json`:
   ```python
   for kind in ("chat", "tool"):
       v = json.loads((raw / f"{kind}-request.json").read_text()); v["stream"] = True
       (raw / f"{kind}-stream-request.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
   ```
2. **LAB03 no-artifact.** Build a `measurements` row only if `"bytes" in f0`;
   otherwise write a `status=no-artifact` row with a reason. Do not crash.
3. **Resilient download.** For `glm-47-flash` and `qwen3-coder-next`, delete `.part` and
   download again, or use resumable downloading (`curl -C -` into the target directory,
   then `fetch_artifact.py` without `--download`). Compare `bytes`/SHA against the catalog.
4. **gemma4.** Either build a fresh llama.cpp (b8407 does not recognize `gemma4`) in a separate
   pinned bundle, or record `fail` with “unsupported architecture” in LAB04/05
   and do not rerun.
5. **Version the driver.** Move `/tmp/opencode/overnight.py` into
   `experiments/local-models/campaign/overnight.py` with `overnight-models.json`.

## 4. Restart order

1. Fix the driver (items 3.1, 3.2) and move it into the repository (item 3.5).
2. **LAB05 streaming** for `gpt-oss-20b`, `qwen36-27b`, `qwen3-coder-30b-a3b`,
   `qwen35-35b-a3b`: regenerate stream requests and complete 4 cases × 3 contexts
   (expected 8/8; benchmarks already recorded).
3. **Finish downloading** `glm-47-flash`, `qwen3-coder-next` → LAB03 → LAB04 → LAB05.
4. **gemma4**: decide on the engine (item 3.4).
5. Run `npm run lab:check --mode submission` for every session; create a PR.

## 5. Acceptance criteria

- LAB03: all 7 models have `verification.json` = `verified`.
- LAB04: all compatible models offload 100% of layers to GPU and have 3 paired repeats.
- LAB05: 8/8 HTTP cases (chat/tool × stream) at each of 8K/16K/32K; long/overflow/cancel.
- `lab:check --mode submission` reports no errors for every session.
- Incompatible models (gemma4) receive explicit `fail`/`blocked` with a reason, not omission.

## 6. Branches and PRs

- Continue on `overnight-models-20261008` (already pushed) or a new
  `overnight-models-fixes`.
- Result: either one campaign PR or one PR per model (3 sessions per model).
- Do not merge until `lab:check` passes.

## 7. Risks

- `glm-47-flash` (MLA) and `gemma4` require a runtime cache/architecture report: a separate check.
- About 57 GiB remain to download for `qwen3-coder-next`; a slow connection costs time.
- `--jinja` without model-specific sampling/reasoning is suitable for smoke tests; quality is checked manually during the day.

## 8. Repair progress

The repository’s `overnight-fix.py` driver already implements fixes 3.1 (stream requests
`<kind>-stream-request.json`) and 3.2 (LAB03 does not crash on `no-artifact`); resilient
resumption through `curl -C -` and `lab05` / `full` / `gemma4` modes were added. Sessions repeat under new
session IDs `<model>-overnight2`; earlier sessions remain an honest failure record.

| Step | Result |
| --- | --- |
| LAB05 streaming, 4 models | gpt-oss-20b, qwen3-coder-30b-a3b, qwen35-35b-a3b: 8/8/8; qwen36-27b: 8/7/8 |
| glm-47-flash | download completed, LAB03 verified, LAB04 completed, LAB05 8/7/8 |
| qwen3-coder-next | download completed (4 shards), LAB03 verified, LAB04 completed, LAB05 8/8/8 |
| gemma4-31b-it | b8407 does not recognize `gemma4`; run on llama.cpp **b10000** (official ggml-org build, ROCm 7.2 + Vulkan; HIP runtime: ROCm 7.2.1 libraries from the AMD b8407 bundle). LAB04 completed (offload 61/0 layers, Vulkan/HIP), LAB05 8/8/8 |

The only non-8/8 result is `ctx16384-tool-stream-r2`: qwen36-27b exhausted its 2048-token budget
on reasoning (`finish_reason=length`); glm-47-flash returned `alpha`
without calling a tool (`finish_reason=stop`). This is model behavior with default sampling,
not a driver bug; recorded as `blocked` with a reason.

**gemma4 condition:** changing the engine version (b8407 → b10000) creates a new condition group, comparable
only with itself; other models still use b8407.
