#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync, rmSync, copyFileSync, renameSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { readRun, writeRun } from './lib/records.mjs';
import { inventory, copyTree, sha256, safePath, acquireLock } from './lib/files.mjs';
import { replayFetcher } from '../experiments/common/egress.mjs';
import { loadProfile, selectProvider, controlFiles } from './lib/harnesses.mjs';
import { args, options, main } from './lib/cli.mjs';
export function prepareRun(root, runId, { variant = 'baseline', asOf, sourceArchive, provider } = {}) {
  const record = readRun(root, runId), dir = join(root, 'results/runs', runId);
  if (record.status !== 'planned') throw new Error('Only planned runs may be prepared; create a new run to replay');
  if (!['baseline', 'without-spec'].includes(variant)) throw new Error('Variant must be baseline or without-spec');
  const expectedAgent = { T001: 'a1-dossier', T002: 'a2-janitor', T003: 'a3-ledger-auditor' }[record.task.slice(0,4)];
  if (!expectedAgent || record.agent !== expectedAgent) throw new Error('Agent does not match the task contract');
  const profile = loadProfile(root, record.harness.name);
  const selectedProvider = selectProvider(profile, provider ?? record.model.provider);
  if (record.model.provider && record.model.provider !== selectedProvider.name) throw new Error('Provider differs from the planned run');
  const lock = acquireLock(dir);
  const staging = join(dir, '.preparing');
  try {
    if (existsSync(staging) || existsSync(join(dir, 'inputs'))) throw new Error('Preparation already has partial files; inspect before retrying');
    const workspace = join(dir, 'workspace');
    if (existsSync(workspace) && readdirSync(workspace).some(x => x !== '.gitkeep')) throw new Error('Workspace is not empty');
    mkdirSync(staging); const stagedWorkspace = join(staging, 'workspace');
    const setup = join(root, 'tasks', record.task, 'setup.sh');
    const setupArgs = [setup, stagedWorkspace];
    if (record.task.startsWith('T003')) setupArgs.push(record.harness.name);
    if (record.task.startsWith('T001')) setupArgs.push(asOf ?? record.date);
    const result = spawnSync('bash', setupArgs, { cwd: root, encoding: 'utf8', env: { PATH: process.env.PATH, HOME: process.env.HOME, LC_ALL: 'C', GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' } });
    if (result.status !== 0) throw new Error(`Setup failed: ${result.stderr || result.error?.message || result.status}`);
    mkdirSync(join(stagedWorkspace, 'artifacts'), { recursive: true });
    const inputs = join(staging, 'inputs'), control = join(inputs, 'control'); mkdirSync(control, { recursive: true });
    const spec = readFileSync(join(root, 'agents', record.agent, 'spec.md'), 'utf8');
    const contract = readFileSync(join(root, 'tasks', record.task, 'task.md'), 'utf8');
    writeFileSync(join(inputs, 'spec.md'), spec); writeFileSync(join(inputs, 'task.md'), contract); copyFileSync(setup, join(inputs, 'setup.sh'));
    const harness = join(root, 'experiments', record.harness.name);
    for (const file of controlFiles(profile)) { mkdirSync(dirname(join(control, file.target)), { recursive: true }); copyFileSync(safePath(harness, file.source), join(control, file.target)); }
    for (const file of ['entrypoint.mjs','egress.mjs']) copyFileSync(join(root, 'experiments/common', file), join(control, file));
    const agentCwd = record.task.startsWith('T002') ? '/workspace/sample' : '/workspace';
    const extra = record.task.startsWith('T001') ? '\nСеть источников: только GET через gateway. Для каждого URL используй curl --noproxy egress --get --data-urlencode "url=URL" http://egress:8080/fetch. JSON содержит реальный status, final url и body. Начальные ссылки и ссылки глубины 1 разрешены; прочие запрещены. Снимки ответов сохраняет координатор. Не считай HTTP 4xx/5xx успешно полученным источником.' : '';
    const prompt = `${variant === 'baseline' ? spec + '\n\n' : ''}${contract}\n\nРабочая папка: ${agentCwd}. Входы: brief.md${record.task.startsWith('T001') ? ' и sources.txt' : ''}. Все итоговые артефакты писать в /workspace/artifacts/. Run-id: ${runId}. ${record.task.startsWith('T002') ? `Работай в ветке janitor/${runId}.` : ''}${extra}\n`;
    writeFileSync(join(control, 'prompt.txt'), prompt);
    const sources = record.task.startsWith('T001') ? readFileSync(join(stagedWorkspace, 'sources.txt'), 'utf8').split('\n').map(x => x.replace(/\s+#.*$/, '').trim()).filter(Boolean) : [];
    writeFileSync(join(control, 'network.json'), JSON.stringify({ connect_domains: [...new Set([...selectedProvider.connect_domains, ...(record.task.startsWith('T002') ? ['registry.npmjs.org'] : [])])], sources }, null, 2) + '\n');
    if (sourceArchive && !record.task.startsWith('T001')) throw new Error('Source archives apply only to T001');
    if (sourceArchive) {
      const archive = readFileSync(sourceArchive, 'utf8');
      replayFetcher(archive); // Validate once before sealing; live fetch fallback is never allowed.
      writeFileSync(join(control, 'sources.replay.jsonl'), archive);
    }
    const seedCommit = record.task.startsWith('T002') ? spawnSync('git', ['-C', join(stagedWorkspace, 'sample'), 'rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim() : null;
    const coordinator = join(inputs, 'coordinator'); mkdirSync(coordinator);
    for (const file of ['prepare-run.mjs','run.mjs','judge-run.mjs','compare.mjs']) copyFileSync(join(root, 'scripts', file), join(coordinator, file));
    copyTree(join(root, 'scripts/lib'), join(coordinator, 'lib'));
    copyFileSync(join(root, 'results/schema.json'), join(coordinator, 'schema.json'));
    const manifest = { version: 1, seed_commit: seedCommit, source_mode: record.task.startsWith('T001') ? (sourceArchive ? 'replay' : 'live') : 'none', source_archive_sha256: sourceArchive ? sha256(readFileSync(sourceArchive)) : null, task: record.task, harness: record.harness.name, provider: selectedProvider.name, model_policy: profile.model_policy, variant, files: inventory(inputs), workspace: inventory(stagedWorkspace) };
    const manifestText = JSON.stringify(manifest, null, 2) + '\n'; writeFileSync(join(inputs, 'manifest.json'), manifestText);
    const git = (...argv) => spawnSync('git', argv, { cwd: root, encoding: 'utf8' });
    const revision = git('rev-parse','HEAD');
    record.inputs = { manifest_path: 'inputs/manifest.json', manifest_sha256: sha256(manifestText), prepared_at: new Date().toISOString() };
    record.provenance = { ...record.provenance, git_commit: revision.status === 0 ? revision.stdout.trim() : null, git_dirty: revision.status === 0 ? !!git('status','--porcelain').stdout.trim() : null, runner_version: '1', source_revision_reason: revision.status === 0 ? null : 'Source tree is not a Git checkout' };
    record.harness_changes = [
      { component: 'Docker workspace isolation', kind: 'walls', ledger: 'L003' },
      { component: `Input snapshot; variant=${variant}`, kind: 'words', ledger: 'L004' },
      { component: 'Recorded lifecycle and validation', kind: 'walls', ledger: 'L005' },
      { component: 'External evaluation', kind: 'walls', ledger: 'L006' },
      { component: 'Task-scoped egress gateway', kind: 'walls', ledger: 'L007' },
      { component: 'Sealed provider profile, credentials and model selection policy', kind: 'walls', ledger: 'L016' },
      { component: 'Pinned CLI adapter and explicit configuration', kind: 'words', ledger: profile.ledger },
    ];
    record.model.provider = selectedProvider.name;
    record.model.selection = profile.model_policy;
    record.model.lock = profile.model_policy === 'managed';
    record.evaluation.method = record.task.startsWith('T002') ? 'hidden-check' : 'rubric';
    record.status = 'prepared';
    if (existsSync(workspace)) rmSync(workspace, { recursive: true });
    renameSync(stagedWorkspace, workspace); renameSync(inputs, join(dir, 'inputs'));
    try { writeRun(root, record); } catch (error) { rmSync(join(dir, 'inputs'), { recursive: true, force: true }); rmSync(workspace, { recursive: true, force: true }); mkdirSync(workspace); throw error; }
    return record;
  } finally { rmSync(staging, { recursive: true, force: true }); rmSync(lock, { recursive: true, force: true }); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => { const a = args(); options(a, ['run','variant','as-of','source-archive','provider'], ['run']); const r = prepareRun(process.cwd(), a.run, { variant: a.variant, asOf: a['as-of'], sourceArchive: a['source-archive'], provider: a.provider }); console.log(`[prepare] ${r.run_id}: ${r.status}`); });
