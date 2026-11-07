import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, copyFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRun, writeRun, readRun, METRIC_FIELDS } from '../../../scripts/lib/records.mjs';
import { prepareRun } from '../../../scripts/prepare-run.mjs';
import { copyTree, inventory, sha256 } from '../../../scripts/lib/files.mjs';
import { controlFiles, loadProfile } from '../../../scripts/lib/harnesses.mjs';
import { prepareHandoff, validateVerdict, importVerdict } from './evaluation.mjs';

const repo = fileURLToPath(new URL('../../../', import.meta.url));
const hash = file => sha256(readFileSync(file));
const write = (path, object) => writeFileSync(path, JSON.stringify(object, null, 2) + '\n');

function fixture(t, id) {
  const root = mkdtempSync(join(tmpdir(), 'independent-evaluation-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const task = id === 'T002' ? 'T002-repo-janitor' : 'T004-feature-from-spec';
  const agent = id === 'T002' ? 'a2-janitor' : 'a4-implementer';
  const publicFiles = ['results/schema.json', 'experiments/claude-code/README.md',
    ...controlFiles(loadProfile(repo, 'claude-code')).map(f => 'experiments/claude-code/' + f.source),
    'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs'];
  for (const file of publicFiles) {
    mkdirSync(dirname(join(root, file)), { recursive: true });
    copyFileSync(join(repo, file), join(root, file));
  }
  copyTree(join(repo, 'scripts'), join(root, 'scripts'));
  mkdirSync(join(root, 'agents', agent), { recursive: true });
  writeFileSync(join(root, 'agents', agent, 'spec.md'), '# Synthetic fixture mission\n');
  const episode = join(root, 'tasks', task);
  mkdirSync(episode, { recursive: true });
  writeFileSync(join(episode, 'task.md'), '# Synthetic transport fixture\n\n## Budget\nUp to 30 turns or $2.\n');
  write(join(episode, 'task.json'), { schema_version: 1, id: task, agent, workspace: 'repo',
    branch_prefix: 'fixture', evaluation: 'hidden-check', required_artifacts: ['report.md'],
    network: { connect_domains: [], sources: false }, setup_args: [] });
  writeFileSync(join(episode, 'setup.sh'), '#!/bin/sh\nset -eu\nmkdir -p "$1/sample" "$1/artifacts"\ngit -C "$1/sample" init -q\ngit -C "$1/sample" config user.name fixture\ngit -C "$1/sample" config user.email fixture@example.invalid\nprintf "fixture\\n" > "$1/sample/input.txt"\ngit -C "$1/sample" add .\ngit -C "$1/sample" commit -qm seed\n');
  const record = prepareRun(root, createRun({ root, harness: 'claude-code', agent, task: id }).run_id);
  const dir = join(root, 'results/runs', record.run_id);
  writeFileSync(join(dir, 'workspace/artifacts/report.md'), '# Synthetic result, not task performance\n');
  copyTree(join(dir, 'workspace/artifacts'), join(dir, 'artifacts'));
  write(join(dir, 'trace/artifacts.json'), inventory(join(dir, 'artifacts')));
  write(join(dir, 'trace/final-workspace.json'), inventory(join(dir, 'workspace')));
  record.status = 'awaiting_review';
  record.harness.version = loadProfile(repo, 'claude-code').version;
  record.model = { ...record.model, id: 'fixture-model', observed_id: null, identity_evidence: 'Synthetic transport fixture' };
  record.permissions.mode = 'fixture'; record.sandbox = { kind: 'container', network: 'off' };
  Object.assign(record.execution, { command: ['fixture'], cwd: '/workspace/sample', started_at: '2026-11-07T00:00:00Z',
    finished_at: '2026-11-07T00:00:01Z', exit_code: 0, image_id: 'sha256:' + 'a'.repeat(64),
    timeout_s: 60, network_policy: 'fixture', budget_policy: 'observed' });
  record.loop.budget_usd = 2; record.loop.stop_reason = 'fixture-complete';
  record.metrics_unavailable = Object.fromEntries(METRIC_FIELDS.filter(field => { const [group, key] = field.split('.'); return record[group][key] === null; }).map(field => [field, 'Synthetic fixture; no model calls']));
  record.status = 'running'; writeRun(root, record);
  record.status = 'awaiting_review'; writeRun(root, record);
  const handoff = join(root, 'handoff');
  prepareHandoff(root, record.run_id, handoff, { solverId: 'solving-context', checkerRevision: 'a'.repeat(40) });
  const manifest = JSON.parse(readFileSync(join(handoff, 'submission/manifest.json')));
  const receipt = { ...manifest, submission_manifest_sha256: hash(join(handoff, 'submission/manifest.json')),
    result: 'fail', evaluator: 'independent-context', check_output: 'Synthetic checker verdict; no actual hidden checker read',
    check_command: '["fixture-check"]', check_environment: 'fixture-toolchain', checked_at: '2026-11-07T00:00:02Z',
    network: 'none', independent_context: true, infrastructure_failure: null, source_unchanged: true,
    checker_exit_code: 1, check_package_sha256: 'b'.repeat(64) };
  const evidence = join(root, 'returned-check'); mkdirSync(evidence);
  for (const stream of ['stdout', 'stderr']) {
    writeFileSync(join(evidence, stream + '.txt'), stream === 'stdout' ? 'Synthetic check failed\n' : '');
    receipt[stream + '_sha256'] = hash(join(evidence, stream + '.txt'));
  }
  return { root, dir, record, handoff, receipt, evidence };
}

for (const task of ['T002', 'T004']) test(`${task}: sealed handoff → independently supplied fail → existing judge import`, t => {
  const f = fixture(t, task);
  const before = readFileSync(join(f.dir, 'run.json'));
  assert.doesNotThrow(() => validateVerdict(f.root, f.handoff, f.receipt));
  assert.deepEqual(readFileSync(join(f.dir, 'run.json')), before);
  write(join(f.evidence, 'completed.json'), f.receipt);
  const result = importVerdict(f.root, f.handoff, join(f.evidence, 'completed.json'));
  assert.equal(result.status, 'completed'); assert.equal(result.verdict.result, 'fail');
  assert.match(result.verdict.check_output, /Synthetic check failed/);
  assert.throws(() => importVerdict(f.root, f.handoff, join(f.evidence, 'completed.json')), /awaiting_review/);
});

test('independence, checker revision, infrastructure status and hashes are mandatory', t => {
  const f = fixture(t, 'T002');
  for (const patch of [{ evaluator: 'solving-context' }, { checker_revision: 'c'.repeat(40) },
    { submission_id: 'other' }, { network: 'allowlist' }, { independent_context: false },
    { infrastructure_failure: 'checker-timeout' }, { source_unchanged: false },
    { result: 'pass', checker_exit_code: 1 }, { workspace_sha256: 'd'.repeat(64) }]) {
    assert.throws(() => validateVerdict(f.root, f.handoff, { ...f.receipt, ...patch }));
  }
  assert.equal(readRun(f.root, f.record.run_id).status, 'awaiting_review');
  writeFileSync(join(f.handoff, 'submission/artifacts/report.md'), 'tampered');
  assert.throws(() => validateVerdict(f.root, f.handoff, f.receipt), /Submission changed/);
});

test('changed source and changed returned check logs cannot import a verdict', t => {
  const f = fixture(t, 'T004');
  write(join(f.evidence, 'completed.json'), f.receipt);
  writeFileSync(join(f.evidence, 'stdout.txt'), 'different check output');
  assert.throws(() => importVerdict(f.root, f.handoff, join(f.evidence, 'completed.json')), /log changed/);
  writeFileSync(join(f.dir, 'workspace/artifacts/report.md'), 'source tampering');
  assert.throws(() => validateVerdict(f.root, f.handoff, f.receipt), /workspace changed/i);
});
