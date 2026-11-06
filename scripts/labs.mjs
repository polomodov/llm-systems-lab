#!/usr/bin/env node
import { main } from './lib/cli.mjs';
import { loadLabCatalog } from './lib/labs.mjs';
await main(() => {
  if (process.argv.length > 2) throw new Error('Usage: npm run labs');
  const catalog = loadLabCatalog(process.cwd(), { checkDocuments: true });
  console.table(catalog.labs.map(lab => ({ id: lab.id, title: lab.title, harness: lab.harness ?? '—', prerequisites: [...lab.prerequisites, ...(lab.prerequisites_any ? [`(${lab.prerequisites_any.join(' or ')})`] : [])].join(', ') || '—', readiness: lab.readiness, effort: lab.effort })));
  console.log('Route: docs/labs/README.md. Readiness describes task prerequisites, not completion.');
});
