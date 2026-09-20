import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import { once } from 'node:events';
import {
  chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync,
  rmSync, symlinkSync, writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { apiKey, containerArgs, runExperiment, verifyInputs } from '../scripts/run.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';
import { createRun, readRun } from '../scripts/lib/records.mjs';
import { copyTree, inventory, safePath } from '../scripts/lib/files.mjs';
import { createGateway, normalizeUrl, publicAddress } from '../experiments/common/egress.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const temp = t => {
  const directory = mkdtempSync(join(tmpdir(), 'harness-runtime-test-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return directory;
};
async function gateway(t, policy, dependencies) {
  const server = createGateway(policy, dependencies);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); }));
  return { server, url: `http://127.0.0.1:${server.address().port}` };
}
const request = (base, target, options) => fetch(`${base}/fetch?url=${encodeURIComponent(target)}`, options);
const syntheticKey = 'sk-ant-synthetic-runtime-test-key';

function fixture(t, { git = true } = {}) {
  const directory = temp(t);
  const files = [
    'tasks/T001-dossier-from-sources/task.md', 'tasks/T001-dossier-from-sources/setup.sh',
    'agents/a1-dossier/spec.md', 'experiments/claude-code/README.md',
    'experiments/claude-code/adapter.mjs', 'experiments/claude-code/harness.json', 'experiments/claude-code/settings.example.json',
    'experiments/common/entrypoint.mjs', 'experiments/common/egress.mjs',
    'scripts/prepare-run.mjs', 'scripts/run.mjs', 'scripts/judge-run.mjs', 'scripts/compare.mjs',
    'scripts/lib/cli.mjs', 'scripts/lib/files.mjs', 'scripts/lib/records.mjs', 'results/schema.json',
  ];
  for (const path of files) {
    mkdirSync(dirname(join(directory, path)), { recursive: true });
    copyFileSync(join(root, path), join(directory, path));
  }
  if (git) {
    const result = spawnSync('git', ['-c', 'init.templateDir=', 'init', '-q', '--initial-branch=main'], { cwd: directory, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const commit = spawnSync('git', ['-c', 'user.name=fixture', '-c', 'user.email=fixture@example.test', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'fixture'], { cwd: directory, encoding: 'utf8' });
    assert.equal(commit.status, 0, commit.stderr);
  }
  const record = createRun({ root: directory, harness: 'claude-code', agent: 'a1-dossier', task: 'T001' });
  return { root: directory, record, dir: join(directory, 'results/runs', record.run_id) };
}

test('gateway permits GET for exact initial URLs and one link level, caches responses, and records fetched documents', async t => {
  const initial = 'https://source.example/article';
  const child = 'https://source.example/child?a=1&b=2';
  const grandchild = 'https://other.example/grandchild';
  const fetched = [], audited = [];
  const { url } = await gateway(t, { sources: [initial] }, {
    fetcher: async target => {
      fetched.push(target);
      return { url: target, status: 200, content_type: 'text/html', body: target === initial
        ? '<a href="/child?a=1&amp;b=2">child</a><a href="javascript:bad()">bad</a>'
        : `<a href="${grandchild}">grandchild</a>` };
    }, audit: row => audited.push(row),
  });
  assert.equal((await request(url, child)).status, 403);
  assert.equal((await request(url, initial)).status, 200);
  assert.equal((await request(url, `${initial}#section`)).status, 200);
  assert.equal((await request(url, child)).status, 200);
  assert.equal((await request(url, grandchild)).status, 403);
  assert.equal((await request(url, `${initial}?arbitrary=value`)).status, 403);
  assert.deepEqual(fetched, [initial, child]);
  assert.equal(audited.length, 2);
  assert.equal(audited[0].requested_url, initial);
  assert.ok(Number.isFinite(Date.parse(audited[0].fetched_at)));
});

test('gateway rejects mutation methods, arbitrary forward proxy requests, and unauthorized CONNECT before resolution', async t => {
  const { url, server } = await gateway(t, { sources: ['https://source.example/'], connect_domains: ['api.anthropic.com'] }, {
    fetcher: async () => assert.fail('Rejected request reached fetcher'),
    resolver: async () => assert.fail('Rejected CONNECT reached resolver'),
  });
  for (const method of ['POST', 'PUT', 'DELETE']) assert.equal((await request(url, 'https://source.example/', { method })).status, 403);
  assert.equal((await fetch(`${url}/anything`)).status, 403);
  const forwarded = await new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port: server.address().port, path: 'https://source.example/' }, res => { res.resume(); resolve(res.statusCode); });
    req.on('error', reject);
  });
  assert.equal(forwarded, 403);
  for (const target of ['api.anthropic.com.attacker.example:443', '127.0.0.1:443', 'api.anthropic.com:80']) {
    const result = await new Promise((resolve, reject) => {
      const client = net.connect(server.address().port, '127.0.0.1', () => client.write(`CONNECT ${target} HTTP/1.1\r\nHost: ${target}\r\n\r\n`));
      let response = '';
      client.on('data', chunk => { response += chunk; });
      client.on('end', () => resolve(response)); client.on('error', reject);
      client.setTimeout(2000, () => client.destroy(new Error('CONNECT test timeout')));
    });
    assert.match(result, /403 Forbidden/);
  }
});

