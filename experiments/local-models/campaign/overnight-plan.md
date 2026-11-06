# Overnight campaign: LAB03 + LAB04 + LAB05 for other models

Window: about 12–14 hours (overnight run). Machine: Ryzen AI Max+ 395 / gfx1151 / 124 GiB.
Launch: `overnight.py` (branch `overnight-models-20261008`, worktree `/tmp/opencode/overnight-wt-20261008-154949`).

## Workflow rule

Each model receives **three preregistered sessions** (LAB03 → LAB04 → LAB05):
commit the protocol and plan BEFORE execution in a separate commit, then collect measurements, then
commit the results. A failure in one lab does not stop the campaign: record status in
`overnight-<run>-status.json` and the reason in the corresponding session report.

## Queue (smallest first to complete as much as possible)

| # | Model | Quant | Weights | LAB03 | LAB04 | LAB05 |
| --- | --- | --- | ---: | --- | --- | --- |
| 1 | gpt-oss-20b | MXFP4 | 11.3 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 2 | qwen36-27b | Q5_K_M | 18.2 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 3 | gemma4-31b-it | Q5_K_M | 20.2 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 4 | qwen3-coder-30b-a3b | Q5_K_M | 20.3 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 5 | qwen35-35b-a3b | Q5_K_M | 24.5 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 6 | glm-47-flash | Q8_0 | 29.7 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 7 | qwen3-coder-next (4 shard) | Q5_K_M | 52.9 GiB | verify | Vulkan/HIP | 8/16/32K+tools |

Total downloads: about 177 GiB (disk: about 1.5 TB free). Conditional giants
(qwen35-122b-a10b, glm-45-air) and LAB06 are outside this night’s scope.

## Time estimate

- Downloads: at about 20 MB/s, approximately 2.5 h for 177 GiB.
- LAB03: about 1 min after download.
- LAB04: offload proof + warmup + 3×2 benchmarks, approximately 10–20 min per model.
- LAB05: 3 contexts × (memory-fill benchmark + server + 4×2 HTTP cases), approximately 40–90 min.
- Total: approximately 9–13 h; if behind schedule, models 6–7 may not finish, which is reflected in status.

## LAB06

Excluded: requires a native BF16 checkpoint and vLLM/SGLang support for the specific architecture.
A separate campaign follows compatibility verification.

## Limitations

- The automated campaign uses default sampling/`--jinja`; model-specific
  reasoning and tool parsing are configured manually in daytime sessions. A poor parser
  is not a verdict on the model.
- GLM-4.7-Flash (MLA) and gemma4 (sliding/global) require a separate runtime cache report.
- One backend for LAB05 (HIP), as in previous sessions.

## Monitoring

```sh
tail -f experiments/local-models/campaign/overnight-<run>.log
cat experiments/local-models/campaign/overnight-<run>-status.json
git -C /tmp/opencode/overnight-wt-<run> log --oneline
du -sh "$HOME/local-model-lab-artifacts"
```

## Morning

Branch `overnight-models-20261008` is pushed automatically; no PR is created.
After reviewing reports and `lab:check`, create one PR for the campaign or one per model.
