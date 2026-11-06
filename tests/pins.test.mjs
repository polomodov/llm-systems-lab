import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { auditPins, harnessIds } from '../scripts/lib/pins.mjs';
import { validateProfile } from '../scripts/lib/harnesses.mjs';
import { taskLimits } from '../scripts/lib/contracts.mjs';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/** Minimal root with one harness: the audit checks only the profiles it finds. */
function fixture(t, id = 'claude-code') {
  const root = mkdtempSync(join(tmpdir(), 'harness-pins-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const path of ['README.md', 'docs/harnesses.md', `experiments/${id}/harness.json`, `experiments/${id}/Dockerfile`, `experiments/${id}/README.md`]) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    copyFileSync(join(repository, path), join(root, path));
  }
  return root;
}

test('the repository pins every harness identically in profile, Dockerfile and documentation', () => {
  const result = auditPins(repository);
  assert.deepEqual(result.errors, []);
  assert.equal(result.ids.length, harnessIds(repository).length);
  assert.ok(result.ids.includes('claude-code'));
  for (const id of result.ids) assert.match(JSON.parse(readFileSync(join(repository, 'experiments', id, 'harness.json'), 'utf8')).version, /^\d+\.\d+\.\d+/);
});

test('a pin that drifts in one place is reported, not silently accepted', t => {
  const docker = fixture(t);
  const dockerfile = join(docker, 'experiments/claude-code/Dockerfile');
  writeFileSync(dockerfile, readFileSync(dockerfile, 'utf8').replace('RUN test "$HARNESS_VERSION" = "2.1.83"', 'RUN test -n "$HARNESS_VERSION"'));
  assert.deepEqual(auditPins(docker).errors, ['claude-code: Dockerfile must assert the pinned 2.1.83']);

  const profile = fixture(t);
  const file = join(profile, 'experiments/claude-code/harness.json');
  writeFileSync(file, readFileSync(file, 'utf8').replace('"version": "2.1.83"', '"version": "2.1.84"'));
  const errors = auditPins(profile).errors;
  assert.equal(errors.length, 5, errors.join('; '));
  for (const place of ['Dockerfile must default', 'Dockerfile must assert', 'README.md must show', 'docs/harnesses.md row', 'experiments/claude-code/README.md']) {
    assert.ok(errors.some(error => error.includes(place)), `${place} not reported: ${errors.join('; ')}`);
  }
});

test('a harness profile without an exact version pin is invalid', () => {
  const profile = JSON.parse(readFileSync(join(repository, 'experiments/claude-code/harness.json'), 'utf8'));
  assert.equal(validateProfile({ ...profile }, 'claude-code').version, '2.1.83');
  for (const version of [undefined, null, '', 'latest', '2.1', 'v2.1.83', '2.1.83 (Claude Code)', 2]) {
    assert.throws(() => validateProfile({ ...profile, version }, 'claude-code'), /exact version pin/, String(version));
  }
});

test('task budgets are read from the contracts, not from the runner', () => {
  const contract = id => readFileSync(join(repository, 'tasks', id, 'task.md'), 'utf8');
  assert.deepEqual(taskLimits(contract('T001-dossier-from-sources')), { turns: 40, budget: 3 });
  assert.deepEqual(taskLimits(contract('T002-repo-janitor')), { turns: 30, budget: 2 });
  assert.deepEqual(taskLimits(contract('T003-harness-self-audit')), { turns: 20, budget: 1 });
  // Original sealed Russian contracts remain readable.
  assert.deepEqual(taskLimits('## Бюджет\nДо 7 ходов или $0,5 стоимости.\n'), { turns: 7, budget: 0.5 });
  assert.deepEqual(taskLimits('## Budget\nUp to 7 turns or $0.5 in cost.\n'), { turns: 7, budget: 0.5 });
});

test('an unreadable or ambiguous budget stops the run instead of falling back to a default', () => {
  for (const [contract, expected] of [
    ['', /empty/],
    ['# T\n\nNo budget specified.\n', /Budget/],
    ['## Budget\nThe operator will decide.\n', /exactly once/],
    ['## Budget\nUp to 5 turns or $1.\nUp to 9 turns or $2.\n', /exactly once/],
    ['## Budget\nUp to 0 turns or $1.\n', /turn limit/],
    ['## Budget\nUp to 5000 turns or $1.\n', /turn limit/],
    ['## Budget\nUp to 5 turns or $0.\n', /USD limit/],
    ['## Budget\nUp to 5 turns or $9999.\n', /USD limit/],
  ]) assert.throws(() => taskLimits(contract), expected, JSON.stringify(contract));
  // Read the budget only from its own section, never from neighboring text.
  assert.throws(() => taskLimits('## Budget\nSee below.\n\n## Evaluation\nUp to 5 turns or $1.\n'), /exactly once/);
});