test('gateway blocks private destinations even if a source list explicitly includes one', async t => {
  const { url } = await gateway(t, { sources: ['http://127.0.0.1/'] });
  const result = await request(url, 'http://127.0.0.1/');
  assert.equal(result.status, 502);
  assert.match(await result.text(), /denied/);
});

test('gateway coalesces concurrent requests into one immutable source snapshot', async t => {
  let count = 0;
  const rows = [];
  const { url } = await gateway(t, { sources: ['https://source.example/'] }, {
    fetcher: async target => {
      const version = ++count;
      await new Promise(resolve => setTimeout(resolve, 25));
      return { url: target, status: 200, content_type: 'text/plain', body: `version ${version}` };
    }, audit: row => rows.push(row),
  });
  const responses = await Promise.all([request(url, 'https://source.example/'), request(url, 'https://source.example/')]);
  const bodies = await Promise.all(responses.map(response => response.json()));
  assert.deepEqual(bodies[0], bodies[1]);
  assert.equal(count, 1);
  assert.equal(rows.length, 1);
});

test('URL normalization accepts only public web schemes without credentials or custom ports', () => {
  assert.equal(normalizeUrl('https://EXAMPLE.com:443/a#fragment'), 'https://example.com/a');
  for (const target of ['file:///etc/passwd', 'ftp://example.com/a', 'https://user:password@example.com/', 'https://example.com:8443/a']) {
    assert.throws(() => normalizeUrl(target), /Only public HTTP/);
  }
});

test('public address policy rejects private, reserved, mapped loopback, and malformed addresses', () => {
  const denied = ['127.0.0.1', '10.1.2.3', '172.16.0.1', '192.168.0.1', '169.254.169.254', '100.100.100.200', '0.0.0.0', '224.0.0.1', '198.18.0.1', '192.0.2.1', '198.51.100.1', '203.0.113.1', '::1', '::ffff:127.0.0.1', '0:0:0:0:0:ffff:127.0.0.1', 'fc00::1', 'fe80::1', '2001:db8::1', 'not:an:address', '1.2.3.', ''];
  for (const ip of denied) assert.equal(publicAddress(ip), false, ip);
  for (const ip of ['1.1.1.1', '8.8.8.8', '2606:4700:4700::1111']) assert.equal(publicAddress(ip), true, ip);
});

