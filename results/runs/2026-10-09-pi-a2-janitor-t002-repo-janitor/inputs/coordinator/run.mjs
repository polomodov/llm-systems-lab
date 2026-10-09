#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { readRun, writeRun } from './lib/records.mjs';
import { inventory, copyTree, sha256, safePath, acquireLock } from './lib/files.mjs';
import { validateProfile, selectProvider, selectModel } from './lib/harnesses.mjs';
import { taskLimits } from './lib/contracts.mjs';
import { localRecordErrors } from './lib/local-inference.mjs';
import { args, options, main } from './lib/cli.mjs';
export function docker(argv, { env = process.env, timeout = 120000 } = {}) {
  const result = spawnSync('docker', argv, { encoding: 'utf8', env, timeout, maxBuffer: 16 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`Docker ${argv[0]} failed: ${result.error?.message || result.stderr.trim() || result.status}`);
  return result.stdout.trim();
}
export function credentials(root, keys) {
  if (!keys.length) return {};
  const path = join(root, '.env');
  if (!existsSync(path)) throw new Error(`Create .env with ${keys.join(', ')}; host credentials are not imported`);
  const lines = readFileSync(path, 'utf8').split(/\r?\n/), result = {};
  for (const key of keys) {
    if (!/^[A-Z][A-Z0-9_]*$/.test(key)) throw new Error('Invalid credential variable');
    const matches = lines.filter(line => new RegExp(`^\\s*${key}\\s*=`).test(line));
    if (matches.length !== 1) throw new Error(`.env must define ${key} exactly once`);
    let value = matches[0].slice(matches[0].indexOf('=') + 1).trim();
    if (/^(["']).*\1$/.test(value)) value = value.slice(1, -1);
    if (!value || /[\s$`\\"']/.test(value)) throw new Error(`Invalid literal ${key}`);
    result[key] = value;
  }
  return result;
}
// Backward-compatible helper for the first adapter; all runner logic is generic.
export const apiKey = root => credentials(root, ['ANTHROPIC_API_KEY']).ANTHROPIC_API_KEY;

export function verifyInputs(dir, record, { workspace = true } = {}) {
  const manifestPath = safePath(dir, record.inputs.manifest_path), text = readFileSync(manifestPath);
  if (sha256(text) !== record.inputs.manifest_sha256) throw new Error('Input manifest was modified');
  const manifest = JSON.parse(text);
  const actual = inventory(join(dir, 'inputs')).filter(x => x.path !== 'manifest.json');
  if (JSON.stringify(actual) !== JSON.stringify(manifest.files)) throw new Error('Sealed input snapshot was modified');
  if (workspace && JSON.stringify(inventory(join(dir, 'workspace'))) !== JSON.stringify(manifest.workspace)) throw new Error('Workspace differs from prepared initial state; make a new run');
  return manifest;
}
export function containerArgs({ name, network, image, workspace, control, readOnlyWorkspace, uid = 1000, gid = 1000, credentialKeys = ['ANTHROPIC_API_KEY'], nativeCache = false }) {
  return ['run', '--name', name, '--label', 'harness-lab=true', '--network', network,
    '--dns', '127.0.0.1', '--user', `${uid}:${gid}`, '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256', '--memory', '2g', '--cpus', '2',
    '--tmpfs', '/tmp:rw,nosuid,size=512m,mode=1777',
    ...(nativeCache ? ['--tmpfs','/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777','--env','TMPDIR=/tmp/harness-native','--env','XDG_CACHE_HOME=/tmp/harness-native'] : []),
    '--mount', `type=bind,src=${workspace},dst=/workspace${readOnlyWorkspace ? ',readonly' : ''}`,
    ...(readOnlyWorkspace ? ['--mount', `type=bind,src=${join(workspace, 'artifacts')},dst=/workspace/artifacts`] : []),
    '--mount', `type=bind,src=${control},dst=/control,readonly`,
    '--workdir', '/workspace', '--env', 'HOME=/tmp/home', '--env', 'XDG_CONFIG_HOME=/tmp/home/.config', '--env', 'XDG_DATA_HOME=/tmp/home/.local/share',
    '--env', 'HTTP_PROXY=http://egress:8080', '--env', 'HTTPS_PROXY=http://egress:8080', '--env', 'NO_PROXY=localhost,127.0.0.1,egress', '--env', 'NODE_USE_ENV_PROXY=1',
    ...credentialKeys.flatMap(key => ['--env', key]), '--env', 'DISABLE_TELEMETRY=1', '--env', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1',
    '--entrypoint', 'node', image, '/control/entrypoint.mjs'];
}
export async function execute(argv, { env, timeout, name, maxBytes = 32 * 1024 * 1024 }) {
  return new Promise(resolveResult => {
    const child = spawn('docker', argv, { env, stdio: ['ignore','pipe','pipe'] });
    const out = [], err = []; let bytes = 0, timedOut = false, interruption = null, outputLimit = false;
    const stop = () => { try { docker(['kill', name], { timeout: 10000 }); } catch {} child.kill('SIGTERM'); };
    const timer = setTimeout(() => { timedOut = true; stop(); }, timeout * 1000);
    const interrupt = signal => { interruption = signal; stop(); };
    const onInt = () => interrupt('SIGINT'), onTerm = () => interrupt('SIGTERM');
    process.on('SIGINT', onInt); process.on('SIGTERM', onTerm);
    const collect = list => chunk => { bytes += chunk.length; if (bytes > maxBytes) { outputLimit = true; stop(); } else list.push(chunk); };
    child.stdout.on('data', collect(out)); child.stderr.on('data', collect(err));
    let spawnError = null; child.on('error', error => { spawnError = error.message; });
    child.on('close', (code, signal) => { clearTimeout(timer); process.removeListener('SIGINT', onInt); process.removeListener('SIGTERM', onTerm); resolveResult({ stdout: Buffer.concat(out).toString('utf8'), stderr: Buffer.concat(err).toString('utf8'), code, signal: interruption ?? signal, timedOut, outputLimit, spawnError }); });
  });
}
export async function runExperiment(root, runId, { image, model, timeout = 900, proxyImage = 'node:24.13.1-bookworm-slim', budgetMode = 'hard', provider } = {}) {
  const record = readRun(root, runId), dir = join(root, 'results/runs', runId);
  if (process.getuid?.() === 0) throw new Error('Run the coordinator as a non-root user so bind mounts have safe ownership');
  if (record.status !== 'prepared') throw new Error('Only a prepared run can execute');
  if (!image || !model) throw new Error('Explicit --image and --model are required');
  if (!Number.isInteger(timeout) || timeout <= 0 || timeout > 86400) throw new Error('timeout must be 1..86400 seconds');
  if (!['hard','observed'].includes(budgetMode)) throw new Error('budget-mode must be hard or observed');
  const manifest = verifyInputs(dir, record), control = join(dir, 'runtime-control');
  const adapter = await import(pathToFileURL(join(dir, 'inputs/control/adapter.mjs')));
  const limits = taskLimits(readFileSync(safePath(dir, 'inputs/task.md'), 'utf8'));
  const profile = validateProfile(JSON.parse(readFileSync(join(dir, 'inputs/control/harness.json'), 'utf8')), record.harness.name);
  const selectedProvider = selectProvider(profile, provider ?? record.model.provider ?? manifest.provider);
  if (selectedProvider.name !== manifest.provider || (record.model.provider && record.model.provider !== selectedProvider.name)) throw new Error('Provider differs from the sealed preparation; create a new run');
  const selectedModel = selectModel(profile, selectedProvider, model);
  if (record.model.id && selectModel(profile, selectedProvider, record.model.id).recorded !== selectedModel.recorded) throw new Error('Requested model differs from the planned run');
  if (budgetMode === 'hard' && profile.budget.usd !== 'hard') throw new Error(`${profile.id} has no verified hard USD cap; use --budget-mode observed for exploratory runs`);
  const launch = { model: selectedModel.requested, provider: selectedProvider.name, turns: profile.budget.turns === 'unavailable' ? null : limits.turns, budget: budgetMode === 'hard' ? limits.budget : null, cwd: record.task.startsWith('T002') ? '/workspace/sample' : '/workspace' };
  const local=selectedProvider.name==='local';
  if(local && localRecordErrors(record).length)throw new Error(localRecordErrors(record).join('; '));
  if(local) {const text=readFileSync(join(dir,'inputs/control/local-deployment.json'));if(sha256(text)!==record.local_inference.deployment_sha256 || JSON.stringify(JSON.parse(text))!==JSON.stringify(record.local_inference.deployment))throw new Error('Sealed deployment differs from local record');}
  const localRuntime=local?await import(pathToFileURL(join(dir,'inputs/coordinator-common/local-runtime.mjs'))):null;
  adapter.buildCommand({ ...launch, prompt: readFileSync(join(dir,'inputs/control/prompt.txt'),'utf8') });
  const capability=local?randomBytes(32).toString('hex'):null;
  const secrets = credentials(root, selectedProvider.credential_env), env = { ...process.env, ...secrets };
  const secretValues = [...Object.values(secrets),...(capability?[capability]:[])];
  const redact = text => secretValues.reduce((out, secret) => out.replaceAll(secret, '[REDACTED]'), String(text));
  const lock = acquireLock(dir);
  const suffix = randomBytes(6).toString('hex'), network = `harness-lab-${suffix}`, proxy = `${network}-egress`, name = `${network}-agent`;
  let started = false, native=null, worker=null;const localResponses=[];
  try {
    const imageId = docker(['image','inspect','--format','{{.Id}}',image]);
    const proxyId = docker(['image','inspect','--format','{{.Id}}',proxyImage]);
    const [executable, ...versionArgs] = profile.version_command;
    const version = docker(['run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--tmpfs','/tmp:rw,mode=1777',...(profile.native_cache ? ['--tmpfs','/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777','--env','TMPDIR=/tmp/harness-native','--env','XDG_CACHE_HOME=/tmp/harness-native'] : []),'--env','HOME=/tmp','--entrypoint',executable,imageId,...versionArgs], { timeout: 30000 });
    if (!version || version.length > 300) throw new Error('Harness returned an invalid version');
    const exactVersion = version.match(/\b\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?\b/)?.[0];
    if (!exactVersion) throw new Error('Harness did not report an exact version');
    if (exactVersion !== profile.version) throw new Error(`Image reports ${exactVersion}, sealed profile pins ${profile.version}: rebuild the image at the pin or update the pin together with its evidence`);
    if (record.harness.version && record.harness.version !== exactVersion) throw new Error('Harness version differs from the planned version');
    writeFileSync(join(dir,'trace/harness-version.txt'), version + '\n');
    if (existsSync(control)) throw new Error('Runtime control already exists; inspect failed run before retrying');
    copyTree(join(dir,'inputs/control'), control); writeFileSync(join(control,'launch.json'), JSON.stringify(launch, null, 2) + '\n');
    if(local) {
      native=await localRuntime.startNative(record.local_inference.deployment,join(dir,'trace/local-native'));
      record.local_inference.observed=native.proof;
    }
    record.harness.version = exactVersion; record.harness.mode = profile.mode ?? 'cli'; record.model.id = selectedModel.recorded; record.model.provider = selectedProvider.name; record.model.selection = selectedModel.policy; record.model.lock = selectedModel.locked; record.model.observed_id = null; record.model.identity_evidence = 'request-only';
    record.permissions = { mode: 'container; harness-specific headless permissions; no interactive approvals', blocked: [], asked: null };
    record.sandbox = { kind: 'container', network: 'allowlist' };
    record.loop.budget_usd = limits.budget;
    record.metrics_unavailable = { ...record.metrics_unavailable, 'permissions.asked': 'CLI does not provide a complete approval counter', 'loop.compactions': 'CLI does not provide a complete compaction counter', 'loop.subagents': 'CLI does not provide a complete subagent counter' };
    record.execution = { ...record.execution, command: ['node','/control/entrypoint.mjs'], cwd: launch.cwd, image_id: imageId, proxy_image_id: proxyId, timeout_s: timeout, network_policy: sha256(readFileSync(join(control,'network.json'))), budget_policy: budgetMode, started_at: new Date().toISOString(), finished_at: null, exit_code: null, signal: null, timed_out: false };
    record.status = 'running'; record.notes = `${record.notes}\nvariant=${manifest.variant}; provider=${selectedProvider.name}; model selection=${selectedModel.policy}; turn limit=${profile.budget.turns}; budget policy=${budgetMode}${budgetMode === 'observed' ? '; exploratory: task USD limit is not enforced and turn limit may be advisory' : ''}`.trim();
    writeRun(root, record); started = true;
    docker(['network','create','--internal','--label','harness-lab=true',network]);
    mkdirSync(join(dir,'trace/network'), { recursive: true });
    docker(['create','--name',proxy,'--label','harness-lab=true','--network','bridge',...(local?['--publish','127.0.0.1::8081','--env','LAB_BRIDGE_TOKEN']:[]),'--user',`${process.getuid?.() ?? 1000}:${process.getgid?.() ?? 1000}`,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--mount',`type=bind,src=${control},dst=/control,readonly`,'--mount',`type=bind,src=${join(dir,'trace/network')},dst=/audit`,'--entrypoint','node',proxyId,local?'/control/local-broker.mjs':'/control/egress.mjs'], {env:local?{...process.env,LAB_BRIDGE_TOKEN:capability}:process.env});
    docker(['network','connect','--alias','egress',network,proxy]); docker(['start',proxy]);
    if(local) {
      const mapping=docker(['port',proxy,'8081/tcp']);const match=/^127\.0\.0\.1:(\d+)$/.exec(mapping);if(!match)throw new Error('Broker control port must be published on IPv4 loopback only');
      worker=localRuntime.startWorker('http://127.0.0.1:'+match[1],capability,record.local_inference.deployment,{verify:native.verify,trace:join(dir,'trace/inference'),audit:row=>localResponses.push(row)});
    }
    // Readiness is bounded and independent of external network availability.
    docker(['exec',proxy,'node','--input-type=module','-e',"for(let i=0;i<40;i++){try{if((await fetch('http://127.0.0.1:8080/health',{headers:{host:'egress:8080'}})).ok)process.exit(0)}catch{}await new Promise(r=>setTimeout(r,100));}process.exit(1)"], { timeout: 10000 });
    const begin = Date.now();
    const result = await execute(containerArgs({ name, network, image: imageId, workspace: join(dir,'workspace'), control, readOnlyWorkspace: !record.task.startsWith('T002'), uid: process.getuid?.() ?? 1000, gid: process.getgid?.() ?? 1000, credentialKeys: selectedProvider.credential_env, nativeCache: profile.native_cache === true }), { env, timeout, name });
    record.loop.wall_clock_s = Math.ceil((Date.now() - begin) / 1000);
    const stdout = redact(result.stdout), stderr = redact(result.stderr);
    writeFileSync(join(dir,'trace/stdout.jsonl'), stdout); writeFileSync(join(dir,'trace/stderr.txt'), stderr);
    const sourcePath = join(dir,'trace/network/sources.jsonl');
    const sources = existsSync(sourcePath) ? readFileSync(sourcePath,'utf8') : '';
    writeFileSync(join(dir,'trace/sources.jsonl'), redact(sources));
    const parsed = adapter.parseTrace(stdout); Object.assign(record.loop, parsed.loop); Object.assign(record.metrics_unavailable, parsed.metrics_unavailable);
    for (const key of Object.keys(parsed.loop)) delete record.metrics_unavailable[`loop.${key}`];
    record.model.observed_id = parsed.modelId && selectedModel.policy === 'explicit' ? selectModel(profile, selectedProvider, parsed.modelId).recorded : parsed.modelId; record.model.identity_evidence = parsed.modelId ? 'assistant response in trace' : selectedModel.policy === 'managed' ? 'managed mode requested; underlying model identity unavailable' : 'request-only; observed identity unavailable';
    if(local) {
      await worker.close();
      const valid=localResponses.length>0 && localResponses.every(row=>row.accepted && row.usage);
      record.loop.tokens_in=valid?localResponses.reduce((sum,row)=>sum+row.usage.input,0):null;
      record.loop.tokens_out=valid?localResponses.reduce((sum,row)=>sum+row.usage.output,0):null;
      for(const key of ['tokens_in','tokens_out']) {if(valid)delete record.metrics_unavailable['loop.'+key];else record.metrics_unavailable['loop.'+key]='Primary local HTTP usage missing or incomplete; SDK zeros not accepted.';}
      record.loop.cost_usd=null;record.metrics_unavailable['loop.cost_usd']='Local hardware/energy cost not measured; SDK placeholder prices are not billing evidence.';
      await native.verify();
      record.model.observed_id=record.local_inference.deployment.alias;record.model.identity_evidence='Controlled native process, pre-Popen file hashes, sealed command and props/template checks before/after HTTP requests';
    }
    record.execution.finished_at = new Date().toISOString(); record.execution.exit_code = result.code; record.execution.signal = result.signal; record.execution.timed_out = result.timedOut;
    const mismatch = selectedModel.policy === 'explicit' && (parsed.modelIds ?? []).some(id => selectModel(profile, selectedProvider, id).recorded !== selectedModel.recorded);
    record.loop.stop_reason = result.timedOut ? 'timeout' : result.outputLimit ? 'trace_size_limit' : result.signal ? 'interrupted' : mismatch ? 'model_mismatch' : parsed.stopReason;
    const traceFailed = ['trace_incomplete','interrupted','error'].includes(parsed.stopReason) || /^error[:_]/.test(parsed.stopReason);
    const failed = (local && localResponses.some(row=>!row.accepted)) || traceFailed || result.code !== 0 || result.signal || result.timedOut || result.outputLimit || mismatch || result.spawnError;
    record.status = failed ? 'aborted' : 'awaiting_review'; record.verdict.result = failed ? 'aborted' : 'pending';
    if (failed) record.notes += `\nExecution aborted: ${record.loop.stop_reason}`;
    const finalWorkspace = inventory(join(dir,'workspace'));
    if (manifest.seed_commit) {
      if (!/^[a-f0-9]{40,64}$/.test(manifest.seed_commit)) throw new Error('Invalid prepared seed commit');
      const patch = docker(['run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user',`${process.getuid?.() ?? 1000}:${process.getgid?.() ?? 1000}`,'--mount',`type=bind,src=${join(dir,'workspace')},dst=/workspace,readonly`,'--entrypoint','git',imageId,'-c','safe.directory=/workspace/sample','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-C','/workspace/sample','diff','--no-ext-diff','--no-textconv','--binary',manifest.seed_commit,'--']);
      if (secretValues.some(secret => patch.includes(secret))) throw new Error('Provider credential detected in patch; refusing to archive it');
      writeFileSync(join(dir,'trace/change.patch'), patch + '\n');
    }
    for (const item of inventory(join(dir,'workspace/artifacts'))) if (secretValues.some(secret => readFileSync(join(dir,'workspace/artifacts',item.path)).includes(Buffer.from(secret)))) throw new Error('Provider credential detected in artifacts; refusing to archive it');
    const rows = copyTree(join(dir,'workspace/artifacts'), join(dir,'artifacts'));
    writeFileSync(join(dir,'trace/artifacts.json'), JSON.stringify(rows, null, 2) + '\n');
    writeFileSync(join(dir,'trace/final-workspace.json'), JSON.stringify(finalWorkspace, null, 2) + '\n');
    writeRun(root, record);
    return record;
  } catch (error) {
    if (started || local) {
      record.status = 'aborted'; record.verdict.result = 'aborted'; record.loop.stop_reason = 'runner_error'; record.notes += `\nRunner error: ${redact(error.message)}`; record.execution.finished_at = new Date().toISOString();
      writeRun(root, record);
    }
    throw new Error(redact(error.message));
  } finally {
    await worker?.close();await native?.close();
    for (const container of [name,proxy]) { try { docker(['rm','-f',container], { timeout: 15000 }); } catch {} }
    try { docker(['network','rm',network], { timeout: 15000 }); } catch {}
    rmSync(lock, { recursive: true, force: true });
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(async () => {
  const a = args(); options(a, ['run','image','model','timeout','proxy-image','budget-mode','provider'], ['run','image','model']);
  const r = await runExperiment(process.cwd(), a.run, { image: a.image, model: a.model, timeout: Number(a.timeout ?? 900), proxyImage: a['proxy-image'], budgetMode: a['budget-mode'] ?? 'hard', provider: a.provider }); console.log(`[run] ${r.run_id}: ${r.status}; ${r.loop.stop_reason}`);
  if (r.status === 'aborted') process.exitCode = 1;
});
