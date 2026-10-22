import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createLabReport } from '../scripts/lib/labs.mjs';
import { checkLabReport } from '../scripts/lib/lab-reports.mjs';
import { createRun, METRIC_FIELDS } from '../scripts/lib/records.mjs';
import { sha256 } from '../scripts/lib/files.mjs';

const repo = fileURLToPath(new URL('../', import.meta.url));
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'lab-report-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'docs/labs/templates'), { recursive: true });
  copyFileSync(join(repo, 'docs/labs/catalog.json'), join(root, 'docs/labs/catalog.json'));
  for (const file of ['manifest.json', 'report.md', 'measurements.tsv']) copyFileSync(join(repo, 'docs/labs/templates', file), join(root, 'docs/labs/templates', file));
  const { directory: report } = createLabReport(root, { lab: 'LAB20', session: 'unit-fixture' });
  const dir = join(root, report);
  const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8'));
  const save = () => writeFileSync(join(dir, 'manifest.json'), JSON.stringify(manifest));
  return { root, report, dir, manifest, save };
}
function submission(f) {
  Object.assign(f.manifest, {
    status: 'completed', evidence_class: 'synthetic', operator: 'Fixture reviewer', hypothesis: 'Synthetic coverage fixture',
    protocol_before_run: 'raw/protocol.md', protocol_recorded_at: '2026-09-21T00:00:00.000Z',
    conclusion: 'Infrastructure fixture only; no model evaluation', evidence_files: ['raw/protocol.md', 'raw/review.json'],
    planned_attempts: [{ id: 'sample-01', configuration_id: 'rubric-v1', kind: 'exercise', status: 'completed', run_id: null, evidence_files: ['raw/review.json'], reason: null }],
    unavailable: { ...Object.fromEntries(Object.keys(f.manifest.conditions).map(key => [`conditions.${key}`, 'Offline exercise, not applicable'])), measurements: 'No numeric observations in this fixture' },
  });
  writeFileSync(join(f.dir, 'raw/protocol.md'), 'Synthetic protocol saved before fixture execution.\n');
  writeFileSync(join(f.dir, 'raw/review.json'), '{"evidence_class":"synthetic"}\n');
  f.save();
  return f;
}
const check = f => checkLabReport(f.root, { report: f.report, mode: 'submission' });

test('draft check is read-only and does not mistake an empty template for a submission', t => {
  const f = fixture(t), before = readFileSync(join(f.dir, 'manifest.json'), 'utf8');
  assert.deepEqual(checkLabReport(f.root, { report: f.report }).errors, []);
  assert.ok(check(f).errors.length > 0);
  assert.equal(readFileSync(join(f.dir, 'manifest.json'), 'utf8'), before);
  const result = check(submission(f));
  assert.deepEqual(result.errors, []);
  assert.equal(result.ready_for_review, true);
  assert.equal(result.experiment_pass, null);
  assert.equal(f.manifest.reviewer_decision, null);
});

test('attempt register retains failures and omissions, and rejects unexplained or pending work', t => {
  const f = submission(fixture(t));
  f.manifest.planned_attempts.push({ id: 'sample-02', configuration_id: 'rubric-v1', kind: 'exercise', status: 'failed', run_id: null, evidence_files: ['raw/review.json'], reason: 'Fixture processing failure' });
  f.manifest.planned_attempts.push({ id: 'sample-03', configuration_id: 'rubric-v1', kind: 'exercise', status: 'not-run', run_id: null, evidence_files: [], reason: 'Reviewer unavailable' });
  f.save(); assert.deepEqual(check(f).errors, []);
  f.manifest.planned_attempts[2].reason = null; f.save();
  assert.match(check(f).errors.join('\n'), /omission needs a reason/);
  f.manifest.planned_attempts[2].status = 'planned'; f.save();
  assert.match(check(f).errors.join('\n'), /unresolved planned attempt/);
  f.manifest.planned_attempts[2].status = 'not-run';
  f.manifest.planned_attempts[2].reason = 'Dependency unavailable';
  f.manifest.status = 'blocked'; f.save();
  assert.match(check(f).errors.join('\n'), /unavailable.completion/);
  f.manifest.unavailable.completion = 'Study cannot continue'; f.save();
  assert.equal(check(f).ready_for_review, true);
  assert.equal(check(f).status, 'blocked');
});

