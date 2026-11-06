import { localRecordErrors } from './local-inference.mjs';
import { loadTaskDescriptor } from './tasks.mjs';
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { isAbsolute, join, relative, resolve, sep } from "node:path";

const schema = JSON.parse(readFileSync(new URL("../../results/schema.json", import.meta.url), "utf8"));
const RUN_ID = /^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SEGMENT = /^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$/;
export const METRIC_FIELDS = ["permissions.asked", "loop.turns", "loop.budget_usd", "loop.cost_usd", "loop.tokens_in", "loop.tokens_out", "loop.wall_clock_s", "loop.compactions", "loop.subagents"];
const knownPlaceholder = /^(?:unknown|unverified|latest|default|tbd|auto|n\/a)$/i;
const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const nonempty = (value) => typeof value === "string" && value.trim().length > 0;
const has = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const sha256 = (file) => createHash("sha256").update(readFileSync(file)).digest("hex");

function typeMatches(value, type) {
  if (type === "null") return value === null;
  if (type === "object") return isObject(value);
  if (type === "array") return Array.isArray(value);
  if (type === "integer") return Number.isSafeInteger(value);
  if (type === "number") return typeof value === "number" && Number.isFinite(value);
  return typeof value === type;
}

function validateSchema(value, rule, path, errors) {
  if (rule.$ref) rule = rule.$ref.split("/").slice(1).reduce((node, key) => node[key], schema);
  if (rule.type && ![].concat(rule.type).some((type) => typeMatches(value, type))) {
    errors.push(`${path}: expected ${[].concat(rule.type).join("|")}`);
    return;
  }
  if (rule.enum && !rule.enum.includes(value)) errors.push(`${path}: expected ${rule.enum.join("|")}`);
  if (typeof value === "string") {
    if (rule.minLength && value.trim().length < rule.minLength) errors.push(`${path}: must not be blank`);
    if (rule.pattern && !new RegExp(rule.pattern).test(value)) errors.push(`${path}: invalid format`);
    if (rule.format === "date-time" && (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value) || !Number.isFinite(Date.parse(value)))) errors.push(`${path}: expected UTC ISO timestamp`);
    if (rule.format === "date" && (!Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) errors.push(`${path}: invalid date`);
  }
  if (typeof value === "number") {
    if (rule.minimum !== undefined && value < rule.minimum) errors.push(`${path}: must be >= ${rule.minimum}`);
    if (rule.exclusiveMinimum !== undefined && value <= rule.exclusiveMinimum) errors.push(`${path}: must be > ${rule.exclusiveMinimum}`);
  }
  if (Array.isArray(value)) {
    if (rule.minItems && value.length < rule.minItems) errors.push(`${path}: must have at least ${rule.minItems} items`);
    value.forEach((item, index) => validateSchema(item, rule.items ?? {}, `${path}[${index}]`, errors));
  }
  if (isObject(value)) {
    for (const key of rule.required ?? []) if (!has(value, key)) errors.push(`${path}.${key}: missing`);
    for (const [key, item] of Object.entries(value)) {
      if (has(rule.properties ?? {}, key)) validateSchema(item, rule.properties[key], `${path}.${key}`, errors);
      else if (rule.additionalProperties === false) errors.push(`${path}.${key}: unknown field`);
      else if (isObject(rule.additionalProperties)) validateSchema(item, rule.additionalProperties, `${path}.${key}`, errors);
    }
  }
}

function assertSegment(value, label) {
  if (typeof value !== "string" || !SEGMENT.test(value)) throw new Error(`${label}: use only letters, digits and hyphens`);
}

/** Reject symlinks at every existing component before touching run-owned files. */
function safePath(root, ...parts) {
  const base = realpathSync(root);
  const target = resolve(base, ...parts);
  const rel = relative(base, target);
  if (rel.startsWith(`..${sep}`) || rel === ".." || isAbsolute(rel)) throw new Error("path escapes repository");
  let cursor = base;
  for (const part of rel.split(sep).filter(Boolean)) {
    cursor = join(cursor, part);
    try {
      if (lstatSync(cursor).isSymbolicLink()) throw new Error(`symlinks are not allowed: ${relative(base, cursor)}`);
    } catch (error) { if (error.code !== "ENOENT") throw error; }
  }
  return target;
}

