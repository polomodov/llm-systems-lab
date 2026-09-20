import test from 'node:test';
import assert from 'node:assert/strict';
import { appendFileSync, chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadProfile, validateProfile, selectProvider, selectModel, controlFiles } from '../scripts/lib/harnesses.mjs';
import { credentials, containerArgs, runExperiment } from '../scripts/run.mjs';
import { createRun } from '../scripts/lib/records.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';
import { copyTree } from '../scripts/lib/files.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const ids = ['claude-code', 'opencode', 'codex', 'antigravity-cli', 'pi', 'mini-swe-agent', 'openhands', 'copilot-cli', 'amp'];
const temp = (t) => {
  const path = mkdtempSync(join(tmpdir(), 'harness-profile-'));
  t.after(() => rmSync(path, { recursive: true, force: true }));
  return path;
};

test('all declared harness profiles reference real control files and literal provider domains', () => {
  for (const id of ids) {
    const profile = loadProfile(root, id);
    assert.equal(profile.id, id);
    for (const file of controlFiles(profile)) assert.ok(existsSync(join(root, 'experiments', id, file.source)), `${id}/${file.source}`);
    for (const provider of Object.keys(profile.providers)) {
      assert.equal(selectProvider(profile, provider).name, provider);
      assert.throws(() => selectProvider(profile, 'not-configured'), /not configured/);
    }
  }
});

test('profile validation rejects traversal, reserved control names and permissive provider hostnames', () => {
  const profile = loadProfile(root, 'codex');
  for (const patch of [
    { config_files: [{ source: '../outside', target: 'config.json' }] },
    { config_files: [{ source: 'config.json', target: 'launch.json' }] },
    { runtime_files: ['entrypoint.mjs'] },
    { providers: { openai: { ...profile.providers.openai, connect_domains: ['*.openai.com'] } } },
    { providers: { openai: { ...profile.providers.openai, credential_env: ['CODEX_API_KEY=secret'] } } },
  ]) assert.throws(() => validateProfile({ ...profile, ...patch }));
});

test('managed mode selectors remain distinct from exact model identities', () => {
  const profile = loadProfile(root, 'amp');
  const provider = selectProvider(profile);
  for (const mode of profile.managed_modes) {
    assert.deepEqual(selectModel(profile, provider, `managed:${mode}`), { recorded: `managed:${mode}`, requested: mode, locked: true, policy: 'managed' });
  }
  for (const value of ['gpt-5-2025-08-07', 'managed:not-a-mode', 'medium']) assert.throws(() => selectModel(profile, provider, value));
  const codex = loadProfile(root, 'codex');
  assert.deepEqual(selectModel(codex, selectProvider(codex), 'openai/gpt-5-2025-08-07'), { recorded: 'gpt-5-2025-08-07', requested: 'gpt-5-2025-08-07', locked: false, policy: 'explicit' });
  for (const value of ['managed:medium', 'latest', 'gpt-latest', 'auto']) assert.throws(() => selectModel(codex, selectProvider(codex), value));
});

test('credentials import only selected literal keys and reject missing/duplicate selected keys', (t) => {
  const directory = temp(t);
  writeFileSync(join(directory, '.env'), 'CODEX_API_KEY=synthetic-codex\nGEMINI_API_KEY=synthetic-gemini\nUNSELECTED=$(must-not-run)\n');
  assert.deepEqual(credentials(directory, ['CODEX_API_KEY']), { CODEX_API_KEY: 'synthetic-codex' });
  assert.deepEqual(credentials(directory, ['GEMINI_API_KEY']), { GEMINI_API_KEY: 'synthetic-gemini' });
  assert.throws(() => credentials(directory, ['MISSING_KEY']), /exactly once/);
  writeFileSync(join(directory, '.env'), 'CODEX_API_KEY=first\nCODEX_API_KEY=second\n');
  assert.throws(() => credentials(directory, ['CODEX_API_KEY']), /exactly once/);
  writeFileSync(join(directory, '.env'), 'CODEX_API_KEY=$(must-not-run)\n');
  assert.throws(() => credentials(directory, ['CODEX_API_KEY']), /Invalid literal/);
});

test('container only requests credentials selected by provider, without values or an env-file mount', () => {
  const knownKeys = new Set(ids.flatMap(id => Object.values(loadProfile(root, id).providers).flatMap(provider => provider.credential_env)));
  for (const id of ids) {
    const profile = loadProfile(root, id);
    for (const provider of Object.values(profile.providers)) {
      const argv = containerArgs({ name: 'synthetic', network: 'isolated', image: 'synthetic-image', workspace: '/lab/workspace', control: '/lab/control', credentialKeys: provider.credential_env });
      const imported = argv.flatMap((value, index) => value === '--env' && knownKeys.has(argv[index + 1]) ? [argv[index + 1]] : []);
      assert.deepEqual(imported, provider.credential_env);
      assert.equal(argv.includes('--env-file'), false);
      assert.equal(argv.some(value => value.includes('.env')), false);
    }
  }
});

