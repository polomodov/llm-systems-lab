import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRun, readRun, writeRun } from '../scripts/lib/records.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';
import { reconcileRun, orphans, processAlive } from '../scripts/reconcile-run.mjs';
import { captureSources, parseSources } from '../scripts/capture-sources.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const secret = 'sk-ant-synthetic-reconcile-key';
function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'harness-reconcile-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  for (const path of ['tasks/T001-dossier-from-sources/task.md', 'tasks/T001-dossier-from-sources/setup.sh', 'agents/a1-dossier/spec.md', 'experiments/claude-code/README.md', 'experiments/claude-code/adapter.mjs', 'experiments/claude-code/harness.json', 'experiments/claude-code/settings.example.json', 'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs', 'results/schema.json']) {
    mkdirSync(dirname(join(directory, path)), { recursive: true });
    copyFileSync(join(root, path), join(directory, path));
  }
  mkdirSync(join(directory, 'scripts/lib'), { recursive: true });
  for (const file of readdirSync(join(root, 'scripts'))) if (file.endsWith('.mjs')) copyFileSync(join(root, 'scripts', file), join(directory, 'scripts', file));
  for (const file of readdirSync(join(root, 'scripts/lib'))) copyFileSync(join(root, 'scripts/lib', file), join(directory, 'scripts/lib', file));
  writeFileSync(join(directory, '.env'), `ANTHROPIC_API_KEY=${secret}\n`);
  const record = createRun({ root: directory, harness: 'claude-code', agent: 'a1-dossier', task: 'T001' });
  prepareRun(directory, record.run_id);
  return { root: directory, record: readRun(directory, record.run_id), dir: join(directory, 'results/runs', record.run_id) };
}
/** The record a coordinator leaves behind when it is killed between container start and completion. */
function killedCoordinator(f, runtime = true) {
  const record = f.record;
  record.harness.version = '2.1.83'; record.model.id = 'claude-synthetic'; record.model.selection = 'explicit'; record.model.lock = false; record.model.identity_evidence = 'request-only';
  record.permissions = { mode: 'container; headless', blocked: [], asked: null }; record.sandbox = { kind: 'container', network: 'allowlist' };
  record.loop.budget_usd = 3;
  record.metrics_unavailable = { ...record.metrics_unavailable, 'permissions.asked': 'n/a', 'loop.compactions': 'n/a', 'loop.subagents': 'n/a' };
  record.execution = { ...record.execution, command: ['node', '/control/entrypoint.mjs'], cwd: '/workspace', image_id: 'sha256:' + 'a'.repeat(64), proxy_image_id: 'sha256:' + 'b'.repeat(64), timeout_s: 900, network_policy: 'c'.repeat(64), budget_policy: 'hard', started_at: '2026-11-05T10:00:00.000Z', finished_at: null, exit_code: null, signal: null, timed_out: false };
  record.status = 'running';
  writeRun(f.root, record);
  mkdirSync(join(f.dir, '.lock'));
  mkdirSync(join(f.dir, 'trace/network'), { recursive: true });
  writeFileSync(join(f.dir, 'trace/network/sources.jsonl'), JSON.stringify({ type: 'source', requested_url: 'https://a.example/', url: 'https://a.example/', status: 200, content_type: 'text/html', body: `key ${secret}` }) + '\n');
  if (runtime) writeFileSync(join(f.dir, 'trace/runtime.json'), JSON.stringify({ network: 'harness-lab-abc', proxy: 'harness-lab-abc-egress', agent: 'harness-lab-abc-agent', coordinator_pid: 999999, host: 'fixture', started_at: record.execution.started_at }));
  return record;
}
const fakeDocker = (calls, { agentState = 'exited\t137\t2026-11-05T10:05:00Z', proxyMissing = false } = {}) => argv => {
  calls.push(argv);
  if (argv[0] === 'inspect') { if (proxyMissing && argv.at(-1).endsWith('-egress')) return { ok: false, stdout: '', stderr: 'No such object' }; return { ok: true, stdout: (argv.at(-1).endsWith('-agent') ? agentState : 'running\t0\t0001-01-01T00:00:00Z') + '\n', stderr: '' }; }
  if (argv[0] === 'logs') return { ok: true, stdout: `{"type":"assistant","content":"${secret}"}\n`, stderr: 'stderr line\n' };
  return { ok: true, stdout: '', stderr: '' };
};

