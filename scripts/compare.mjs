#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { readRun } from './lib/records.mjs';
import { verifyRunIntegrity } from './lib/integrity.mjs';
import { sha256 } from './lib/files.mjs';
import { args, options, main } from './lib/cli.mjs';
export function summarize(root, ids) {
  const dir = join(root,'results/runs');
  const selected = ids ?? (existsSync(dir) ? readdirSync(dir).filter(id => /^\d{4}-/.test(id)) : []);
  const groups = new Map(), pending = [], excluded = [];
  for (const id of selected) {
    const record = readRun(root, id);
    verifyRunIntegrity(root, record);
    if (!['completed','aborted'].includes(record.status)) { pending.push(id); continue; }
    if (!record.inputs.manifest_path) { excluded.push({ run_id: id, reason: 'aborted before input preparation' }); continue; }
    const manifest = JSON.parse(readFileSync(join(dir,id,record.inputs.manifest_path),'utf8'));
    if (!record.execution.started_at) { excluded.push({ run_id: id, reason: 'aborted before execution' }); continue; }
    const inputKey = sha256(JSON.stringify({ contract: manifest.files.filter(row => ['spec.md','task.md','setup.sh'].includes(row.path)), workspace: manifest.workspace.filter(row => !row.path.split('/').includes('.git')), seed_commit: manifest.seed_commit ?? null, source_mode: manifest.source_mode ?? 'none', source_archive_sha256: manifest.source_archive_sha256 ?? null }));
    const conditions = { task: record.task, agent: record.agent, model: record.model.id, provider: record.model.provider, model_selection: record.model.selection, model_lock: record.model.lock, inputs: inputKey, variant: manifest.variant, budget_policy: record.execution.budget_policy, budget_usd: record.loop.budget_usd, timeout_s: record.execution.timeout_s, sandbox: record.sandbox.kind, network: record.sandbox.network, evaluation: record.evaluation.method ?? (record.task.startsWith('T002') ? 'hidden-check' : 'rubric'), source_mode: manifest.source_mode ?? 'none' };
    if(record.model.provider==='local') {conditions.local_inference=record.local_inference.fingerprint;conditions.local_bridge=sha256(JSON.stringify(manifest.files.filter(row=>/^control\/(adapter|run|harness|local-)|^coordinator-common\/local[_-]/.test(row.path))));}
    const key = JSON.stringify(conditions);
    if (!groups.has(key)) groups.set(key,{ conditions, harnesses: new Map() });
    const group = groups.get(key), harnessKey = JSON.stringify([record.harness.name,record.harness.version,record.harness.mode,record.execution.image_id]);
    if (!group.harnesses.has(harnessKey)) group.harnesses.set(harnessKey,{ name: record.harness.name, version: record.harness.version, mode: record.harness.mode, image_id: record.execution.image_id, runs: [] });
    group.harnesses.get(harnessKey).runs.push(record);
  }
  return { pending, excluded, groups: [...groups.values()].map(group => ({ conditions: group.conditions, harnesses: [...group.harnesses.values()].map(h => {
    const runs = h.runs.sort((a,b) => a.run_id.localeCompare(b.run_id));
    const mean = key => { const values = runs.map(r=>r.loop[key]).filter(v=>typeof v==='number'); return { value: values.length ? values.reduce((a,b)=>a+b,0)/values.length : null, measured: values.length, total: runs.length }; };
    const triples = []; for(let i=0;i+2<runs.length;i+=3) { const batch=runs.slice(i,i+3); triples.push({ runs: batch.map(r=>r.run_id), pass_at_3: batch.some(r=>r.verdict.result==='pass'), pass_pow_3: batch.every(r=>r.verdict.result==='pass') }); }
    return { name:h.name,version:h.version,mode:h.mode,image_id:h.image_id,runs:runs.map(r=>({id:r.run_id,result:r.verdict.result})), model_identity_observed:runs.filter(r=>r.model.selection !== 'managed' && r.model.observed_id===r.model.id).length,workspace_available:runs.filter(r=>existsSync(join(dir,r.run_id,'workspace'))).length,pass:runs.filter(r=>r.verdict.result==='pass').length,total:runs.length,mean_cost_usd:mean('cost_usd'),mean_wall_clock_s:mean('wall_clock_s'),triples,unbatched_runs:runs.length%3 };
  }) })) };
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const a=args(); options(a,['runs']); const report=summarize(process.cwd(),a.runs?.split(',')); console.log(JSON.stringify(report,null,2)); if(!report.groups.length) console.error('[compare] No completed experiments or executed failures; no performance claims can be made.');
});
