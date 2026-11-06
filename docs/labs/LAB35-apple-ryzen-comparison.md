# LAB35. Apple versus Ryzen on identical tasks

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Comparative agent campaign / `implementation-required` |
| Time | 4–8 operator hours plus execution and independent evaluation |
| Prerequisites | LAB04, LAB08, LAB09, LAB32, LAB34; manifests for both machines |
| Minimum | One shared GGUF, one task/agent/harness, three attempts per machine and a comparable inference series |
| Limitation | The agent phase awaits an accepted LAB08 local provider bridge; an HTTP server alone does not unblock it |

## Objective

Compare the usefulness of two machines on shared inputs, separating inference performance from successful completion of an agent task.

## Hypothesis

Latency/throughput differences between two deployments produce measurable changes in completion time or success rate under the same contract and budget. Higher tokens/s alone does not establish better agent quality.

## Preparation

```sh
npm run lab:new -- --lab LAB35 --session apple-vs-ryzen
export LAB_DIR='experiments/local-models/measurements/LAB35-apple-vs-ryzen'
npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --engine llama-cpp-metal --format json \
  > "$LAB_DIR/raw/apple-plan.json"
npm run --silent local:plan -- --hardware ryzen-ai-max-395-128gb-linux --engine llama-cpp-vulkan --format json \
  > "$LAB_DIR/raw/ryzen-plan.json"
npm run check
```

These are plans only. Actual manifests and passed LAB08 checks are required; `run --provider local` is not currently supported. Do not run a cloud model disguised as local. Without a bridge, mark the agent phase `blocked`; infrastructure measurements may be performed in a separate session.

## Procedure

1. Before execution, create a conditions matrix in `raw/protocol.md`. Primary pair: one GGUF with identical hashes, the same llama.cpp commit, tokenizer/template, prompt/output budgets, sampling/reasoning, KV/state, offload policy, threads and server slots. Apple backend: Metal; Ryzen: Vulkan or ROCm selected in advance according to LAB04. If both Ryzen backends are available, these are two separate comparisons, not a winner selected after viewing results.

2. Check comparability: OS/ISA/GPU differ by definition. Save hardware profiles, compiler/build flags, power, background load and network placement. The primary baseline is concurrency 1; cache policy is fixed. If runtime flags or weights differ, record the difference and interpret the result as a whole-deployment comparison. For MLX, add a separate supplementary pair with its own quant/artifacts; do not merge it with the controlled GGUF comparison.

3. Repeat one public LAB32 HTTP prompt and the LAB34 load fixture on both machines: separate warmup and three repetitions at the same admitted context size. Measure TTFT only with a streaming client; the non-streaming driver yields total latency. Alternate machines according to the protocol; report cold starts and prefix cache separately. Copy raw archives into the new report with source session IDs and hashes; do not alter existing results.

4. After LAB08 acceptance, choose one supported harness, agent specification and existing episode. For the first experiment, use T002/a2-janitor according to LAB08/09. Pin **one** harness version/image, permission/sandbox/network policy and input snapshot. Turn/USD limits come from the sealed task contract; do not add new defaults. If one image cannot run identically on both architectures, use the same agent host for two inference endpoints through the accepted bridge, or explicitly document different harness deployments; do not conceal emulation/different images.

5. Follow the LAB09 lifecycle: new-run → prepare → execution → independent evaluation. Take the exact local-provider command from the implemented and tested LAB08 interface, not assumed flags. Run one separate pilot, then three preregistered attempts for each primary pair. Model warmup is separate from recorded agent attempts. Do not read or modify `tasks/*/check/`; do not change task contracts. Preserve all started failures in real run records; absent usage/cost is `null` with a reason, not 0.

6. Before comparing, ensure metadata and compare already distinguish hardware/deployment fingerprints as LAB08 requires. Without this support, the final agent comparison is blocked. For the selected real IDs:

   ```sh
   export RUN_IDS='<actual comma-separated run IDs>'
   npm run --silent compare -- --runs "$RUN_IDS" > "$LAB_DIR/raw/agent-comparison.json"
   ```

   This does not create results. Link IDs in the manifest and planned attempts. Show pass/total, every wall time, tokens/turns/cost completeness and errors. Started failures enter the denominator; list not-run separately. Three attempts give an initial variability estimate, not statistical proof of superiority.

7. Form a practical conclusion using the preselected rule: whether each machine suits this task and these conditions, where quality/latency/memory limits lie, and what further data is needed. Compare energy efficiency only with identical energy-measurement methods; model API price=0 does not mean the computer and electricity cost nothing.

## Results tables

| Condition | Hardware / OS | Engine SHA / backend | Weights / template hash | Context / cache / slots | Differences / evidence |
| --- | --- | --- | --- | --- | --- |
| Apple GGUF | | | | | |
| Ryzen GGUF | | | | | |
| Supplementary MLX | | | | | |

| Condition / repetition | Run ID | Verdict | Wall s | Tokens / turns | Cost USD / completeness | Error / not-run |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

| Pair | Inference latency / throughput | Pass / total | Wall-time variability | Supported conclusions / unknowns |
| --- | --- | --- | --- | --- |
| | | | | |

## Deliverables

Report/TSV/manifest, comparison protocol, both hardware/artifact/runtime identities, HTTP raw evidence, run IDs and independent verdicts, compare JSON or a specific integration blocker. An educational manifest does not replace run.json.

## Completion criteria

- [ ] Controlled GGUF and supplementary MLX deployment kept distinct.
- [ ] Bridge/metadata/isolation accepted before agent runs.
- [ ] Three recorded attempts per machine, including failures, or blocked with a reason.
- [ ] Shared contract, evaluator and run records preserved without changing hidden checks.
- [ ] Conclusion tied to task, conditions and evidence, not just tokens/s.
- [ ] `lab:check --mode submission` and `npm run check` completed.

## Review questions

1. Why does comparing Metal and ROCm also include OS and hardware effects?
2. When can one discuss the engine's isolated effect, and when only a deployment?
3. How does an identical task budget affect speed and quality comparisons?
4. Why must started failures remain in pass/total?
5. What additional measurements are needed to calculate cost per successful task?

## Sources

- [Experiment protocol](../method.md), [LAB08](LAB08-local-bridge.md), [LAB09](LAB09-agent-campaign.md).
- [LAB04](LAB04-backends.md), [LAB32](LAB32-apple-context-tools.md), [LAB34](LAB34-apple-load.md).
- [Run record schema](../../results/schema.json), [comparison](../../scripts/compare.mjs).
