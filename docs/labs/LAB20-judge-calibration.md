# LAB20. Calibrating two independent evaluators

## Profile

| Field | Value |
| --- | --- |
| Type | Evaluation with a fixed rubric, entirely offline |
| Time | 1–2 hours, including disagreement analysis |
| Prerequisites | LAB01; two people able to read a short answer independently |
| Readiness | `available`: teaching dataset and rubric included; no API, GPU, or real agent runs required |
| Minimum scope | Four anonymized answers × two evaluators × five criteria = 40 separate decisions |
| Extension | A second batch of answers prepared beforehand; calibration on actual campaign artifacts |

## Objective

Check whether two evaluators understand criteria identically, and distinguish evaluation errors from agent errors. The result is the original independent decisions, a disagreement map, and proposed rubric clarifications.

## Hypothesis

“Two evaluators independently apply one rubric to one dataset, agreeing on all four final verdicts and at least 18 of 20 criterion decisions.” This is a **teaching admission criterion** chosen in advance, not a statistically established reliability level.

The changed factor is the evaluator. Answers, rubric version, sources, and time allowance are identical. The experiment checks inter-rater agreement; rereading the same answers after discussion is not an independent repetition. Even complete agreement may reflect a shared error, so a public teaching reference is used afterward.

## Preparation

```bash
npm run lab:new -- --lab LAB20 --session judge-pilot
LAB_DIR='experiments/local-models/measurements/LAB20-judge-pilot'
npm run check
```

Read the [teaching dataset contract](episodes/judge-calibration/episode.md) and [rubric](episodes/judge-calibration/rubric.json). The dataset contains four artificially written answers; none is a model measurement. Do not open `reference-evaluation.json` before completing independent evaluations: the file is public, and the restriction preserves the exercise's integrity. The coordinator supplies links to answers and rubric; do not attach an author name, harness, or presumed quality to candidate codes.

Preserve the input and plan versions:

```bash
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
node --input-type=module - <<'NODE' > "$LAB_DIR/raw/input-hashes.json"
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const base = 'docs/labs/episodes/judge-calibration/';
const names = ['episode.md', 'rubric.json', ...['a', 'b', 'c', 'd'].map(x => `candidate-${x}.md`)];
console.log(JSON.stringify(names.map(name => ({ file: base + name, sha256: createHash('sha256').update(readFileSync(base + name)).digest('hex') })), null, 2));
NODE
```

Do not assign both roles to one person. If no second evaluator is available, you may prepare your own evaluation, but the inter-rater part remains incomplete. Two calls to one model constitute a separate experiment with dependent evaluations and a known configuration; they do not replace two humans in the minimum route.

## Procedure

1. **Record the protocol before evaluation.** R1 reads candidates `a → b → c → d`; R2 reads `d → c → b → a`. Each gets up to 25 minutes for the entire batch; the identical limit includes reading source materials and the rubric. Record evaluator identifiers, time, input version, and the hypothesis's admission rule. Evaluators must not discuss answers before submitting their tables.

2. **Provide identical inputs.** Each receives the assignment, three sources, five criteria, and four answers. Hide only the mapping to actual authors when doing the extension. This artificial dataset has no model author. Do not hide task requirements or factual sources: they are necessary for evaluation.

3. **Obtain independent decisions.** For each candidate, each evaluator marks C1–C5 true/false and gives a short quotation or identifies a missing element. An unevaluated criterion is `unknown` with a reason; it is neither false nor sufficient for pass. Pass requires all five true. Preserve separate `raw/rater-r1.tsv` and `raw/rater-r2.tsv` with columns `candidate`, `criterion`, `value`, and `evidence`; place verdicts in the report's summary table. Record actual time. Do not revise earlier rows after reading the other file.

4. **Calculate agreement before discussion.** Primary criterion agreement: matching true/false decisions / pairs with two known decisions. Also show completeness: evaluated pairs / 20. Verdict agreement: matching pass/fail decisions / fully evaluated candidates; show completeness /4. Any `unknown` leaves minimum calibration incomplete. Do not silently remove a disputed answer from the denominator. Give raw numerators and denominators, not only percentages.

5. **Open the public reference.** Compare each evaluation with [reference-evaluation.json](episodes/judge-calibration/reference-evaluation.json). For R1 and R2 separately, count false passes among reference failures and false failures among reference passes. These are disagreements with a specific teaching rubric, not measured accuracy of a universal judge. If you dispute the reference, identify the exact item; do not retroactively correct original answers.

