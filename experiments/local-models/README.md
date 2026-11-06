# Local models: Ryzen/Linux and Apple/macOS

Apple M5 Max / 128 GB / macOS has a [separate LAB28–35 track and profiles](apple/README.md). Select `--hardware apple-m5-max-128gb-macos` for `local:plan` and `local:engines`. Without the flag, the original Ryzen files below are used; there is no automatic machine detection.

This is a research campaign, not a tenth harness. One local inference server will serve several existing harnesses; backend, model, and harness are recorded separately. Catalogs specify planned conditions; actual Ryzen LAB02–06/26 measurements and the local LAB08 pilot are retained in the [measurement archive](measurements/README.md) at a pinned commit, outside the working tree. Apple hardware results are listed in the [machine index](apple/README.md). The [shared status table](../../docs/labs/README.md#execution-status-as-of-2026-10-22) distinguishes measurements, limited qualifications, and acceptance. Hardware probes do not replace agent run records.

Use the [lab course](../../docs/labs/README.md) for step-by-step execution. `npm run lab:new -- --lab LAB02 --session first-pass` creates an empty report, manifest, and measurement table in `measurements/LAB02-first-pass/`. A course manifest does not replace `results/runs/<run-id>/run.json`; actual agent attempts are recorded separately.

In the extended course, LAB25 compares quality across quantizations, and LAB26 measures concurrent load. Shared LAB20–27 also save reports in `measurements/`. [Exercises without an API](../../docs/labs/practice.md) live separately in `practice/`; their synthetic traces do not establish hardware compatibility or model quality. [lab:check](../../docs/labs/report-validation.md) checks report completeness and accounting for failed/skipped attempts.

[`runbook.md`](runbook.md) is a consolidated operator worksheet for LAB02–LAB05 during one machine session: the same commands with paths filled in. The lab guides remain normative; check source drift with `sha256sum -c experiments/local-models/runbook.sources.sha256`.

- [Testing order and selection criteria](../../docs/local-models.md).
- [Candidates, weight formats, and primary sources](../../docs/local-model-candidates.md).
- [Linux preflight and backend runbook](../../docs/local-model-runtime.md).
- [Different engines and ROCm/Vulkan](../../docs/local-inference-engines.md): 12 profiles in `engines.json`; kernels and serving layers are tracked separately.
- `models.json`: dated candidate catalog; sizes are estimates or file metadata, not RAM measurements.
- `hardware.json`: hardware hypothesis and conservative memory reserves.

From the repository root:

```bash
npm run local:plan
npm run local:plan -- --context 32768
npm run local:plan -- --format json
npm run local:engines
npm run local:plan -- --engine llama-cpp-rocm
npm run local:plan -- --engine vllm-rocm --model gpt-oss-20b
npm run local:plan -- --engine all --format json
```

After measuring available memory, recalculate the plan, for example:

```bash
npm run local:plan -- --memory-gib 125 --gpu-budget-gib 90
```

The numbers in the last command are examples, not the owner’s machine specifications. `--memory-gib` means measured total usable RAM; the planner subtracts the OS reserve separately. `--gpu-budget-gib` is a safe GPU-allocation budget established after preflight. These values neither modify the file nor configure the OS.

`candidate` means the model passes a rough reserve calculation; `conditional` indicates an additional catalog caveat; `over-budget` means the selected budget is exceeded. None of these statuses means the model has already fit on the hardware. Actual KV/state, staging buffers, kernel workspace, and single-allocation limits require execution to determine.

With `--engine`, additional statuses appear: `artifact-required` (an engine-specific artifact is needed; GGUF sizes/quantization are not used) and `engine-memory-required` (GGUF weights are known, but serving-runtime memory is not). `hardware_support` describes documented support separately from `fit_verified=false`. Without `--engine`, the original GGUF calculation remains; it is not a universal estimate for every engine.

The command does not download weights, contact a server, create run records, or schedule background work. Pi/T002 already has a separate [local provider](../pi/README.md) with a sealed deployment and native llama.cpp ROCm/Linux or Metal/macOS. Other local adapters and tasks need implementation/acceptance; LAB08 records the status of each specific admission.
