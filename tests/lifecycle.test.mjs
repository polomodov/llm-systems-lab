import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRun, readRun, writeRun, METRIC_FIELDS } from '../scripts/lib/records.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';
import { judgeRun } from '../scripts/judge-run.mjs';
import { summarize } from '../scripts/compare.mjs';
import { copyTree, inventory, sha256 } from '../scripts/lib/files.mjs';
import { verifyRunIntegrity } from '../scripts/lib/integrity.mjs';
import { verifyInputs } from '../scripts/run.mjs';

const repository = fileURLToPath(new URL('../', import.meta.url));

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'harness-lifecycle-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  // Only explicit public inputs are copied; hidden checks are never inspected.
  for (const path of ['docs/harness-ledger.md', 'agents/a2-janitor/spec.md', 'tasks/T002-repo-janitor/task.md', 'tasks/T002-repo-janitor/setup.sh', 'experiments/claude-code/README.md', 'experiments/claude-code/settings.example.json', 'experiments/claude-code/adapter.mjs', 'experiments/claude-code/harness.json', 'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs']) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    copyFileSync(join(repository, path), join(root, path));
  }
  copyTree(join(repository, 'scripts'), join(root, 'scripts'));
  mkdirSync(join(root, 'results'));
  copyFileSync(join(repository, 'results/schema.json'), join(root, 'results/schema.json'));
  return root;
}

function prepared(root, options) {
  const record = createRun({ root, harness: 'claude-code', agent: 'a2', task: 'T002' });
  return prepareRun(root, record.run_id, options);
}

function syntheticExecution(root, record, { aborted = false, observed = true } = {}) {
  // This is runner plumbing evidence in an ephemeral fixture, never an agent experiment.
  const dir = join(root, 'results/runs', record.run_id);
  record.harness.version = 'fixture-1.0.0';
  record.model = { ...record.model, id: 'synthetic-model-2026-09-20', observed_id: observed ? 'synthetic-model-2026-09-20' : null, identity_evidence: observed ? 'fixture trace' : 'request-only' };
  record.permissions.mode = 'fixture';
  record.sandbox = { kind: 'container', network: 'allowlist' };
  record.loop.budget_usd = 2;
  record.execution = { ...record.execution, command: ['fixture'], cwd: '/workspace/sample', started_at: '2026-09-20T12:00:00.000Z', image_id: 'sha256:' + 'c'.repeat(64), timeout_s: 60, network_policy: 'fixture', budget_policy: 'hard' };
  record.status = 'running';
  writeRun(root, record);
  writeFileSync(join(dir, 'workspace/artifacts/report.md'), '# Синтетический отчёт\nПроверка только инфраструктуры.\n');
  const rows = copyTree(join(dir, 'workspace/artifacts'), join(dir, 'artifacts'));
  writeFileSync(join(dir, 'trace/artifacts.json'), JSON.stringify(rows, null, 2) + '\n');
  writeFileSync(join(dir, 'trace/final-workspace.json'), JSON.stringify(inventory(join(dir, 'workspace')), null, 2) + '\n');
  record.loop.wall_clock_s = 1;
  record.loop.cost_usd = 0;
  record.loop.stop_reason = aborted ? 'fixture timeout' : 'fixture completed';
  record.metrics_unavailable = Object.fromEntries(METRIC_FIELDS.filter(field => {
    const [group, key] = field.split('.');
    return record[group][key] === null;
  }).map(field => [field, 'Synthetic fixture exposes no provider measurement']));
  record.execution.finished_at = '2026-09-20T12:00:01.000Z';
  record.execution.exit_code = aborted ? 137 : 0;
  record.status = aborted ? 'aborted' : 'awaiting_review';
  record.verdict.result = aborted ? 'aborted' : 'pending';
  return writeRun(root, record);
}

function evaluation(root, record, overrides = {}) {
  const dir = join(root, 'results/runs', record.run_id);
  const path = join(root, `${record.run_id}-evaluation.json`);
  writeFileSync(path, JSON.stringify({ run_id: record.run_id, result: 'pass', method: 'hidden-check', evaluator: 'synthetic-fixture', check_output: 'Synthetic verdict; no hidden check was executed', artifacts_sha256: sha256(readFileSync(join(dir, 'trace/artifacts.json'))), workspace_sha256: sha256(readFileSync(join(dir, 'trace/final-workspace.json'))), ...overrides }));
  return path;
}

