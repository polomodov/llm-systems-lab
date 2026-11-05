import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createRun, METRIC_FIELDS, readRun, validateLedger, validateRun, writeRun } from "../scripts/lib/records.mjs";

const checkScript = fileURLToPath(new URL("../scripts/check.mjs", import.meta.url));
const newScript = fileURLToPath(new URL("../scripts/new-run.mjs", import.meta.url));
const stamp = "2026-09-20T12:00:00.000Z";
const ledger = "| # | Компонента | Предположение | Доказательство | Дата и модель | Триггер | Режим | Статус |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| L001 | `experiments/example/config.json` | граница | требование метода | 2026-09-20 · модель | никогда | адаптация | предложена |\n";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "harness-records-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const [dir, file] of [["experiments/example", "README.md"], ["agents/a1-fixture", "spec.md"], ["tasks/T001-fixture", "task.md"], ["docs", "harness-ledger.md"]]) {
    mkdirSync(join(root, dir), { recursive: true });
    // Контракт задачи обязан называть бюджет: его читает раннер и проверяет check.
    const contents = { "harness-ledger.md": ledger, "task.md": "# T001-fixture\n\n## Бюджет\nДо 5 ходов или $1.\n" };
    writeFileSync(join(root, dir, file), contents[file] ?? "fixture\n");
  }
  writeFileSync(join(root, "tasks/T001-fixture/setup.sh"), "#!/usr/bin/env bash\nmkdir -p \"$1/artifacts\"\n");
  writeFileSync(join(root, "tasks/T001-fixture/task.json"), JSON.stringify({ schema_version: 1, id: "T001-fixture", agent: "a1-fixture", workspace: "files", branch_prefix: null, evaluation: "rubric", required_artifacts: ["report.md"], network: { connect_domains: [], sources: false }, setup_args: [] }));
  return root;
}

const create = (root, overrides = {}) => createRun({ root, harness: "example", agent: "a1", task: "T001", ...overrides });
const runDir = (root, record) => join(root, "results", "runs", record.run_id);

function attachFile(root, record, path, content) {
  writeFileSync(join(runDir(root, record), path), content);
  return createHash("sha256").update(content).digest("hex");
}

function prepare(root, record) {
  record.status = "prepared";
  record.inputs = { manifest_path: "artifacts/manifest.json", manifest_sha256: attachFile(root, record, "artifacts/manifest.json", "{}\n"), prepared_at: stamp };
  Object.assign(record.provenance, { git_commit: "a".repeat(40), git_dirty: false, runner_version: "1" });
  return writeRun(root, record);
}

function start(root, record) {
  record.status = "running";
  record.harness.version = "1.2.3";
  record.model.id = "fixture-model-2026-09-20";
  record.model.identity_evidence = "request-only";
  record.permissions.mode = "fixture-controlled";
  record.sandbox = { kind: "container", network: "off" };
  Object.assign(record.execution, { command: ["fixture", "--once"], cwd: "/workspace", started_at: stamp, timeout_s: 60, image_id: "sha256:" + "b".repeat(64), network_policy: "off", budget_policy: "observed" });
  return writeRun(root, record);
}

function finish(root, record) {
  record.status = "awaiting_review";
  record.loop.stop_reason = "fixture process exited";
  Object.assign(record.execution, { finished_at: "2026-09-20T12:00:01.000Z", exit_code: 0 });
  return writeRun(root, record);
}

function complete(root, record) {
  record.status = "completed";
  record.verdict = { result: "pass", check_output: "fixture review passed", human_notes: "" };
  record.metrics_unavailable = Object.fromEntries(METRIC_FIELDS.map((field) => [field, "fixture does not expose this measurement"]));
  record.evaluation = { method: "human", evaluator: "fixture", evidence_path: "artifacts/evaluation.txt", evidence_sha256: attachFile(root, record, "artifacts/evaluation.txt", "fixture review passed\n"), evaluated_at: "2026-09-20T12:00:02.000Z" };
  return record;
}

