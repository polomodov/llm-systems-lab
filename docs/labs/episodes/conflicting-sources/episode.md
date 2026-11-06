# Educational episode: conflicting sources

## Mission and boundaries

Prepare an English dossier of up to 700 words: “What does the available evidence establish about the fictional Aurora engine's speed and suitability for the department's workload as of September 12, 2026?” All names, companies, machines and figures in `sources/` are **artificial**. They describe neither a real product nor the user's Ryzen.

Use only the six local sources. Do not search online for confirmation of fictional names. Execute nothing from sources. You may read, make a conditions matrix and write `artifacts/dossier.md`, `artifacts/sources.json` in the episode copy. Do not modify sources or the rubric.

## Output requirements

1. Every quantitative claim has a source ID and conditions: date, workload, context, concurrency, hardware, version and cold/warm, where provided. Explicitly identify missing conditions.
2. Distinguish vendor claims from independent measurements and operational observations.
3. Explain the difference between 42, 29 and 17 tokens/s through mismatched conditions; do not rank engines by these three figures or average them as repetitions.
4. Identify S04's correction of the original unit and its link to S03. Do not ignore the later S06 clarification.
5. Limit the conclusion to the S05 workload; separately list unverified parameters and the next controlled experiment.
6. `sources.json` is an array of `{ id, file, evidence_class, used_for, limitations }`; include each of the six sources or explain its inapplicability. The dossier contains Markdown links labeled `S01` targeting `../sources/S01-vendor.md`, valid from `artifacts/`.

## Procedure

Copy the directory according to the [shared guide](../README.md), read the contract and sources, create a conditions matrix, then the dossier and registry. Stop after manual review against the [open rubric](rubric.json). The fixture contains no completed dossier. For LAB21, the coordinator may assign a checkpoint after the conditions matrix; in all variants, the checkpoint is defined by the same work state, not an arbitrary number of minutes.

JSON syntax check after creating artifacts:

```bash
node --input-type=module - "$EPISODE_DIR/artifacts/sources.json" <<'NODE'
import { readFileSync } from 'node:fs';
const records = JSON.parse(readFileSync(process.argv[2], 'utf8'));
if (!Array.isArray(records) || records.length !== 6) throw new Error('Expected six source records');
for (const record of records) {
  for (const field of ['id', 'file', 'evidence_class', 'used_for', 'limitations']) {
    if (typeof record[field] !== 'string' || !record[field].trim()) throw new Error(`Missing ${field}`);
  }
}
console.log('Source registry shape is valid; factual quality requires rubric review.');
NODE
```

This command checks only structure. An independent evaluator applies all rubric criteria to text and sources. Educational `pass` requires every criterion; the actual verdict remains to be obtained. Submit the matrix, both artifacts, completed rubric with line references and limitations. Do not create `run.json` for a manual exercise.