test('API key parser uses exactly one literal .env entry without shell expansion', t => {
  const directory = temp(t);
  assert.throws(() => apiKey(directory), /Create .env/);
  for (const literal of [syntheticKey, `"${syntheticKey}"`, `'${syntheticKey}'`]) {
    writeFileSync(join(directory, '.env'), `# Comment\nUNRELATED=ignored\nANTHROPIC_API_KEY=${literal}\n`);
    assert.equal(apiKey(directory), syntheticKey);
  }
  for (const literal of ['', '$SECRET', '`command`', 'contains spaces', `"${syntheticKey}`, `${syntheticKey}"`, `${syntheticKey}\\escaped`]) {
    writeFileSync(join(directory, '.env'), `ANTHROPIC_API_KEY=${literal}\n`);
    assert.throws(() => apiKey(directory), /Invalid literal/, literal);
  }
  writeFileSync(join(directory, '.env'), `ANTHROPIC_API_KEY=${syntheticKey}\nANTHROPIC_API_KEY=${syntheticKey}\n`);
  assert.throws(() => apiKey(directory), /exactly once/);
});

test('container arguments expose only workspace and immutable control; read-only tasks write only artifacts', () => {
  for (const readOnlyWorkspace of [true, false]) {
    const argv = containerArgs({ name: 'test-agent', network: 'test-internal', image: 'sha256:synthetic', workspace: '/host/run/workspace', control: '/host/run/runtime-control', readOnlyWorkspace, uid: 123, gid: 456 });
    const mounts = argv.flatMap((arg, index) => arg === '--mount' ? [argv[index + 1]] : []);
    assert.deepEqual(mounts, [
      `type=bind,src=/host/run/workspace,dst=/workspace${readOnlyWorkspace ? ',readonly' : ''}`,
      ...(readOnlyWorkspace ? ['type=bind,src=/host/run/workspace/artifacts,dst=/workspace/artifacts'] : []),
      'type=bind,src=/host/run/runtime-control,dst=/control,readonly',
    ]);
    assert.equal(argv[argv.indexOf('--network') + 1], 'test-internal');
    assert.equal(argv[argv.indexOf('--user') + 1], '123:456');
    for (const flag of ['--read-only', '--cap-drop', '--security-opt', '--pids-limit', '--memory', '--cpus']) assert.ok(argv.includes(flag), flag);
    assert.equal(argv.includes('--privileged'), false);
    assert.equal(argv.some(arg => arg.includes('docker.sock')), false);
    assert.ok(argv.includes('ANTHROPIC_API_KEY'));
    assert.equal(argv.some(arg => arg.includes(syntheticKey)), false);
  }
});

test('safePath rejects traversal, absolute paths, live and dangling symlink escapes', t => {
  const directory = temp(t), inside = join(directory, 'run'), outside = join(directory, 'outside');
  mkdirSync(inside); mkdirSync(outside);
  assert.equal(safePath(inside, 'nested/file'), join(inside, 'nested/file'));
  for (const path of ['', '.', '..', '../outside/file', join(outside, 'file'), 'bad\0path']) assert.throws(() => safePath(inside, path));
  symlinkSync(outside, join(inside, 'live'), 'dir');
  assert.throws(() => safePath(inside, 'live/file'), /[Ss]ymlink/);
  symlinkSync(join(outside, 'not-yet-existing'), join(inside, 'dangling'));
  assert.throws(() => safePath(inside, 'dangling'), /[Ss]ymlink/);
  assert.equal(existsSync(join(outside, 'not-yet-existing')), false);
});

test('snapshot inventory rejects links and records content and executable permission changes', t => {
  const directory = temp(t), source = join(directory, 'source'), dest = join(directory, 'dest');
  mkdirSync(source); writeFileSync(join(source, 'script'), 'original'); chmodSync(join(source, 'script'), 0o755);
  const before = inventory(source);
  assert.equal(before[0].executable, true);
  copyTree(source, dest);
  assert.deepEqual(inventory(dest), before);
  writeFileSync(join(source, 'script'), 'changed');
  assert.notEqual(inventory(source)[0].sha256, before[0].sha256);
  symlinkSync(join(source, 'script'), join(source, 'link'));
  assert.throws(() => inventory(source), /Symlink/);
});

