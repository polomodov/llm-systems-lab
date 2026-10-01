#!/usr/bin/env node
import { args, options, main } from './lib/cli.mjs';
import { checkLabReport } from './lib/lab-reports.mjs';

await main(() => {
  const opts = args();
  options(opts, ['report', 'mode'], ['report']);
  const result = checkLabReport(process.cwd(), opts);
  console.log(JSON.stringify(result, null, 2));
  if (result.errors.length) process.exitCode = 1;
});
