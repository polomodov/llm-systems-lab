# LAB27. Updating a model or harness and retesting components

## Profile

| Field | Value |
| --- | --- |
| Type | Regression comparison of pinned configurations and ledger retesting |
| Time | 2–4 hours of operator time plus six attempts and independent evaluation; ablation adds six attempts |
| Prerequisites | LAB09 and LAB10, fixed inputs, and an independent evaluator |
| Readiness | `available`: cloud comparison of two models works with the current runner; the local branch requires accepted LAB08 |
| Minimum scope | One task × two exact model IDs × three new paired baseline repetitions, one harness version |
| Extension | A new harness version with an unchanged model; or six new component-retest attempts on the selected new configuration |

## Objective

Test whether an updated configuration retains the ability to perform a pinned task, and determine which earlier harness assumptions need retesting. Establish grounds to keep a component, remove it after ablation, or defer the decision pending more data.

## Hypothesis

When moving from model A to model B in a fixed harness, the selected task performs no worse under a predefined rule: for example, no pair lost on independent verdict and no new unhandled protocol errors. Time, tokens, and cost are secondary metrics with explicitly stated provenance.

The component extension has a separate hypothesis: on the new model, the component no longer improves results. A successful update alone does not prove that a component is unnecessary. Three pairs are a training regression check, not proof of statistical equivalence or absence of rare errors.

## Preparation

```bash
npm run lab:new -- --lab LAB27 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB27-my-session'
npm run check
```

The minimum is performed in the cloud without Ryzen. Use one harness from [LAB11–19](README.md) that supports **both** exact IDs with one provider. The example below uses Pi from LAB15. Prepare its verified immutable image IDs and smoke test; credentials remain only in `.env` under the selected profile. Pi's observed underlying model may be unknown: retain the requested ID and identity source rather than claiming a provider observation.

Do not use `latest` or a managed mode instead of an exact snapshot in the primary comparison. In Amp/Copilot, changes to the available hidden underlying model may be unobservable; such checks are permitted as separate service diagnostics with this limitation. If the old snapshot is no longer available, the historical baseline can be analyzed separately, but it does not replace new paired runs and increases confounding with calendar time.

## Procedure

1. **Declare the plan and fixed conditions.** Assign T002, seed commit, `baseline`, timeout 900 s, provider, harness image/version, proxy image, and budget policy. Record models A/B, the reason for updating, and the regression criterion. Pair order: A→B, B→A, A→B. Both variants receive a new workspace; old successful runs are not selected retrospectively. Save the git revision and tree state in new files:

   ```bash
   (
     set -eu
     set -o noclobber
     git rev-parse HEAD > "$LAB_DIR/raw/revision.txt"
     git status --short > "$LAB_DIR/raw/tree-status.txt"
     node --test experiments/pi/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   )
   ```

   Do not update dependencies or images during this series. The SDK's built-in model metadata—context/output/pricing/reasoning defaults—may also differ across models. Record effective A/B values; if they cannot be aligned, frame the conclusion around two configured deployments rather than model weights alone.

2. **Prepare the first cloud attempt A.** Take image IDs from completed LAB15. The version below matches this practicum's pinned Dockerfile; another runtime that was actually verified requires its own recorded version:

   ```bash
   PROVIDER_ID='anthropic'
   MODEL_A='<exact available ID of the previous model>'
   MODEL_B='<exact available ID of the new model>'
   IMAGE_ID='<immutable Pi 0.73.1 image ID from LAB15>'
   PROXY_IMAGE_ID='<immutable proxy image ID from LAB15>'
   MODEL_ID="$MODEL_A"
   npm run new-run -- --harness pi --harness-version 0.73.1 --agent a2-janitor \
     --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<new ID from new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID"
   ```

   For OpenAI, select `PROVIDER_ID='openai'` before creating any records. Check availability and support for both IDs in the pinned SDK; do not replace an unavailable model with a similar alias. In the first pair's manifest, compare task/seed and material control settings. Full hashes may differ because of run IDs and the model identity under study.

