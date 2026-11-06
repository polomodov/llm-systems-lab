# LAB09. Autonomous-agent pilot and comparison campaign

## Profile

| Field | Value |
| --- | --- |
| Lab type | Measurement: real attempts, independent evaluation, and comparison under identical conditions |
| Time | Estimate: 2–4 operator hours for cloud or 4–8 for local, plus execution and evaluation; 12 cloud attempts with timeout 900 s allow up to 3 hours of agent execution, excluding setup/review |
| Prerequisites | LAB01 and the selected harnesses' individual LAB11–19; local additionally requires completed LAB08 for every included harness and a ready model configuration |
| Readiness | Cloud lifecycle implemented; actual account/model availability checked before execution. The local series is **conditional** and cannot be run before LAB08 acceptance |
| Minimum cloud scope | 3 pilots + 9 new attempts: three harnesses × one shared model/provider × T002 × 3; suitable pilots may come from LAB11–19 |
| Minimum local scope | 4 pilots + 12 preassigned comparison attempts: one model, T002, four primary harnesses |
| Extension | 72 T001/T002 attempts for three finalists; 36 separate T003 attempts; cloud diagnostics covering all nine harnesses are optional |

## Objective

Measure how different harnesses execute the same episode with a fixed model and conditions. Separate engineering readiness from task quality, observed values from unknowns, and controlled comparison from diagnostics of different deployments.

## Hypothesis

With identical model, inputs, inference settings, limits, and evaluation method, selected harnesses may differ in the proportion of successful triples, time, and required components. The hypothesis is tested for this series; no difference in three attempts does not prove that the harnesses are equivalent in general.

## Preparation

```bash
npm run lab:new -- --lab LAB09 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB09-my-session'
npm run harnesses
npm run check
```

Complete the manifest and attempt schedule before the first execution. Choose one verified model deployment and a shared timeout, such as 900 s; read task limits from the public contract. Preserve harness versions, immutable image IDs, permission mode, budget policy, and judging method. Prepare actual provider credentials in `.env` without exposing their values in the report.

**Cloud is a standalone main route without LAB08.** Choose three harnesses sharing an actually available provider/model ID. For example, Claude Code, OpenCode, and Pi profiles permit Anthropic; Pi, mini-SWE-agent, and OpenHands also permit a shared OpenAI branch. This is the intersection of current profile capabilities, not a guarantee that the account can access a model. Use individual labs from the [LAB11–19 catalog](README.md) for images, provider, smoke tests, and trace details. A completed T002 there may serve as a pilot if its actual conditions match; the comparison triple is always new. Study Amp and an unconfirmed Copilot selector separately; do not add them to an exact-model group just to obtain a third row.

Record the selected route (`cloud` or `local`) and required scope in the lab report. If no shared deployment exists for three harnesses, a diagnostic report on different models remains useful but does not replace the minimum controlled comparison.

The local core uses Pi, mini-SWE-agent, OpenCode, and OpenHands. Each must pass LAB08 separately; the existence of `local:plan` does not mean an integration is ready. Codex is an additional branch after its own verification. Claude Code, Antigravity, Copilot, and Amp do not automatically receive a local route.

## Procedure

1. **Choose the scope and record the order.** Do not run the whole matrix before the pilot. Save a table of planned slots and the stopping rule in the report. Main minimum and extensions:

   | Series | Composition | Attempt count | Purpose |
   | --- | --- | --- | --- |
   | Cloud pilot | 3 selected harnesses × 1 shared model/provider × T002 | 3; suitable LAB11–19 attempts allowed | Admission to cloud comparison |
   | Cloud minimum | 3 × 1 × T002 × 3 | 9 new | Standalone LAB09 completion without a local bridge |
   | Pilot core | 4 harnesses × 1 model × T002 × 1 | 4 | Verify the actual lifecycle and protocol |
   | Local minimum | 4 × 1 × T002 × 3 | 12 new | Compare preassigned triples |
   | Adding T001 | 4 × 1 × T001 × 3 | 12 more | Dossier using one frozen archive |
   | Full main series | 4 × 3 models × T001/T002 × 3 | 72 total | Extend to three finalists; do not duplicate suitable slots already completed |
   | T003 audit | 4 × 3 × T003 × 3 | 36 separate | Diagnostics, not a causal harness ranking |
   | Cloud coverage of all harnesses | 9 harnesses × each available provider/model × T002 × 1 | 9 pilots from LAB11–19 for the full harness route | Deployment verification, separate from same-model comparison |

   Do not retroactively include pilots in comparison triples. Account separately for technical incompatibility before task startup; do not exclude a slow model solely for its speed. Choose the harness order by round in advance, alternating first/last positions. For both series, execute one attempt at a time; for local, use one model server and one slot on Ryzen.

