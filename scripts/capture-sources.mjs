#!/usr/bin/env node
// Snapshot web sources for a task (T001) to support reproducible series.
// Run task setup.sh in an empty temporary directory, read sources.txt and fetch
// each seed URL with the gateway fetchPublic function. Depth-1 links are not
// archived: replay will report them as unavailable sources.
// Write a JSONL archive in trace/sources.jsonl format with an adjacent manifest;
// never overwrite existing files.
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { fetchPublic, normalizeUrl, replayFetcher } from '../experiments/common/egress.mjs';
import { loadTaskDescriptor } from './lib/tasks.mjs';
import { sha256, safePath } from './lib/files.mjs';
import { args, options, main } from './lib/cli.mjs';

export function parseSources(text) {
  return [...new Set(text.split('\n').map(line => line.replace(/\s+#.*$/, '').trim()).filter(Boolean).map(normalizeUrl))];
}
export async function captureSources(root, { task, asOf, out, fetcher = fetchPublic, now = () => new Date() } = {}) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asOf ?? '') || new Date(asOf).toISOString().slice(0, 10) !== asOf) throw new Error('--as-of must be a calendar date YYYY-MM-DD');
  const descriptor = loadTaskDescriptor(root, task);
  if (!descriptor.network.sources) throw new Error(`${task} has no web sources to capture`);
  const target = safePath(root, out ?? join('tasks', task, 'archive', `sources-${asOf}.jsonl`));
  const manifestPath = target.replace(/\.jsonl$/, '') + '.manifest.json';
  if (!target.endsWith('.jsonl')) throw new Error('Archive path must end with .jsonl');
  if (existsSync(target) || existsSync(manifestPath)) throw new Error(`Archive exists: ${target}; captures are never overwritten`);
  const staging = mkdtempSync(join(tmpdir(), 'harness-capture-'));
  try {
    const workspace = join(staging, 'workspace');
    const setup = spawnSync('bash', [join(root, 'tasks', task, 'setup.sh'), workspace, ...(descriptor.setup_args.includes('as-of') ? [asOf] : [])], { cwd: root, encoding: 'utf8', env: { PATH: process.env.PATH, HOME: process.env.HOME, LC_ALL: 'C' } });
    if (setup.status !== 0) throw new Error(`Setup failed: ${setup.stderr || setup.status}`);
    const urls = parseSources(readFileSync(join(workspace, 'sources.txt'), 'utf8'));
    const rows = [], failed = [];
    for (const url of urls) {
      try {
        const result = await fetcher(url);
        rows.push({ type: 'source', requested_url: url, fetched_at: now().toISOString(), url: result.url, status: result.status, content_type: result.content_type, body: result.body });
      } catch (error) { failed.push({ url, error: error.message }); }
    }
    const archive = rows.map(row => JSON.stringify(row) + '\n').join('');
    if (rows.length) replayFetcher(archive); // The archive must be loadable by prepare-run before it is written.
    else throw new Error(`No source was fetched: ${failed.map(f => `${f.url}: ${f.error}`).join('; ')}`);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, archive, { flag: 'wx' });
    const manifest = { kind: 'source-archive', task, as_of: asOf, captured_at: now().toISOString(), depth: 0, sha256: sha256(archive), sources: urls.length, fetched: rows.map(row => ({ url: row.requested_url, status: row.status, bytes: Buffer.byteLength(row.body) })), failed, note: 'Live pages captured on captured_at, not on as_of; depth-1 links are not archived and read as unavailable in replay.' };
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
    return { archive: target, manifest: manifestPath, fetched: rows.length, failed };
  } finally { rmSync(staging, { recursive: true, force: true }); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(async () => {
  const a = args(); options(a, ['task', 'as-of', 'out'], ['task', 'as-of']);
  const result = await captureSources(process.cwd(), { task: a.task.startsWith('T') && !a.task.includes('-') ? `${a.task}-dossier-from-sources` : a.task, asOf: a['as-of'], out: a.out });
  console.log(`[capture] ${result.fetched} fetched, ${result.failed.length} failed → ${result.archive}`);
  for (const f of result.failed) console.error(`[capture] failed ${f.url}: ${f.error}`);
});
