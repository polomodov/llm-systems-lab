#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { args, main, options } from './lib/cli.mjs';
import { buildLocalPlan } from './lib/local-plan.mjs';
import { buildEnginePlan } from './lib/local-engines.mjs';

await main(() => {
  const opts = args();
  options(opts, ['format', 'model', 'context', 'gpu-budget-gib', 'memory-gib', 'engine']);
  const format = opts.format ?? 'table';
  if (!['json', 'table'].includes(format)) throw new Error('--format must be json or table');
  const input = {};
  if (opts.model !== undefined) input.model = opts.model;
  for (const [flag, key] of [['context', 'context'], ['gpu-budget-gib', 'gpuBudgetGib'], ['memory-gib', 'memoryGib']]) {
    if (opts[flag] !== undefined) {
      if (!/^(?:\d+\.?\d*|\.\d+)$/.test(opts[flag])) throw new Error(`--${flag} must be a positive decimal number`);
      input[key] = Number(opts[flag]);
    }
  }
  const directory = join(process.cwd(), 'experiments', 'local-models');
  const catalog = JSON.parse(readFileSync(join(directory, 'models.json'), 'utf8'));
  const hardware = JSON.parse(readFileSync(join(directory, 'hardware.json'), 'utf8'));
  const plan = opts.engine === undefined ? buildLocalPlan(catalog, hardware, input) : buildEnginePlan(
    catalog,
    hardware,
    JSON.parse(readFileSync(join(directory, 'engines.json'), 'utf8')),
    { ...input, engine: opts.engine },
  );
  if (format === 'json') {
    console.log(JSON.stringify(plan, null, 2));
    return;
  }
  const fixed = value => value === null ? 'unknown' : value.toFixed(2);
  console.log(`${plan.hardware_id}; контекст ${plan.context_tokens}; бюджет ${fixed(plan.budget.effective_gib)} GiB.`);
  if (opts.engine !== undefined) {
    console.table(plan.rows.map(row => ({
      engine: row.engine.id,
      backend: row.engine.backend,
      model: row.id,
      quantization: row.quantization ?? 'artifact required',
      weights_GiB: fixed(row.estimates.weights_gib),
      runtime_GiB: fixed(row.estimates.runtime_reserve_gib),
      total_GiB: fixed(row.estimates.total_gib),
      headroom_GiB: fixed(row.headroom_gib),
      fit_status: row.fit_status,
    })));
    console.log('Это план, не замеры. Поддержка движка указана по документации; неизвестные артефакты и резервы памяти требуют отдельной проверки.');
    console.log('До запуска нужны: артефакт для движка, калибровка памяти, hardware-smoke и local-provider-bridge.');
    return;
  }
  console.table(plan.rows.map(row => ({
    priority: row.priority,
    model: row.id,
    quantization: row.quantization,
    weights_GiB: fixed(row.estimates.weights_gib),
    total_GiB: fixed(row.estimates.total_gib),
    headroom_GiB: fixed(row.headroom_gib),
    status: row.status,
  })));
  console.log('Плановые оценки: резервы памяти не являются расчётом KV-кеша по архитектуре. candidate не подтверждает размещение модели.');
  console.log('До запуска нужны: hardware-preflight, artifact-pin, backend-smoke, local-provider-bridge.');
});