test('measurements distinguish measured zero from unknown, reject malformed values and retain evidence', t => {
  const f = submission(fixture(t));
  const header = readFileSync(join(f.dir, 'measurements.tsv'), 'utf8').trimEnd();
  const row = ['obs-01', 'rubric-v1', '', '', '', '', '1', 'disagreements', '0', 'count', 'measured', 'raw/review.json', ''];
  const write = (...rows) => writeFileSync(join(f.dir, 'measurements.tsv'), header + '\n' + rows.map(value => value.join('\t')).join('\n') + '\n');
  write(row); assert.deepEqual(check(f).errors, []);
  row[10] = 'unavailable'; row[12] = 'Not exposed'; write(row);
  assert.match(check(f).errors.join('\n'), /never a fabricated zero/);
  row[8] = ''; write(row); assert.deepEqual(check(f).errors, []);
  row[10] = 'measured'; row[12] = ''; row[8] = '1e999'; write(row);
  assert.match(check(f).errors.join('\n'), /finite decimal/);
  row[8] = '1'; row[11] = 'raw/missing.json'; write(row);
  assert.match(check(f).errors.join('\n'), /absent from evidence_files/);
  row[11] = 'raw/review.json'; write(row, row);
  assert.match(check(f).errors.join('\n'), /duplicate observation_id/);
  row[1] = 'unplanned-configuration'; write(row);
  assert.match(check(f).errors.join('\n'), /absent from attempt register/);
});

test('evidence paths reject symlinks, traversal, missing files, secrets and directories', t => {
  const f = submission(fixture(t));
  for (const path of ['../outside', '/tmp/secret', '.env', 'raw/check/result.json', 'https://example.test/data', 'raw/missing', 'raw']) {
    f.manifest.evidence_files = [path]; f.save();
    assert.ok(check(f).errors.some(error => error.startsWith('evidence_files:')), path);
  }
  symlinkSync(join(f.dir, 'raw/review.json'), join(f.dir, 'raw/link.json'));
  f.manifest.evidence_files = ['raw/link.json']; f.save();
  assert.match(check(f).errors.join('\n'), /Symlinks/);
  assert.throws(() => checkLabReport(f.root, { report: '../escape' }), /Report must/);
});

test('legacy drafts are preserved; synthetic practice files and inconsistent identities cannot be submitted', t => {
  const f = submission(fixture(t));
  f.manifest.schema_version = 1; f.save();
  assert.deepEqual(checkLabReport(f.root, { report: f.report }).errors, []);
  assert.match(check(f).errors.join('\n'), /requires manifest v2/);
  f.manifest.schema_version = 2; f.manifest.session_id = 'different'; f.save();
  assert.match(check(f).errors.join('\n'), /directory differs/);
  f.manifest.kind = 'lab-practice'; f.save();
  assert.throws(() => check(f), /not a practice trace/);
});