function runDirectory(root, runId) {
  if (typeof runId !== "string" || !RUN_ID.test(runId)) throw new Error("invalid run_id");
  return safePath(root, "results", "runs", runId);
}

function validArtifactPath(value) {
  return nonempty(value) && !isAbsolute(value) && !value.includes("\\") && !value.includes("\0") && value.split("/").every((part, index, parts) => part !== ".." && part !== "." && (part !== "" || index === parts.length - 1));
}

function resolveCatalog(root, category, value, requiredFile) {
  assertSegment(value, category);
  const catalog = safePath(root, category);
  const matches = readdirSync(catalog).filter((name) => name.toLowerCase() === value.toLowerCase() || name.toLowerCase().startsWith(`${value.toLowerCase()}-`));
  const exact = matches.find((name) => name.toLowerCase() === value.toLowerCase());
  if (!exact && matches.length !== 1) throw new Error(`${category}: ${value} ${matches.length ? "is ambiguous" : "not found"}`);
  const name = exact ?? matches[0];
  const dir = safePath(root, category, name);
  if (!lstatSync(dir).isDirectory() || (requiredFile && !existsSync(safePath(root, category, name, requiredFile)))) throw new Error(`${category}: invalid ${name}`);
  return name;
}

export function validateRun(record, { root, folderName } = {}) {
  const errors = [];
  validateSchema(record, schema, "run", errors);
  if (!isObject(record)) return errors;
  errors.push(...localRecordErrors(record).map(error=>'run.local_inference: '+error));
  if (folderName && record.run_id !== folderName) errors.push("run.run_id: must match directory name");
  if (typeof record.run_id === "string" && record.date && !record.run_id.startsWith(`${record.date}-`)) errors.push("run.date: must match run_id date");
  const attemptedAbort = record.status === "aborted" && record.execution?.started_at != null;
  const prepared = ["prepared", "running", "awaiting_review", "completed"].includes(record.status) || attemptedAbort;
  const executed = ["running", "awaiting_review", "completed"].includes(record.status) || attemptedAbort;
  const finished = ["awaiting_review", "completed"].includes(record.status);
  const terminal = ["completed", "aborted"].includes(record.status);
  const requireValue = (value, field) => { if (value === null || value === undefined || (typeof value === "string" && !nonempty(value))) errors.push(`run.${field}: required for ${record.status}`); };
  if (!terminal && record.verdict?.result !== "pending") errors.push("run.verdict.result: unfinished runs must be pending");
  if (record.status === "completed" && !["pass", "fail", "partial"].includes(record.verdict?.result)) errors.push("run.verdict.result: completed runs need pass, fail or partial");
  if (record.status === "aborted" && record.verdict?.result !== "aborted") errors.push("run.verdict.result: aborted runs must be aborted");
  if (prepared) {
    for (const field of ["manifest_path", "manifest_sha256", "prepared_at"]) requireValue(record.inputs?.[field], `inputs.${field}`);
    requireValue(record.provenance?.runner_version, "provenance.runner_version");
    if (!nonempty(record.provenance?.source_revision_reason)) requireValue(record.provenance?.git_dirty, "provenance.git_dirty");
    if (record.provenance?.git_commit === null && !nonempty(record.provenance?.source_revision_reason)) errors.push("run.provenance: git_commit or source_revision_reason required");
  }
  if (executed) {
    for (const [field, value] of [["harness.version", record.harness?.version], ["model.id", record.model?.id], ["model.identity_evidence", record.model?.identity_evidence], ["permissions.mode", record.permissions?.mode], ["sandbox.kind", record.sandbox?.kind], ["sandbox.network", record.sandbox?.network], ["execution.started_at", record.execution?.started_at], ["execution.cwd", record.execution?.cwd], ["execution.timeout_s", record.execution?.timeout_s], ["execution.image_id", record.execution?.image_id], ["execution.network_policy", record.execution?.network_policy], ["execution.budget_policy", record.execution?.budget_policy]]) requireValue(value, field);
    for (const [field, value] of [["harness.version", record.harness?.version], ["model.id", record.model?.id]]) if (typeof value === "string" && knownPlaceholder.test(value)) errors.push(`run.${field}: specify an exact observed identifier`);
    if (!Array.isArray(record.execution?.command) || record.execution.command.length === 0) errors.push("run.execution.command: required for execution");
  }
  if (finished) {
    requireValue(record.execution?.finished_at, "execution.finished_at");
    requireValue(record.loop?.stop_reason, "loop.stop_reason");
    if (record.execution?.exit_code === null && record.execution?.signal === null && record.execution?.timed_out !== true) errors.push("run.execution: exit_code, signal or timed_out is required after execution");
  }
  if (attemptedAbort) requireValue(record.execution?.finished_at, "execution.finished_at");
  if (record.model?.selection === "managed") {
    if (record.model.id !== null && !/^managed:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(record.model.id)) errors.push("run.model.id: managed selection requires managed:mode, not an invented model ID");
    if (record.model.lock !== true) errors.push("run.model.lock: managed selection must be locked");
  } else if (typeof record.model?.id === "string" && record.model.id.startsWith("managed:")) errors.push("run.model.selection: managed selector requires managed policy");
  if (record.execution?.started_at && record.execution?.finished_at && Date.parse(record.execution.finished_at) < Date.parse(record.execution.started_at)) errors.push("run.execution.finished_at: precedes started_at");
  if (terminal) requireValue(record.loop?.stop_reason, "loop.stop_reason");
  if (record.status === "completed") {
    for (const field of METRIC_FIELDS) {
      const [group, key] = field.split(".");
      if (record[group]?.[key] === null && !nonempty(record.metrics_unavailable?.[field])) errors.push(`run.${field}: supply measurement or metrics_unavailable reason`);
    }
    for (const field of ["method", "evaluator", "evidence_path", "evidence_sha256", "evaluated_at"]) requireValue(record.evaluation?.[field], `evaluation.${field}`);
    requireValue(record.verdict?.check_output, "verdict.check_output");
  }
  if (isObject(record.metrics_unavailable)) for (const field of Object.keys(record.metrics_unavailable)) {
    if (!METRIC_FIELDS.includes(field)) errors.push(`run.metrics_unavailable.${field}: unknown metric`);
    else { const [group, key] = field.split("."); if (record[group]?.[key] !== null) errors.push(`run.metrics_unavailable.${field}: reason only allowed for null measurement`); }
  }
  for (const [field, value] of [["trace_path", record.trace_path], ["inputs.manifest_path", record.inputs?.manifest_path], ["evaluation.evidence_path", record.evaluation?.evidence_path]]) {
    if (value !== null && value !== undefined && !validArtifactPath(value)) errors.push(`run.${field}: expected a relative path inside the run directory`);
  }
  if (root) {
    try {
      const dir = runDirectory(root, record.run_id);
      for (const [category, id, requiredFile] of [["experiments", record.harness?.name, "README.md"], ["agents", record.agent, "spec.md"], ["tasks", record.task, "task.md"]]) {
        assertSegment(id, category);
        if (!existsSync(safePath(root, category, id, requiredFile))) errors.push(`run: ${category}/${id}/${requiredFile} missing`);
      }
      for (const [field, path, hash] of [["inputs.manifest", record.inputs?.manifest_path, record.inputs?.manifest_sha256], ["evaluation.evidence", record.evaluation?.evidence_path, record.evaluation?.evidence_sha256]]) {
        if (!path || !validArtifactPath(path)) continue;
        const file = safePath(root, relative(realpathSync(root), dir), path);
        if (!existsSync(file) || !lstatSync(file).isFile()) errors.push(`run.${field}: file missing`);
        else if (hash && sha256(file) !== hash) errors.push(`run.${field}: SHA-256 mismatch`);
      }
      if (record.trace_path && validArtifactPath(record.trace_path)) {
        const trace = safePath(root, relative(realpathSync(root), dir), record.trace_path);
        if (!existsSync(trace) || !lstatSync(trace).isDirectory()) errors.push("run.trace_path: directory missing");
      }
    } catch (error) { errors.push(`run: ${error.message}`); }
  }
  return errors;
}

