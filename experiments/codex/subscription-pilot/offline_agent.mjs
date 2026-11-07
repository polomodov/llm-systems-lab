// Executed only inside a network-none Docker container with invented credentials.
import fs from 'node:fs';
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import https from 'node:https';
import assert from 'node:assert/strict';
import { createFixtureServer } from './provider-base.mjs';
assert.equal(process.getuid(), 1000);
assert.equal(process.env.HOME, '/run/subscription-home');
assert.equal(process.env.CODEX_HOME, '/run/subscription-home/.codex');
for (const key of ['OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'ANTHROPIC_API_KEY', 'SSH_AUTH_SOCK']) assert(!process.env[key]);
fs.mkdirSync(process.env.CODEX_HOME, { recursive: true, mode: 0o700 });
fs.mkdirSync('/app/evidence/agent', { recursive: true });
const encode = object => Buffer.from(JSON.stringify(object)).toString('base64url');
const token = [encode({ alg: 'none', typ: 'JWT' }), encode({ exp: 4102444800, email: 'fixture@example.invalid',
  'https://api.openai.com/auth': { chatgpt_account_id: 'subscription-fixture-account', chatgpt_user_id: 'subscription-fixture-user', chatgpt_plan_type: 'pro' } }), 'Zml4dHVyZS1vbmx5'].join('.');
const refresh = 'offline-refresh-not-a-real-token';
const auth = { auth_mode: 'chatgpt', OPENAI_API_KEY: null, tokens: { id_token: token, access_token: token, refresh_token: refresh,
  account_id: 'subscription-fixture-account' }, last_refresh: new Date().toISOString() };
fs.writeFileSync(process.env.CODEX_HOME + '/auth.json', JSON.stringify(auth), { mode: 0o600 });
fs.copyFileSync('/app/config.toml', process.env.CODEX_HOME + '/config.toml');
const base = createFixtureServer('/app/evidence/agent/mock-requests.jsonl');
const handlers = base.listeners('request');
const server = https.createServer({ key: fs.readFileSync('/app/fixture-key.pem'), cert: fs.readFileSync('/app/fixture-cert.pem') });
let completed = false; const requests = [];
const reset = Math.floor(Date.now() / 1000) + 7200;
server.on('request', (req, res) => {
  const route = new URL(req.url, 'http://127.0.0.1').pathname;
  const authenticated = req.headers.authorization === 'Bearer ' + token;
  requests.push({ route, method: req.method, authenticated_with_fixture: authenticated });
  if (!authenticated) { res.writeHead(401); res.end('{}'); return; }
  if (route.endsWith('/accounts/check')) {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ accounts: [{ id: 'subscription-fixture-account', workspace_backend_origin: 'NO_CONSTRAINT', account_routing_override: 'NO_CONSTRAINT' }] })); return;
  }
  if (route.includes('usage')) {
    const used = completed ? 12 : 10;
    const data = { account_id: 'subscription-fixture-account', user_id: 'subscription-fixture-user', plan_type: 'pro',
      rate_limit: { allowed: true, limit_reached: false,
        primary_window: { used_percent: used, limit_window_seconds: 18000, reset_after_seconds: 7200, reset_at: reset },
        secondary_window: { used_percent: 20, limit_window_seconds: 604800, reset_after_seconds: 7200, reset_at: reset } },
      credits: { has_credits: false, unlimited: false, balance: '0' } };
    res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(data)); return;
  }
  if (route.endsWith('/responses')) req.url = '/v1/responses';
  else if (route.endsWith('/models')) req.url = '/v1/models';
  else { res.writeHead(404); res.end('{}'); return; }
  for (const handler of handlers) handler(req, res);
});
await new Promise(resolve => server.listen(8768, '127.0.0.1', resolve));
const clean = text => text.split(token).join('[REDACTED-FIXTURE-TOKEN]').split(refresh).join('[REDACTED-FIXTURE-TOKEN]');
async function command(args, timeout = 25000, extraEnv = {}) {
  const child = spawn('codex', args, { env: { ...process.env, ...extraEnv }, stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '', stderr = '';
  child.stdout.on('data', data => { stdout += data; }); child.stderr.on('data', data => { stderr += data; });
  const timer = setTimeout(() => child.kill('SIGKILL'), timeout);
  const code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('exit', resolve); });
  clearTimeout(timer); return { code, stdout: clean(stdout), stderr: clean(stderr) };
}
async function quota() {
  const child = spawn('codex', ['app-server', '--listen', 'stdio://'], { env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
  const pending = new Map(); let next = 0; let stderr = '';
  child.stderr.on('data', data => { stderr += data; });
  const lines = readline.createInterface({ input: child.stdout });
  lines.on('line', line => { const value = JSON.parse(line); if (pending.has(value.id)) { pending.get(value.id)(value); pending.delete(value.id); } });
  const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
  async function rpc(method, params) {
    const id = ++next;
    const result = new Promise(resolve => pending.set(id, resolve));
    child.stdin.write(JSON.stringify({ id, method, ...(params ? { params } : {}) }) + '\n');
    return Promise.race([result, new Promise((_, reject) => child.once('exit', () => reject(new Error('RPC process exited: ' + clean(stderr))))) ]);
  }
  try {
    const init = await rpc('initialize', { clientInfo: { name: 'offline-subscription-pilot', version: '1' }, capabilities: { experimentalApi: true } });
    assert(!init.error, JSON.stringify(init)); child.stdin.write('{"method":"initialized"}\n');
    const account = await rpc('account/read', { refreshToken: false });
    assert.equal(account.result?.account?.type, 'chatgpt', JSON.stringify(account));
    const response = await rpc('account/rateLimits/read', { excludeResetCreditDetails: true });
    assert(!response.error, JSON.stringify(response));
    return { kind: 'subscription-quota-snapshot-v1', synthetic: true, account_scope: 'offline-subscription-fixture', auth_mode: 'chatgpt',
      method: 'account/rateLimits/read', observed_at: new Date().toISOString(), result: response.result };
  } finally { clearTimeout(timer); lines.close(); child.kill('SIGTERM'); }
}
try {
  const rejectedHome = process.env.CODEX_HOME + '/rejected-api-profile';
  fs.mkdirSync(rejectedHome, { mode: 0o700 });
  fs.copyFileSync('/app/config.toml', rejectedHome + '/config.toml');
  fs.writeFileSync(rejectedHome + '/auth.json', JSON.stringify({ auth_mode: 'apikey', OPENAI_API_KEY: 'offline-api-key-not-real' }), { mode: 0o600 });
  const rejected = await command(['exec', '--model', 'gpt-6.1-sol', '--json', '--skip-git-repo-check', '--', 'Do not use tools.'], 20000, { CODEX_HOME: rejectedHome });
  assert.notEqual(rejected.code, 0, 'API authentication must not replace subscription authentication');
  assert.equal(requests.length, 0, 'Rejected API profile must not reach even the fixture backend');
  fs.writeFileSync('/app/evidence/api-fallback-rejection.json', JSON.stringify({ rejected: true, backend_requests: requests.length }));
  fs.rmSync(rejectedHome, { recursive: true });
  const login = await command(['login', 'status']);
  fs.writeFileSync('/app/evidence/login-status.json', JSON.stringify(login));
  assert.equal(login.code, 0, JSON.stringify(login));
  fs.writeFileSync('/app/evidence/quota-before.json', JSON.stringify(await quota()));
  const prompt = fs.readFileSync('/app/instruction.md', 'utf8');
  const result = await command(['exec', '--model', 'gpt-6.1-sol', '--json', '--color', 'never', '--skip-git-repo-check',
    '--dangerously-bypass-approvals-and-sandbox', '--', prompt], 180000);
  fs.writeFileSync('/app/evidence/agent/codex.txt', result.stdout + result.stderr);
  fs.writeFileSync('/app/evidence/process.json', JSON.stringify({ exit_code: result.code }));
  completed = true;
  fs.writeFileSync('/app/evidence/quota-after.json', JSON.stringify(await quota()));
  if (fs.existsSync(process.env.CODEX_HOME + '/sessions')) fs.cpSync(process.env.CODEX_HOME + '/sessions', '/app/evidence/agent/sessions', { recursive: true });
  fs.writeFileSync('/app/evidence/isolation.json', JSON.stringify({ uid: process.getuid(), auth_mode: 'chatgpt',
    credential_mode: fs.statSync(process.env.CODEX_HOME + '/auth.json').mode & 0o777,
    host_auth_reused: false, api_env_present: false, fixture_only: true, requests }));
  assert.equal(result.code, 0, JSON.stringify(result));
} finally { server.close(); }