3. **Execute the record and register every outcome.**

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   ```

   Pi limits native turns, while `observed` does not stop exactly at USD 2: retain this deviation from the contract's hard cap identically for both models. `awaiting_review` does not mean pass; `aborted` remains the outcome of a started attempt. If the model protocol is incompatible, retain the trace and failure. Do not modify the adapter only for B midway through the series: that begins a separate deployment comparison.

4. **Obtain an independent verdict and finish the remaining pairs.** Create a new template for each `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The evaluator completes result/evaluator/check_output under the [common workflow](harness-workflow.md), retaining hashes. Where possible, provide result contents without the model name. Only after evaluation:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   ```

   Create five more records using steps 2–4, assigning `MODEL_ID="$MODEL_B"` or `MODEL_ID="$MODEL_A"` according to the plan. Record the newly issued ID for each `new-run`; do not reuse existing records. Separate new retries after fixes do not replace the original six slots. Hidden checks are run by the external evaluator, not the solving agent.

5. **Compare groups and locate regressions.**

   ```bash
   RUN_IDS='<A1>,<B1>,<B2>,<A2>,<A3>,<B3>'
   (
     set -o noclobber
     npm run --silent compare -- --runs "$RUN_IDS" > "$LAB_DIR/raw/compare.json"
   )
   npm run check
   ```

   Model IDs remain separate groups. Compare does not combine them into an automatic regression verdict: manually compare all conditions, pairs, pass/partial/fail/aborted outcomes, stop reasons, and unknown fields. Distinguish parser/protocol changes, an actually incorrect task solution, missing credentials/model access, and timeout. Do not call a missing metric a cost improvement or treat equal turn counts across harnesses as equal work.

6. **Open retests for relevant components.** In the [ledger](../harness-ledger.md), find assumptions whose “new model” or “SDK version” trigger has fired. Retain the old date/model and links to old evidence, and add new observations with specific run IDs. A component's earlier benefit does not automatically carry over to B. If the minimum includes no new ablation, explicitly state “contribution after the update is unverified” in the conclusion and give a retest plan. Do not mark it “confirmed” based on one new baseline or unit tests.

7. **Extension: repeat the ablation on B.** For the available `without-spec`, use the full [LAB10](LAB10-ablation.md) protocol: three **new** `baseline`/`without-spec` pairs, totaling six additional attempts with model B. Do not select pairs from successful step 5 results after seeing outcomes. Compare the new effect with the earlier LAB10 under known conditions. If the new minimum without the component meets the predefined criterion, the component becomes a removal candidate. This is a limited conclusion that may require a second task before actual removal.

   Make removal a separate change: retain evidence, describe the removed prompt/hook, update the ledger and NOTES, rerun relevant tests and `npm run check`. If a component contains both an infrastructure boundary and a model assumption, separate them first. Docker/network walls, hidden-check isolation, timeout, and the independent judge are not removed because a model improved.

8. **Alternative extension: update only the harness.** Fix one model ID and its availability, original tasks/seed/archive, provider, limits, and judge. Prepare two independently pinned builds of the old and new versions; add the expected upstream package revision and the version actually observed. The current Pi Dockerfile checks `HARNESS_VERSION=0.73.1`: changing `--harness-version` in the run record or an arbitrary `--build-arg` does not correctly update the SDK. A new version requires an explicit Dockerfile/adapter change where needed, native SDK smoke verification, and parser tests; show these edits as a separate diff.

   Prepare each version's runs from its corresponding checkout/config, retaining provenance and immutable image IDs. Do not run a new binary under an incorrectly declared version or change already sealed inputs. Repeat three paired baseline attempts using steps 1–5, specifying versions A/B instead of models A/B. Native prompt/tool schema changes built into the new version itself are part of the update under study; list them. Changes to the task seed, gateway, driver, or model alongside the SDK are confounded factors that preclude a clean conclusion about the harness.

9. **Choose a decision and the next trigger.** Allowed outcomes: accept the new configuration within the tested task; retain the old one because of a specific regression; retest a component; remove a component in a separate evidence-backed change; defer selection due to insufficient comparable data. Create separate episodes for new tasks; do not change `tasks/*/task.md`. T001 uses one frozen source archive. In a version comparison, T003 may have different audited inputs and remains change diagnostics, not a clean same-input quality benchmark.

## Results tables

| Condition | A | B | Sole intervention or confounded factor |
| --- | --- | --- | --- |
| Provider / exact requested model / identity source | | | |
| Harness version / image / native defaults | | | |
| Task seed / archive / prompt variant | | | |
| Context/output / timeout / turns / USD policy | | | |

| Pair / order | Run ID A | Run ID B | Verdict / stop reason A/B | Time / tokens / cost A/B | Regression evidence |
| --- | --- | --- | --- | --- | --- |
| 1 / A→B | | | | | |
| 2 / B→A | | | | | |
| 3 / A→B | | | | | |

| Ledger ID / component | Old evidence / conditions | Trigger that fired | New evidence | Retest complete? | Decision / next trigger |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

| Ablation on B, if performed | New baseline IDs | New without-spec IDs | Paired outcomes | Grounds to keep/remove/continue |
| --- | --- | --- | --- | --- |
| | | | | |

## Deliverables

A report and manifest, predefined pair plan and regression threshold, six new baseline run records with traces and independent evaluations, compare output, identity/conditions table, and ledger retest proposal. For an extension, attach six more ablation attempts or the diff/version/smoke of the new harness version, keeping these branches separate. Use the [completeness check](report-validation.md). Evidence from the old version is retained after the update.

## Completion criteria

- [ ] One update factor is selected; other conditions are fixed or explicitly identified as confounded.
- [ ] Six preassigned new attempts and independent verdicts for those completing execution are retained.
- [ ] Every abort, protocol error, and unknown metric is stated; successful attempts are not cherry-picked.
- [ ] A verifiable paired comparison is manually constructed from different compare groups.
- [ ] Old evidence is not overwritten; the ledger contains an honest retest decision, not an unsupported benefit after the update.
- [ ] Component removal is proposed only after a separate ablation; infrastructure boundaries are preserved.
- [ ] The report is complete, and `npm run check` passes.

If one model is unavailable, there is no evaluator, or the old version cannot be reproduced, retain `blocked` with completed preparation. Historical data analysis is useful but does not satisfy the minimum of new paired runs.

## Review questions

1. Why does updating the model and harness simultaneously prevent locating a regression's source?
2. What remains unknown even with a pinned requested snapshot of a cloud model?
3. Why does a new baseline pass not prove that an old hook is unnecessary?
4. Which native changes naturally belong to the effect of a new harness version?
5. How does finding no regression in three pairs differ from a compatibility guarantee?
6. How can earlier evidence be preserved in the ledger when a retest trigger fires?
7. Which components must not be removed based on model ablation, and why?

## Sources

- [Method and comparison conditions](../method.md), [assumptions ledger](../harness-ledger.md).
- [Agent series](LAB09-agent-campaign.md), [ablation and ledger decisions](LAB10-ablation.md), [cloud Pi](LAB15-pi.md).
- [Pi Dockerfile](../../experiments/pi/Dockerfile), [native runtime](../../experiments/pi/run.mjs), [provider profile](../../experiments/pi/harness.json).
- [Creating records](../../scripts/new-run.mjs), [common evaluation workflow](harness-workflow.md). The executor checks model ID availability and compatibility of a new upstream release for their exact versions.
