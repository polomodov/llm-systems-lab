import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync, chmodSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { LEGACY_TASKS, loadTaskDescriptor, sealedTaskDescriptor, validateTaskDescriptor, agentCwd } from '../scripts/lib/tasks.mjs';
import { createRun } from '../scripts/lib/records.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const descriptor = (over = {}) => ({ schema_version: 1, id: 'T009-fixture-task', agent: 'a9-fixture', workspace: 'repo', branch_prefix: 'fix', evaluation: 'hidden-check', required_artifacts: ['report.md'], network: { connect_domains: [], sources: false }, setup_args: [], ...over });

test('task descriptors reject unknown fields, escaping names and inconsistent combinations', () => {
  assert.equal(validateTaskDescriptor(descriptor(), 'T009-fixture-task').id, 'T009-fixture-task');
  for (const over of [
    { schema_version: 2 }, { id: '../escape' }, { id: 'T009-Fixture' }, { agent: 'janitor' }, { workspace: 'vm' },
    { branch_prefix: 'Fix/x' }, { workspace: 'files', branch_prefix: 'fix' }, { evaluation: 'human' },
    { required_artifacts: [] }, { required_artifacts: ['../x'] }, { required_artifacts: ['a', 'a'] },
    { network: { connect_domains: ['Registry.NPMJS.org'], sources: false } }, { network: { connect_domains: [], sources: true } },
    { network: { connect_domains: ['example.org/path'], sources: false } }, { setup_args: ['model'] }, { extra: true },
  ]) assert.throws(() => validateTaskDescriptor(descriptor(over), 'T009-fixture-task'), JSON.stringify(over));
  assert.throws(() => validateTaskDescriptor(descriptor(), 'T010-other'), /differs from directory/);
  assert.equal(agentCwd(descriptor()), '/workspace/sample');
  assert.equal(agentCwd(descriptor({ workspace: 'files', branch_prefix: null })), '/workspace');
});

test('every task in the catalog has a valid descriptor whose agent exists, and legacy snapshots fall back to built-in descriptions', () => {
  const tasks = readdirSync(join(root, 'tasks')).filter(name => existsSync(join(root, 'tasks', name, 'task.md')));
  assert.ok(tasks.length >= 3);
  for (const id of tasks) {
    const task = loadTaskDescriptor(root, id);
    assert.equal(task.id, id);
    assert.ok(existsSync(join(root, 'agents', task.agent, 'spec.md')), `${id}: agent ${task.agent}`);
  }
  for (const id of Object.keys(LEGACY_TASKS)) validateTaskDescriptor(LEGACY_TASKS[id], id);
  const empty = mkdtempSync(join(tmpdir(), 'harness-tasks-'));
  try {
    mkdirSync(join(empty, 'inputs'), { recursive: true });
    assert.equal(sealedTaskDescriptor(empty, 'T002-repo-janitor').branch_prefix, 'janitor');
    assert.throws(() => sealedTaskDescriptor(empty, 'T009-fixture-task'), /no task.json/);
    assert.throws(() => loadTaskDescriptor(empty, 'T002-repo-janitor/../x'), /Invalid task id/);
  } finally { rmSync(empty, { recursive: true, force: true }); }
});