function runFixture(f, { status = 'planned', started = false } = {}) {
  for (const [directory, file] of [['experiments/example', 'README.md'], ['agents/a1-fixture', 'spec.md'], ['tasks/T001-fixture', 'task.md']]) {
    mkdirSync(join(f.root, directory), { recursive: true }); writeFileSync(join(f.root, directory, file), 'Public synthetic unit-test fixture only\n');
  }
  const record = createRun({ root: f.root, harness: 'example', agent: 'a1', task: 'T001' });
  const dir = join(f.root, 'results/runs', record.run_id);
  if (status !== 'planned') {
    record.status = status;
    record.loop.stop_reason = 'Synthetic fixture';
    record.verdict.result = status === 'completed' ? 'fail' : status === 'awaiting_review' ? 'pending' : 'aborted';
    if (started) {
      writeFileSync(join(dir, 'artifacts/inputs.json'), '{}');
      record.inputs = { manifest_path: 'artifacts/inputs.json', manifest_sha256: sha256('{}'), prepared_at: '2026-09-21T00:01:00.000Z' };
      record.provenance.runner_version = 'fixture';
      record.provenance.source_revision_reason = 'Temporary unit-test fixture';
      record.harness.version = '1.0.0'; record.model.id = 'fixture-model'; record.model.identity_evidence = 'Synthetic fixture';
      record.permissions.mode = 'fixture'; record.sandbox = { kind: 'container', network: 'off' };
      Object.assign(record.execution, { command: ['fixture'], cwd: '/workspace', started_at: '2026-09-21T00:02:00.000Z', finished_at: '2026-09-21T00:03:00.000Z', exit_code: 0, timeout_s: 60, image_id: 'sha256:' + 'b'.repeat(64), network_policy: 'off', budget_policy: 'observed' });
    }
    if (status === 'completed') {
      writeFileSync(join(dir, 'artifacts/evaluation.txt'), 'Synthetic fail verdict');
      record.metrics_unavailable = Object.fromEntries(METRIC_FIELDS.map(field => [field, 'Synthetic fixture has no model metrics']));
      record.evaluation = { method: 'human', evaluator: 'fixture', evidence_path: 'artifacts/evaluation.txt', evidence_sha256: sha256('Synthetic fail verdict'), evaluated_at: '2026-09-21T00:04:00.000Z' };
      record.verdict.check_output = 'Synthetic fail verdict';
    }
    writeFileSync(join(dir, 'run.json'), JSON.stringify(record));
  }
  f.manifest.evidence_class = 'experimental';
  f.manifest.run_ids = [record.run_id];
  f.manifest.planned_attempts = [{ id: 'agent-01', configuration_id: 'baseline', kind: 'agent-run', status: 'not-run', run_id: record.run_id, evidence_files: [], reason: 'Not executed' }];
  f.save();
  return record;
}

test('run links require records, correct statuses and one-to-one attempt accounting', t => {
  const f = submission(fixture(t));
  const record = runFixture(f);
  f.manifest.status = 'blocked'; f.manifest.unavailable.completion = 'No execution yet'; f.save();
  assert.deepEqual(check(f).errors, []);
  f.manifest.planned_attempts[0].status = 'completed'; f.save();
  assert.match(check(f).errors.join('\n'), /status disagrees/);
  f.manifest.planned_attempts = []; f.save();
  assert.match(check(f).errors.join('\n'), /absent from the attempt register/);
  f.manifest.evidence_class = 'synthetic'; f.save();
  assert.match(check(f).errors.join('\n'), /Only experimental/);
  rmSync(join(f.root, 'results/runs', record.run_id, 'run.json'));
  assert.match(check(f).errors.join('\n'), /cannot read/);
});

test('started failures cannot be relabeled as omissions, and late protocols are rejected', t => {
  const f = submission(fixture(t)); runFixture(f, { status: 'aborted', started: true });
  assert.match(check(f).errors.join('\n'), /started run cannot be omitted/);
  f.manifest.planned_attempts[0].status = 'failed'; f.save(); assert.deepEqual(check(f).errors, []);
  f.manifest.protocol_recorded_at = '2026-09-21T01:00:00.000Z'; f.save();
  assert.match(check(f).errors.join('\n'), /after run/);
  f.manifest.status = 'blocked';
  f.manifest.unavailable.completion = 'Historical run has no pre-registration';
  f.manifest.unavailable.protocol_before_run = 'Protocol reconstructed after the run; cannot support controlled comparison';
  f.save(); assert.deepEqual(check(f).errors, []);
  f.manifest.protocol_recorded_at = null; f.manifest.protocol_before_run = null;
  f.save(); assert.deepEqual(check(f).errors, []);
  f.manifest.status = 'completed'; f.save();
  assert.match(check(f).errors.join('\n'), /protocol_before_run: required/);
});

