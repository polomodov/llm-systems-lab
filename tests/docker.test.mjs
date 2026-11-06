import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { containerArgs } from '../scripts/run.mjs';

// Explicit opt-in; uses only a prebuilt local image and a synthetic agent.
// Run: HARNESS_DOCKER_TEST=1 node --test tests/docker.test.mjs
const enabled = process.env.HARNESS_DOCKER_TEST === '1';
const image = 'node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2';
const env = { ...process.env, ANTHROPIC_API_KEY: 'synthetic-infrastructure-test-only' };
delete env.NODE_TEST_CONTEXT;
const docker = argv => {
  const result = spawnSync('docker', argv, { encoding: 'utf8', env, timeout: 20_000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout.trim();
};

test('real Docker boundary hides coordinator files, protects root and inputs, and blocks direct external egress', { skip: !enabled }, t => {
  docker(['image', 'inspect', '--format', '{{.Id}}', image]);
  // Colima on macOS normally exports /Users, but not the system /var/folders.
  const directory = mkdtempSync(join(process.env.HARNESS_DOCKER_TMPDIR ?? homedir(), '.harness-docker-test-'));
  const suffix = randomBytes(6).toString('hex');
  const name = `harness-test-agent-${suffix}`, network = `harness-test-internal-${suffix}`;
  t.after(() => {
    spawnSync('docker', ['rm', '-f', name], { encoding: 'utf8', timeout: 15_000 });
    spawnSync('docker', ['network', 'rm', network], { encoding: 'utf8', timeout: 15_000 });
    rmSync(directory, { recursive: true, force: true });
  });
  const workspace = join(directory, 'workspace'), control = join(directory, 'control');
  mkdirSync(join(workspace, 'artifacts'), { recursive: true }); mkdirSync(control);
  writeFileSync(join(directory, '.env'), 'SYNTHETIC_SECRET=coordinator-only');
  writeFileSync(join(directory, 'run.json'), '{"synthetic":"coordinator-only"}');
  mkdirSync(join(directory, 'repository'));
  writeFileSync(join(directory, 'repository/private-check-canary'), 'coordinator-only');
  writeFileSync(join(workspace, 'brief.md'), 'read-only episode input');
  writeFileSync(join(control, 'entrypoint.mjs'), `
import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import net from 'node:net';
assert.notEqual(process.getuid(), 0);
assert.equal(process.env.ANTHROPIC_API_KEY, 'synthetic-infrastructure-test-only');
for (const path of ['/run.json', '/.env', '/repository', '/workspace/run.json', '/workspace/.env', '/workspace/check', ${JSON.stringify(directory)}]) {
  assert.equal(existsSync(path), false, path);
}
assert.equal(readFileSync('/workspace/brief.md', 'utf8'), 'read-only episode input');
assert.throws(() => writeFileSync('/etc/agent-test', 'write forbidden'));
assert.throws(() => writeFileSync('/workspace/brief.md', 'write forbidden'));
assert.throws(() => writeFileSync('/control/entrypoint.mjs', 'write forbidden'));
const status = readFileSync('/proc/self/status', 'utf8');
assert.match(status, /CapEff:\\s+0000000000000000/);
assert.match(status, /NoNewPrivs:\\s+1/);
const egress = await new Promise(resolve => {
  const socket = net.connect({ host: '1.1.1.1', port: 443 });
  socket.once('connect', () => { socket.destroy(); resolve('connected'); });
  socket.once('error', error => resolve(error.code));
  socket.setTimeout(1500, () => { socket.destroy(); resolve('timeout'); });
});
assert.notEqual(egress, 'connected', 'Direct external egress must be blocked');
writeFileSync('/workspace/artifacts/smoke.json', JSON.stringify({ isolated: true, direct_egress: egress }));
console.log(JSON.stringify({ isolated: true, direct_egress: egress }));
`);
  docker(['network', 'create', '--internal', '--label', 'harness-lab-test=true', network]);
  const output = docker(containerArgs({
    name, network, image, workspace, control, readOnlyWorkspace: true,
    uid: process.getuid?.() || 1000, gid: process.getgid?.() || 1000,
  }));
  assert.equal(JSON.parse(output).isolated, true);
  assert.equal(JSON.parse(readFileSync(join(workspace, 'artifacts/smoke.json'), 'utf8')).isolated, true);
  assert.equal(readFileSync(join(workspace, 'brief.md'), 'utf8'), 'read-only episode input');
});
