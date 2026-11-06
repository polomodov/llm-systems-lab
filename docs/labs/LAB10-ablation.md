# LAB10. Paired specification ablation and a ledger decision

## Profile

| Field | Value |
| --- | --- |
| Lab type | Controlled experiment: remove one prompt component and compare paired triples |
| Time | Estimate: 2–4 operator hours plus execution and independent evaluation; six runs with timeout 900 s allow up to 90 minutes of agent execution, excluding setup/review |
| Prerequisites | Completed cloud or local LAB09; verified deployment and independent evaluator |
| Readiness | `baseline` and `without-spec` variants implemented; local branch requires a ready LAB08 integration |
| Minimum scope | One harness × one model × one task × two variants × three repetitions = 6 new attempts |
| Extension | Repeat on a second task or second harness after completing the first series |

## Objective

Measure the contribution of the harness-independent agent specification text in the prompt and make an evidence-limited decision about that component. Keep the contract, infrastructure boundaries, and all other conditions unchanged.

## Hypothesis

Adding the specification to the contract improves outcomes on the selected task with a fixed model and harness. The intervention is: the `baseline` prompt contains spec + task, while `without-spec` contains the task without the added spec block. Improvement must appear in preselected paired attempts, not in successful examples selected after execution.

No difference in three pairs means no effect was detected in this small series, not proof that the specification is unnecessary for every task. Three failures in both variants may indicate an overly difficult task or a protocol problem.

## Preparation

```bash
npm run lab:new -- --lab LAB10 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB10-my-session'
npm run check
```

Choose one completed LAB09 configuration. Pin model/deployment identity, provider, harness version and image ID, context/output, sampling/reasoning, timeout, budget policy, seed commit or source archive, and judging method. T002 is recommended for the first experiment because its initial files are reproducible. Fill in three pairs and variant order before execution.

The cloud route uses current commands without LAB08 or Ryzen. Obtain build commands, smoke tests, and details of the selected harness from its [individual LAB11–19](README.md); obtain the evaluation procedure from the [shared workflow](harness-workflow.md). The main example below uses Pi; for another harness, replace harness/provider/model/image and proxy image with its actual conditions. Managed Amp permits ablation at one mode, but that additional series does not assert an unchanged underlying model and does not replace an exact-model control.

## Procedure

1. **Define the sole intervention.** Read the `prepareRun` implementation and confirm that `without-spec` removes only the added specification text from `prompt.txt`. `inputs/spec.md` remains part of the evidence snapshot; the task contract, Docker wall, gateway, timeout, and external evaluation remain. Do not remove files from `agents/`, edit `tasks/*/task.md`, or read hidden checks. This command currently implements no other ablations.

2. **Assign paired order and primary metrics.** Minimum schedule: pair 1 `baseline → without-spec`, pair 2 `without-spec → baseline`, pair 3 `baseline → without-spec`. Continue balancing the order if extending. Each run gets a clean workspace and a new ID. The primary metric is the independent verdict; secondary metrics are pass@3, pass^3, and time. Specify handling of aborted runs and missing metrics in advance. Use an identical seed within a pair only if the backend actually supports it; do not attribute determinism to a cloud API.

3. **Prepare the first baseline.** The example uses the **existing cloud CLI**; fill in values from the selected series. For local, use the actually accepted LAB08 interface and the same recorded conditions, without inventing flags.

   ```bash
   HARNESS_ID='pi'
   PROVIDER_ID='anthropic'
   MODEL_ID='<exact ID from the selected series>'
   IMAGE_REF='<same image ID as in the selected series>'
   PROXY_IMAGE_REF='<same proxy image ID as in the selected series>'
   npm run new-run -- --harness "$HARNESS_ID" --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   BASELINE_RUN_ID='<new ID returned by new-run>'
   npm run prepare-run -- --run "$BASELINE_RUN_ID" --variant baseline --provider "$PROVIDER_ID"
   ```

4. **Prepare the paired without-spec as a new record.** Do not reuse the baseline ID or edit its `inputs/control/prompt.txt`:

   ```bash
   npm run new-run -- --harness "$HARNESS_ID" --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   ABLATION_RUN_ID='<another new ID returned by new-run>'
   npm run prepare-run -- --run "$ABLATION_RUN_ID" --variant without-spec --provider "$PROVIDER_ID"
   ```

   Check both `inputs/manifest.json` files: identical task, provider, seed commit, and initial files outside the administrative `.git`; `variant` and the generated prompt differ. Full manifest/prompt hashes need not match: they reflect the intervention and different run IDs. Do not remove that difference from evidence to make hashes match.

5. **Execute variants in the assigned order.** Example command for each selected ID:

   ```bash
   RUN_ID="$BASELINE_RUN_ID"
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   ```

   Before the second execution, assign `RUN_ID="$ABLATION_RUN_ID"` and repeat the same command. For pairs 2 and 3, create four more new records using steps 3–4 and execute them according to plan. Do not fix the adapter between variants in one series; a necessary fix ends the current configuration and requires a new series. Do not change budget policy for one variant. Preserve native-limit parameters and their limitations from LAB09.

6. **Obtain independent evaluations without revealing the variant.** Where possible, show the judge results under neutral labels; keep the run-ID mapping with the coordinator. For `awaiting_review`, create a template, have an external evaluator complete it, and apply it:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   Between commands, the evaluator must fill in result/evaluator/check_output while preserving artifact/workspace hashes. T002 uses a hidden check outside the agent container. `aborted` remains an execution failure and does not go through judge; `awaiting_review` without a judge receives no invented verdict. Add evaluation and raw-trace references to the pairs table.

