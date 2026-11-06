#!/usr/bin/env node
import { args, options, main } from './lib/cli.mjs';
import { createLabReport } from './lib/labs.mjs';
await main(() => {
  const opts = args();
  options(opts, ['lab', 'session'], ['lab', 'session']);
  const result = createLabReport(process.cwd(), opts);
  console.log(`[lab:new] ${result.directory}`);
  console.log('[lab:new] status=not-started; blank report; no experiments were run');
});
