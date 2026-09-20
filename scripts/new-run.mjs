#!/usr/bin/env node
import { createRun } from "./lib/records.mjs";

const usage = "usage: npm run new-run -- --harness <name> --agent <code> --task <id> [--n <positive integer>] [--model <exact-id|managed:mode>] [--provider <name>] [--harness-version <exact-version>]";
try {
  const options = {};
  const allowed = new Set(["harness", "agent", "task", "n", "model", "provider", "harness-version"]);
  const args = process.argv.slice(2);
  if (args.length === 1 && ["--help", "-h"].includes(args[0])) { console.log(usage); process.exit(0); }
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index].replace(/^--/, "");
    const value = args[index + 1];
    if (!args[index].startsWith("--") || !allowed.has(key) || !value || value.startsWith("--") || key in options) throw new Error(`invalid or duplicate option: ${args[index]}`);
    options[key] = value;
  }
  for (const key of ["harness", "agent", "task"]) if (!options[key]) throw new Error(`missing --${key}`);
  const record = createRun({ ...options, harnessVersion: options["harness-version"] });
  console.log(`[new-run] results/runs/${record.run_id}/run.json`);
  console.log(`[new-run] status=planned; no experimental evidence`);
} catch (error) { console.error(`[new-run] ${error.message}\n${usage}`); process.exitCode = 1; }
