#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { readRun } from './lib/records.mjs';
import { verifyRunIntegrity } from './lib/integrity.mjs';
import { sha256 } from './lib/files.mjs';
import { args, options, main } from './lib/cli.mjs';
import { sealedTaskDescriptor } from './lib/tasks.mjs';
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
    const inputKey = sha256(JSON.stringify({ contract: manifest.files.filter(row => ['spec.md','task.md','task.json','setup.sh'].includes(row.path)), workspace: manifest.workspace.filter(row => !row.path.split('/').includes('.git')), seed_commit: manifest.seed_commit ?? null, source_mode: manifest.source_mode ?? 'none', source_archive_sha256: manifest.source_archive_sha256 ?? null }));
    const conditions = { task: record.task, agent: record.agent, model: record.model.id, provider: record.model.provider, model_selection: record.model.selection, model_lock: record.model.lock, inputs: inputKey, variant: manifest.variant, budget_policy: record.execution.budget_policy, budget_usd: record.loop.budget_usd, timeout_s: record.execution.timeout_s, sandbox: record.sandbox.kind, network: record.sandbox.network, evaluation: record.evaluation.method ?? sealedTaskDescriptor(join(dir,id), record.task).evaluation, source_mode: manifest.source_mode ?? 'none' };
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
/** Human-readable report. It repeats the JSON facts and adds no ranking: groups are only comparable inside themselves. */
export function renderMarkdown(report, { generatedAt = new Date().toISOString() } = {}) {
  const fmt = m => m.value === null ? `— (${m.measured}/${m.total})` : `${Math.round(m.value * 100) / 100} (${m.measured}/${m.total})`;
  const lines = ['# Сравнение прогонов', '', `Сформировано: ${generatedAt}. Группа = одинаковые условия (задача, агент, модель, входы, вариант, бюджет, сеть, оценка); сравнивать можно только внутри группы. Числа — наши измерения по указанным run ID; неизвестные метрики показаны прочерком с долей измеренных прогонов.`, ''];
  if (!report.groups.length) lines.push('Нет завершённых или исполненных прогонов: утверждения о производительности невозможны.', '');
  for (const [index, group] of report.groups.entries()) {
    const c = group.conditions;
    lines.push(`## Группа ${index + 1}: ${c.task} · ${c.agent} · ${c.model ?? 'модель не задана'}`, '', `- Провайдер: ${c.provider}; выбор модели: ${c.model_selection}; lock: ${c.model_lock}`, `- Вариант: ${c.variant}; бюджет: ${c.budget_usd ?? '—'} USD (${c.budget_policy}); таймаут: ${c.timeout_s} с`, `- Песочница: ${c.sandbox}/${c.network}; оценка: ${c.evaluation}; источники: ${c.source_mode}`, `- Входы: \`${c.inputs.slice(0, 12)}\``, '', '| Обвязка | Версия | Образ | Прогоны | pass | pass@3 / pass^3 по тройкам | Средняя стоимость, USD | Среднее время, с | Модель подтверждена |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- |');
    for (const h of group.harnesses) {
      const triples = h.triples.length ? h.triples.map(t => `${t.pass_at_3 ? '✔' : '✖'}/${t.pass_pow_3 ? '✔' : '✖'}`).join(', ') + (h.unbatched_runs ? ` (+${h.unbatched_runs} вне троек)` : '') : `нет полных троек (${h.total})`;
      lines.push(`| ${h.name} | ${h.version ?? '—'} | \`${(h.image_id ?? '').slice(7, 19) || '—'}\` | ${h.runs.map(r => `${r.id} (${r.result})`).join('<br>')} | ${h.pass}/${h.total} | ${triples} | ${fmt(h.mean_cost_usd)} | ${fmt(h.mean_wall_clock_s)} | ${h.model_identity_observed}/${h.total} |`);
    }
    lines.push('');
  }
  if (report.pending.length) lines.push(`Не завершены (planned/prepared/running/awaiting_review): ${report.pending.join(', ')}.`, '');
  if (report.excluded.length) lines.push('Исключены:', ...report.excluded.map(x => `- ${x.run_id}: ${x.reason}`), '');
  return lines.join('\n');
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const a=args(); options(a,['runs','out','format']);
  const format = a.format ?? (a.out?.endsWith('.md') ? 'markdown' : 'json');
  if (!['json','markdown'].includes(format)) throw new Error('--format must be json or markdown');
  const report=summarize(process.cwd(),a.runs?.split(','));
  const text = format === 'markdown' ? renderMarkdown(report) : JSON.stringify(report,null,2);
  if (a.out) {
    const target = resolve(process.cwd(), a.out);
    if (!target.startsWith(process.cwd() + '/') || target.startsWith(join(process.cwd(), 'results/runs') + '/')) throw new Error('--out must stay inside the repository and outside results/runs');
    mkdirSync(dirname(target), { recursive: true }); writeFileSync(target, text + '\n'); console.log(`[compare] ${format} report written to ${a.out}`);
  } else console.log(text);
  if(!report.groups.length) console.error('[compare] No completed experiments or executed failures; no performance claims can be made.');
});
