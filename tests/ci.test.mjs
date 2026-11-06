import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { changedFiles, plan, planChanges, validateImageVersion } from '../.github/scripts/harness-ci.mjs';
import { harnessIds } from '../scripts/lib/pins.mjs';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ids = harnessIds(repository);

test('CI limits PR images to changed harnesses and skips documentation-only images', () => {
  const report = planChanges(ids, 'pull_request', ['experiments/pi/run.mjs', 'experiments/amp/Dockerfile', 'experiments/codex/README.md']);
  assert.deepEqual(report.matrix.include, [{ harness: 'amp' }, { harness: 'pi' }]);
  assert.equal(report.docker, 'true');
  const docs = ['README.md', 'docs/roadmap.md', 'experiments/pi/README.md', 'experiments/pi/measurements/observed.json'];
  assert.deepEqual(planChanges(ids, 'pull_request', docs), { matrix: { include: [] }, 'has-images': 'false', docker: 'false' });
  assert.equal(planChanges(ids, 'push', docs).docker, 'true');
});

test('CI rebuilds every harness for shared infrastructure, manual and scheduled runs', () => {
  for (const path of ['.github/workflows/ci.yml', '.github/scripts/harness-ci.mjs', 'scripts/run.mjs', 'tests/docker.test.mjs', 'experiments/common/local-broker.mjs', 'package.json', 'mise.toml', '.mise.toml', 'mise.lock']) {
    const report = planChanges(ids, 'pull_request', [path]);
    assert.equal(report.matrix.include.length, ids.length, path);
    assert.equal(report.docker, 'true');
  }
  for (const event of ['workflow_dispatch', 'schedule']) {
    const report = plan(repository, { GITHUB_EVENT_NAME: event });
    assert.deepEqual(report.matrix.include.map(row => row.harness), ids);
    assert.equal(report['has-images'], 'true');
  }
  assert.throws(() => plan(repository, { GITHUB_EVENT_NAME: 'pull_request_target' }), /Unsupported CI event/);
});

