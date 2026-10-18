import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createLabReport, loadLabCatalog, validateLabCatalog } from '../scripts/lib/labs.mjs';

const repository = fileURLToPath(new URL('../', import.meta.url));
const catalog = () => ({ schema_version: 1, updated_at: '2026-09-21', labs: [
  { id: 'LAB01', title: 'Синтетическое задание', file: 'LAB01-fixture.md', kind: 'foundation', readiness: 'available', prerequisites: [], effort: '1 час' },
  { id: 'LAB02', title: 'Синтетическое продолжение', file: 'LAB02-fixture.md', kind: 'measurement', readiness: 'target-machine', prerequisites: ['LAB01'], effort: '2 часа' },
] });
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'lab-course-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'docs/labs/templates'), { recursive: true });
  writeFileSync(join(root, 'docs/labs/catalog.json'), JSON.stringify(catalog()));
  for (const name of ['report.md', 'manifest.json', 'measurements.tsv']) copyFileSync(join(repository, 'docs/labs/templates', name), join(root, 'docs/labs/templates', name));
  return root;
}

test('course prerequisites cannot contain missing works, cycles or escaping file paths', () => {
  assert.equal(validateLabCatalog(catalog()).labs.length, 2);
  for (const mutate of [
    value => value.labs[0].prerequisites.push('LAB02'),
    value => value.labs[0].prerequisites.push('LAB99'),
    value => value.labs[0].prerequisites.push('LAB01'),
    value => value.labs.push({ ...value.labs[0] }),
    value => { value.labs[0].file = '../README.md'; },
    value => { value.updated_at = '2026-02-30'; },
    value => { value.labs[0].harness = '../escape'; },
    value => { value.labs[0].harness = 'pi'; },
    value => { value.require_harness_coverage = 'yes'; },
    value => { for (const lab of value.labs) Object.assign(lab, { kind: 'agent', harness: 'pi' }); },
    value => { value.labs[1].area = '../escape'; },
    value => { value.labs[1].area = 'local-models'; },
    value => { Object.assign(value.labs[1], { kind: 'agent', harness: 'pi', area: 'space' }); },
  ]) { const value = catalog(); mutate(value); assert.throws(() => validateLabCatalog(value)); }
});

function harnessFixture(root) {
  const value = catalog();
  value.labs.push({ id: 'LAB11', title: 'Harness fixture', file: 'LAB11-pi.md', kind: 'agent', harness: 'pi', readiness: 'available', prerequisites: ['LAB01'], effort: '2 часа' });
  mkdirSync(join(root, 'experiments/pi'), { recursive: true });
  copyFileSync(join(repository, 'experiments/pi/harness.json'), join(root, 'experiments/pi/harness.json'));
  writeFileSync(join(root, 'docs/labs/catalog.json'), JSON.stringify(value));
  return value;
}

test('harness reports are routed to their own directory and preserve old common reports', t => {
  const root = fixture(t);
  harnessFixture(root);
  const common = createLabReport(root, { lab: 'LAB01', session: 'same-session' });
  const harness = createLabReport(root, { lab: 'LAB11', session: 'same-session' });
  assert.equal(common.directory, 'experiments/local-models/measurements/LAB01-same-session');
  assert.equal(harness.directory, 'experiments/pi/measurements/LAB11-same-session');
  const manifest = JSON.parse(readFileSync(join(root, harness.directory, 'manifest.json')));
  assert.equal(manifest.harness_id, 'pi');
  assert.equal(manifest.status, 'not-started');
  assert.deepEqual(manifest.run_ids, []);
  assert.equal(existsSync(join(root, 'results')), false);
  assert.throws(() => createLabReport(root, { lab: 'LAB11', session: 'same-session' }), /EEXIST/);
  rmSync(join(root, 'experiments/pi/harness.json'));
  assert.throws(() => createLabReport(root, { lab: 'LAB11', session: 'missing-profile' }), /ENOENT/);
  assert.equal(existsSync(join(root, 'experiments/pi/measurements/LAB11-missing-profile')), false);
});

test('area reports are routed to the area directory without a harness identity', t => {
  const root = fixture(t);
  const value = catalog();
  value.labs[1].area = 'space';
  writeFileSync(join(root, 'docs/labs/catalog.json'), JSON.stringify(value));
  const report = createLabReport(root, { lab: 'LAB02', session: 'ryzen-01' });
  assert.equal(report.directory, 'experiments/space/measurements/LAB02-ryzen-01');
  assert.equal(JSON.parse(readFileSync(join(root, report.directory, 'manifest.json'))).harness_id, null);
  assert.equal(createLabReport(root, { lab: 'LAB01', session: 'ryzen-01' }).directory, 'experiments/local-models/measurements/LAB01-ryzen-01');
});

test('course coverage rejects an omitted harness or a lab pointing to an unknown harness', t => {
  const root = fixture(t);
  const value = harnessFixture(root);
  value.require_harness_coverage = true;
  writeFileSync(join(root, 'experiments/README.md'), 'Not a harness directory');
  for (const lab of value.labs) copyFileSync(join(repository, 'docs/labs/LAB01-reproducibility.md'), join(root, 'docs/labs', lab.file));
  const save = () => writeFileSync(join(root, 'docs/labs/catalog.json'), JSON.stringify(value));
  save();
  assert.equal(loadLabCatalog(root, { checkDocuments: true }).labs.length, 3);
  const ownLab = value.labs.pop();
  save();
  assert.throws(() => loadLabCatalog(root, { checkDocuments: true }), /Missing laboratory for harness: pi/);
  value.labs.push({ ...ownLab, harness: 'not-installed' });
  save();
  assert.throws(() => loadLabCatalog(root, { checkDocuments: true }), /ENOENT/);
});

