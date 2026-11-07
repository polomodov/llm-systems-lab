import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

// The evaluator reports a missing asyncio.timeout as an infrastructure failure, which hides the cause.
// This test names it. The evaluator source is hash-protected, so the check lives here.
test('python3 on PATH can run the independent evaluator', () => {
  const result = spawnSync('python3', ['-c', 'import asyncio, sys; print(sys.version.split()[0]); asyncio.timeout'], { encoding: 'utf8' });
  assert.equal(result.error, undefined, 'python3 was not found. Run the checks through mise: mise run verify');
  assert.equal(result.status, 0, `python3 ${result.stdout.trim()} has no asyncio.timeout, which needs Python 3.11 or newer. Run the checks through mise: mise run verify`);
});