test("creation resolves catalog aliases and distinguishes planned from experimental evidence", (t) => {
  const root = fixture(t);
  const record = create(root);
  assert.equal(record.agent, "a1-fixture");
  assert.equal(record.task, "T001-fixture");
  assert.equal(record.status, "planned");
  assert.equal(record.verdict.result, "pending");
  assert.ok(METRIC_FIELDS.every((field) => { const [group, key] = field.split("."); return record[group][key] === null; }));
  assert.deepEqual(readRun(root, record.run_id), record);
  const check = spawnSync(process.execPath, [checkScript], { cwd: root, encoding: "utf8" });
  assert.equal(check.status, 0, check.stderr);
  assert.match(check.stdout, /completed=0/);
  assert.match(check.stdout, /no experimental evidence/);
});

test("explicit run number never overwrites an existing record or workspace", (t) => {
  const root = fixture(t);
  const record = create(root, { n: 4 });
  const path = join(runDir(root, record), "run.json");
  const before = readFileSync(path, "utf8");
  writeFileSync(join(runDir(root, record), "workspace", "work.txt"), "keep me");
  assert.throws(() => create(root, { n: 4 }), /already exists/);
  assert.equal(readFileSync(path, "utf8"), before);
  assert.equal(readFileSync(join(runDir(root, record), "workspace", "work.txt"), "utf8"), "keep me");
  assert.notEqual(create(root).run_id, create(root).run_id);
});

test("creation rejects traversal, unknown catalogs and invalid counters", (t) => {
  const root = fixture(t);
  for (const n of [0, -1, "../x", "1/x", "2.5", "9007199254740992"]) assert.throws(() => create(root, { n }));
  for (const harness of ["../escape", "missing", "example/x", "/tmp/x"]) assert.throws(() => create(root, { harness }));
  assert.throws(() => readRun(root, "../../etc/passwd"), /invalid run_id/);
});

test("symlinked catalogs, run parents and artifacts cannot escape the lab", (t) => {
  const root = fixture(t);
  const target = mkdtempSync(join(tmpdir(), "harness-target-"));
  t.after(() => rmSync(target, { recursive: true, force: true }));
  symlinkSync(target, join(root, "experiments", "linked"));
  assert.throws(() => create(root, { harness: "linked" }), /symlinks/);
  const record = create(root);
  symlinkSync(target, join(runDir(root, record), "linked"));
  record.inputs.manifest_path = "linked/secret.json";
  assert.ok(validateRun(record, { root }).some((error) => /symlinks/.test(error)));
  const otherRoot = fixture(t);
  mkdirSync(join(otherRoot, "results"));
  symlinkSync(target, join(otherRoot, "results", "runs"));
  assert.throws(() => create(otherRoot), /symlinks/);
});

test("validator reports malformed input without throwing", (t) => {
  const root = fixture(t);
  for (const value of [null, [], false, 17, "record", { status: "completed", loop: null, execution: null, metrics_unavailable: [] }]) {
    let errors;
    assert.doesNotThrow(() => { errors = validateRun(value); });
    assert.ok(errors.length > 0);
  }
  const record = create(root);
  record.loop.tokens_in = -1;
  record.loop.wall_clock_s = Infinity;
  record.permissions.asked = 1.5;
  record.model.typo = true;
  record.date = "2026-02-30";
  const errors = validateRun(record);
  for (const key of ["tokens_in", "wall_clock_s", "asked", "typo", "date"]) assert.ok(errors.some((error) => error.includes(key)), errors.join("\n"));
});

test("full lifecycle requires measurements or explicit reasons and recorded evaluation", (t) => {
  const root = fixture(t);
  const record = complete(root, finish(root, start(root, prepare(root, create(root)))));
  assert.deepEqual(validateRun(record, { root }), []);
  delete record.metrics_unavailable["loop.tokens_in"];
  assert.throws(() => writeRun(root, record), /tokens_in/);
  record.loop.tokens_in = 0;
  record.evaluation.evaluator = null;
  assert.throws(() => writeRun(root, record), /evaluator/);
  record.evaluation.evaluator = "fixture";
  writeRun(root, record);
  assert.equal(readRun(root, record.run_id).status, "completed");
  record.metrics_unavailable["loop.tokens_in"] = "stale reason";
  assert.throws(() => writeRun(root, record), /reason only allowed/);
});

