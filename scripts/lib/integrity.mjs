import { lstatSync, readFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { inventory, safePath, sha256 } from './files.mjs';

function ownedPath(root, path, kind = 'file') {
  const full = safePath(root, path);
  let cursor = resolve(root);
  for (const part of relative(cursor, full).split(sep)) {
    cursor = join(cursor, part);
    if (lstatSync(cursor).isSymbolicLink()) throw new Error(`Run integrity: symlink is not accepted: ${path}`);
  }
  const stat = lstatSync(full);
  if (kind === 'file' ? !stat.isFile() : !stat.isDirectory()) throw new Error(`Run integrity: expected ${kind}: ${path}`);
  return full;
}

function sameInventory(path, expected, label) {
  if (!Array.isArray(expected) || JSON.stringify(inventory(path)) !== JSON.stringify(expected)) throw new Error(`Run integrity: ${label} changed after snapshot`);
}

/** Verify native coordinator snapshots without importing the runner or records module. */
export function verifyRunIntegrity(root, record) {
  if (!record?.inputs?.manifest_path) return;
  if (!/^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(record.run_id)) throw new Error('Run integrity: invalid run_id');
  const dir = ownedPath(root, `results/runs/${record.run_id}`, 'directory');
  const manifestPath = ownedPath(dir, record.inputs.manifest_path);
  const manifestText = readFileSync(manifestPath);
  if (sha256(manifestText) !== record.inputs.manifest_sha256) throw new Error('Run integrity: input manifest SHA-256 mismatch');
  const manifest = JSON.parse(manifestText);
  // Generic record importers may attach their own manifest format. Native files
  // always declare version; an unknown native version must never silently pass.
  if (manifest?.version === undefined) return;
  if (manifest.version !== 1) throw new Error('Run integrity: unsupported native manifest version');
  if (manifest.task !== record.task || manifest.harness !== record.harness.name) throw new Error('Run integrity: manifest identity differs from record');
  const inputs = ownedPath(dir, relative(dir, dirname(manifestPath)), 'directory');
  const actual = inventory(inputs).filter(row => row.path !== basename(manifestPath));
  if (!Array.isArray(manifest.files) || JSON.stringify(actual) !== JSON.stringify(manifest.files)) throw new Error('Run integrity: sealed input snapshot changed');
  if (record.status === 'prepared') sameInventory(ownedPath(dir, 'workspace', 'directory'), manifest.workspace, 'prepared workspace');
  if (record.status !== 'completed') return;

  const evidencePath = ownedPath(dir, record.evaluation.evidence_path);
  const evidenceText = readFileSync(evidencePath);
  if (sha256(evidenceText) !== record.evaluation.evidence_sha256) throw new Error('Run integrity: evaluation SHA-256 mismatch');
  const evidence = JSON.parse(evidenceText);
  if (evidence.run_id !== record.run_id || evidence.result !== record.verdict.result || evidence.method !== record.evaluation.method || evidence.evaluator !== record.evaluation.evaluator || evidence.check_output !== record.verdict.check_output) throw new Error('Run integrity: sealed evaluation differs from record');
  let workspaceExists = false;
  try {
    const workspaceStat = lstatSync(join(dir, 'workspace'));
    if (workspaceStat.isSymbolicLink()) throw new Error('Run integrity: symlink is not accepted: workspace');
    workspaceExists = true;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  for (const [path, field, directory, label] of [
    ['trace/artifacts.json', 'artifacts_sha256', 'artifacts', 'artifacts'],
    ['trace/final-workspace.json', 'workspace_sha256', 'workspace', 'final workspace'],
  ]) {
    const text = readFileSync(ownedPath(dir, path));
    if (typeof evidence[field] !== 'string' || sha256(text) !== evidence[field]) throw new Error(`Run integrity: ${path} differs from sealed evaluation`);
    const snapshot = JSON.parse(text);
    if (!Array.isArray(snapshot)) throw new Error(`Run integrity: ${path} must contain an inventory`);
    // Workspaces are intentionally git-ignored. The committed final manifest is
    // still bound to evaluation when checking a clone of the empirical archive.
    if (directory !== 'workspace' || workspaceExists) sameInventory(ownedPath(dir, directory, 'directory'), snapshot, label);
  }
}
