import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { buildLocalPlan } from '../scripts/lib/local-plan.mjs';
import { buildEnginePlan, validateEngineCatalog } from '../scripts/lib/local-engines.mjs';

const planCli = fileURLToPath(new URL('../scripts/local-plan.mjs', import.meta.url));
const enginesCli = fileURLToPath(new URL('../scripts/local-engines.mjs', import.meta.url));
const fixture = () => {
  const makeModel = (id, weights, fit) => ({
    id, model_id: `Example/${id}`, priority: 1, architecture: 'dense', parameters_total_b: 100, parameters_active_b: 100,
    quantization: 'Q4_K_M', weights_gib_estimate: weights, weights_basis: 'Synthetic GGUF size',
    context_tokens: [8192, 16384, 32768], sources: [`https://example.com/models/${id}`], fit, reason: 'Synthetic candidate',
    model_revision: 'a'.repeat(40),
    artifact: { repository: `Example/${id}-GGUF`, revision: 'b'.repeat(40), files: [{ path: `${id}.gguf`, bytes: weights * (2 ** 30), sha256: 'c'.repeat(64) }], total_bytes: weights * (2 ** 30), checksum_status: 'publisher_metadata_not_download_verified' },
  });
  const makeEngine = (id, backend, kind, support, policy, reserve) => ({
    id, name: id, kind, engine: id.split('-')[0], backend, priority: 1, hardware_support: support,
    artifact_policy: policy, runtime_reserve_gib: reserve, sources: [`https://example.com/engines/${id}`], notes: 'Support is synthetic documentation, not measured on hardware',
  });
  return {
    models: { schema_version: 1, as_of: '2026-09-20', models: [makeModel('large', 70, 'conditional'), makeModel('small', 20, 'candidate')] },
    hardware: {
      schema_version: 1, id: 'synthetic-linux', cpu: 'Synthetic processor', os: 'linux', reported_memory_gb: 128, planning_memory_gib: 119.2,
      os_reserve_gib: 16, gpu_budget_gib: 89.4, runtime_reserve_gib: 6, kv_cache_reserve_gib: { '8192': 4, '16384': 8, '32768': 16 },
      measurement_status: 'unverified', sources: ['https://example.com/hardware'],
    },
    engines: { schema_version: 1, as_of: '2026-09-21', engines: [
      makeEngine('vllm-rocm', 'rocm', 'engine', 'experimental', 'separate-artifact', 12),
      makeEngine('llama-cpp-vulkan', 'vulkan', 'engine', 'documented', 'catalog-gguf', 6),
      makeEngine('llama-cpp-rocm', 'rocm', 'engine', 'conditional', 'catalog-gguf', 14),
      makeEngine('wrapper-vulkan', 'vulkan', 'serving-wrapper', 'experimental', 'catalog-gguf', null),
    ] },
  };
};

test('engine plans cover the full matrix and keep support distinct from fit', () => {
  const { models, hardware, engines } = fixture();
  const before = JSON.stringify({ models, hardware, engines });
  const plan = buildEnginePlan(models, hardware, engines);
  assert.equal(plan.engine_count, 4);
  assert.equal(plan.model_count, 2);
  assert.equal(plan.rows.length, 8);
  assert.equal(plan.measurement_status, 'unverified');
  assert.equal(plan.as_of, '2026-09-21');
  assert.equal(plan.model_catalog_as_of, '2026-09-20');
  assert.equal(plan.budget.effective_gib, 89.4);
  assert.equal(new Set(plan.rows.map(row => `${row.engine.id}/${row.id}`)).size, 8);
  for (const row of plan.rows) {
    assert.equal(row.fit_verified, false);
    assert.equal(row.model_revision, 'a'.repeat(40));
    assert.ok(row.sources.includes(`https://example.com/models/${row.id}`));
    assert.ok(row.sources.includes(`https://example.com/engines/${row.engine.id}`));
    assert.ok(row.notes.includes('not measured'));
  }
  const documented = plan.rows.find(row => row.engine.id === 'llama-cpp-vulkan' && row.id === 'small');
  assert.equal(documented.engine.hardware_support, 'documented');
  assert.equal(documented.fit_status, 'candidate');
  assert.equal(documented.fit_verified, false);
  assert.equal(JSON.stringify({ models, hardware, engines }), before);
  documented.artifact.files[0].path = 'changed.gguf';
  assert.equal(models.models[1].artifact.files[0].path, 'small.gguf');
});

