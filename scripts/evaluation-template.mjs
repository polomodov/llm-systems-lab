#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { readRun } from './lib/records.mjs';
import { sha256 } from './lib/files.mjs';
import { args, options, main } from './lib/cli.mjs';
await main(() => {
  const a = args(); options(a, ['run'], ['run']);
  const record = readRun(process.cwd(), a.run);
  if (record.status !== 'awaiting_review') throw new Error('Run must be awaiting_review');
  const dir = join(process.cwd(),'results/runs',a.run);
  console.log(JSON.stringify({ run_id:a.run, result:null, method:record.evaluation.method, evaluator:'', check_output:'', human_notes:'', artifacts_sha256:sha256(readFileSync(join(dir,'trace/artifacts.json'))), workspace_sha256:sha256(readFileSync(join(dir,'trace/final-workspace.json'))) },null,2));
});
