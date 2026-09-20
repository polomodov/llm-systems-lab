import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { buildLocalPlan, validateLocalPlanData } from '../scripts/lib/local-plan.mjs';

const cli = fileURLToPath(new URL('../scripts/local-plan.mjs', import.meta.url));
const fixture = () => ({
  catalog: {
    schema_version: 1,
    as_of: '2026-09-20',
    models: [
      { id: 'large', model_id: 'Example/Large', priority: 3, architecture: 'moe', parameters_total_b: 200, parameters_active_b: 10, quantization: 'Q4_K_M', weights_gib_estimate: 90, weights_basis: 'Synthetic estimate', context_tokens: [8192, 16384, 32768], sources: ['https://example.com/large'], fit: 'candidate', reason: 'Synthetic model' },
      { id: 'small', model_id: 'Example/Small', priority: 1, architecture: 'dense', parameters_total_b: 50, parameters_active_b: 50, quantization: 'Q4_K_M', weights_gib_estimate: 32, weights_basis: 'Synthetic estimate', context_tokens: [8192, 16384, 32768], sources: ['https://example.com/small'], fit: 'candidate', reason: 'Synthetic model' },
      { id: 'conditional', model_id: 'Example/Conditional', priority: 2, architecture: 'hybrid-moe', parameters_total_b: 100, parameters_active_b: 5, quantization: 'Q4_K_M', weights_gib_estimate: 48, weights_basis: 'Synthetic estimate', context_tokens: [8192, 16384, 32768], sources: ['https://example.com/conditional'], fit: 'conditional', reason: 'Backend support unverified' },
    ],
  },
  hardware: {
    schema_version: 1, id: 'ryzen-ai-max-395-128gb-linux', cpu: 'AMD Ryzen AI Max+ 395', os: 'linux',
    reported_memory_gb: 128, planning_memory_gib: 119.2, os_reserve_gib: 16, gpu_budget_gib: 89.4, runtime_reserve_gib: 6,
    kv_cache_reserve_gib: { '8192': 4, '16384': 8, '32768': 16 }, measurement_status: 'unverified', sources: ['https://example.com/hardware'],
  },
});

test('local plans rank candidates without claiming measurements or confirmed fit', () => {
  const { catalog, hardware } = fixture();
  const before = JSON.stringify({ catalog, hardware });
  assert.equal(validateLocalPlanData(catalog, hardware), true);
  const plan = buildLocalPlan(catalog, hardware);
  assert.equal(plan.context_tokens, 16384);
  assert.equal(plan.measurement_status, 'unverified');
  assert.deepEqual(plan.rows.map(row => [row.id, row.status]), [['small', 'candidate'], ['conditional', 'conditional'], ['large', 'over-budget']]);
  assert.equal(plan.budget.effective_gib, 89.4);
  assert.equal(plan.rows[2].estimates.weights_gib, 90, 'MoE active parameter count must not replace full weights');
  for (const row of plan.rows) {
    assert.equal(row.fit_verified, false);
    assert.deepEqual(row.needs, ['hardware-preflight', 'artifact-pin', 'backend-smoke', 'local-provider-bridge']);
  }
  assert.equal(JSON.stringify({ catalog, hardware }), before, 'Inputs are not mutated');
});

test('effective budget respects OS memory, GPU budget and context reserves', () => {
  const { catalog, hardware } = fixture();
  const short = buildLocalPlan(catalog, hardware, { model: 'small', context: 8192, gpuBudgetGib: 60, memoryGib: 64 });
  assert.equal(short.budget.effective_gib, 48);
  assert.equal(short.rows[0].estimates.total_gib, 42);
  assert.equal(short.rows[0].headroom_gib, 6);
  assert.equal(short.rows[0].status, 'candidate');
  const long = buildLocalPlan(catalog, hardware, { model: 'small', context: 32768, gpuBudgetGib: 60, memoryGib: 64 });
  assert.equal(long.rows[0].estimates.total_gib, 54);
  assert.equal(long.rows[0].headroom_gib, -6);
  assert.equal(long.rows[0].status, 'over-budget');
  const gpuLimited = buildLocalPlan(catalog, hardware, { model: 'small', context: 8192, gpuBudgetGib: 40 });
  assert.equal(gpuLimited.budget.effective_gib, 40);
  assert.equal(gpuLimited.rows[0].status, 'over-budget');
});