test('a finished unjudged run is retained as awaiting-review only in a blocked submission', t => {
  const f = submission(fixture(t));
  const record = runFixture(f, { status: 'awaiting_review', started: true });
  const runPath = join(f.root, 'results/runs', record.run_id, 'run.json');
  const before = readFileSync(runPath, 'utf8');
  Object.assign(f.manifest, { status: 'blocked' });
  f.manifest.unavailable.completion = 'Independent verdict is pending';
  Object.assign(f.manifest.planned_attempts[0], { status: 'awaiting-review', reason: 'Execution finished; no independent evaluation yet' });
  const header = readFileSync(join(f.dir, 'measurements.tsv'), 'utf8');
  writeFileSync(join(f.dir, 'measurements.tsv'), header + ['obs-01', 'baseline', '', '', '', '', '1', 'wall-clock', '60', 's', 'measured', 'raw/review.json', ''].join('\t') + '\n');
  f.save();
  assert.deepEqual(check(f).errors, []);
  assert.equal(check(f).ready_for_review, true);
  assert.equal(check(f).experiment_pass, null);
  assert.equal(readFileSync(runPath, 'utf8'), before);
  f.manifest.status = 'completed'; f.save();
  assert.match(check(f).errors.join('\n'), /awaiting-review requires a blocked report/);
  f.manifest.status = 'blocked'; f.manifest.planned_attempts[0].reason = null; f.save();
  assert.match(check(f).errors.join('\n'), /awaiting-review needs a reason/);
  f.manifest.planned_attempts[0].reason = 'Pending';
  f.manifest.planned_attempts[0].status = 'not-run'; f.save();
  assert.match(check(f).errors.join('\n'), /started run cannot be omitted/);
  f.manifest.planned_attempts[0].status = 'completed'; f.save();
  assert.match(check(f).errors.join('\n'), /status disagrees with run record/);
});

test('awaiting-review rejects missing, unstarted, aborted or already judged runs and non-agent attempts', t => {
  for (const status of ['planned', 'aborted', 'completed']) {
    const f = submission(fixture(t));
    runFixture(f, { status, started: status !== 'planned' });
    f.manifest.status = 'blocked'; f.manifest.unavailable.completion = 'Fixture blocker';
    Object.assign(f.manifest.planned_attempts[0], { status: 'awaiting-review', reason: 'Pending' }); f.save();
    assert.match(check(f).errors.join('\n'), /awaiting-review requires a finished run/);
  }
  const f = submission(fixture(t));
  f.manifest.status = 'blocked'; f.manifest.unavailable.completion = 'Fixture blocker';
  Object.assign(f.manifest.planned_attempts[0], { status: 'awaiting-review', reason: 'Pending' }); f.save();
  assert.match(check(f).errors.join('\n'), /awaiting-review is only for agent-run/);
  f.manifest.planned_attempts[0].kind = 'agent-run'; f.manifest.evidence_class = 'experimental'; f.save();
  assert.match(check(f).errors.join('\n'), /missing run record/);
});

test('an unperformed configuration cannot yield measured data or a completed report', t => {
  const f = submission(fixture(t));
  f.manifest.planned_attempts[0].status = 'not-run'; f.manifest.planned_attempts[0].reason = 'Not attempted'; f.save();
  const header = readFileSync(join(f.dir, 'measurements.tsv'), 'utf8');
  writeFileSync(join(f.dir, 'measurements.tsv'), header + ['obs-01', 'rubric-v1', '', '', '', '', '1', 'count', '1', 'count', 'measured', 'raw/review.json', ''].join('\t') + '\n');
  assert.match(check(f).errors.join('\n'), /at least one performed attempt/);
  assert.match(check(f).errors.join('\n'), /measured data requires a performed attempt/);
});

test('UTC timestamps reject impossible calendar dates and local-time ambiguity', t => {
  const f = submission(fixture(t));
  for (const value of ['2026-02-30T00:00:00.000Z', '2026-09-21T00:00:00', '2026-09-21T24:00:00Z']) {
    f.manifest.protocol_recorded_at = value; f.save();
    assert.match(check(f).errors.join('\n'), /Invalid protocol_recorded_at/);
  }
  f.manifest.protocol_recorded_at = '2026-09-21T00:00:00Z'; f.save();
  assert.deepEqual(check(f).errors, []);
});