test('separate artifacts never inherit GGUF quantization, sizes, artifacts or reserve estimates', () => {
  const { models, hardware, engines } = fixture();
  const plan = buildEnginePlan(models, hardware, engines, { engine: 'vllm-rocm', model: 'large', gpuBudgetGib: 10 });
  assert.equal(plan.rows.length, 1);
  const row = plan.rows[0];
  assert.equal(row.model_id, 'Example/large');
  assert.equal(row.model_revision, 'a'.repeat(40));
  assert.equal(row.quantization, null);
  assert.equal(row.artifact, null);
  assert.equal(row.weights_basis, null);
  assert.deepEqual(row.estimates, { weights_gib: null, runtime_reserve_gib: null, kv_cache_reserve_gib: null, total_gib: null });
  assert.equal(row.headroom_gib, null);
  assert.equal(row.fit_status, 'artifact-required');
  assert.deepEqual(row.needs, ['exact-engine-artifact', 'engine-memory-calibration', 'hardware-smoke', 'local-provider-bridge']);
});

test('unknown runtime memory does not turn a GGUF size into a fit prediction', () => {
  const { models, hardware, engines } = fixture();
  const row = buildEnginePlan(models, hardware, engines, { engine: 'wrapper-vulkan', model: 'small' }).rows[0];
  assert.equal(row.quantization, 'Q4_K_M');
  assert.equal(row.estimates.weights_gib, 20);
  assert.equal(row.artifact.repository, 'Example/small-GGUF');
  assert.equal(row.estimates.runtime_reserve_gib, null);
  assert.equal(row.estimates.total_gib, null);
  assert.equal(row.headroom_gib, null);
  assert.equal(row.fit_status, 'engine-memory-required');
});

test('known engine reserves replace the hardware baseline and preserve model conditions', () => {
  const { models, hardware, engines } = fixture();
  const vulkan = buildEnginePlan(models, hardware, engines, { engine: 'llama-cpp-vulkan', model: 'large' }).rows[0];
  assert.equal(vulkan.estimates.total_gib, 84);
  assert.equal(vulkan.fit_status, 'conditional');
  const rocm = buildEnginePlan(models, hardware, engines, { engine: 'llama-cpp-rocm', model: 'large' }).rows[0];
  assert.equal(rocm.estimates.runtime_reserve_gib, 14);
  assert.equal(rocm.estimates.total_gib, 92);
  assert.equal(rocm.headroom_gib, -2.6);
  assert.equal(rocm.fit_status, 'over-budget');
  const short = buildEnginePlan(models, hardware, engines, { engine: 'llama-cpp-rocm', model: 'large', context: 8192 }).rows[0];
  assert.equal(short.estimates.total_gib, 88);
  assert.equal(short.fit_status, 'conditional');
});