2. **Check cloud coverage if needed.** The nine supported adapters are `claude-code`, `opencode`, `codex`, `antigravity-cli`, `pi`, `mini-swe-agent`, `openhands`, `copilot-cli`, and `amp`. For each, choose only a provider from `npm run harnesses` and an available exact ID according to the adapter README/account. For Amp, use a supported `managed:<mode>`; do not claim the underlying model is known. A Copilot selector is likewise not a proven snapshot. These nine rows need not use one model and do not form a fair same-model ranking. For a controlled cloud subseries, use only the intersection of actually available model IDs with the same provider.

3. **Create a new record for one slot.** The following is the **existing cloud CLI**; replace every angle-bracketed value before running it. For a local series, use the documented, verified interface implemented in LAB08: this text does not introduce a working `--local` or ready-to-use `--provider local`.

   ```bash
   HARNESS_ID='pi'
   PROVIDER_ID='anthropic'
   MODEL_ID='<exact available model ID>'
   IMAGE_REF='<verified image tag or image ID>'
   PROXY_IMAGE_REF='<one pinned proxy image ID for the series>'
   npm run new-run -- --harness "$HARNESS_ID" --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   ```

   Copy the output run ID into the appropriate slot and variable. Do not invent or reuse IDs:

   ```bash
   RUN_ID='<ID returned by new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID"
   ```

4. **Pin T001/T002/T003 inputs.** For T002, preserve one seed commit, an identical contract, and initial files. For T001, first obtain `trace/sources.jsonl` from a recorded discovery run; if none exists yet, perform one separate live T001 and preserve it as the archive source outside the controlled series. The archive must contain response bodies and statuses, not just URLs. Use the same archive and `as-of` in all compared attempts:

   ```bash
   SOURCE_ARCHIVE='<path to the discovery run trace/sources.jsonl>'
   AS_OF_DATE='<shared YYYY-MM-DD date>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   This is an alternative preparation of a **new T001 record** with `a1-dossier`, not another prepare on an already prepared T002. Replay does not fetch missing responses from the internet. For T003, use `a3-ledger-auditor`: setup copies the selected harness's configuration, so different harnesses have different inputs; place this series in the diagnostic section.

5. **Execute the attempt and check its state.** Existing cloud run command:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   ```

   Eight adapters require `observed` because they lack a verified hard USD cap. When comparing them with Claude, explicitly use a common policy; separately studied `hard` attempts do not belong in the same group. `observed` means a research deviation from the contractual USD cap; timeout remains an enforced limit. Native turns/iterations in different systems are not equivalent units. Do not change the model, provider, initial files, or sealed snapshot after prepare.

6. **Hand the result to an independent evaluator.** The normal sequence is `planned → prepared → running → awaiting_review → completed`. Exit 0 does not mean pass. For `aborted`, preserve the reason and do not invoke judge to turn an error into completed. For `awaiting_review`, create a clean JSON template:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The evaluator works outside the agent container, does not modify artifacts, and does not provide hidden checks to the agent. They fill in `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output`, and optionally `human_notes`, preserving generated hashes. T002 uses an external hidden check; T001/T003 use a rubric, with T001 also using its designated checking script. The operator defines the specific way to run the hidden evaluator; no universal existing command for all tasks is assumed here. If no independent evaluator is available, the record remains `awaiting_review`.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `judge-run` links the evaluation to manifests and checks integrity; it does not make the substantive decision itself. The lab report only references the resulting record.

7. **Close the pilot and freeze the comparison series.** Record protocol/timeout/identity errors from the three cloud or four local pilots. Fixing an adapter or backend creates a new configuration and new attempts. After fixes, define nine cloud or twelve local slots; execute them sequentially, obtaining a new run ID for each. Do not discard failures after execution started or replace a failed attempt with a successful retry. Stop expansion if the core protocol still fails, memory is insufficient, or no independent judge is available; include the reason in the report.

