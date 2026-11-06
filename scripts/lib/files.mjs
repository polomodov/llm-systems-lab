import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, lstatSync, mkdirSync, copyFileSync, realpathSync, existsSync } from 'node:fs';
import { join, relative, resolve, sep, dirname } from 'node:path';
export const sha256 = value => createHash('sha256').update(value).digest('hex');
export function inventory(root, prefix = '') {
  const rows = [];
  for (const name of readdirSync(join(root, prefix)).sort()) {
    const path = join(prefix, name), full = join(root, path), stat = lstatSync(full);
    if (stat.isSymbolicLink()) throw new Error(`Symlink is not accepted in snapshots/artifacts: ${path}`);
    if (stat.isDirectory()) rows.push(...inventory(root, path));
    else if (stat.isFile()) rows.push({ path: path.split(sep).join('/'), sha256: sha256(readFileSync(full)), bytes: stat.size, executable: !!(stat.mode & 0o111) });
    else throw new Error(`Unsupported file type: ${path}`);
  }
  return rows;
}
export function safePath(root, path) {
  if (typeof path !== 'string' || !path || path.includes('\0')) throw new Error('Invalid relative path');
  const full = resolve(root, path), rel = relative(resolve(root), full);
  if (!rel || rel.startsWith(`..${sep}`) || rel === '..' || resolve(path) === path) throw new Error(`Path escapes run: ${path}`);
  let cursor = resolve(root);
  for (const part of rel.split(sep)) {
    cursor = join(cursor, part);
    try { if (lstatSync(cursor).isSymbolicLink()) throw new Error(`Symlinks are not accepted: ${path}`); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return full;
}
export function copyTree(source, dest) {
  const rows = inventory(source);
  mkdirSync(dest, { recursive: true });
  for (const row of rows) { const to = join(dest, row.path); mkdirSync(dirname(to), { recursive: true }); copyFileSync(join(source, row.path), to); }
  return rows;
}
/** One writer per run: report a stale lock directory explicitly instead of an opaque EEXIST. */
export function acquireLock(dir) {
  const lock = join(dir, '.lock');
  try { mkdirSync(lock); } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    throw new Error(`Run is locked by ${lock}: another coordinator works on it, or a previous one was killed. Inspect the run and containers labelled harness-lab=true, then remove that directory to retry.`);
  }
  return lock;
}
