#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { args, main, options } from './lib/cli.mjs';
import { validateEngineCatalog } from './lib/local-engines.mjs';

await main(() => {
  const opts = args();
  options(opts, ['format']);
  const format = opts.format ?? 'table';
  if (!['json', 'table'].includes(format)) throw new Error('--format must be json or table');
  const catalog = JSON.parse(readFileSync(join(process.cwd(), 'experiments', 'local-models', 'engines.json'), 'utf8'));
  validateEngineCatalog(catalog);
  const engines = [...catalog.engines].sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id, 'en'));
  if (format === 'json') {
    console.log(JSON.stringify({ ...catalog, engines }, null, 2));
    return;
  }
  console.table(engines.map(engine => ({
    priority: engine.priority,
    id: engine.id,
    name: engine.name,
    kind: engine.kind,
    engine: engine.engine,
    backend: engine.backend,
    hardware_support: engine.hardware_support,
    artifact_policy: engine.artifact_policy,
    runtime_reserve_GiB: engine.runtime_reserve_gib ?? 'unknown',
  })));
  console.log('Поддержка указана по документации; работа на этом компьютере и расход памяти не подтверждены.');
});