6. **Analyze disagreements.** The coordinator compiles a table: answer, criterion, two decisions, answer text, rubric rule, agreed interpretation. Distinguish a missed fact, ambiguous criterion, excessive evaluator requirement, and disagreement with the reference. For example, including numbers is not inherently required if a criterion only requires correctly attributing numbers that are given. Base the discussion on wording, not opinions about the author.

7. **Decide on admission.** If the predefined rule is met, mark “admitted to a pilot series with this rubric” and note the small-batch limitations. Otherwise, preserve the result as a completed exercise that found a problem and prepare a new rubric version. Readmission requires a new answer batch created before its evaluation. Repeating the familiar four answers is useful for learning but does not demonstrate transferable agreement.

8. **Prepare the submission.** Complete the [lab report and completeness check](report-validation.md): evidence class `synthetic`, planned exercises, pre-evaluation protocol file, and references to your tables. Keep `run_ids: []`: the minimum contains no agent runs. Checks do not assign an evaluator-quality verdict or replace disagreement analysis:

   ```bash
   npm run lab:check -- --report "$LAB_DIR" --mode submission
   npm run check
   ```

   Do not record this exercise as passing a task's hidden check.

9. **Extension to actual artifacts.** After a campaign, choose a predeclared batch including successful, unsuccessful, and disputed work. The coordinator preserves the mapping from anonymized codes to real run IDs. Do not show judges the model, variant, or price before verdict assignment. Apply the existing task's contract and external judge; calibration does not replace required independent `judge-run` evaluation. Supporting [offline practice](practice.md) is suitable for learning trace reading, but synthetic scenarios do not measure a real model's behavior.

## Results tables

| Candidate | Criterion | R1: true/false/unknown | Evidence R1 | R2: true/false/unknown | Evidence R2 | Agreement |
| --- | --- | --- | --- | --- | --- | --- |
| candidate-a | C1; repeat for all 20 pairs | After evaluation | Answer excerpt | After evaluation | Answer excerpt | After comparison |

| Candidate | Verdict R1 | Verdict R2 | Reference verdict after reveal | Disagreement reason |
| --- | --- | --- | --- | --- |
| a/b/c/d, separate row | After evaluation | After evaluation | After independent evaluations | Fill in |

| Metric | Numerator | Denominator | Completeness | Interpretation |
| --- | --- | --- | --- | --- |
| Criterion agreement | Matching known decisions | Pairs with two known decisions | Out of 20 | Teaching threshold 18/20 with complete evaluation |
| Verdict agreement | Matching decisions | Fully evaluated candidates | Out of 4 | Threshold 4/4 |
| False pass R1/R2, separately | Reference failures marked pass | All reference failures | Out of all candidates | Proportion for this batch |
| False fail R1/R2, separately | Reference passes marked fail | All reference passes | Out of all candidates | Proportion for this batch |

## Deliverables

The pre-evaluation plan, hashes, two original decision files, four verdicts from each judge, agreement tables and errors relative to the reference, discussion record, admission decision, and a separate proposed rubric version if needed. Calculate all agreement numbers from your evaluations; the dataset contains no ready-made human-evaluation results.

## Completion criteria

- [ ] Two independent evaluators each completed 20 decisions before discussion and reading the reference.
- [ ] Original decisions preserved; the discussed version does not overwrite them.
- [ ] Numerators, denominators, and unknowns shown; threshold chosen before viewing results.
- [ ] Human agreement and correspondence to the teaching reference assessed separately.
- [ ] Every disagreement analyzed against text and rule.
- [ ] Conclusion limited to this rubric and small batch; no reliability claim for all tasks.
- [ ] Report fully completed, `run_ids` empty, and `npm run check` passes.

## Review questions

1. Why does a shared error by both judges produce high agreement?
2. Why preserve original evaluations after agreeing on a decision?
3. How does an unknown decision differ from fail?
4. Why is repeating a familiar dataset after discussion not an independent check?
5. What would need to change in the rubric when moving from a dossier to a code fix?

## Sources

- [Teaching dataset and contract](episodes/judge-calibration/episode.md), [rubric](episodes/judge-calibration/rubric.json).
- [Evidence classes and independent evaluation](../method.md), [LAB09: agent campaign](LAB09-agent-campaign.md).
- [Shared evaluation workflow for real runs](harness-workflow.md), [evaluation template](../../scripts/evaluation-template.mjs).
