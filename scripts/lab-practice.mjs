#!/usr/bin/env node
import { args, options, main } from './lib/cli.mjs';
import { createLabPractice, listPracticeScenarios } from './lib/lab-practice.mjs';

await main(() => {
  const opts = args();
  options(opts, ['scenario', 'session', 'list']);
  if (opts.list !== undefined) {
    if (opts.list !== 'true' || opts.scenario !== undefined || opts.session !== undefined) throw new Error('Use --list true alone, or --scenario <id> --session <slug>');
    for (const scenario of listPracticeScenarios(process.cwd())) console.log(`${scenario.id}\t${scenario.title}\t${scenario.related_labs.join(',')}`);
    return;
  }
  options(opts, ['scenario', 'session'], ['scenario', 'session']);
  const result = createLabPractice(process.cwd(), opts);
  console.log(`[lab:practice] ${result.directory}`);
  console.log(`[lab:practice] evidence_class=synthetic; status=${result.status}; response_state=${result.response_state}`);
  console.log('[lab:practice] Записанный учебный сценарий; модель не запускалась, verdict отсутствует.');
});