7. **Account for other tasks when extending.** For T001, both prepare commands receive identical `--as-of` and `--source-archive` from LAB09. Live discovery is outside this ablation. For T003, the same harness yields an identical audited source set, but `without-spec` does not remove naturally present specification/configuration files from the workspace. Only the additional prompt block is tested here; this is not an “agent cannot see the specification anywhere” experiment. T003 does not provide identical inputs across different harnesses.

8. **Build a report for six actual IDs.** Fill two strings with exactly three IDs for each variant, without spaces after commas:

   ```bash
   BASELINE_RUN_IDS='<baseline-1>,<baseline-2>,<baseline-3>'
   ABLATION_RUN_IDS='<without-spec-1>,<without-spec-2>,<without-spec-3>'
   npm run --silent compare -- --runs "$BASELINE_RUN_IDS,$ABLATION_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   Compare keeps baseline/without-spec in different groups. This is expected: it does not compute the causal effect automatically. Confirm that all other material conditions match; for local, also check the LAB08 deployment fingerprint. Identify any `pending`/`excluded` records; do not turn them into passes or silently remove them. The CLI constructs triples by run ID within each group; recover pairing from the table filled in beforehand, not by sorting the overall list.

9. **Derive a limited conclusion.** For each variant, show three outcomes, pass/3, pass@3, and pass^3. For each pair, show the outcome change and wall-clock difference when both measurements exist; do not compare unknown cost with a number. Possible conclusions include: the specification helps; no clear effect; less text improves the result; insufficient data because of a technical error. Support each claim with specific run IDs and artifacts. Do not claim statistical significance from one triple or generalize to other models.

10. **Update the ledger and propose an action.** Find the prompt/spec component in `docs/harness-ledger.md`; it is usually associated with snapshot/variant, but do not extend the conclusion to the row's entire infrastructure. Add a separate row with an unused `LNNN` if the measured assumption is otherwise mixed with a boundary. Fill in component, assumption, actual baseline/without-spec record references, date/exact model, retest trigger, ownership, and status. The ledger rules for “confirmed” require real completed before/after runs; a synthetic test and these instructions are insufficient. An unchanged result after removal makes the text a removal candidate, not grounds to remove Docker/network walls. Add the conclusion to `experiments/<harness>/NOTES.md`.

   Make actual removal a separate change, preserving evidence. If replacing spec with a new mechanism, begin a new hypothesis and series. Do not set cost to 0 to tidy a table: local-only can justify zero inference fee, not zero energy, hardware cost, or an unknown `cost_usd` field.

## Results tables

| Pair | Assigned order | Baseline run ID | Without-spec run ID | Shared conditions verified | Judge/evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | baseline → without-spec | After creation | After creation | Yes/no with reason | After evaluation |
| 2 | without-spec → baseline | After creation | After creation | Yes/no with reason | After evaluation |
| 3 | baseline → without-spec | After creation | After creation | Yes/no with reason | After evaluation |

| Pair | Baseline outcome/time | Without-spec outcome/time | Outcome change | Time Δ, s | Interpretation limit |
| --- | --- | --- | --- | --- | --- |
| 1 | After measurement | After measurement | From verdict | Only two measured values | Fill in |

| Variant | Actual run IDs | pass/total | pass@3 | pass^3 | Cost/time measurement coverage | Pending/excluded |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | Fill in | After evaluation | After evaluation | After evaluation | measured/total | All reasons |
| without-spec | Fill in | After evaluation | After evaluation | After evaluation | measured/total | All reasons |

| Ledger ID | Tested assumption | Evidence run IDs | Conclusion within this series | Decision | Retest trigger |
| --- | --- | --- | --- | --- | --- |
| Actual unused/existing ID | Fill in | Before/after | Fill in | Keep/removal candidate/new series needed | New model/task/version |

## Deliverables

- Lab report/manifest, preassigned pairs, measurements, and raw compare JSON.
- References to six new run records and independent evaluations; all deviations and unfinished states.
- Verification that conditions match except for the intervention, including replay archive or seed commit.
- Ledger row/update with actual evidence links and a limited conclusion; a note in NOTES.

## Completion criteria

- [ ] The intervention is limited to the native `without-spec` variant; task contract and boundaries are preserved.
- [ ] Three pairs and their order are assigned in advance; every attempt has a new run ID.
- [ ] Other conditions within pairs match, or differences explicitly preclude causal interpretation of the pair.
- [ ] All outcomes are preserved and independently evaluated where execution reached review.
- [ ] Compare uses exact IDs; paired analysis is performed separately from automatic grouping.
- [ ] The ledger contains actual evidence and a retest trigger.
- [ ] Unknown metrics are not replaced with zeros; the conclusion does not exceed the series' scope.
- [ ] `npm run check` passes; an unfinished series is marked incomplete on submission.

## Review questions

1. Why would removing `inputs/spec.md` after prepare invalidate the experiment?
2. What exactly does `without-spec` remove, and why does the wording particularly matter for T003?
3. Why use paired order if the model is nondeterministic anyway?
4. Why are different compare groups for baseline and ablation expected?
5. Can you conclude that spec is unnecessary if both triples contain only failures?
6. How does a candidate for instruction removal differ from a decision to remove an infrastructure boundary?

## Sources

- [Ablation in the protocol](../method.md), [prepare implementation](../../scripts/prepare-run.mjs), [compare grouping and triples](../../scripts/compare.mjs).
- [Ledger and allowed statuses](../harness-ledger.md), [evaluation verification](../../scripts/judge-run.mjs).
- [LAB09: campaigns and independent judge](LAB09-agent-campaign.md), [LAB08: local integration](LAB08-local-bridge.md).