test('a killed coordinator leaves a running record that reconciliation turns into an aborted one with recovered, redacted evidence', t => {
  const f = fixture(t);
  killedCoordinator(f);
  const calls = [];
  const result = reconcileRun(f.root, f.record.run_id, { docker: fakeDocker(calls), alive: () => false, now: () => new Date('2026-11-05T11:00:00.000Z') });
  const record = readRun(f.root, f.record.run_id);
  assert.equal(record.status, 'aborted');
  assert.equal(record.verdict.result, 'aborted');
  assert.equal(record.loop.stop_reason, 'coordinator_lost');
  assert.equal(record.execution.exit_code, 137);
  assert.equal(record.execution.finished_at, '2026-11-05T11:00:00.000Z');
  assert.match(record.notes, /coordinator_lost/);
  assert.equal(existsSync(join(f.dir, '.lock')), false);
  assert.deepEqual(result.removed.map(c => c.name), ['harness-lab-abc-agent', 'harness-lab-abc-egress']);
  assert.ok(calls.some(c => c[0] === 'rm' && c.includes('harness-lab-abc-agent')));
  assert.ok(calls.some(c => c[0] === 'network' && c[1] === 'rm' && c[2] === 'harness-lab-abc'));
  for (const file of ['trace/recovered-agent.log', 'trace/recovered-proxy.log', 'trace/sources.jsonl', 'trace/reconciliation.json']) {
    const text = readFileSync(join(f.dir, file), 'utf8');
    assert.equal(text.includes(secret), false, file);
  }
  assert.match(readFileSync(join(f.dir, 'trace/recovered-agent.log'), 'utf8'), /\[REDACTED\]/);
  assert.equal(readFileSync(join(f.dir, 'run.json'), 'utf8').includes(secret), false);
  assert.throws(() => reconcileRun(f.root, f.record.run_id, { docker: fakeDocker([]) }), /Only a running record/);
});

test('reconciliation refuses while the recorded coordinator is alive, tolerates missing containers and runs started without runtime names', t => {
  const f = fixture(t);
  killedCoordinator(f);
  assert.throws(() => reconcileRun(f.root, f.record.run_id, { docker: fakeDocker([]), alive: () => true }), /still alive/);
  assert.equal(readRun(f.root, f.record.run_id).status, 'running');
  const later = () => new Date('2026-11-05T11:00:00.000Z');
  const result = reconcileRun(f.root, f.record.run_id, { docker: fakeDocker([], { proxyMissing: true }), alive: () => true, force: true, now: later });
  assert.deepEqual(result.missing, ['harness-lab-abc-egress']);
  const g = fixture(t);
  killedCoordinator(g, false);
  const calls = [];
  const second = reconcileRun(g.root, g.record.run_id, { docker: fakeDocker(calls), now: later });
  assert.equal(second.removed.length, 0);
  assert.equal(calls.length, 0);
  assert.match(readRun(g.root, g.record.run_id).notes, /without trace\/runtime\.json/);
  assert.equal(processAlive(process.pid), true);
  assert.equal(processAlive(0), false);
  const list = orphans(argv => argv[0] === 'ps' ? { ok: true, stdout: 'harness-lab-x-agent\tExited (137)\n', stderr: '' } : { ok: true, stdout: 'harness-lab-x\n', stderr: '' });
  assert.deepEqual(list, { containers: [{ name: 'harness-lab-x-agent', status: 'Exited (137)' }], networks: ['harness-lab-x'], error: null });
});

test('source capture archives initial URLs through the task setup, records failures and never overwrites an archive', async t => {
  const f = fixture(t);
  const seen = [];
  const fetcher = async url => { seen.push(url); if (url.includes('metr.org')) throw new Error('synthetic timeout'); return { url, status: 200, content_type: 'text/html', body: `<p>${url}</p>` }; };
  const result = await captureSources(f.root, { task: 'T001-dossier-from-sources', asOf: '2026-11-05', fetcher, now: () => new Date('2026-11-05T12:00:00.000Z') });
  assert.equal(result.fetched, 5);
  assert.equal(result.failed.length, 1);
  assert.equal(seen.length, 6);
  const archive = readFileSync(result.archive, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert.equal(archive.length, 5);
  assert.ok(archive.every(row => row.type === 'source' && row.fetched_at === '2026-11-05T12:00:00.000Z'));
  const manifest = JSON.parse(readFileSync(result.manifest, 'utf8'));
  assert.equal(manifest.sources, 6); assert.equal(manifest.failed[0].url.includes('metr.org'), true); assert.equal(manifest.depth, 0);
  const record = createRun({ root: f.root, harness: 'claude-code', agent: 'a1-dossier', task: 'T001' });
  const prepared = prepareRun(f.root, record.run_id, { asOf: '2026-11-05', sourceArchive: result.archive });
  assert.equal(JSON.parse(readFileSync(join(f.root, 'results/runs', prepared.run_id, 'inputs/manifest.json'), 'utf8')).source_mode, 'replay');
  await assert.rejects(captureSources(f.root, { task: 'T001-dossier-from-sources', asOf: '2026-11-05', fetcher }), /never overwritten/);
  await assert.rejects(captureSources(f.root, { task: 'T001-dossier-from-sources', asOf: 'today', fetcher }), /calendar date/);
  await assert.rejects(captureSources(f.root, { task: 'T001-dossier-from-sources', asOf: '2026-11-06', fetcher: async () => { throw new Error('offline'); } }), /No source was fetched/);
  assert.equal(existsSync(join(f.root, 'tasks/T001-dossier-from-sources/archive/sources-2026-11-06.jsonl')), false);
  assert.deepEqual(parseSources('https://a.example/x  # note\n\nhttps://a.example/x\nhttps://b.example/#frag\n'), ['https://a.example/x', 'https://b.example/']);
});