export function createRun({ root = process.cwd(), harness, agent, task, n, model = null, harnessVersion = null, provider = null }) {
  harness = resolveCatalog(root, "experiments", harness, "README.md");
  agent = resolveCatalog(root, "agents", agent, "spec.md");
  task = resolveCatalog(root, "tasks", task, "task.md");
  if (existsSync(safePath(root, "tasks", task, "task.json")) && loadTaskDescriptor(root, task).agent !== agent) throw new Error(`task ${task} expects agent ${loadTaskDescriptor(root, task).agent}`);
  if (n !== undefined && !/^[1-9]\d*$/.test(String(n))) throw new Error("n must be a positive integer");
  if (n !== undefined && !Number.isSafeInteger(Number(n))) throw new Error("n must be a safe integer");
  const date = new Date().toISOString().slice(0, 10);
  const base = `${date}-${harness}-${agent}-${task}`.toLowerCase();
  const runs = safePath(root, "results", "runs");
  mkdirSync(runs, { recursive: true });
  let counter = 1;
  let runId;
  let dir;
  while (true) {
    runId = n !== undefined ? `${base}-${n}` : `${base}${counter === 1 ? "" : `-${counter}`}`;
    dir = runDirectory(root, runId);
    try { mkdirSync(dir); break; }
    catch (error) {
      if (error.code !== "EEXIST") throw error;
      if (n !== undefined) throw new Error(`run already exists: ${runId}; it was not changed`);
      counter++;
    }
  }
  const record = {
    schema_version: 1, run_id: runId, date, status: "planned",
    harness: { name: harness, version: harnessVersion, mode: "cli" }, agent, task,
    model: { id: model, provider, selection: model?.startsWith('managed:') ? 'managed' : null, lock: model?.startsWith('managed:') ?? false, reasoning: null, observed_id: null, identity_evidence: null },
    permissions: { mode: null, blocked: [], asked: null }, sandbox: { kind: null, network: null },
    loop: { turns: null, stop_reason: null, budget_usd: null, cost_usd: null, tokens_in: null, tokens_out: null, wall_clock_s: null, compactions: null, subagents: null },
    metrics_unavailable: {},
    inputs: { manifest_path: null, manifest_sha256: null, prepared_at: null },
    provenance: { git_commit: null, git_dirty: null, recorded_at: new Date().toISOString(), runner_version: null, source_revision_reason: null },
    execution: { command: [], cwd: null, started_at: null, finished_at: null, exit_code: null, signal: null, timed_out: false, image_id: null, timeout_s: null, network_policy: null, budget_policy: null, proxy_image_id: null },
    evaluation: { method: null, evaluator: null, evidence_path: null, evidence_sha256: null, evaluated_at: null },
    verdict: { result: "pending", check_output: "", human_notes: "" },
    harness_changes: [], trace_path: "trace/", notes: "",
  };
  try {
    for (const sub of ["workspace", "trace", "artifacts"]) mkdirSync(join(dir, sub));
    const errors = validateRun(record, { root, folderName: runId });
    if (errors.length) throw new Error(errors.join("\n"));
    writeFileSync(join(dir, "run.json"), `${JSON.stringify(record, null, 2)}\n`, { flag: "wx", mode: 0o600 });
    return record;
  } catch (error) { rmSync(dir, { recursive: true, force: true }); throw error; }
}

