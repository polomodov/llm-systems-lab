import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  copyFileSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync,
  readdirSync, rmSync, symlinkSync, writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tasks = {
  T001: 'T001-dossier-from-sources',
  T002: 'T002-repo-janitor',
  T003: 'T003-harness-self-audit',
  T004: 'T004-feature-from-spec',
  T005: 'T005-data-normalization',
  T006: 'T006-security-hardening',
};
const temp = t => {
  const directory = mkdtempSync(join(tmpdir(), 'harness-setup-test-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return directory;
};
const command = (executable, args, options = {}) => {
  const env = { ...(options.env ?? process.env) };
  // A nested Node test runner must not inherit the parent runner's IPC mode.
  delete env.NODE_TEST_CONTEXT;
  return spawnSync(executable, args, { encoding: 'utf8', timeout: 30_000, ...options, env });
};
const setup = (id, destination, args = [], options = {}) => command('bash', [
  join(root, 'tasks', tasks[id], 'setup.sh'), destination, ...args,
], { cwd: tmpdir(), ...options });
const succeeds = result => assert.equal(result.status, 0, result.stderr || result.error?.message);
const fails = result => assert.notEqual(result.status, 0, result.stdout);
const read = (directory, file) => readFileSync(join(directory, file), 'utf8');
const json = (directory, file) => JSON.parse(read(directory, file));
const git = (directory, ...args) => {
  const result = command('git', args, { cwd: directory });
  succeeds(result);
  return result.stdout.trim();
};
const listFiles = (directory, prefix = '') => readdirSync(directory).sort().flatMap(name => {
  const relative = prefix ? `${prefix}/${name}` : name;
  return lstatSync(join(directory, name)).isDirectory()
    ? listFiles(join(directory, name), relative) : [relative];
});

test('T001 fixes a reproducible URL-list snapshot and creates the shared artifacts directory', t => {
  const directory = temp(t);
  const first = join(directory, 'first');
  const second = join(directory, 'second');
  const env = { ...process.env };
  delete env.T001_AS_OF;
  succeeds(setup('T001', first, [], { env }));
  succeeds(setup('T001', second, [], { env }));
  assert.deepEqual(listFiles(first), ['brief.md', 'sources.snapshot.json', 'sources.txt']);
  for (const file of listFiles(first)) assert.equal(read(first, file), read(second, file));
  const snapshot = json(first, 'sources.snapshot.json');
  assert.equal(snapshot.as_of, '2026-09-19');
  assert.equal(snapshot.kind, 'url-list-only');
  assert.equal(snapshot.content_archived, false);
  assert.equal(snapshot.urls.length, 6);
  assert.equal(snapshot.sha256, createHash('sha256').update(read(first, 'sources.txt')).digest('hex'));
  assert.match(read(first, 'brief.md'), /Cutoff date: 2026-09-19/);
  assert.ok(lstatSync(join(first, 'artifacts')).isDirectory());
});

test('T001 accepts explicit or environment cutoff dates and rejects invalid calendar dates before writing', t => {
  const directory = temp(t);
  const env = { ...process.env, T001_AS_OF: '2026-08-01' };
  succeeds(setup('T001', join(directory, 'env'), [], { env }));
  succeeds(setup('T001', join(directory, 'arg'), ['2026-08-02'], { env }));
  assert.equal(json(join(directory, 'env'), 'sources.snapshot.json').as_of, '2026-08-01');
  assert.equal(json(join(directory, 'arg'), 'sources.snapshot.json').as_of, '2026-08-02');
  for (const [index, date] of ['today', '2026-02-30', '2026-13-01'].entries()) {
    const destination = join(directory, `invalid-${index}`);
    fails(setup('T001', destination, [date]));
    assert.equal(existsSync(destination), false);
  }
});

for (const id of Object.keys(tasks)) {
  const args = id === 'T003' ? ['claude-code'] : [];
  test(`${id} requires an explicit destination, accepts an empty directory, and never overwrites a populated one`, t => {
    const directory = temp(t);
    fails(command('bash', [join(root, 'tasks', tasks[id], 'setup.sh')], { cwd: directory }));
    const destination = join(directory, 'workspace with spaces');
    mkdirSync(destination);
    succeeds(setup(id, destination, args));
    writeFileSync(join(destination, 'operator-file'), 'keep me');
    fails(setup(id, destination, args));
    assert.equal(read(destination, 'operator-file'), 'keep me');
  });

  test(`${id} refuses files and symlinks without changing the target`, t => {
    const directory = temp(t);
    const ordinaryFile = join(directory, 'file');
    writeFileSync(ordinaryFile, 'keep');
    fails(setup(id, ordinaryFile, args));
    assert.equal(readFileSync(ordinaryFile, 'utf8'), 'keep');
    const target = join(directory, 'target');
    mkdirSync(target);
    const link = join(directory, 'link');
    symlinkSync(target, link, 'dir');
    fails(setup(id, link, args));
    assert.deepEqual(readdirSync(target), []);
    const dangling = join(directory, 'dangling');
    symlinkSync(join(directory, 'missing'), dangling, 'dir');
    fails(setup(id, dangling, args));
    assert.equal(existsSync(join(directory, 'missing')), false);
  });
}

test('T002 starts on main with the same commit even under different user Git defaults', t => {
  const directory = temp(t);
  const userConfig = join(directory, 'gitconfig');
  writeFileSync(userConfig, '[init]\n  defaultBranch = operator-branch\n[commit]\n  gpgsign = true\n[core]\n  autocrlf = true\n');
  const env = { ...process.env, GIT_CONFIG_GLOBAL: userConfig };
  const first = join(directory, 'first');
  const second = join(directory, 'second');
  succeeds(setup('T002', first, [], { env }));
  succeeds(setup('T002', second));
  assert.equal(git(join(first, 'sample'), 'branch', '--show-current'), 'main');
  assert.equal(git(join(first, 'sample'), 'status', '--porcelain'), '');
  assert.equal(git(join(first, 'sample'), 'rev-parse', 'HEAD'), git(join(second, 'sample'), 'rev-parse', 'HEAD'));
  assert.match(read(join(first, 'sample'), 'brief.md'), /\.\.\/artifacts\/report\.md/);
  assert.ok(lstatSync(join(first, 'artifacts')).isDirectory());
});

test('T002 preserves independent implementation, lint, and dependency defects for the episode', t => {
  const directory = temp(t);
  succeeds(setup('T002', join(directory, 'workspace')));
  const sample = join(directory, 'workspace', 'sample');
  const lint = command(process.execPath, ['scripts/lint.mjs'], { cwd: sample });
  fails(lint);
  assert.match(lint.stderr, /console\.log/);
  assert.match(lint.stderr, /TODO without issue/);
  const tests = command(process.execPath, ['--test', '--test-reporter=tap', 'test/slugify.test.js'], { cwd: sample });
  fails(tests);
  assert.match(tests.stdout, /trims dashes on both ends/);
  assert.match(tests.stdout, /# tests 3/);
  assert.match(tests.stdout, /# fail 1/);
  assert.equal(json(sample, 'package.json').dependencies.lodash, '4.17.15');
});

for (const [harness, active] of [['claude-code', '.claude/settings.json'], ['opencode', 'opencode.json']]) {
  test(`T003 prepares an allowlisted repository and the active ${harness} configuration`, t => {
    const destination = join(temp(t), 'workspace');
    succeeds(setup('T003', destination, [harness]));
    const manifest = json(destination, 'repository.snapshot.json');
    assert.equal(manifest.active_config, active);
    for (const { path, sha256 } of manifest.files) {
      assert.equal(sha256, createHash('sha256').update(readFileSync(join(destination, path))).digest('hex'), path);
    }
    const paths = listFiles(destination);
    assert.ok(paths.includes('docs/method.md'));
    assert.ok(paths.includes('agents/a3-ledger-auditor/spec.md'));
    assert.ok(paths.includes('tasks/T003-harness-self-audit/task.md'));
    assert.ok(paths.includes(active));
    assert.equal(paths.some(path => /(^|\/)(check|results|\.git|\.env)(\/|$)/.test(path)), false);
    assert.equal(read(destination, 'ledger-template.md'), read(destination, 'docs/harness-ledger.md'));
    assert.ok(lstatSync(join(destination, 'artifacts')).isDirectory());
    const settings = json(destination, active);
    for (const groups of Object.values(settings.hooks ?? {})) {
      for (const group of groups) {
        for (const hook of group.hooks ?? []) {
          if (hook.type === 'command') {
            assert.match(hook.command, /^node \/workspace\/\.claude\/hooks\/[^/]+\.mjs$/);
            assert.ok(existsSync(join(destination, hook.command.replace('node /workspace/', ''))));
          }
        }
      }
    }
  });
}

test('T003 rejects traversal and unconfigured harnesses before writing', t => {
  const directory = temp(t);
  for (const [index, harness] of ['../claude-code', 'missing', 'common'].entries()) {
    const destination = join(directory, `workspace-${index}`);
    fails(setup('T003', destination, [harness]));
    assert.equal(existsSync(destination), false);
  }
});

test('T003 ignores added private files and rejects a symlink inside its source allowlist', t => {
  const directory = temp(t);
  const original = join(directory, 'original');
  succeeds(setup('T003', original, ['opencode']));
  const fixture = join(directory, 'source-repository');
  mkdirSync(fixture);
  // Build a synthetic source repository from the already-sanitized snapshot only.
  for (const { path } of json(original, 'repository.snapshot.json').files) {
    mkdirSync(dirname(join(fixture, path)), { recursive: true });
    copyFileSync(join(original, path), join(fixture, path));
  }
  writeFileSync(join(fixture, '.env'), 'SYNTHETIC_TEST_SECRET=not-a-real-credential');
  writeFileSync(join(fixture, 'experiments/opencode/private.json'), '{"synthetic":"private"}');
  const script = join(fixture, 'tasks/T003-harness-self-audit/setup.sh');
  const clean = join(directory, 'clean');
  succeeds(command('bash', [script, clean, 'opencode']));
  assert.equal(existsSync(join(clean, '.env')), false);
  assert.equal(existsSync(join(clean, 'experiments/opencode/private.json')), false);
  rmSync(join(fixture, 'docs/method.md'));
  symlinkSync(join(fixture, '.env'), join(fixture, 'docs/method.md'));
  const refused = join(directory, 'refused');
  fails(command('bash', [script, refused, 'opencode']));
  assert.equal(existsSync(refused), false);
});