function temporary(t) {
  const dir = mkdtempSync(join(tmpdir(), 'harness-ci-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function git(root, argv) {
  const result = spawnSync('git', argv, {
    cwd: root, encoding: 'utf8', env: { ...process.env, GIT_AUTHOR_NAME: 'CI fixture', GIT_AUTHOR_EMAIL: 'ci@example.invalid', GIT_COMMITTER_NAME: 'CI fixture', GIT_COMMITTER_EMAIL: 'ci@example.invalid' },
  });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}

test('CI diff handles renamed/deleted inputs and fails closed for unavailable commits', t => {
  const root = temporary(t);
  git(root, ['init', '--quiet']);
  mkdirSync(join(root, 'experiments/pi'), { recursive: true });
  writeFileSync(join(root, 'experiments/pi/Dockerfile'), 'FROM example\n');
  git(root, ['add', '.']);
  git(root, ['commit', '--quiet', '-m', 'base']);
  const base = git(root, ['rev-parse', 'HEAD']);
  git(root, ['mv', 'experiments/pi/Dockerfile', 'experiments/pi/README.md']);
  git(root, ['commit', '--quiet', '-m', 'rename']);
  const head = git(root, ['rev-parse', 'HEAD']);
  const files = changedFiles(root, base, head);
  assert.deepEqual(files, ['experiments/pi/Dockerfile', 'experiments/pi/README.md']);
  assert.deepEqual(planChanges(ids, 'pull_request', files).matrix.include, [{ harness: 'pi' }]);
  assert.throws(() => changedFiles(root, '--output=/tmp/unwanted', head), /full commit SHAs/);
  assert.throws(() => changedFiles(root, 'f'.repeat(40), head), /git rev-parse failed/);
  assert.throws(() => plan(repository, { GITHUB_EVENT_NAME: 'pull_request' }), /full commit SHAs/);
  const firstPush = plan(repository, { GITHUB_EVENT_NAME: 'push', CI_BASE_SHA: '0'.repeat(40), CI_HEAD_SHA: git(repository, ['rev-parse', 'HEAD']) });
  assert.equal(firstPush.matrix.include.length, ids.length);
});

test('CI checks every harness after a force push without requiring the old history', () => {
  const env = {
    GITHUB_EVENT_NAME: 'push',
    CI_BASE_SHA: 'f'.repeat(40),
    CI_HEAD_SHA: git(repository, ['rev-parse', 'HEAD']),
  };
  assert.deepEqual(plan(repository, { ...env, CI_FORCE_PUSH: 'true' }), {
    matrix: { include: ids.map(harness => ({ harness })) }, 'has-images': 'true', docker: 'true',
  });
  assert.throws(() => plan(repository, env), /git rev-parse failed/);
  assert.throws(() => plan(repository, { ...env, CI_FORCE_PUSH: 'true', CI_HEAD_SHA: 'f'.repeat(40) }), /git rev-parse failed/);
  assert.throws(() => plan(repository, { ...env, GITHUB_EVENT_NAME: 'pull_request', CI_FORCE_PUSH: 'true' }), /git rev-parse failed/);
});

test('CI version smoke rejects missing/mismatched pins including similar release prefixes', () => {
  assert.equal(validateImageVersion('2.1.83 (Claude Code)', '2.1.83'), '2.1.83');
  assert.equal(validateImageVersion('Amp CLI 0.0.1789920039-gafe14b', '0.0.1789920039-gafe14b'), '0.0.1789920039-gafe14b');
  for (const output of ['', 'latest', '2.1.830', '2.1.83-beta', '2.1.84', 'x'.repeat(301)]) {
    assert.throws(() => validateImageVersion(output, '2.1.83'), /invalid version|exact version|profile pins/);
  }
});

test('CI PR selection excludes changes made only on the base branch', t => {
  const root = temporary(t);
  git(root, ['init', '--quiet', '--initial-branch=main']);
  mkdirSync(join(root, 'experiments/pi'), { recursive: true });
  writeFileSync(join(root, 'experiments/pi/harness.json'), readFileSync(join(repository, 'experiments/pi/harness.json')));
  writeFileSync(join(root, 'README.md'), 'base\n');
  git(root, ['add', '.']);
  git(root, ['commit', '--quiet', '-m', 'base']);
  git(root, ['checkout', '--quiet', '-b', 'feature']);
  writeFileSync(join(root, 'README.md'), 'feature documentation\n');
  git(root, ['commit', '--quiet', '-am', 'feature docs']);
  const head = git(root, ['rev-parse', 'HEAD']);
  git(root, ['checkout', '--quiet', 'main']);
  mkdirSync(join(root, 'scripts'));
  writeFileSync(join(root, 'scripts/run.mjs'), '// unrelated main change\n');
  git(root, ['add', '.']);
  git(root, ['commit', '--quiet', '-m', 'main runner change']);
  const base = git(root, ['rev-parse', 'HEAD']);
  assert.deepEqual(changedFiles(root, base, head, { mergeBase: true }), ['README.md']);
  assert.deepEqual(changedFiles(root, base, head), ['README.md', 'scripts/run.mjs']);
  const env = { CI_BASE_SHA: base, CI_HEAD_SHA: head };
  assert.deepEqual(plan(root, { ...env, GITHUB_EVENT_NAME: 'pull_request' }), {
    matrix: { include: [] }, 'has-images': 'false', docker: 'false',
  });
  assert.equal(plan(root, { ...env, GITHUB_EVENT_NAME: 'push' })['has-images'], 'true');
});

test('CI smoke executes the profile command offline and cleans up even on version mismatch', t => {
  const dir = temporary(t);
  const bin = join(dir, 'docker');
  const log = join(dir, 'calls.jsonl');
  writeFileSync(bin, `#!${process.execPath}\nimport fs from 'node:fs';\nconst args = process.argv.slice(2);\nfs.appendFileSync(process.env.CI_TEST_CALLS, JSON.stringify(args) + '\\n');\nif (args[0] === 'image') console.log('sha256:' + 'a'.repeat(64));\nif (args[0] === 'run') console.log(process.env.CI_TEST_VERSION);\n`);
  chmodSync(bin, 0o755);
  // Расширение отсутствует у исполняемого mock docker; package.json задаёт ESM для Node 22.
  writeFileSync(join(dir, 'package.json'), '{"type":"module"}');
  for (const version of ['0.73.1', '0.73.2']) {
    writeFileSync(log, '');
    const result = spawnSync(process.execPath, ['.github/scripts/harness-ci.mjs', 'smoke', 'pi'], {
      cwd: repository, encoding: 'utf8', env: { ...process.env, PATH: `${dir}:${process.env.PATH}`, CI_TEST_CALLS: log, CI_TEST_VERSION: version },
    });
    assert.equal(result.status, version === '0.73.1' ? 0 : 1, result.stderr);
    const calls = readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line));
    const run = calls.find(args => args[0] === 'run');
    assert.equal(run[run.indexOf('--network') + 1], 'none');
    assert.equal(run[run.indexOf('--user') + 1], '1000:1000');
    assert.equal(run[run.indexOf('--entrypoint') + 1], 'node');
    assert.equal(run.at(-1), "require('/opt/pi/node_modules/@mariozechner/pi-coding-agent/package.json').version");
    assert.ok(!run.includes('--env-file'));
    assert.deepEqual(run.flatMap((arg, i) => arg === '--env' ? [run[i + 1]] : []), ['HOME=/tmp']);
    assert.deepEqual(calls.at(-1), ['rm', '--force', run[run.indexOf('--name') + 1]]);
  }
});
