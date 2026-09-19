#!/usr/bin/env node
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

const schema = JSON.parse(readFileSync("results/schema.json", "utf8"));
const runsDir = "results/runs";
const ledger = existsSync("docs/harness-ledger.md") ? readFileSync("docs/harness-ledger.md", "utf8") : "";
const ledgerIds = new Set([...ledger.matchAll(/^\|\s*(L\d{3})\s*\|/gm)].map((m) => m[1]));

const typeOk = (v, t) => t === "integer" ? Number.isInteger(v) : t === "number" ? typeof v === "number" : t === "array" ? Array.isArray(v) : typeof v === t;
function validate(obj, sch, path, errors) {
  if (sch.type && !typeOk(obj, sch.type)) { errors.push(`${path}: expected ${sch.type}`); return; }
  if (sch.enum && !sch.enum.includes(obj)) errors.push(`${path}: not in ${sch.enum.join("|")}`);
  if (sch.pattern && typeof obj === "string" && !new RegExp(sch.pattern).test(obj)) errors.push(`${path}: does not match ${sch.pattern}`);
  if (sch.type === "object") {
    for (const r of sch.required ?? []) if (!(r in obj)) errors.push(`${path}.${r}: missing`);
    for (const [k, sub] of Object.entries(sch.properties ?? {})) if (k in obj) validate(obj[k], sub, `${path}.${k}`, errors);
  }
  if (sch.type === "array" && sch.items) obj.forEach((it, i) => validate(it, sch.items, `${path}[${i}]`, errors));
}

let runs = 0, failed = 0;
if (existsSync(runsDir)) {
  for (const name of readdirSync(runsDir)) {
    const dir = join(runsDir, name);
    if (!statSync(dir).isDirectory()) continue;
    runs++;
    const file = join(dir, "run.json");
    if (!existsSync(file)) { console.error(`✖ ${name}: run.json missing`); failed++; continue; }
    const errors = [];
    let rec;
    try { rec = JSON.parse(readFileSync(file, "utf8")); } catch (e) { console.error(`✖ ${name}: invalid JSON`); failed++; continue; }
    validate(rec, schema, "run", errors);
    if (rec.run_id !== name) errors.push(`run.run_id "${rec.run_id}" != folder "${name}"`);
    for (const ch of rec.harness_changes ?? []) if (ch.ledger && !ledgerIds.has(ch.ledger)) errors.push(`ledger row ${ch.ledger} not found in docs/harness-ledger.md`);
    if (rec.verdict?.result !== "aborted" && !rec.harness?.version) errors.push("harness.version is empty for a finished run");
    if (rec.verdict?.result !== "aborted" && !rec.model?.id) errors.push("model.id is empty for a finished run");
    if (errors.length) { failed++; console.error(`✖ ${name}\n  ${errors.join("\n  ")}`); } else console.log(`✔ ${name}: ${rec.verdict.result}`);
  }
}
console.log(`[check] runs=${runs} failed=${failed} ledger rows=${ledgerIds.size}`);
process.exit(failed ? 1 : 0);