test('Codex synthetic execution redacts selected credentials and aborts zero-exit native errors', async (t) => {
  const directory = temp(t);
  const files = [
    'tasks/T001-dossier-from-sources/task.md', 'tasks/T001-dossier-from-sources/setup.sh', 'agents/a1-dossier/spec.md',
    'experiments/codex/README.md', ...controlFiles(loadProfile(root, 'codex')).map(file => `experiments/codex/${file.source}`),
    'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs', 'results/schema.json',
  ];
  for (const file of files) {
    mkdirSync(dirname(join(directory, file)), { recursive: true });
    copyFileSync(join(root, file), join(directory, file));
  }
  copyTree(join(root, 'scripts'), join(directory, 'scripts'));
  const record = createRun({ root: directory, harness: 'codex', agent: 'a1-dossier', task: 'T001' });
  prepareRun(directory, record.run_id);
  const selected = 'synthetic-codex-selected-secret', other = 'synthetic-gemini-unselected-secret';
  writeFileSync(join(directory, '.env'), `CODEX_API_KEY=${selected}\nGEMINI_API_KEY=${other}\n`);
  const bin = join(directory, 'fake-bin'); mkdirSync(bin);
  const calls = join(directory, 'docker-calls.jsonl');
  writeFileSync(join(bin, 'docker'), `#!${process.execPath}
const fs = require('node:fs');
const argv = process.argv.slice(2);
fs.appendFileSync(${JSON.stringify(calls)}, JSON.stringify(argv) + '\\n');
if (argv[0] === 'image') console.log('sha256:' + 'a'.repeat(64));
else if (argv.includes('--version')) console.log('codex-cli 0.155.1');
else if (argv[0] === 'run') {
  console.log(JSON.stringify({type:'thread.started',thread_id:'synthetic-session'}));
  console.log(JSON.stringify({type:'item.completed',item:{type:'agent_message',text:process.env.CODEX_API_KEY}}));
  console.log(JSON.stringify({type:'turn.completed',usage:{input_tokens:10,cached_input_tokens:4,output_tokens:2}}));
  console.error(process.env.CODEX_API_KEY);
  if (process.env.GEMINI_API_KEY === ${JSON.stringify(other)}) process.exitCode=42;
}
`);
  chmodSync(join(bin, 'docker'), 0o755);
  const previousPath = process.env.PATH;
  process.env.PATH = `${bin}:${previousPath}`;
  t.after(() => { process.env.PATH = previousPath; });
  const result = await runExperiment(directory, record.run_id, { image: 'synthetic-image', model: 'gpt-5-2025-08-07', budgetMode: 'observed', timeout: 10 });
  assert.equal(result.status, 'awaiting_review');
  assert.equal(result.model.provider, 'openai');
  assert.equal(result.loop.tokens_in, 10);
  assert.equal(result.loop.turns, null);
  const runDir = join(directory, 'results/runs', record.run_id);
  for (const file of ['trace/stdout.jsonl', 'trace/stderr.txt']) {
    const trace = readFileSync(join(runDir, file), 'utf8');
    assert.ok(trace.includes('[REDACTED]'));
    assert.equal(trace.includes(selected), false);
  }
  const recordedCalls = readFileSync(calls, 'utf8');
  assert.equal(recordedCalls.includes(selected), false);
  assert.equal(recordedCalls.includes(other), false);
  assert.equal(recordedCalls.includes('GEMINI_API_KEY'), false);
  appendFileSync(join(bin, 'docker'), '\nif (argv[0] === "run" && !argv.includes("--version")) console.log(JSON.stringify({type:"turn.failed",error:{message:"synthetic native failure"}}));\n');
  const next = createRun({ root: directory, harness: 'codex', agent: 'a1-dossier', task: 'T001' });
  prepareRun(directory, next.run_id);
  const failed = await runExperiment(directory, next.run_id, { image: 'synthetic-image', model: 'gpt-5-2025-08-07', budgetMode: 'observed', timeout: 10 });
  assert.equal(failed.execution.exit_code, 0);
  assert.equal(failed.loop.stop_reason, 'error');
  assert.equal(failed.status, 'aborted');
  assert.equal(failed.verdict.result, 'aborted');
});
