#!/usr/bin/env node
// Harbor experiment tests import the pinned Harbor package, so they run here and not in `npm test`.
// The experiment directories are hash-protected and only read. The environment lives outside
// experiments/ because fixture-copy tests reject the symlinks a virtual environment contains.
// `--setup` installs the same locked versions as harbor-interop/bootstrap.py, without the viewer
// build the tests do not need. It uses a symlinked bootstrap venv: a copied mise Python binary
// cannot find libpython on macOS, which is why bootstrap.py itself fails there.
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { main } from './lib/cli.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const common = join(root, 'experiments/common');
const lock = JSON.parse(readFileSync(join(common, 'harbor-interop/lock.json'), 'utf8'));
const environment = join(root, '.cache/harbor-test');
const venv = join(environment, 'venv');
const python = join(venv, 'bin/python');
const pythonSuites = ['harbor-native-pilot', 'harbor-native-2026-11', 'harbor-interop'];
const nodeSuites = ['harbor-native-pilot', 'harbor-native-2026-11'];

function run(command, argv, options = {}) {
  const result = spawnSync(command, argv, { stdio: 'inherit', ...options });
  if (result.error) throw result.error;
  return result.status;
}

function must(command, argv, options) {
  if (run(command, argv, options) !== 0) throw new Error(`Failed: ${command} ${argv.join(' ')}`);
}

function output(command, argv) {
  const result = spawnSync(command, argv, { encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`Failed: ${command} ${argv.join(' ')}\n${result.stderr}`);
  return result.stdout.trim();
}

function setup() {
  const version = output('python3', ['-c', 'import sys; print(sys.version.split()[0])']);
  if (version !== lock.python || process.versions.node !== lock.node) {
    throw new Error(`Harbor needs Python ${lock.python} and Node ${lock.node}, found ${version} and ${process.versions.node}. Run through mise: mise exec -- node scripts/test-harbor.mjs --setup`);
  }
  mkdirSync(environment, { recursive: true });
  const source = join(environment, 'harbor');
  // Only the locked commit is needed. A shallow fetch is smaller, and rerunning resumes after a network failure.
  if (!existsSync(join(source, '.git'))) must('git', ['init', '--quiet', source]);
  if (run('git', ['-C', source, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}'], { stdio: 'ignore' }) !== 0) {
    must('git', ['-C', source, 'fetch', '--depth', '1', lock.harbor_repository, lock.harbor_commit]);
    must('git', ['-C', source, 'checkout', '--quiet', '--detach', 'FETCH_HEAD']);
  }
  if (output('git', ['-C', source, 'rev-parse', 'HEAD']) !== lock.harbor_commit) throw new Error('Harbor source revision does not match lock.json');
  must('git', ['-C', source, 'diff', '--exit-code', 'HEAD', '--', '.']);
  const uvLock = createHash('sha256').update(readFileSync(join(source, 'uv.lock'))).digest('hex');
  if (uvLock !== lock.upstream_uv_lock_sha256) throw new Error('Harbor uv.lock does not match lock.json');
  const bootstrap = join(environment, 'bootstrap');
  if (!existsSync(join(bootstrap, 'bin/python'))) must('python3', ['-m', 'venv', bootstrap]);
  must(join(bootstrap, 'bin/python'), ['-m', 'pip', 'install', `uv==${lock.uv}`]);
  must(join(bootstrap, 'bin/uv'), ['sync', '--project', source, '--frozen', '--no-dev', '--python', output('python3', ['-c', 'import sys; print(sys.executable)'])], {
    env: { ...process.env, UV_PROJECT_ENVIRONMENT: venv },
  });
  console.log('[harbor] Pinned Harbor ready. No model calls or task runs were made.');
}

function test() {
  if (!existsSync(python)) throw new Error('Harbor test environment is missing. Run: mise exec -- node scripts/test-harbor.mjs --setup');
  const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1' };
  // Every suite runs even after a failure, so one report shows all of them.
  const failed = [];
  for (const suite of nodeSuites) {
    if (run(process.execPath, ['--test', join(common, suite, 'mock-provider.test.mjs')], { cwd: root, env }) !== 0) failed.push(`${suite} (node)`);
  }
  for (const suite of pythonSuites) {
    if (run(python, ['-m', 'unittest', 'discover', '-s', join(common, suite), '-p', 'test_*.py'], { cwd: root, env }) !== 0) failed.push(`${suite} (python)`);
  }
  if (failed.length) throw new Error(`Harbor suites failed: ${failed.join(', ')}`);
  console.log(`[harbor] ${nodeSuites.length} Node and ${pythonSuites.length} Python suites passed.`);
}

await main(() => {
  const flags = process.argv.slice(2);
  if (flags.some(flag => flag !== '--setup')) throw new Error('Usage: test-harbor.mjs [--setup]');
  if (flags.length) setup(); else test();
});
