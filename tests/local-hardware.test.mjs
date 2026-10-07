import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { DEFAULT_HARDWARE, HARDWARE_PROFILES, loadLocalHardware } from '../scripts/lib/local-hardware.mjs';
import { buildLocalPlan, validateLocalPlanData } from '../scripts/lib/local-plan.mjs';
import { buildEnginePlan } from '../scripts/lib/local-engines.mjs';

const repo = fileURLToPath(new URL('../', import.meta.url));
const apple = 'apple-m5-max-128gb-macos';
const models = JSON.parse(readFileSync(join(repo, 'experiments/local-models/models.json')));
const invoke = (root, command, ...flags) => spawnSync(process.execPath,
  [join(repo, `scripts/${command}.mjs`), ...flags], { cwd: root, encoding: 'utf8' });
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'local-hardware-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const dir = join(root, 'experiments/local-models');
  mkdirSync(join(dir, 'apple'), { recursive: true });
  for (const file of ['models.json', 'hardware.json', 'engines.json', 'apple/hardware.json', 'apple/engines.json']) {
    cpSync(join(repo, 'experiments/local-models', file), join(dir, file));
  }
  return { root, dir };
}

test('Apple unknown GPU budget stays null, with explicit override restoring only a planning estimate', () => {
  const { hardware } = loadLocalHardware(repo, apple);
  const before = JSON.stringify(hardware);
  assert.equal(validateLocalPlanData(models, hardware), true);
  const plan = buildLocalPlan(models, hardware);
  assert.equal(plan.budget.memory_gib, 128);
  assert.equal(plan.budget.available_memory_gib, 112);
  assert.equal(plan.budget.gpu_budget_gib, null);
  assert.equal(plan.budget.effective_gib, null);
  for (const row of plan.rows) {
    assert.equal(row.budget_gib, null);
    assert.equal(row.headroom_gib, null);
    assert.equal(row.status, 'hardware-memory-required');
    assert.equal(row.fit_verified, false);
    assert.ok(row.estimates.total_gib > 0);
  }
  const row = plan.rows[0];
  const atBoundary = buildLocalPlan(models, hardware, { model: row.id, gpuBudgetGib: row.estimates.total_gib });
  assert.equal(atBoundary.rows[0].headroom_gib, 0);
  assert.notEqual(atBoundary.rows[0].status, 'hardware-memory-required');
  assert.equal(atBoundary.rows[0].fit_verified, false);
  assert.equal(buildLocalPlan(models, hardware, { model: row.id, gpuBudgetGib: 1 }).rows[0].status, 'over-budget');
  assert.equal(buildLocalPlan(models, hardware, { gpuBudgetGib: 120, memoryGib: 80 }).budget.effective_gib, 64);
  for (const value of [null, 0, -1, NaN, Infinity, '90']) {
    assert.throws(() => buildLocalPlan(models, hardware, { gpuBudgetGib: value }));
  }
  for (const value of [undefined, -1, NaN, Infinity, '90']) {
    assert.throws(() => validateLocalPlanData(models, { ...hardware, gpu_budget_gib: value }));
  }
  assert.equal(JSON.stringify(hardware), before);
});

test('Apple engine matrix keeps artifact and runtime requirements ahead of unknown hardware memory', () => {
  const { hardware, engines } = loadLocalHardware(repo, apple, { engines: true });
  const plan = buildEnginePlan(models, hardware, engines);
  assert.equal(plan.engine_count, 5);
  assert.equal(plan.rows.length, models.models.length * 5);
  for (const row of plan.rows) {
    assert.equal(row.engine.backend, 'metal');
    assert.equal(row.budget_gib, null);
    assert.equal(row.headroom_gib, null);
    assert.equal(row.fit_verified, false);
    if (row.engine.artifact_policy === 'separate-artifact') {
      assert.equal(row.fit_status, 'artifact-required');
      assert.equal(row.artifact, null);
      assert.equal(row.quantization, null);
      assert.equal(row.weights_basis, null);
      assert.deepEqual(row.estimates, { weights_gib: null, runtime_reserve_gib: null, kv_cache_reserve_gib: null, total_gib: null });
    } else if (row.engine.id === 'llama-cpp-metal') {
      assert.equal(row.fit_status, 'hardware-memory-required');
    } else {
      assert.equal(row.fit_status, 'engine-memory-required');
      assert.equal(row.estimates.total_gib, null);
    }
  }
  for (const row of buildEnginePlan(models, hardware, engines, { gpuBudgetGib: 96 }).rows) {
    if (row.engine.artifact_policy === 'separate-artifact') assert.equal(row.estimates.weights_gib, null);
  }
});

