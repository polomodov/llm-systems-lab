#!/usr/bin/env node
import { appendFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { harnessIds } from '../../scripts/lib/pins.mjs';
import { loadProfile } from '../../scripts/lib/harnesses.mjs';
import { main } from '../../scripts/lib/cli.mjs';

const events = new Set(['pull_request', 'push', 'workflow_dispatch', 'schedule']);
const commit = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;

function command(program, argv, options = {}) {
  const result = spawnSync(program, argv, { encoding: 'utf8', timeout: 30_000, maxBuffer: 1024 * 1024, ...options });
  if (result.error || result.status !== 0) throw new Error(`${program} ${argv[0]} failed: ${result.error?.message || result.stderr?.trim() || result.signal || result.status}`);
  return result.stdout?.trim() ?? '';
}

// Return both sides of a rename so moving a Dockerfile into documentation
// cannot hide removal of an executable input. A failed diff never means no changes.
export function changedFiles(root, base, head, { mergeBase = false } = {}) {
  for (const sha of [base, head]) {
    if (!commit.test(sha ?? '')) throw new Error('CI_BASE_SHA and CI_HEAD_SHA must be full commit SHAs');
    command('git', ['rev-parse', '--verify', `${sha}^{commit}`], { cwd: root });
  }
  // PRs compare the branch with its merge base; pushes compare two main states.
  // New changes to the base branch therefore do not rebuild unrelated PRs.
  const start = mergeBase ? command('git', ['merge-base', base, head], { cwd: root }) : base;
  const output = command('git', ['diff', '--name-only', '--no-renames', '-z', start, head, '--'], { cwd: root });
  return output.split('\0').filter(Boolean);
}

export function planChanges(ids, event, files = [], { full = false } = {}) {
  if (!events.has(event)) throw new Error(`Unsupported CI event: ${event}`);
  const all = full || event === 'workflow_dispatch' || event === 'schedule' || files.some(file =>
    ['.github/', 'scripts/', 'tests/', 'experiments/common/'].some(prefix => file.startsWith(prefix)) ||
    ['package.json', 'package-lock.json', 'npm-shrinkwrap.json', '.dockerignore', 'mise.toml', '.mise.toml', 'mise.lock'].includes(file));
  const selected = all ? ids : ids.filter(id => files.some(file => {
    const prefix = `experiments/${id}/`;
    if (!file.startsWith(prefix)) return false;
    const relative = file.slice(prefix.length);
    return !relative.endsWith('.md') && !relative.startsWith('measurements/');
  }));
  return {
    matrix: { include: selected.map(harness => ({ harness })) },
    'has-images': String(selected.length > 0),
    docker: String(event !== 'pull_request' || all || selected.length > 0),
  };
}

export function plan(root, env = process.env) {
  const event = env.GITHUB_EVENT_NAME;
  if (!events.has(event)) throw new Error(`Unsupported CI event: ${event}`);
  const ids = harnessIds(root);
  for (const id of ids) loadProfile(root, id);
  // After a history rewrite, the old before SHA may be absent from a fresh
  // checkout. GitHub forced=true requires a full check instead of a diff.
  const full = event === 'push' && (env.CI_FORCE_PUSH === 'true' || /^0{40}$|^0{64}$/.test(env.CI_BASE_SHA ?? ''));
  if (full) {
    if (!commit.test(env.CI_HEAD_SHA ?? '')) throw new Error('CI_HEAD_SHA must be a full commit SHA');
    command('git', ['rev-parse', '--verify', `${env.CI_HEAD_SHA}^{commit}`], { cwd: root });
  }
  const files = event === 'pull_request' || (event === 'push' && !full)
    ? changedFiles(root, env.CI_BASE_SHA, env.CI_HEAD_SHA, { mergeBase: event === 'pull_request' }) : [];
  return planChanges(ids, event, files, { full });
}

export const imageTag = profile => `harness-lab/${profile.id}:${profile.version}`;

export function build(root, id) {
  const profile = loadProfile(root, id);
  command('docker', ['build', '--pull', '--build-arg', `HARNESS_VERSION=${profile.version}`, '--tag', imageTag(profile), join(root, 'experiments', id)], {
    cwd: root, stdio: 'inherit', timeout: 25 * 60_000, env: { ...process.env, BUILDKIT_PROGRESS: 'plain' },
  });
}

export function validateImageVersion(output, expected) {
  if (!output || output.length > 300) throw new Error('Harness returned an invalid version');
  // Use the same CLI version interpretation as scripts/run.mjs before an agent run.
  const actual = output.match(/\b\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?\b/)?.[0];
  if (!actual) throw new Error('Harness did not report an exact version');
  if (actual !== expected) throw new Error(`Image reports ${actual}, profile pins ${expected}`);
  return actual;
}

export function smoke(root, id) {
  const profile = loadProfile(root, id);
  const image = command('docker', ['image', 'inspect', '--format', '{{.Id}}', imageTag(profile)]);
  if (!/^sha256:[0-9a-f]{64}$/.test(image)) throw new Error('Docker returned an invalid image ID');
  const name = `harness-ci-${id}-${randomBytes(6).toString('hex')}`;
  const [executable, ...versionArgs] = profile.version_command;
  try {
    const output = command('docker', ['run', '--rm', '--name', name, '--network', 'none', '--read-only',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '1000:1000',
      '--pids-limit', '256', '--memory', '2g', '--cpus', '2', '--tmpfs', '/tmp:rw,nosuid,size=512m,mode=1777',
      ...(profile.native_cache ? ['--tmpfs', '/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777',
        '--env', 'TMPDIR=/tmp/harness-native', '--env', 'XDG_CACHE_HOME=/tmp/harness-native'] : []),
      '--env', 'HOME=/tmp', '--entrypoint', executable, image, ...versionArgs]);
    const version = validateImageVersion(output, profile.version);
    console.log(JSON.stringify({ harness: id, version, image, network: 'none' }));
  } finally {
    // Also after a timeout: stopping the Docker client does not stop its container.
    spawnSync('docker', ['rm', '--force', name], { encoding: 'utf8', timeout: 15_000 });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const [action, id, ...extra] = process.argv.slice(2);
  const root = process.cwd();
  if (action === 'plan' && !id) {
    const result = plan(root);
    if (process.env.GITHUB_OUTPUT) for (const [key, value] of Object.entries(result)) {
      appendFileSync(process.env.GITHUB_OUTPUT, `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}\n`);
    }
    console.log(JSON.stringify(result));
  } else if (['build', 'smoke'].includes(action) && id && !extra.length) {
    if (action === 'build') build(root, id);
    else smoke(root, id);
  } else throw new Error('Usage: node .github/scripts/harness-ci.mjs plan | build <harness> | smoke <harness>');
});