test('public setup → sealed inputs → synthetic execution → external verdict → comparison works', t => {
  const root = fixture(t);
  const initial = prepared(root);
  assert.equal(initial.status, 'prepared');
  assert.equal(initial.provenance.git_commit, null);
  assert.match(initial.provenance.source_revision_reason, /not a Git checkout/);
  const before = readFileSync(join(root, 'results/runs', initial.run_id, initial.inputs.manifest_path), 'utf8');
  assert.throws(() => prepareRun(root, initial.run_id), /Only planned/);
  const executed = syntheticExecution(root, initial);
  assert.equal(executed.verdict.result, 'pending');
  const result = judgeRun(root, executed.run_id, evaluation(root, executed));
  assert.equal(result.status, 'completed');
  assert.equal(readRun(root, result.run_id).verdict.result, 'pass');
  assert.equal(readFileSync(join(root, 'results/runs', initial.run_id, initial.inputs.manifest_path), 'utf8'), before);
  const report = summarize(root);
  assert.equal(report.groups.length, 1);
  const harness = report.groups[0].harnesses[0];
  assert.equal(harness.pass, 1);
  assert.equal(harness.total, 1);
  assert.equal(harness.mean_cost_usd.value, 0);
  assert.equal(harness.triples.length, 0);
  assert.equal(harness.unbatched_runs, 1);
  assert.throws(() => judgeRun(root, result.run_id, evaluation(root, result)), /Only awaiting_review/);
});

test('judge rejects wrong run, unbound evidence and modified outputs without completing record', t => {
  const root = fixture(t);
  const record = syntheticExecution(root, prepared(root));
  assert.throws(() => judgeRun(root, record.run_id, evaluation(root, record, { run_id: 'other' })), /run_id does not match/);
  assert.throws(() => judgeRun(root, record.run_id, evaluation(root, record, { artifacts_sha256: '0'.repeat(64) })), /bind to SHA-256/);
  const path = evaluation(root, record);
  writeFileSync(join(root, 'results/runs', record.run_id, 'artifacts/report.md'), '# Changed\n');
  assert.throws(() => judgeRun(root, record.run_id, path), /Artifacts changed/);
  assert.equal(readRun(root, record.run_id).status, 'awaiting_review');
});

test('judge rejects modified sealed control inputs independently of manifest hash', t => {
  const root = fixture(t);
  const record = syntheticExecution(root, prepared(root));
  const path = evaluation(root, record);
  writeFileSync(join(root, 'results/runs', record.run_id, 'inputs/control/prompt.txt'), 'tampered prompt');
  assert.throws(() => judgeRun(root, record.run_id, path), /Sealed input snapshot was modified/);
  assert.equal(readRun(root, record.run_id).status, 'awaiting_review');
});

test('repeated setup has stable comparable input hashes while ablation gets a separate group', t => {
  const root = fixture(t);
  for (const variant of ['baseline', 'baseline', 'without-spec']) {
    const record = syntheticExecution(root, prepared(root, { variant }));
    judgeRun(root, record.run_id, evaluation(root, record));
  }
  const report = summarize(root);
  assert.equal(report.groups.length, 2);
  assert.deepEqual(report.groups.map(group => group.harnesses[0].total).sort(), [1, 2]);
  assert.deepEqual(new Set(report.groups.map(group => group.conditions.variant)), new Set(['baseline', 'without-spec']));
});

test('executed aborts remain in the pass denominator and triples even without observed model identity', t => {
  const root = fixture(t);
  for (const result of ['pass', 'fail', 'aborted']) {
    const record = syntheticExecution(root, prepared(root), { aborted: result === 'aborted', observed: result !== 'aborted' });
    if (result !== 'aborted') judgeRun(root, record.run_id, evaluation(root, record, { result }));
  }
  const report = summarize(root);
  assert.equal(report.groups.length, 1, 'Aborts must not form a separate evaluation/model-coverage cohort');
  const harness = report.groups[0].harnesses[0];
  assert.equal(harness.pass, 1);
  assert.equal(harness.total, 3);
  assert.equal(harness.triples.length, 1);
  assert.equal(harness.triples[0].pass_at_3, true);
  assert.equal(harness.triples[0].pass_pow_3, false);
});

test('completed evidence remains sealed when later checked or compared', t => {
  const root = fixture(t);
  const record = syntheticExecution(root, prepared(root));
  const completed = judgeRun(root, record.run_id, evaluation(root, record));
  const dir = join(root, 'results/runs', record.run_id);
  const check = () => spawnSync(process.execPath, [join(repository, 'scripts/check.mjs')], { cwd: root, encoding: 'utf8' });
  assert.equal(check().status, 0);
  for (const path of ['inputs/control/prompt.txt', 'artifacts/report.md', 'workspace/artifacts/report.md', 'trace/artifacts.json', 'trace/final-workspace.json']) {
    const file = join(dir, path);
    const original = readFileSync(file);
    try {
      writeFileSync(file, `${original.toString('utf8')}\n`);
      assert.throws(() => verifyRunIntegrity(root, completed), /Run integrity/);
      assert.throws(() => summarize(root), /Run integrity/);
      const result = check();
      assert.equal(result.status, 1, path);
      assert.match(result.stderr, /Run integrity/);
      assert.match(result.stdout, /completed=0/);
    } finally { writeFileSync(file, original); }
  }
  assert.equal(check().status, 0);
  assert.equal(summarize(root).groups[0].harnesses[0].total, 1);
});

