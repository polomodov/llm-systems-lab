#!/usr/bin/env node
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { readRun, writeRun } from './lib/records.mjs';
import { inventory, sha256 } from './lib/files.mjs';
import { verifyInputs } from './run.mjs';
import { args, options, main } from './lib/cli.mjs';
export function judgeRun(root, runId, evaluationFile) {
  const record = readRun(root, runId), dir = join(root, 'results/runs', runId);
  if (record.status !== 'awaiting_review') throw new Error('Only awaiting_review runs can be judged; completed evidence is not overwritten');
  verifyInputs(dir, record, { workspace: false });
  const evaluationText = readFileSync(evaluationFile, 'utf8'), evaluation = JSON.parse(evaluationText);
  if (evaluation.run_id !== runId) throw new Error('Evaluation run_id does not match');
  if (!['pass','fail','partial'].includes(evaluation.result)) throw new Error('Evaluation result must be pass, fail or partial');
  if (!['hidden-check','rubric'].includes(evaluation.method)) throw new Error('Evaluation method must be hidden-check or rubric');
  if (record.evaluation.method && evaluation.method !== record.evaluation.method) throw new Error('Evaluation method differs from the prepared protocol');
  for (const key of ['evaluator','check_output']) if (typeof evaluation[key] !== 'string' || !evaluation[key].trim()) throw new Error(`Evaluation requires ${key}`);
  const artifactText = readFileSync(join(dir,'trace/artifacts.json'));
  const current = inventory(join(dir,'artifacts'));
  if (JSON.stringify(current) !== JSON.stringify(JSON.parse(artifactText))) throw new Error('Artifacts changed after execution');
  if (evaluation.artifacts_sha256 !== sha256(artifactText)) throw new Error('Evaluation must bind to SHA-256 of trace/artifacts.json');
  const finalPath = join(dir,'trace/final-workspace.json');
  if (!existsSync(finalPath)) throw new Error('Final workspace manifest is missing');
  const finalText = readFileSync(finalPath);
  if (evaluation.workspace_sha256 !== sha256(finalText)) throw new Error('Evaluation must bind to SHA-256 of trace/final-workspace.json');
  if (JSON.stringify(inventory(join(dir,'workspace'))) !== JSON.stringify(JSON.parse(finalText))) throw new Error('Workspace changed after execution');
  const required = record.task.startsWith('T001') ? ['dossier.md','sources.json'] : record.task.startsWith('T002') ? ['report.md'] : ['ledger.md','ablation-plan.md'];
  if (evaluation.result === 'pass') for (const file of required) if (!current.some(row => row.path === file && row.bytes > 0)) throw new Error(`A pass requires nonempty artifacts/${file}`);
  const lock = join(dir,'.lock'); mkdirSync(lock);
  try {
    const target = join(dir,'trace/evaluation.json');
    writeFileSync(target, evaluationText, { flag: 'wx' });
    record.evaluation = { method: evaluation.method, evaluator: evaluation.evaluator, evidence_path: 'trace/evaluation.json', evidence_sha256: sha256(evaluationText), evaluated_at: new Date().toISOString() };
    record.verdict = { result: evaluation.result, check_output: evaluation.check_output, human_notes: typeof evaluation.human_notes === 'string' ? evaluation.human_notes : '' };
    record.status = 'completed';
    try { writeRun(root, record); } catch (error) { rmSync(target); throw error; }
    return record;
  } finally { rmSync(lock, { recursive: true, force: true }); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const a = args(); options(a, ['run','evaluation'], ['run','evaluation']); const r = judgeRun(process.cwd(), a.run, resolve(a.evaluation)); console.log(`[judge] ${r.run_id}: ${r.verdict.result}`);
});