test('protocol-class preparation retains unstarted run references without claiming execution', t => {
  const f = submission(fixture(t));
  const exercise = structuredClone(f.manifest.planned_attempts[0]);
  runFixture(f);
  f.manifest.evidence_class = 'protocol'; f.manifest.planned_attempts.push(exercise); f.save();
  assert.deepEqual(check(f).errors, []);
  const other = submission(fixture(t)); runFixture(other, { status: 'aborted', started: true });
  other.manifest.evidence_class = 'protocol'; other.manifest.planned_attempts[0].status = 'failed'; other.save();
  assert.match(check(other).errors.join('\n'), /Protocol report cannot contain a started run/);
});

test('independent fail verdict is a valid completed attempt and changed evidence is detected', t => {
  const f = submission(fixture(t)); const record = runFixture(f, { status: 'completed', started: true });
  f.manifest.planned_attempts[0].status = 'completed'; f.manifest.planned_attempts[0].reason = null; f.save();
  assert.deepEqual(check(f).errors, []);
  writeFileSync(join(f.root, 'results/runs', record.run_id, 'artifacts/evaluation.txt'), 'Changed after evaluation');
  assert.match(check(f).errors.join('\n'), /SHA-256 mismatch/);
});

test('CLI returns nonzero for incomplete submissions and rejects unknown options', t => {
  const f = fixture(t), script = join(repo, 'scripts/check-lab.mjs');
  const run = args => spawnSync(process.execPath, [script, '--report', f.report, ...args], { cwd: f.root, encoding: 'utf8' });
  assert.equal(run([]).status, 0);
  const incomplete = run(['--mode', 'submission']);
  assert.equal(incomplete.status, 1);
  assert.equal(JSON.parse(incomplete.stdout).ready_for_review, false);
  assert.equal(run(['--grade', 'pass']).status, 1);
});

test('all Apple labs create compatible drafts and accept honest blocked submissions without run records', t => {
  const f = fixture(t);
  for (let n = 28; n <= 35; n++) {
    const { directory: report } = createLabReport(f.root, { lab: `LAB${n}`, session: 'apple-draft' });
    assert.equal(report, `experiments/local-models/measurements/LAB${n}-apple-draft`);
    assert.deepEqual(checkLabReport(f.root, { report }).errors, []);
    const dir = join(f.root, report);
    const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json')));
    assert.equal(manifest.schema_version, 2);
    assert.equal(manifest.harness_id, null);
    assert.deepEqual(manifest.run_ids, []);
    Object.assign(manifest, {
      status: 'blocked', evidence_class: 'protocol', operator: 'Fixture',
      hypothesis: 'Admission requires hardware evidence', conclusion: 'No experiment was run',
      protocol_before_run: 'raw/protocol.md', protocol_recorded_at: '2026-10-07T00:00:00Z',
      evidence_files: ['raw/protocol.md'],
      planned_attempts: [{ id: 'smoke', configuration_id: 'apple', kind: n === 35 ? 'agent-run' : 'measurement',
        status: 'not-run', run_id: null, evidence_files: [], reason: 'Hardware/bridge unavailable in fixture' }],
      unavailable: {
        completion: 'Hardware/bridge unavailable in fixture', measurements: 'No experiment was run',
        ...Object.fromEntries(Object.keys(manifest.conditions).map(key => [`conditions.${key}`, 'Unavailable in offline fixture'])),
      },
    });
    writeFileSync(join(dir, 'raw/protocol.md'), 'Offline preparation; no inference or agent runs.\n');
    writeFileSync(join(dir, 'manifest.json'), JSON.stringify(manifest));
    const result = checkLabReport(f.root, { report, mode: 'submission' });
    assert.deepEqual(result.errors, [], `LAB${n}`);
    assert.equal(result.ready_for_review, true);
    assert.equal(result.experiment_pass, null);
  }
});