function fixture(t, task) {
  const directory = mkdtempSync(join(tmpdir(), 'harness-tasks-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  for (const path of ['experiments/claude-code/README.md', 'experiments/claude-code/adapter.mjs', 'experiments/claude-code/harness.json', 'experiments/claude-code/settings.example.json', 'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs', 'results/schema.json']) {
    mkdirSync(dirname(join(directory, path)), { recursive: true });
    copyFileSync(join(root, path), join(directory, path));
  }
  mkdirSync(join(directory, 'scripts/lib'), { recursive: true });
  for (const file of readdirSync(join(root, 'scripts'))) if (file.endsWith('.mjs')) copyFileSync(join(root, 'scripts', file), join(directory, 'scripts', file));
  for (const file of readdirSync(join(root, 'scripts/lib'))) copyFileSync(join(root, 'scripts/lib', file), join(directory, 'scripts/lib', file));
  for (const agent of ['a9-fixture', 'a1-other']) { mkdirSync(join(directory, 'agents', agent), { recursive: true }); writeFileSync(join(directory, 'agents', agent, 'spec.md'), `# ${agent}\n`); }
  const dir = join(directory, 'tasks', task.id); mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'task.md'), `# ${task.id}\n\n## Бюджет\nДо 7 ходов или $1.\n`);
  writeFileSync(join(dir, 'task.json'), JSON.stringify(task));
  const setup = task.workspace === 'repo'
    ? '#!/usr/bin/env bash\nset -e\nmkdir -p "$1/sample" "$1/artifacts"\ncd "$1/sample"\necho hello > file.txt\nexport GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=s GIT_AUTHOR_EMAIL=s@x GIT_COMMITTER_NAME=s GIT_COMMITTER_EMAIL=s@x\ngit -c init.templateDir= init -q --initial-branch=main && git add -A && git -c commit.gpgsign=false commit -qm start\n'
    : '#!/usr/bin/env bash\nset -e\nmkdir -p "$1/artifacts"\necho brief > "$1/brief.md"\n';
  writeFileSync(join(dir, 'setup.sh'), setup); chmodSync(join(dir, 'setup.sh'), 0o755);
  return directory;
}

test('a repo task is prepared with its branch, seed commit, extra egress domain and sealed descriptor', t => {
  const task = descriptor({ network: { connect_domains: ['registry.npmjs.org'], sources: false } });
  const dir = fixture(t, task);
  assert.throws(() => createRun({ root: dir, harness: 'claude-code', agent: 'a1', task: 'T009' }), /expects agent a9-fixture/);
  const record = createRun({ root: dir, harness: 'claude-code', agent: 'a9', task: 'T009' });
  const prepared = prepareRun(dir, record.run_id);
  const run = join(dir, 'results/runs', record.run_id);
  const manifest = JSON.parse(readFileSync(join(run, 'inputs/manifest.json'), 'utf8'));
  assert.match(manifest.seed_commit, /^[a-f0-9]{40}$/);
  assert.equal(manifest.source_mode, 'none');
  assert.ok(manifest.files.some(row => row.path === 'task.json'));
  assert.equal(prepared.evaluation.method, 'hidden-check');
  assert.equal(sealedTaskDescriptor(run, task.id).branch_prefix, 'fix');
  const prompt = readFileSync(join(run, 'inputs/control/prompt.txt'), 'utf8');
  assert.match(prompt, new RegExp(`Работай в ветке fix/${record.run_id}`));
  assert.match(prompt, /Рабочая папка: \/workspace\/sample\./);
  assert.doesNotMatch(prompt, /Сеть источников/);
  const network = JSON.parse(readFileSync(join(run, 'inputs/control/network.json'), 'utf8'));
  assert.ok(network.connect_domains.includes('registry.npmjs.org'));
  assert.deepEqual(network.sources, []);
  assert.throws(() => prepareRun(dir, createRun({ root: dir, harness: 'claude-code', agent: 'a9', task: 'T009' }).run_id, { sourceArchive: join(run, 'inputs/manifest.json') }), /tasks with web sources/);
});

test('a files task is prepared read-only in /workspace without branch or seed commit', t => {
  const task = descriptor({ workspace: 'files', branch_prefix: null, evaluation: 'rubric', required_artifacts: ['normalized.json', 'report.md'] });
  const dir = fixture(t, task);
  const record = createRun({ root: dir, harness: 'claude-code', agent: 'a9', task: 'T009' });
  const prepared = prepareRun(dir, record.run_id);
  const run = join(dir, 'results/runs', record.run_id);
  const manifest = JSON.parse(readFileSync(join(run, 'inputs/manifest.json'), 'utf8'));
  assert.equal(manifest.seed_commit, null);
  assert.equal(prepared.evaluation.method, 'rubric');
  const prompt = readFileSync(join(run, 'inputs/control/prompt.txt'), 'utf8');
  assert.match(prompt, /Рабочая папка: \/workspace\./);
  assert.doesNotMatch(prompt, /Работай в ветке/);
  const network = JSON.parse(readFileSync(join(run, 'inputs/control/network.json'), 'utf8'));
  assert.equal(network.connect_domains.includes('registry.npmjs.org'), false);
  assert.deepEqual(sealedTaskDescriptor(run, task.id).required_artifacts, ['normalized.json', 'report.md']);
});