test('models of the same priority are ordered by weights, then id', () => {
  const { catalog, hardware } = fixture();
  for (const model of catalog.models) model.priority = 1;
  catalog.models.push({ ...catalog.models[1], id: 'alphabetical', model_id: 'Example/Alphabetical' });
  assert.deepEqual(buildLocalPlan(catalog, hardware).rows.map(row => row.id), ['alphabetical', 'small', 'conditional', 'large']);
});

test('decimal budget boundaries and conditional fit remain explicit', () => {
  const { catalog, hardware } = fixture();
  const small = catalog.models.find(model => model.id === 'small');
  small.weights_gib_estimate = 75.4;
  const boundary = buildLocalPlan(catalog, hardware, { model: 'small' }).rows[0];
  assert.equal(boundary.headroom_gib, 0);
  assert.equal(boundary.status, 'candidate');
  small.weights_gib_estimate += 0.001;
  assert.equal(buildLocalPlan(catalog, hardware, { model: 'small' }).rows[0].status, 'over-budget');
  const conditional = buildLocalPlan(catalog, hardware, { model: 'conditional', context: 8192 }).rows[0];
  assert.equal(conditional.status, 'conditional');
  assert.equal(conditional.fit_verified, false);
});

test('unknown values, invalid quantities and unsupported query options cannot silently become defaults', () => {
  const { catalog, hardware } = fixture();
  for (const options of [
    { model: 'missing' }, { model: '' }, { context: 4096 }, { context: '16384' }, { context: null },
    { memoryGib: null }, { memoryGib: NaN }, { memoryGib: 0 }, { memoryGib: 16 },
    { gpuBudgetGib: Infinity }, { gpuBudgetGib: -1 }, { gpuBudgetGib: '89.4' },
    { 'memory-gib': 100 }, { autoRun: true },
  ]) assert.throws(() => buildLocalPlan(catalog, hardware, options));
  catalog.models[1].context_tokens = [8192];
  assert.throws(() => buildLocalPlan(catalog, hardware, { model: 'small' }), /not listed/);
});

test('input validation rejects invalid evidence, duplicate identities and incoherent units', () => {
  const invalid = [
    ({ catalog }) => { catalog.as_of = '2026-02-30'; },
    ({ catalog }) => { catalog.schema_version = 2; },
    ({ catalog }) => { catalog.models.push({ ...catalog.models[0] }); },
    ({ catalog }) => { catalog.models[1].model_id = catalog.models[0].model_id; },
    ({ catalog }) => { catalog.models[0].id = '../large'; },
    ({ catalog }) => { catalog.models[0].model_id = 'unknown'; },
    ({ catalog }) => { catalog.models[0].weights_gib_estimate = null; },
    ({ catalog }) => { catalog.models[0].weights_gib_estimate = '90'; },
    ({ catalog }) => { catalog.models[0].parameters_active_b = 201; },
    ({ catalog }) => { catalog.models[0].context_tokens = [8192, 8192]; },
    ({ catalog }) => { catalog.models[0].fit = 'verified'; },
    ({ catalog }) => { catalog.models[0].architecture = 'unknown'; },
    ({ catalog }) => { catalog.models[0].sources = []; },
    ({ catalog }) => { catalog.models[0].sources = ['http://example.com']; },
    ({ catalog }) => { catalog.models[0].sources = ['https://secret@example.com']; },
    ({ hardware }) => { hardware.planning_memory_gib = 129; },
    ({ hardware }) => { hardware.gpu_budget_gib = 120; },
    ({ hardware }) => { hardware.os_reserve_gib = 120; },
    ({ hardware }) => { hardware.runtime_reserve_gib = -1; },
    ({ hardware }) => { delete hardware.kv_cache_reserve_gib['8192']; },
    ({ hardware }) => { hardware.kv_cache_reserve_gib['32768'] = 2; },
    ({ hardware }) => { hardware.measurement_status = 'verified'; },
  ];
  for (const mutate of invalid) {
    const inputs = fixture(); mutate(inputs);
    assert.throws(() => validateLocalPlanData(inputs.catalog, inputs.hardware));
  }
});

