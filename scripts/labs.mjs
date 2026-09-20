#!/usr/bin/env node
import { main } from './lib/cli.mjs';
import { loadLabCatalog } from './lib/labs.mjs';
await main(() => {
  if (process.argv.length > 2) throw new Error('Usage: npm run labs');
  const catalog = loadLabCatalog(process.cwd(), { checkDocuments: true });
  console.table(catalog.labs.map(lab => ({ id: lab.id, title: lab.title, harness: lab.harness ?? '—', prerequisites: lab.prerequisites.join(', ') || '—', readiness: lab.readiness, effort: lab.effort })));
  console.log('Маршрут: docs/labs/README.md. Готовность описывает условия задания, а не факт его выполнения.');
});
