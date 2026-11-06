# LAB25. Quantization: agent task quality and resources

## Profile

| Field | Value |
| --- | --- |
| Type | Paired comparison of artifacts from one source model |
| Time | 3–5 hours of operator time plus download, six attempts, and independent evaluation |
| Prerequisites | Accepted local LAB08 and completed local LAB09; LAB02–05 results |
| Readiness | `target-machine`; the agent component is blocked until the LAB08 bridge is implemented |
| Minimum scope | Two quantization variants × three new T002 attempts in one harness; resource probes separately |
| Extension | A third quant; then a second task on frozen inputs; separately, repetition on another model |

## Objective

Determine what memory reduction is acceptable for the selected agent task on a Ryzen AI Max+ 395 with 128 GB of memory under Linux. Relate weight size, peak memory, and speed to independent solution quality and correct tool use.

## Hypothesis

The selected smaller quant uses less memory and preserves acceptable T002 success with the same source checkpoint, engine, context, and harness. Record the acceptance criterion before the series: for example, no pair lost on verdict and no new protocol violations. This is a decision rule for a small training series, not statistical proof of equivalence.

Compare two actually available artifacts of one model. The labels `Q4` and `Q8` alone do not guarantee identical tokenizers, templates, source weights, and conversion procedures. If these factors differ, the result concerns the entire deployment, not just the bit count.

## Preparation

```bash
npm run lab:new -- --lab LAB25 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB25-my-session'
npm run check
```

Choose a model that has already passed local LAB09. The small control model from the [catalog](../../experiments/local-models/models.json) may be used only if provenance and actual compatibility are confirmed for **both** quants. The catalog does not promise every quant combination. Download and verify all shards using [LAB03](LAB03-artifacts.md), without changing the published task contract.

For each artifact, save repository/revision, source model checkpoint/revision, SHA-256 and total bytes of all shards, quantization type, converter revision, and known calibration/imatrix details. Unknown provenance blocks a clean comparison. If only artifacts with different preparation are available, rename the hypothesis in advance as a comparison of two deployments and list the confounded factors.

The current cloud runner does not provide a ready-to-use `--provider local`. After LAB08, use its **actually implemented and verified interface**, which has passed the LAB09 pilot. Do not substitute LAN access for the bridge or add unsupported fields to `run.json`. Until the integration is accepted, preparation and resource probes may be completed, but the report remains `blocked` for the agent minimum.

## Procedure

1. **Freeze the single factor.** Assign neutral groups A/B in the report and complete the conditions table before running: source checkpoint, engine commit/binary, Vulkan or HIP/ROCm backend, driver, GPU offload, KV dtype, context/output, batch/ubatch, template/tokenizer, sampling/reasoning, harness image, and bridge identity. Use one backend and one harness for both variants. Do not reduce context or GPU layer count only for the larger quant to pass acceptance: that is a new configuration with multiple interventions.

2. **Verify artifacts and resource acceptance.** Specify absolute paths to the first shards; each `weights.sha256` must verify the full LAB03 set. Run the check separately in each set's directory:

   ```bash
   (
     set -eu
     cd '<absolute directory for artifact A>'
     sha256sum --check weights.sha256
   )
   ```

   Repeat for B. Save stdout/exit code in new report files. Record available RAM, GPU budget, and OS reserve using LAB02. For both variants, run a short chat and native tool round-trip from LAB05 through the accepted bridge. OOM or missing tool protocol at this stage is `preflight-incompatible`, not a loss in a T002 attempt that has not started.

3. **Measure resources separately from the agent.** For the pinned `llama-bench` from LAB04, use identical parameters and three repetitions of each quant. Example of one generation probe after warmup; `BENCH` is the already verified binary, not a new build:

   ```bash
   BENCH='<absolute path from LAB04>/bin/llama-bench'
   WEIGHTS='<absolute path to GGUF or first shard A>'
   (
     set -eu
     set -o noclobber
     test ! -e "$LAB_DIR/raw/a-r1-process.txt"
     /usr/bin/time -v -o "$LAB_DIR/raw/a-r1-process.txt" \
       "$BENCH" -m "$WEIGHTS" -ngl 999 -t 8 -b 512 -ub 256 \
       -ctk f16 -ctv f16 -fa on -p 0 -n 128 -d 4096 -r 1 -o json \
       > "$LAB_DIR/raw/a-r1-bench.json" 2> "$LAB_DIR/raw/a-r1-bench.log"
   )
   ```

   Filenames for the other repetitions must be new; `/usr/bin/time -o` is not itself protected by shell `noclobber`, so check that the entire prefix is absent before each probe. If the binary version rejects these parameters, stop and agree on an identical configuration using the saved `--help` before starting a new series. LAB04 has a separate pp2048 mode. It may be added identically for A/B. In the table, do not present process duration as loading time or call these probes agent runs.

4. **Preassign three pairs of agent attempts.** Order: A→B, B→A, A→B. Each attempt receives a clean workspace and new ID. All six use T002, one seed commit, `baseline`, identical timeout/native limits, and budget policy. Run one model server at a time; readiness and warmup finish before agent execution. Account for server restart and weight loading separately. After switching quants, verify the deployment fingerprint and the model alias's link to the weight SHA; an identical alias does not mean an identical model.