test('integrity catches changed prepared workspace and mismatched recorded verdict', t => {
  const root = fixture(t);
  const record = prepared(root);
  const workspaceFile = join(root, 'results/runs', record.run_id, 'workspace/sample/brief.md');
  const original = readFileSync(workspaceFile);
  writeFileSync(workspaceFile, 'changed starting inputs');
  assert.throws(() => summarize(root), /prepared workspace changed/);
  writeFileSync(workspaceFile, original);
  const finished = syntheticExecution(root, record);
  const completed = judgeRun(root, record.run_id, evaluation(root, finished));
  completed.verdict.result = 'fail';
  assert.throws(() => verifyRunIntegrity(root, completed), /sealed evaluation differs/);
});

test('prepared archives validate sealed inputs without ignored workspace while execution still requires the live tree', t => {
  const root = fixture(t);
  const record = prepared(root);
  const dir = join(root, 'results/runs', record.run_id);
  const check = () => spawnSync(process.execPath, [join(repository, 'scripts/check.mjs')], { cwd: root, encoding: 'utf8' });
  const workspaceFile = join(dir, 'workspace/sample/brief.md');
  const originalWorkspace = readFileSync(workspaceFile);
  writeFileSync(workspaceFile, 'tampered starting tree');
  assert.throws(() => verifyRunIntegrity(root, record), /prepared workspace changed/);
  assert.equal(check().status, 1);
  writeFileSync(workspaceFile, originalWorkspace);

  rmSync(join(dir, 'workspace'), { recursive: true });
  writeFileSync(join(dir, 'trace/.gitkeep'), '');
  assert.doesNotThrow(() => verifyRunIntegrity(root, record));
  const archived = check();
  assert.equal(archived.status, 0, archived.stderr);
  assert.match(archived.stdout, /prepared\/pending/);
  assert.match(archived.stdout, /workspace отсутствует; архив prepared проверен по sealed inputs; запуск требует live tree/);
  assert.throws(() => verifyInputs(dir, record), /ENOENT/);
  assert.equal(readRun(root, record.run_id).status, 'prepared');

  const sealedFile = join(dir, 'inputs/control/prompt.txt');
  const originalInput = readFileSync(sealedFile);
  writeFileSync(sealedFile, 'tampered sealed input');
  assert.throws(() => verifyRunIntegrity(root, record), /sealed input snapshot changed/);
  assert.equal(check().status, 1);
  writeFileSync(sealedFile, originalInput);
  const manifestFile = join(dir, record.inputs.manifest_path);
  const originalManifest = readFileSync(manifestFile);
  writeFileSync(manifestFile, originalManifest.toString('utf8') + '\n');
  assert.throws(() => verifyRunIntegrity(root, record), /input manifest SHA-256 mismatch/);
  assert.equal(check().status, 1);
  writeFileSync(manifestFile, originalManifest);

  symlinkSync(join(dir, 'missing-tree'), join(dir, 'workspace'));
  assert.throws(() => verifyRunIntegrity(root, record), /symlink is not accepted: workspace/);
  assert.equal(check().status, 1);
  rmSync(join(dir, 'workspace'));
  writeFileSync(join(dir, 'workspace'), 'not a directory');
  assert.throws(() => verifyRunIntegrity(root, record), /expected directory: workspace/);
  assert.equal(check().status, 1);
});

test('completed archives remain verifiable without ignored workspace but reject modified manifests and workspace symlinks', t => {
  const root = fixture(t);
  const record = syntheticExecution(root, prepared(root));
  const completed = judgeRun(root, record.run_id, evaluation(root, record));
  const dir = join(root, 'results/runs', record.run_id);
  assert.equal(summarize(root).groups[0].harnesses[0].workspace_available, 1);
  rmSync(join(dir, 'workspace'), { recursive: true });
  assert.doesNotThrow(() => verifyRunIntegrity(root, completed));
  const report = summarize(root);
  assert.equal(report.groups[0].harnesses[0].workspace_available, 0);
  assert.equal(report.groups[0].harnesses[0].pass, 1);
  const check = () => spawnSync(process.execPath, [join(repository, 'scripts/check.mjs')], { cwd: root, encoding: 'utf8' });
  const archive = check();
  assert.equal(archive.status, 0, archive.stderr);
  assert.match(archive.stdout, /workspace отсутствует; архив проверен без live tree/);
  const final = join(dir, 'trace/final-workspace.json');
  const original = readFileSync(final);
  writeFileSync(final, `${original.toString('utf8')}\n`);
  assert.throws(() => summarize(root), /differs from sealed evaluation/);
  assert.equal(check().status, 1);
  writeFileSync(final, original);
  symlinkSync(join(dir, 'missing-tree'), join(dir, 'workspace'));
  assert.throws(() => summarize(root), /symlink is not accepted: workspace/);
  assert.equal(check().status, 1);
});