test('new coursework is a blank draft and never creates experimental run records', t => {
  const root = fixture(t);
  const result = createLabReport(root, { lab: 'LAB01', session: 'first-pass' });
  const dir = join(root, result.directory);
  assert.equal(result.status, 'not-started');
  assert.deepEqual(readdirSync(dir).sort(), ['manifest.json', 'measurements.tsv', 'raw', 'report.md']);
  const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8'));
  assert.equal(manifest.kind, 'lab-report');
  assert.equal(manifest.status, 'not-started');
  assert.equal(manifest.conclusion, null);
  assert.equal(manifest.reviewer_decision, null);
  assert.deepEqual(manifest.run_ids, []);
  assert.equal(existsSync(join(root, 'results')), false);
  assert.equal(readFileSync(join(dir, 'measurements.tsv'), 'utf8').trim().split('\n').length, 1);
  assert.doesNotMatch(readFileSync(join(dir, 'report.md'), 'utf8'), /\{\{[A-Z_]+\}\}/);
});

test('existing student work and symlink destinations are never overwritten', t => {
  const root = fixture(t);
  const first = createLabReport(root, { lab: 'LAB01', session: 'existing' });
  const file = join(root, first.directory, 'report.md');
  writeFileSync(file, 'student observations');
  assert.throws(() => createLabReport(root, { lab: 'LAB01', session: 'existing' }), /EEXIST/);
  assert.equal(readFileSync(file, 'utf8'), 'student observations');
  const outside = mkdtempSync(join(tmpdir(), 'lab-outside-'));
  t.after(() => rmSync(outside, { recursive: true, force: true }));
  symlinkSync(outside, join(root, 'experiments/local-models/measurements/LAB01-linked'));
  assert.throws(() => createLabReport(root, { lab: 'LAB01', session: 'linked' }), /Symlinks/);
  assert.deepEqual(readdirSync(outside), []);
});

test('invalid requests and missing inputs do not leave partially initialized reports', t => {
  const root = fixture(t);
  for (const request of [
    { lab: 'LAB99', session: 'valid' }, { lab: 'LAB01', session: '../escape' },
    { lab: 'LAB01', session: '/tmp/report' }, { lab: 'LAB01', session: 'Uppercase' },
    { lab: 'LAB01', session: 'a'.repeat(65) },
  ]) assert.throws(() => createLabReport(root, request));
  rmSync(join(root, 'docs/labs/templates/report.md'));
  assert.throws(() => createLabReport(root, { lab: 'LAB01', session: 'missing-template' }));
  assert.equal(existsSync(join(root, 'experiments')), false);
});

test('CLI writes only the requested report and document checks detect unfinished manuals', t => {
  const root = fixture(t);
  const script = join(repository, 'scripts/new-lab.mjs');
  const result = spawnSync(process.execPath, [script, '--lab', 'LAB01', '--session', 'cli-session'], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /not-started/);
  const unknown = spawnSync(process.execPath, [script, '--lab', 'LAB01', '--session', 'second', '--run', 'true'], { cwd: root, encoding: 'utf8' });
  assert.equal(unknown.status, 1);
  assert.equal(existsSync(join(root, 'experiments/local-models/measurements/LAB01-second')), false);
  writeFileSync(join(root, 'docs/labs/LAB01-fixture.md'), '# Incomplete\n');
  assert.throws(() => loadLabCatalog(root, { checkDocuments: true }), /missing section/);
});

test('alternative prerequisites are validated, traversed for cycles and displayed as an OR route', () => {
  const value = catalog();
  value.labs[1].prerequisites = [];
  value.labs[1].prerequisites_any = ['LAB01'];
  assert.equal(validateLabCatalog(value), value);
  for (const alternatives of [[], null, 'LAB01', ['LAB01', 'LAB01'], ['LAB99'], ['LAB02']]) {
    const bad = structuredClone(value);
    bad.labs[1].prerequisites_any = alternatives;
    assert.throws(() => validateLabCatalog(bad));
  }
  const cycle = structuredClone(value);
  cycle.labs[0].prerequisites_any = ['LAB02'];
  assert.throws(() => validateLabCatalog(cycle), /Cyclic/);
  const duplicate = structuredClone(value);
  duplicate.labs[1].prerequisites = ['LAB01'];
  assert.throws(() => validateLabCatalog(duplicate), /alternative prerequisites/);
  const actual = loadLabCatalog(repository, { checkDocuments: true });
  assert.equal(actual.labs.length, 47);
  assert.ok(actual.labs.filter(lab => lab.area === 'space').every(lab => !lab.harness && /^LAB(3[6-9]|4[0-2])$/.test(lab.id)));
  assert.ok(actual.labs.filter(lab => lab.area === 'k8s-gpu').every(lab => !lab.harness && /^LAB4[3-7]$/.test(lab.id)));
  assert.deepEqual(actual.labs.find(lab => lab.id === 'LAB08').prerequisites, ['LAB01']);
  assert.deepEqual(actual.labs.find(lab => lab.id === 'LAB08').prerequisites_any, ['LAB05', 'LAB32']);
  assert.deepEqual(actual.labs.find(lab => lab.id === 'LAB32').prerequisites_any, ['LAB30', 'LAB31']);
  const cli = spawnSync(process.execPath, [join(repository, 'scripts/labs.mjs')], { cwd: repository, encoding: 'utf8' });
  assert.equal(cli.status, 0, cli.stderr);
  assert.match(cli.stdout, /LAB05 или LAB32/);
});