export function readRun(root, runId) {
  const file = safePath(root, relative(realpathSync(root), runDirectory(root, runId)), "run.json");
  let record;
  try { record = JSON.parse(readFileSync(file, "utf8")); }
  catch (error) { throw new Error(`cannot read ${runId}/run.json: ${error.message}`); }
  const errors = validateRun(record, { root, folderName: runId });
  if (errors.length) throw new Error(`invalid ${runId}:\n${errors.join("\n")}`);
  return record;
}

const transitions = {
  planned: ["planned", "prepared", "aborted"],
  prepared: ["prepared", "running", "aborted"],
  running: ["running", "awaiting_review", "aborted"],
  awaiting_review: ["awaiting_review", "completed", "aborted"],
  completed: ["completed"], aborted: ["aborted"],
};

export function writeRun(root, record) {
  const errors = validateRun(record, { root, folderName: record?.run_id });
  if (errors.length) throw new Error(`invalid run record:\n${errors.join("\n")}`);
  const dir = runDirectory(root, record.run_id);
  const file = safePath(root, relative(realpathSync(root), dir), "run.json");
  if (!existsSync(file)) throw new Error("create the run with createRun first");
  const old = JSON.parse(readFileSync(file, "utf8"));
  if (!transitions[old.status]?.includes(record.status)) throw new Error(`invalid status transition: ${old.status} -> ${record.status}`);
  for (const key of ["schema_version", "run_id", "date", "agent", "task"]) if (old[key] !== record[key]) throw new Error(`immutable field: ${key}`);
  if (old.harness?.name !== record.harness.name) throw new Error("immutable field: harness.name");
  const tmp = join(dir, `.run-${randomUUID()}.tmp`);
  try {
    writeFileSync(tmp, `${JSON.stringify(record, null, 2)}\n`, { flag: "wx", mode: 0o600 });
    renameSync(tmp, file);
  } finally { rmSync(tmp, { force: true }); }
  return record;
}