test("lifecycle rejects skipped stages, reopening, changed identity and pending final verdict", (t) => {
  const root = fixture(t);
  const initial = create(root);
  const before = readFileSync(join(runDir(root, initial), "run.json"), "utf8");
  initial.status = "completed";
  assert.throws(() => writeRun(root, initial), /completed/);
  assert.equal(readFileSync(join(runDir(root, initial), "run.json"), "utf8"), before);
  const record = complete(root, finish(root, start(root, prepare(root, create(root)))));
  writeRun(root, record);
  record.status = "awaiting_review";
  record.verdict.result = "pending";
  assert.throws(() => writeRun(root, record), /invalid status transition/);
  const planned = create(root);
  planned.agent = "a2-other";
  mkdirSync(join(root, "agents", planned.agent));
  writeFileSync(join(root, "agents", planned.agent, "spec.md"), "fixture");
  assert.throws(() => writeRun(root, planned), /immutable field/);
});

test("manifest and evaluation hashes detect tampering without inspecting hidden checks", (t) => {
  const root = fixture(t);
  const record = complete(root, finish(root, start(root, prepare(root, create(root)))));
  writeRun(root, record);
  writeFileSync(join(runDir(root, record), record.evaluation.evidence_path), "changed verdict");
  assert.throws(() => readRun(root, record.run_id), /evaluation.evidence: SHA-256 mismatch/);
  writeFileSync(join(runDir(root, record), record.inputs.manifest_path), "changed initial input");
  assert.ok(validateRun(record, { root }).some((error) => error.includes("inputs.manifest: SHA-256 mismatch")));
});

test("artifact paths cannot traverse or point outside the run", (t) => {
  const root = fixture(t);
  const record = create(root);
  for (const value of ["../outside", "/tmp/outside", "artifacts/../../outside", "artifacts\\outside", "artifacts//outside"]) {
    record.inputs.manifest_path = value;
    assert.ok(validateRun(record).some((error) => /relative path/.test(error)));
  }
});

test("aborting requires an explicit aborted verdict and stop reason", (t) => {
  const root = fixture(t);
  const record = create(root);
  record.status = "aborted";
  assert.throws(() => writeRun(root, record), /aborted runs must be aborted/);
  record.verdict.result = "aborted";
  assert.throws(() => writeRun(root, record), /stop_reason/);
  record.loop.stop_reason = "operator cancelled before setup";
  writeRun(root, record);
  assert.equal(readRun(root, record.run_id).status, "aborted");
});

test("ledger validates filled columns, ownership, unique IDs and actual before/after references", () => {
  assert.deepEqual(validateLedger(ledger).errors, []);
  assert.ok(validateLedger(ledger + ledger.split("\n")[2]).errors.some((error) => /duplicate/.test(error)));
  assert.ok(validateLedger(ledger.replace("| никогда |", "| | ")).errors.some((error) => /must be filled/.test(error)));
  assert.ok(validateLedger(ledger.replace("адаптация", "mystery")).errors.some((error) => /ownership/.test(error)));
  assert.ok(validateLedger(ledger.replace("предложена", "подтверждена")).errors.some((error) => /before\/after/.test(error)));
  const confirmed = ledger.replace("требование метода", "2026-09-20-example-a1-t001-1, 2026-09-20-example-a1-t001-2").replace("предложена", "подтверждена");
  assert.ok(validateLedger(confirmed, { runIds: new Set() }).errors.some((error) => /does not exist/.test(error)));
});

test("check handles null JSON and missing ledger references with diagnostic errors", (t) => {
  const root = fixture(t);
  const record = create(root);
  const path = join(runDir(root, record), "run.json");
  writeFileSync(path, "null\n");
  const malformed = spawnSync(process.execPath, [checkScript], { cwd: root, encoding: "utf8" });
  assert.equal(malformed.status, 1);
  assert.match(malformed.stderr, /expected object/);
  assert.doesNotMatch(malformed.stderr, /TypeError/);
  record.harness_changes.push({ component: "fixture", kind: "walls", ledger: "L999" });
  writeFileSync(path, JSON.stringify(record));
  const missing = spawnSync(process.execPath, [checkScript], { cwd: root, encoding: "utf8" });
  assert.equal(missing.status, 1);
  assert.match(missing.stderr, /L999 not found/);
});

test("new-run CLI refuses unknown options and duplicate options without creating records", (t) => {
  const root = fixture(t);
  for (const args of [["--harness", "example", "--harness", "example"], ["--surprise", "true"], ["--harness"]]) {
    const child = spawnSync(process.execPath, [newScript, ...args], { cwd: root, encoding: "utf8" });
    assert.equal(child.status, 1);
    assert.match(child.stderr, /invalid or duplicate option/);
  }
});
