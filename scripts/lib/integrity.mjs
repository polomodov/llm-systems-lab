import { localRecordErrors } from './local-inference.mjs';
import { existsSync, lstatSync, readFileSync } from 'node:fs';
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
  if(record.model?.provider==='local') {
    const errors=localRecordErrors(record);if(errors.length)throw new Error('Run integrity: '+errors.join('; '));
    const text=readFileSync(ownedPath(inputs,'control/local-deployment.json'));
    if(sha256(text)!==record.local_inference.deployment_sha256 || JSON.stringify(JSON.parse(text))!==JSON.stringify(record.local_inference.deployment))throw new Error('Run integrity: local deployment differs from sealed preparation');
    if(record.local_inference.observed) {
      const proof=JSON.parse(readFileSync(ownedPath(dir,'trace/local-native/startup-process.json')));
      if(JSON.stringify(proof)!==JSON.stringify(record.local_inference.observed))throw new Error('Run integrity: observed native proof differs from record');
    }
  }
  if (record.status !== 'prepared' && record.status !== 'completed') return;
  let workspaceExists = false;
  try {
    const workspaceStat = lstatSync(join(dir, 'workspace'));
    if (workspaceStat.isSymbolicLink()) throw new Error('Run integrity: symlink is not accepted: workspace');
    workspaceExists = true;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (record.status === 'prepared') {
    if (!Array.isArray(manifest.workspace)) throw new Error('Run integrity: prepared workspace inventory missing');
    // Git archives omit workspaces. Inspect the sealed preparation in that case;
    // execution still requires the complete live tree through run.verifyInputs.
    if (workspaceExists) sameInventory(ownedPath(dir, 'workspace', 'directory'), manifest.workspace, 'prepared workspace');
    return;
  }

  const evidencePath = ownedPath(dir, record.evaluation.evidence_path);
  const evidenceText = readFileSync(evidencePath);
  if (sha256(evidenceText) !== record.evaluation.evidence_sha256) throw new Error('Run integrity: evaluation SHA-256 mismatch');
  const evidence = JSON.parse(evidenceText);
  if (evidence.run_id !== record.run_id || evidence.result !== record.verdict.result || evidence.method !== record.evaluation.method || evidence.evaluator !== record.evaluation.evaluator || evidence.check_output !== record.verdict.check_output) throw new Error('Run integrity: sealed evaluation differs from record');
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
    if (directory === 'workspace') {
      if (workspaceExists) sameInventory(ownedPath(dir, directory, 'directory'), snapshot, label);
      continue;
    }
    // Git cannot retain an empty directory, so a clean checkout may legitimately
    // lack artifacts/. Absence is only acceptable for an empty sealed inventory.
    if (!existsSync(join(dir, directory))) {
      if (snapshot.length !== 0) throw new Error(`Run integrity: ${label} directory is missing but the sealed inventory is not empty`);
      continue;
    }
    sameInventory(ownedPath(dir, directory, 'directory'), snapshot, label);
  }
}