/** Ledger parsing is intentionally independent of hidden checks and task contents. */
export function validateLedger(markdown, { runIds } = {}) {
  const ids = new Set();
  const errors = [];
  let table = false;
  for (const [index, line] of markdown.split(/\r?\n/).entries()) {
    if (/^\|\s*#\s*\|/.test(line)) { table = true; continue; }
    if (!table || !line.trim().startsWith("|")) continue;
    const cells = line.trim().slice(1, -1).split("|").map((cell) => cell.trim());
    if (cells.every((cell) => /^:?-+:?$/.test(cell))) continue;
    const label = `ledger line ${index + 1}`;
    if (cells.length !== 8) { errors.push(`${label}: expected 8 columns`); continue; }
    const [id, component, assumption, evidence, dateModel, trigger, rawMode, rawStatus] = cells;
    // Original sealed ledgers retain their source-language labels.
    const mode = ({ 'аренда': 'leased', 'адаптация': 'adapted', 'своё': 'owned' })[rawMode] ?? rawMode;
    const status = ({ 'предложена': 'proposed', 'подтверждена': 'confirmed', 'не подтверждена': 'unconfirmed', 'удалена': 'removed' })[rawStatus] ?? rawStatus;
    if (!/^L\d{3}$/.test(id)) errors.push(`${label}: invalid id`);
    if (ids.has(id)) errors.push(`${label}: duplicate id ${id}`);
    ids.add(id);
    for (const [column, cell] of cells.entries()) if (!cell || /^[-—?]+$/.test(cell)) errors.push(`${label}: column ${column + 1} must be filled`);
    if (!/(?:experiments|scripts|results)\//.test(component)) errors.push(`${label}: component must identify its experiments/, scripts/ or results/ path`);
    if (!/\d{4}-\d{2}-\d{2}/.test(dateModel)) errors.push(`${label}: date/model column needs a date`);
    if (!["leased", "adapted", "owned"].includes(mode)) errors.push(`${label}: invalid ownership mode`);
    if (!["proposed", "confirmed", "unconfirmed", "removed"].includes(status)) errors.push(`${label}: invalid status`);
    if (status === "confirmed") {
      const refs = new Set(evidence.match(/\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*/g) ?? []);
      if (refs.size < 2) errors.push(`${label}: confirmed component needs before/after run IDs`);
      if (runIds) for (const ref of refs) if (!runIds.has(ref)) errors.push(`${label}: evidence run ${ref} does not exist`);
    }
  }
  if (!table) errors.push("ledger: table header missing");
  return { ids, errors };
}