8. **Compare only the declared run IDs.** Build a string of actual IDs with no spaces after commas. Do not use the default entire directory if it contains discovery, pilot, or other studies:

   ```bash
   SERIES_RUN_IDS='<run-id-1>,<run-id-2>,<remaining series IDs>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   Check `pending`, `excluded`, reasons for different `conditions`, and the proportion of observed model IDs. Compare constructs triples within each group/harness in run-ID order; for the minimum series, each contains exactly the three attempts chosen in advance. Started aborted runs remain in the denominator; records without an execution start are excluded separately. Do not merge groups manually merely to produce one chart. The LAB08 implementation must distinguish local conditions.

9. **Interpret the result and decide whether to expand.** Record pass/total, `pass@3`, `pass^3`, time with measured/total, and unavailable metrics. With three attempts, show the original outcomes rather than a confident global ranking. Compare success and time, then measured memory and energy; an unknown metric cannot support a claim of superiority. The full 72-attempt series is an extension, not a requirement for the first submission. Preserve finalist selection criteria before starting the extension. Do not mix the 36 T003 attempts with the 72 main attempts.

10. **Record what the harnesses needed.** Add actual run IDs, conditions, errors, and required changes to `experiments/<harness>/NOTES.md`. New components receive a ledger row in the same change; the mere absence of a pass does not justify adding a component. Do not convert unknown cloud cost to 0. In a local series, inference fee, energy, and depreciation are different quantities; 0 inference fee requires a confirmed local-only path, while electricity requires measurement and a tariff.

## Results tables

| Slot | Stage | Harness/version | Model/deployment hash | Task | Repeat | Run ID | Status | Verdict | Exclusion reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fill in before execution | pilot/main/T003/cloud | Fill in | Fill in | T002 | 1 | After new-run | planned before execution | pending before judge | If applicable |

| Conditions/group | Harness | Three actual run IDs | Outcomes | pass/total | pass@3 | pass^3 | Wall-clock, measured/total | Cost, measured/total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fill in from compare | Fill in | Fill in | Preserve all | After evaluation | After evaluation | After evaluation | With units | Explicit unknowns |

| Deviation | How detected | Affected run IDs | Effect on comparison | Next action |
| --- | --- | --- | --- | --- |
| Fill in | Raw evidence | Actual IDs | Separate group/limitation | Fill in |

## Deliverables

- Manifest, preassigned slot matrix, and lab report with raw compare JSON.
- References to all created run records, including discovery, pilot, aborted, pending, and the main series.
- Independent evaluations identifying the judge and linked to unchanged results.
- Table of comparable groups, limits of the conclusion, and NOTES/ledger additions when components changed.

## Completion criteria

- [ ] Every harness and model deployment was checked for readiness before the series.
- [ ] Pilots are separate from preassigned comparison attempts.
- [ ] A route is selected: cloud has 9 comparison attempts after three pilots; local has 12 after four pilots. Smaller scope is marked as an interim report.
- [ ] All started failures are preserved; no outcomes were retroactively replaced.
- [ ] T001 uses one frozen archive; T003 is interpreted separately.
- [ ] `awaiting_review` is not presented as pass; independent judge and evidence are available for completed results.
- [ ] Compare uses exact IDs; model/deployment and other conditions are not mixed.
- [ ] Unobserved cost and metrics are not replaced with zeros; `npm run check` passes.

## Review questions

1. Why do nine different cloud providers/models provide coverage but not a pure harness effect?
2. How would the conclusion change if one T001 ran live and the rest used replay?
3. How does `pass@3` differ from `pass^3`, and which outcomes produce different values?
4. Why must a started attempt that times out remain in the denominator?
5. What specifically prevents causal T003 comparisons across different harnesses?
6. Which data can confirm an identical local model behind one alias?

## Sources

- [Protocol](../method.md), [harness matrix](../harnesses.md), [local campaign](../local-models.md).
- [new-run](../../scripts/new-run.mjs), [prepare-run](../../scripts/prepare-run.mjs), [run](../../scripts/run.mjs).
- [evaluation-template](../../scripts/evaluation-template.mjs), [judge-run](../../scripts/judge-run.mjs), [compare](../../scripts/compare.mjs).
- [LAB08: engineering integration](LAB08-local-bridge.md), [LAB10: ablation](LAB10-ablation.md), [LAB01 index](README.md).
- [Individual LAB11–19](README.md), [shared evidence and evaluation procedure](harness-workflow.md).
