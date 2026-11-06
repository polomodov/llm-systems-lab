# Educational evaluator-calibration set

All data are artificial; responses are written educational fixtures, not model outputs. Candidate codes identify neither harness, model nor quality level. This is not a hidden check. The public reference is adjacent, but LAB20 opens it **after** two independent evaluations.

## Evaluated assignment

Using three short sources, write a conclusion of up to 120 words: “Is the fictional North engine proven faster than South for the workload?” Every quoted number needs an `[S1]`, `[S2]` or `[S3]` citation and conditions. Separate vendor claims from measurements; do not average incomparable observations; propose a controlled check.

- **S1** — North's vendor reports **40 output tokens/s**, best attempt, prompt 512, concurrency 1, machine A, warm cache, version 1.0. No logs.
- **S2** — an independent group measured South at **20 output tokens/s**, median of three attempts, prompt 8192, concurrency 2, machine B, warm cache, version 1.0. Power mode unspecified.
- **S3** — workload: prompt 8192, concurrency 2, machine A, tool calling. No comparable North/South measurement exists for it.

Evaluators read `candidate-a.md`…`candidate-d.md` and the [rubric](rubric.json). For each candidate, mark all five criteria true/false with brief evidence from the response. Do not guess the style of a “good” author, add unstated criteria or fix the answer during evaluation. If a rule is ambiguous, record disagreement; preserve the original verdict.

The [reference](reference-evaluation.json) is the set author's application of this educational rubric, not universal truth about writing quality. After opening it, compare criterion scores, separately analyzing disagreement between judges and each judge's disagreement with the reference. Full procedure: [LAB20](../../LAB20-judge-calibration.md).