test('prepared run snapshots are sealed and every agent-visible mutation is detected before execution', t => {
  const f = fixture(t);
  const prepared = prepareRun(f.root, f.record.run_id, { asOf: '2026-09-19' });
  assert.equal(prepared.status, 'prepared');
  const manifest = verifyInputs(f.dir, prepared);
  assert.equal(manifest.variant, 'baseline');
  assert.match(readFileSync(join(f.dir, 'workspace/brief.md'), 'utf8'), /2026-09-19/);
  assert.throws(() => prepareRun(f.root, f.record.run_id), /Only planned/);
  const original = readFileSync(join(f.dir, 'workspace/brief.md'));
  writeFileSync(join(f.dir, 'workspace/brief.md'), 'tampered');
  assert.throws(() => verifyInputs(f.dir, prepared), /Workspace differs/);
  writeFileSync(join(f.dir, 'workspace/brief.md'), original);
  writeFileSync(join(f.dir, 'inputs/control/prompt.txt'), 'tampered');
  assert.throws(() => verifyInputs(f.dir, prepared), /Sealed input snapshot/);
});

test('manifest modification is detected independently of the data it describes', t => {
  const f = fixture(t);
  const prepared = prepareRun(f.root, f.record.run_id);
  const path = join(f.dir, 'inputs/manifest.json');
  const manifest = JSON.parse(readFileSync(path, 'utf8'));
  manifest.variant = 'without-spec';
  writeFileSync(path, JSON.stringify(manifest));
  assert.throws(() => verifyInputs(f.dir, prepared), /Input manifest was modified/);
});

test('preparation supports source archives and records the lack of Git provenance explicitly', t => {
  const f = fixture(t, { git: false });
  const prepared = prepareRun(f.root, f.record.run_id);
  assert.equal(prepared.status, 'prepared');
  assert.equal(prepared.provenance.git_commit, null);
  assert.match(prepared.provenance.source_revision_reason, /not a Git checkout/);
  assert.equal(readRun(f.root, f.record.run_id).status, 'prepared');
});

test('synthetic execution reads .env and redacts captured stdout and stderr without exposing the key in Docker arguments', async t => {
  const f = fixture(t);
  prepareRun(f.root, f.record.run_id);
  writeFileSync(join(f.root, '.env'), `ANTHROPIC_API_KEY=${syntheticKey}\n`);
  const bin = join(f.root, 'fake-bin'); mkdirSync(bin);
  const callsPath = join(f.root, 'docker-calls.jsonl');
  const executable = join(bin, 'docker');
  writeFileSync(executable, `#!${process.execPath}
const fs = require('node:fs');
const args = process.argv.slice(2);
fs.appendFileSync(${JSON.stringify(callsPath)}, JSON.stringify(args) + '\\n');
if (args[0] === 'image') console.log('sha256:' + 'a'.repeat(64));
else if (args.includes('--version')) console.log('1.2.3 (synthetic fixture)');
else if (args[0] === 'run') {
  const key = process.env.ANTHROPIC_API_KEY;
  console.log(JSON.stringify({ type: 'assistant', message: { model: 'claude-synthetic-20260920', content: key } }));
  console.log(JSON.stringify({ type: 'result', subtype: 'success', num_turns: 1, total_cost_usd: 0, usage: { input_tokens: 1, cache_creation_input_tokens: 0, cache_read_input_tokens: 0, output_tokens: 1 } }));
  console.error('synthetic stderr: ' + key);
}
`);
  chmodSync(executable, 0o755);
  const originalPath = process.env.PATH;
  process.env.PATH = `${bin}:${originalPath}`;
  t.after(() => { process.env.PATH = originalPath; });
  const executed = await runExperiment(f.root, f.record.run_id, {
    image: 'synthetic-image', model: 'claude-synthetic-20260920', timeout: 10,
  });
  assert.equal(executed.status, 'awaiting_review');
  for (const path of ['trace/stdout.jsonl', 'trace/stderr.txt']) {
    const text = readFileSync(join(f.dir, path), 'utf8');
    assert.equal(text.includes(syntheticKey), false, path);
    assert.match(text, /\[REDACTED\]/, path);
  }
  assert.equal(readFileSync(callsPath, 'utf8').includes(syntheticKey), false);
  assert.equal(readFileSync(join(f.dir, 'run.json'), 'utf8').includes(syntheticKey), false);
  assert.equal(existsSync(join(f.dir, '.lock')), false);
});