test('pinned artifact sizes, hashes and paths agree without claiming a verified download', () => {
  const pinned = () => {
    const inputs = fixture();
    inputs.catalog.models[1].model_revision = 'a'.repeat(40);
    inputs.catalog.models[1].artifact = {
      repository: 'Example/Small-GGUF', revision: 'b'.repeat(40),
      files: [
        { path: 'Q4_K_M/small-00001-of-00002.gguf', bytes: 10 * (2 ** 30), sha256: 'c'.repeat(64) },
        { path: 'Q4_K_M/small-00002-of-00002.gguf', bytes: 22 * (2 ** 30), sha256: 'd'.repeat(64) },
      ],
      total_bytes: 32 * (2 ** 30), checksum_status: 'publisher_metadata_not_download_verified',
    };
    return inputs;
  };
  const valid = pinned();
  assert.equal(validateLocalPlanData(valid.catalog, valid.hardware), true);
  valid.catalog.models[1].weights_gib_estimate = 32.1;
  assert.equal(validateLocalPlanData(valid.catalog, valid.hardware), true);
  for (const mutate of [
    model => { model.artifact.total_bytes += 1; },
    model => { model.artifact.files[0].bytes += 1; model.artifact.total_bytes += 1; },
    model => { model.weights_gib_estimate = 31.999; },
    model => { model.weights_gib_estimate = 32.101; },
    model => { model.artifact.files[0].sha256 = 'unknown'; },
    model => { model.artifact.files[0].bytes = 1.5; },
    model => { model.artifact.files[0].bytes = Number.MAX_SAFE_INTEGER + 1; },
    model => { model.artifact.files[0].path = '../model.gguf'; },
    model => { model.artifact.files[0].path = '/model.gguf'; },
    model => { model.artifact.files[0].path = 'folder\\model.gguf'; },
    model => { model.artifact.files[0].path = 'folder/model.bin'; },
    model => { model.artifact.files[1].path = model.artifact.files[0].path; },
    model => { model.artifact.files = []; },
    model => { model.artifact.revision = 'main'; },
    model => { model.artifact.repository = '../outside'; },
    model => { model.model_revision = 'main'; },
    model => { delete model.model_revision; },
    model => { model.artifact.checksum_status = 'download_verified'; },
  ]) {
    const inputs = pinned();
    mutate(inputs.catalog.models[1]);
    assert.throws(() => validateLocalPlanData(inputs.catalog, inputs.hardware));
  }
});

test('CLI emits deterministic JSON and leaves the fixture tree untouched', t => {
  const root = mkdtempSync(join(tmpdir(), 'local-plan-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const directory = join(root, 'experiments', 'local-models');
  mkdirSync(directory, { recursive: true });
  const { catalog, hardware } = fixture();
  writeFileSync(join(directory, 'models.json'), JSON.stringify(catalog));
  writeFileSync(join(directory, 'hardware.json'), JSON.stringify(hardware));
  const before = readdirSync(root, { recursive: true });
  const argv = [cli, '--format', 'json', '--model', 'small', '--context', '8192', '--memory-gib', '64', '--gpu-budget-gib', '60'];
  const first = spawnSync(process.execPath, argv, { cwd: root, encoding: 'utf8' });
  assert.equal(first.status, 0, first.stderr);
  const result = JSON.parse(first.stdout);
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].headroom_gib, 6);
  const second = spawnSync(process.execPath, argv, { cwd: root, encoding: 'utf8' });
  assert.equal(second.stdout, first.stdout);
  assert.deepEqual(readdirSync(root, { recursive: true }), before);
  assert.equal(readFileSync(join(directory, 'models.json'), 'utf8'), JSON.stringify(catalog));
  assert.equal(readFileSync(join(directory, 'hardware.json'), 'utf8'), JSON.stringify(hardware));
  for (const invalid of [['--format', 'csv'], ['--context', '32k'], ['--memory-gib', '0x80'], ['--gpu-budget-gib', 'Infinity'], ['--model', 'unknown'], ['--run', 'true'], ['--context', '8192', '--context', '16384']]) {
    const failure = spawnSync(process.execPath, [cli, ...invalid], { cwd: root, encoding: 'utf8' });
    assert.equal(failure.status, 1, failure.stdout);
    assert.equal(failure.stdout, '');
    assert.match(failure.stderr, /\[lab\]/);
  }
});
