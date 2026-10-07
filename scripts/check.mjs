#!/usr/bin/env node
import { existsSync, lstatSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { validateLedger, validateRun } from "./lib/records.mjs";
import { verifyRunIntegrity } from "./lib/integrity.mjs";
import { validateLocalPlanData } from "./lib/local-plan.mjs";
import { HARDWARE_PROFILES, loadLocalHardware } from "./lib/local-hardware.mjs";
import { loadLabCatalog } from "./lib/labs.mjs";
import { auditPins } from "./lib/pins.mjs";
import { taskLimits } from "./lib/contracts.mjs";

const root = process.cwd();
const runsDir = join(root, "results", "runs");
let failed = 0;
let completed = 0;
const entries = [];
const evidenceIds = new Set();
if (existsSync(join(root, "docs/labs"))) {
  try {
    const catalog = loadLabCatalog(root, { checkDocuments: true });
    console.log(`[check] laboratory manuals=${catalog.labs.length}, harness labs=${catalog.labs.filter(lab => lab.harness).length}: задания, не выполненные работы`);
  } catch (error) { console.error(`[check] labs: ${error.message}`); failed++; }
}
const localDir = join(root, "experiments", "local-models");
if (existsSync(localDir)) {
  for (const id of Object.keys(HARDWARE_PROFILES)) {
    try {
      const catalog = JSON.parse(readFileSync(join(localDir, "models.json"), "utf8"));
      const { hardware, engines } = loadLocalHardware(root, id, { engines: true });
      validateLocalPlanData(catalog, hardware);
      console.log(`[check] ${id}: models=${catalog.models.length}, inference profiles=${engines.engines.length}: план, hardware smoke не выполнен`);
    } catch (error) { console.error(`[check] local plan ${id}: ${error.message}`); failed++; }
  }
}
if (existsSync(join(root, "experiments")) && existsSync(join(root, "docs/harnesses.md")) && existsSync(join(root, "README.md"))) {
  try {
    const pins = auditPins(root);
    for (const error of pins.errors) { console.error(`✖ pin ${error}`); failed++; }
    if (!pins.errors.length) console.log(`[check] pinned harnesses=${pins.ids.length}: профиль, Dockerfile и документация совпадают`);
  } catch (error) { console.error(`[check] pins: ${error.message}`); failed++; }
}
if (existsSync(join(root, "tasks"))) {
  try {
    const tasksDir = join(root, "tasks");
    const contracts = readdirSync(tasksDir).filter((name) => existsSync(join(tasksDir, name, "task.md")));
    for (const name of contracts) taskLimits(readFileSync(join(tasksDir, name, "task.md"), "utf8"));
    console.log(`[check] task contracts=${contracts.length}: лимиты ходов и USD читаются из контракта`);
  } catch (error) { console.error(`[check] task budget: ${error.message}`); failed++; }
}
try {
  if (existsSync(runsDir)) {
    if (lstatSync(join(root, "results")).isSymbolicLink()) throw new Error("results must be a real directory");
    if (lstatSync(runsDir).isSymbolicLink() || !lstatSync(runsDir).isDirectory()) throw new Error("results/runs must be a real directory");
    for (const name of readdirSync(runsDir)) {
      if (name.startsWith(".")) continue;
      const stat = lstatSync(join(runsDir, name));
      if (stat.isDirectory() || stat.isSymbolicLink()) entries.push(name);
    }
  }
} catch (error) { console.error(`[check] ${error.message}`); failed++; }

const ledgerFile = join(root, "docs", "harness-ledger.md");
let ledger = { ids: new Set(), errors: [] };
let ledgerText = "";
try { ledgerText = readFileSync(ledgerFile, "utf8"); ledger = validateLedger(ledgerText); }
catch (error) { ledger.errors.push(`ledger: ${error.message}`); }
for (const error of ledger.errors) { console.error(`✖ ${error}`); failed++; }

for (const name of entries) {
  let record;
  let errors = [];
  try {
    const dir = join(runsDir, name);
    if (lstatSync(dir).isSymbolicLink()) throw new Error("run directory must not be a symlink");
    const file = join(dir, "run.json");
    if (lstatSync(file).isSymbolicLink() || !lstatSync(file).isFile()) throw new Error("run.json must be a regular file");
    record = JSON.parse(readFileSync(file, "utf8"));
    errors = validateRun(record, { root, folderName: name });
    if (errors.length === 0) verifyRunIntegrity(root, record);
    if (Array.isArray(record?.harness_changes)) for (const change of record.harness_changes) {
      if (change?.ledger && !ledger.ids.has(change.ledger)) errors.push(`ledger row ${change.ledger} not found`);
    }
  } catch (error) { errors.push(error.message); }
  if (errors.length) { failed++; console.error(`✖ ${name}\n  ${errors.join("\n  ")}`); }
  else {
    if (record.status === "completed") { completed++; evidenceIds.add(record.run_id); }
    console.log(`✔ ${name}: ${record.status}/${record.verdict.result}`);
    if (record.status === "completed" && !existsSync(join(runsDir, name, "workspace"))) console.log(`[check] ${name}: workspace отсутствует; архив проверен без live tree`);
  }
}
if (ledgerText) for (const error of validateLedger(ledgerText, { runIds: evidenceIds }).errors) {
  if (!ledger.errors.includes(error)) { console.error(`✖ ${error}`); failed++; }
}
console.log(`[check] runs=${entries.length} completed=${completed} failed=${failed} ledger rows=${ledger.ids.size}`);
if (completed === 0) console.log("[check] no experimental evidence: нет завершённых проверенных прогонов");
process.exitCode = failed ? 1 : 0;