5. **Execute attempts through the accepted local runner.** Copy the exact `new-run`, preparation, and execution commands from completed LAB09/LAB08 implementation into `report.md`. Save native launch arguments and the manifest of each deployment. Do not change runtime, prompt, template, reasoning, or driver between pairs. A technical failure after agent execution begins remains that attempt's `aborted` result. A configuration fix ends the old series; a new run does not erase the failure.

6. **Obtain independent evaluations.** The coordinator retains the A/B mapping and gives anonymized results to the evaluator where possible. For every `awaiting_review`, use the existing lifecycle:

   ```bash
   RUN_ID='<actual ID of one attempt>'
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The external evaluator runs the check and completes the template using the [common workflow](harness-workflow.md), retaining hashes. Only afterward:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   Do not read `tasks/*/check/` while solving the task. Agent self-evaluation, a short chat, and a successful API response do not replace a verdict.

7. **Compare quality, protocol, and costs.** Extract malformed tool calls, unknown tools, argument errors, repeated corrections, and final action from the host trace. Define categories before reading A/B; one tool error does not equal an overall task fail. Show all three pair outcomes and known tokens/time. If the bridge supports grouping identity as specified in LAB08, export a comparison:

   ```bash
   RUN_IDS='<A1>,<B1>,<B2>,<A2>,<A3>,<B3>'
   (
     set -o noclobber
     npm run --silent compare -- --runs "$RUN_IDS" > "$LAB_DIR/raw/compare.json"
   )
   ```

   Different quants must remain different groups. Check the other conditions manually: the comparison does not calculate a causal effect. Peak system RAM and GPU allocations may overlap on UMA; do not add them. Do not replace unknown usage or energy consumption with zeros.

8. **Make a limited decision.** Map the “verdicts / time / memory” tradeoff. The smaller quant may be preferred for this task if it meets the predefined criterion and delivers measured savings. Explain differences through specific traces and artifacts; three pairs do not yield a general quantization ranking. To extend, first declare a third quant with the same conditions and three new attempts. Run a second task as a new series: T001 requires one frozen source archive; T003 remains separate harness diagnostics.

## Results tables

| Group | Source checkpoint/revision | Artifact revision/SHA manifest | Quant / converter / calibration | Engine/template/context fingerprint | Acceptance / evidence |
| --- | --- | --- | --- | --- | --- |
| A | | | | | |
| B | | | | | |

| Group / repetition | Weights, bytes | Peak total RAM | GPU allocation | Swap delta | Bench tokens/s / mode | Source |
| --- | --- | --- | --- | --- | --- | --- |
| A / 1 | | | | | | |
| B / 1 | | | | | | |

| Pair / order | Run IDs A/B | Verdict A/B | Tool errors A/B | Wall-clock A/B | Tokens A/B | Independent judge / limitations |
| --- | --- | --- | --- | --- | --- | --- |
| 1 / A→B | | | | | | |
| 2 / B→A | | | | | | |
| 3 / A→B | | | | | | |

| Predefined criterion | Observation | Decision for this task | What needs repetition |
| --- | --- | --- | --- |
| | | | |

## Deliverables

A report and manifest with six real run IDs, the original pair plan, weight/deployment manifests, raw resource probes and telemetry, traces and independent evaluations, a protocol-error table, and a conclusion. Complete the [completeness check](report-validation.md). Resource probes remain in `experiments/local-models/measurements/`; real agent attempts belong in `results/runs/`. Do not include keys, `.env`, or the large weight files themselves in the submission.

## Completion criteria

- [ ] Both artifacts' provenance is confirmed; material differences are explicitly listed.
- [ ] LAB08 and local LAB09 are accepted; there is no unsupported cloud fallback.
- [ ] Resource probes and six preassigned attempts are retained, including every error.
- [ ] Independently judged verdicts exist for attempts that completed execution; `aborted` attempts are not hidden.
- [ ] Paired conditions are checked; measured metrics are distinguished from missing ones.
- [ ] The conclusion addresses the predefined criterion and is limited to this model, task, and engine.
- [ ] `npm run check` passes, and report completeness is checked.

Without a bridge, a suitable second artifact, or hardware acceptance, submit `blocked` with evidence of completed preparation. This is not a completed agent series.

## Review questions

1. Why does an identical model name not prove a shared source checkpoint?
2. When does a Q4/Q8 comparison become a comparison of two deployments?
3. Why can actual T002 time differ more than benchmark speed with an identical output cap?
4. Which protocol errors affect the task, and which does the agent correct independently?
5. Why do three identical successful outcomes not prove quality equivalence?
6. How should a variant be chosen when one is faster and the other completes the task more reliably?

## Sources

- [Experiment method](../method.md), [local models and memory](../local-models.md).
- [Artifacts and hashes](LAB03-artifacts.md), [pinned backend probes](LAB04-backends.md).
- [Local bridge and identity](LAB08-local-bridge.md), [agent series](LAB09-agent-campaign.md), [paired ablation](LAB10-ablation.md).
- Attach the model card, quantization provenance, and `--help` for the **revisions actually selected** to the report. Compatibility of arbitrary quants remains `unverified` until preflight.
