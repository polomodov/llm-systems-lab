#!/usr/bin/env node
import { mkdirSync, existsSync, writeFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, arr) => {
    if (a.startsWith("--")) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith("--") ? arr[i + 1] : "true"]);
    return acc;
  }, []),
);
const need = ["harness", "agent", "task"];
for (const k of need) if (!args[k]) { console.error(`usage: npm run new-run -- --harness <name> --agent <code> --task <id> [--n <k>]`); process.exit(64); }

const date = new Date().toISOString().slice(0, 10);
const base = `${date}-${args.harness}-${args.agent}-${args.task}`.toLowerCase();
let runId = args.n ? `${base}-${args.n}` : base;
let dir = join("results", "runs", runId);
let k = 2;
while (existsSync(dir) && !args.n) { runId = `${base}-${k++}`; dir = join("results", "runs", runId); }

const specPath = join("agents", args.agent, "spec.md");
const taskDir = existsSync(join("tasks", args.task))
  ? args.task
  : (readdirSync("tasks").find((d) => d.toLowerCase().startsWith(args.task.toLowerCase() + "-")) ?? args.task);
const taskPath = join("tasks", taskDir, "task.md");
if (!existsSync(specPath)) console.warn(`[new-run] warning: ${specPath} not found`);
if (!existsSync(taskPath)) console.warn(`[new-run] warning: ${taskPath} not found`);

const record = {
  run_id: runId,
  date,
  harness: { name: args.harness, version: "", mode: "cli" },
  agent: args.agent,
  task: taskDir,
  model: { id: "", lock: false, reasoning: "" },
  permissions: { mode: "", blocked: [], asked: 0 },
  sandbox: { kind: "", network: "" },
  loop: { turns: 0, stop_reason: "", budget_usd: 0, cost_usd: 0, tokens_in: 0, tokens_out: 0, wall_clock_s: 0, compactions: 0, subagents: 0 },
  verdict: { result: "aborted", check_output: "", human_notes: "" },
  harness_changes: [],
  trace_path: "trace/",
  notes: "",
};
for (const sub of ["workspace", "trace", "artifacts"]) mkdirSync(join(dir, sub), { recursive: true });
writeFileSync(join(dir, "run.json"), JSON.stringify(record, null, 2) + "\n");
writeFileSync(join(dir, "workspace", ".gitkeep"), "");
console.log(`[new-run] ${dir}/run.json`);
console.log(`[new-run] next: see experiments/${args.harness}/README.md, agent spec ${specPath}, task ${taskPath}`);