test('selectors reject unknown IDs and catalogs with mismatched identity or backend', t => {
  const { root, dir } = fixture(t);
  for (const value of ['unknown', '../apple', '/tmp', '', 'toString', '__proto__', null]) {
    assert.throws(() => loadLocalHardware(root, value), /Unknown hardware/);
  }
  const selected = loadLocalHardware(root, apple, { engines: true });
  const ryzen = loadLocalHardware(root, DEFAULT_HARDWARE, { engines: true });
  assert.throws(() => buildEnginePlan(models, selected.hardware, ryzen.engines), /incompatible/);
  assert.throws(() => buildEnginePlan(models, ryzen.hardware, selected.engines), /incompatible/);
  assert.throws(() => buildEnginePlan(models, selected.hardware, selected.engines, { engine: 'llama-cpp-rocm' }), /Unknown engine.*hardware/);
  writeFileSync(join(dir, 'apple/engines.json'), JSON.stringify(ryzen.engines));
  assert.throws(() => loadLocalHardware(root, apple, { engines: true }), /incompatible/);
  for (const mutation of [{ id: DEFAULT_HARDWARE }, { os: 'linux' }]) {
    writeFileSync(join(dir, 'apple/hardware.json'), JSON.stringify({ ...selected.hardware, ...mutation }));
    assert.throws(() => loadLocalHardware(root, apple), /identity\/OS mismatch/);
  }
});

test('both CLIs select only the requested platform and preserve default Ryzen JSON without writes', t => {
  const { root, dir } = fixture(t);
  const files = readdirSync(dir, { recursive: true }).filter(name => name.endsWith('.json'));
  const before = files.map(file => readFileSync(join(dir, file), 'utf8'));
  for (const id of Object.keys(HARDWARE_PROFILES)) {
    const selected = loadLocalHardware(root, id, { engines: true });
    const list = invoke(root, 'local-engines', '--hardware', id, '--format', 'json');
    assert.equal(list.status, 0, list.stderr);
    assert.deepEqual(new Set(JSON.parse(list.stdout).engines.map(row => row.id)), new Set(selected.engines.engines.map(row => row.id)));
    const result = invoke(root, 'local-plan', '--hardware', id, '--engine', 'all', '--format', 'json');
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), buildEnginePlan(models, selected.hardware, selected.engines));
  }
  const ryzen = loadLocalHardware(root, DEFAULT_HARDWARE, { engines: true });
  const original = invoke(root, 'local-plan', '--format', 'json');
  assert.equal(original.stdout, JSON.stringify(buildLocalPlan(models, ryzen.hardware), null, 2) + '\n');
  assert.equal(invoke(root, 'local-engines', '--format', 'json').stdout,
    invoke(root, 'local-engines', '--hardware', DEFAULT_HARDWARE, '--format', 'json').stdout);
  const table = invoke(root, 'local-plan', '--hardware', apple);
  assert.equal(table.status, 0, table.stderr);
  assert.match(table.stdout, /hardware-memory-required/);
  assert.match(table.stdout, /unknown/);
  const override = invoke(root, 'local-plan', '--hardware', apple, '--gpu-budget-gib', '96', '--format', 'json');
  assert.equal(override.status, 0, override.stderr);
  assert.equal(JSON.parse(override.stdout).budget.effective_gib, 96);
  for (const [command, flags] of [
    ['local-plan', ['--hardware', 'unknown']], ['local-engines', ['--hardware', '../apple']],
    ['local-plan', ['--hardware', apple, '--engine', 'llama-cpp-vulkan']],
    ['local-plan', ['--engine', 'llama-cpp-metal']],
  ]) {
    const result = invoke(root, command, ...flags);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /Unknown hardware|Unknown engine/);
  }
  assert.deepEqual(files.map(file => readFileSync(join(dir, file), 'utf8')), before);
  assert.deepEqual(readdirSync(dir, { recursive: true }).filter(name => name.endsWith('.json')), files);
});
