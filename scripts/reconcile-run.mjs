#!/usr/bin/env node
// Recover accounting after coordinator loss (SIGKILL or host failure).
// A running record without a live coordinator becomes aborted with reason
// coordinator_lost. Run containers and network are removed; their logs are
// saved in trace/ with the selected credential redacted. Runs never resume
// automatically: every retry requires a new record.
import { existsSync, readFileSync, writeFileSync, rmSync, mkdirSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { readRun, writeRun } from './lib/records.mjs';
import { validateProfile, selectProvider } from './lib/harnesses.mjs';
import { credentials } from './run.mjs';
import { args, options, main } from './lib/cli.mjs';

export function dockerCommand(argv, { env = process.env, timeout = 60000 } = {}) {
  const result = spawnSync('docker', argv, { encoding: 'utf8', env, timeout, maxBuffer: 64 * 1024 * 1024 });
  return { ok: result.status === 0, stdout: result.stdout ?? '', stderr: result.stderr ?? result.error?.message ?? '' };
}
export function processAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; }
}
/** Orphaned lab containers and networks: everything labelled harness-lab=true that no live coordinator owns. */
export function orphans(docker = dockerCommand) {
  const names = text => text.split('\n').map(line => line.trim()).filter(Boolean);
  const containers = docker(['ps', '-a', '--filter', 'label=harness-lab=true', '--format', '{{.Names}}\t{{.Status}}']);
  const networks = docker(['network', 'ls', '--filter', 'label=harness-lab=true', '--format', '{{.Name}}']);
  return { containers: containers.ok ? names(containers.stdout).map(row => { const [name, status] = row.split('\t'); return { name, status }; }) : null, networks: networks.ok ? names(networks.stdout) : null, error: containers.ok && networks.ok ? null : (containers.stderr || networks.stderr).trim() };
}
export function reconcileRun(root, runId, { docker = dockerCommand, now = () => new Date(), alive = processAlive, force = false } = {}) {
  const record = readRun(root, runId), dir = join(root, 'results/runs', runId);
  if (record.status !== 'running') throw new Error(`Only a running record can be reconciled; ${runId} is ${record.status}`);
  const runtimePath = join(dir, 'trace/runtime.json');
  const runtime = existsSync(runtimePath) ? JSON.parse(readFileSync(runtimePath, 'utf8')) : null;
  if (runtime && !force && alive(runtime.coordinator_pid)) throw new Error(`Coordinator pid ${runtime.coordinator_pid} is still alive on this host; wait for it or pass --force only if the pid is known to be unrelated`);
  let redact = text => String(text);
  try {
    const profile = validateProfile(JSON.parse(readFileSync(join(dir, 'inputs/control/harness.json'), 'utf8')), record.harness.name);
    const provider = selectProvider(profile, record.model.provider);
    const secrets = Object.values(credentials(root, provider.credential_env));
    redact = text => secrets.reduce((out, secret) => out.replaceAll(secret, '[REDACTED]'), String(text));
  } catch { /* Without .env the logs are kept unredacted only if the record never had a cloud credential; see note below. */ }
  const removed = [], missing = [], recovered = [];
  const containers = runtime ? [runtime.agent, runtime.proxy] : [];
  for (const name of containers) {
    const inspect = docker(['inspect', '--format', '{{.State.Status}}\t{{.State.ExitCode}}\t{{.State.FinishedAt}}', name]);
    if (!inspect.ok) { missing.push(name); continue; }
    const [status, exitCode, finishedAt] = inspect.stdout.trim().split('\t');
    const logs = docker(['logs', name]);
    if (logs.ok) { const file = `trace/recovered-${name === runtime.agent ? 'agent' : 'proxy'}.log`; writeFileSync(join(dir, file), redact(logs.stdout + logs.stderr)); recovered.push(file); }
    docker(['rm', '-f', name]);
    removed.push({ name, status, exit_code: Number(exitCode), finished_at: finishedAt });
    if (name === runtime.agent && status === 'exited') record.execution.exit_code = Number(exitCode);
  }
  if (runtime) docker(['network', 'rm', runtime.network]);
  const sources = join(dir, 'trace/network/sources.jsonl');
  if (existsSync(sources) && !existsSync(join(dir, 'trace/sources.jsonl'))) { writeFileSync(join(dir, 'trace/sources.jsonl'), redact(readFileSync(sources, 'utf8'))); recovered.push('trace/sources.jsonl'); }
  const stamp = now().toISOString();
  record.status = 'aborted'; record.verdict.result = 'aborted'; record.loop.stop_reason = 'coordinator_lost';
  record.execution.finished_at = stamp; record.execution.signal = null; record.execution.timed_out = false;
  record.metrics_unavailable = { ...record.metrics_unavailable, 'loop.turns': 'Coordinator lost before the trace was parsed', 'loop.tokens_in': 'Coordinator lost before the trace was parsed', 'loop.tokens_out': 'Coordinator lost before the trace was parsed', 'loop.cost_usd': 'Coordinator lost before the trace was parsed', 'loop.wall_clock_s': 'Coordinator lost; execution end time is the reconciliation time, not the agent exit' };
  record.notes = `${record.notes}\nExecution aborted: coordinator_lost; reconciled ${stamp}${runtime ? '' : ' without trace/runtime.json (run started before runtime names were recorded)'}; containers removed: ${removed.map(c => `${c.name} (${c.status}, exit ${c.exit_code})`).join(', ') || 'none'}; not found: ${missing.join(', ') || 'none'}; recovered: ${recovered.join(', ') || 'nothing'}. The hidden check is not applied; a retry is a new run.`.trim();
  mkdirSync(join(dir, 'trace'), { recursive: true });
  writeFileSync(join(dir, 'trace/reconciliation.json'), JSON.stringify({ reconciled_at: stamp, runtime, removed, missing, recovered }, null, 2) + '\n');
  writeRun(root, record);
  rmSync(join(dir, '.lock'), { recursive: true, force: true });
  return { record, removed, missing, recovered };
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const a = args(); options(a, ['run', 'force']);
  if (a.force !== undefined && a.force !== 'yes') throw new Error('--force takes only the value yes');
  if (!a.run) {
    const root = process.cwd();
    const runs = join(root, 'results/runs');
    const running = (existsSync(runs) ? readdirSync(runs).filter(id => /^\d{4}-/.test(id)) : []).filter(id => readRun(root, id).status === 'running');
    console.log(`[reconcile] running records: ${running.join(', ') || 'none'}`);
    const found = orphans();
    if (found.error) console.log(`[reconcile] docker unavailable: ${found.error}`);
    else console.log(`[reconcile] harness-lab containers: ${found.containers.map(c => `${c.name} (${c.status})`).join(', ') || 'none'}; networks: ${found.networks.join(', ') || 'none'}`);
    console.log('Usage: npm run reconcile -- --run <run-id> [--force yes]');
    return;
  }
  const { record, removed, missing, recovered } = reconcileRun(process.cwd(), a.run, { force: a.force === 'yes' });
  console.log(`[reconcile] ${record.run_id}: ${record.status}/${record.loop.stop_reason}; removed ${removed.length}, missing ${missing.length}, recovered ${recovered.join(', ') || 'nothing'}`);
});