test('engine validation rejects malformed profiles and query selectors', () => {
  const { models, hardware, engines } = fixture();
  assert.equal(validateEngineCatalog(engines), true);
  for (const mutate of [
    catalog => { catalog.schema_version = 2; },
    catalog => { catalog.as_of = '2026-02-30'; },
    catalog => { catalog.engines = []; },
    catalog => { catalog.engines.push({ ...catalog.engines[0] }); },
    catalog => { catalog.engines[0].id = 'all'; },
    catalog => { catalog.engines[0].id = '../vllm'; },
    catalog => { catalog.engines[0].name = ''; },
    catalog => { catalog.engines[0].kind = 'harness'; },
    catalog => { catalog.engines[0].backend = 'cuda'; },
    catalog => { catalog.engines[0].hardware_support = 'measured'; },
    catalog => { catalog.engines[0].artifact_policy = 'unknown'; },
    catalog => { catalog.engines[0].priority = 0; },
    catalog => { catalog.engines[0].runtime_reserve_gib = -1; },
    catalog => { catalog.engines[0].runtime_reserve_gib = '12'; },
    catalog => { catalog.engines[0].runtime_reserve_gib = Infinity; },
    catalog => { delete catalog.engines[0].runtime_reserve_gib; },
    catalog => { catalog.engines[0].sources = []; },
    catalog => { catalog.engines[0].sources = ['http://example.com']; },
    catalog => { catalog.engines[0].sources = ['https://secret@example.com']; },
    catalog => { catalog.engines[0].sources.push(catalog.engines[0].sources[0]); },
  ]) {
    const catalog = fixture().engines;
    mutate(catalog);
    assert.throws(() => validateEngineCatalog(catalog));
  }
  for (const options of [{ engine: 'unknown' }, { engine: null }, { engine: '' }, { model: 'unknown' }, { context: 4096 }, { autoRun: true }]) {
    assert.throws(() => buildEnginePlan(models, hardware, engines, options));
  }
});

test('both CLIs emit read-only JSON and original plans work without an engine catalog', t => {
  const root = mkdtempSync(join(tmpdir(), 'local-engines-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const directory = join(root, 'experiments', 'local-models');
  mkdirSync(directory, { recursive: true });
  const { models, hardware, engines } = fixture();
  writeFileSync(join(directory, 'models.json'), JSON.stringify(models));
  writeFileSync(join(directory, 'hardware.json'), JSON.stringify(hardware));
  const invoke = (cli, flags) => spawnSync(process.execPath, [cli, ...flags], { cwd: root, encoding: 'utf8' });
  const original = invoke(planCli, ['--format', 'json']);
  assert.equal(original.status, 0, original.stderr);
  assert.equal(original.stdout, `${JSON.stringify(buildLocalPlan(models, hardware), null, 2)}\n`);
  writeFileSync(join(directory, 'engines.json'), JSON.stringify(engines));
  const before = readdirSync(root, { recursive: true });
  const list = invoke(enginesCli, ['--format', 'json']);
  assert.equal(list.status, 0, list.stderr);
  assert.equal(JSON.parse(list.stdout).engines.length, 4);
  const matrix = invoke(planCli, ['--format', 'json', '--engine', 'all', '--model', 'small']);
  assert.equal(matrix.status, 0, matrix.stderr);
  assert.equal(JSON.parse(matrix.stdout).rows.length, 4);
  const one = invoke(planCli, ['--format', 'json', '--engine', 'vllm-rocm', '--context', '8192']);
  assert.equal(one.status, 0, one.stderr);
  assert.equal(JSON.parse(one.stdout).rows[0].context_tokens, 8192);
  assert.equal(JSON.parse(one.stdout).rows[0].quantization, null);
  for (const [cli, flags] of [[planCli, ['--engine', 'unknown']], [enginesCli, ['--format', 'csv']], [enginesCli, ['--engine', 'all']]]) {
    const result = invoke(cli, flags);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /\[lab\]/);
  }
  const table = invoke(planCli, ['--engine', 'vllm-rocm']);
  assert.equal(table.status, 0, table.stderr);
  assert.match(table.stdout, /artifact-required/);
  assert.match(table.stdout, /unknown/);
  assert.deepEqual(readdirSync(root, { recursive: true }), before);
  for (const [name, value] of [['models', models], ['hardware', hardware], ['engines', engines]]) {
    assert.equal(readFileSync(join(directory, `${name}.json`), 'utf8'), JSON.stringify(value));
  }
});
