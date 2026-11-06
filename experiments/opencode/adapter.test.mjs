import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';

test('OpenCode: JSONL step_finish is not treated as complete session accounting', () => {
  const parsed = parseTrace(JSON.stringify({
    type: 'step_finish', sessionID: 'session-2',
    part: { reason: 'stop', cost: 0, tokens: { input: 10, output: 20, cache: { read: 30, write: 40 } } },
  }));
  assert.deepEqual(parsed.loop, {});
  assert.equal(parsed.modelId, null);
  assert.equal(parsed.sessionId, 'session-2');
  assert.equal(parsed.stopReason, 'stop');
  assert.ok(parsed.metrics_unavailable['loop.cost_usd']);
});

test('OpenCode: unsupported hard USD budget is rejected before launch', () => {
  assert.throws(() => buildCommand({ model: 'pinned', turns: 4, budget: 3, prompt: 'hello' }), /budget-mode observed/);
  const built = buildCommand({ model: 'pinned', turns: 4, budget: null, prompt: 'hello' });
  const runtime = JSON.parse(built.env.OPENCODE_CONFIG_CONTENT);
  assert.equal(runtime.agent.build.steps, 4);
  assert.equal(runtime.small_model, 'anthropic/pinned');
  assert.equal(built.command[built.command.indexOf('--model') + 1], 'anthropic/pinned');
});

test('OpenCode: a stream error takes precedence over intermediate step_finish', () => {
  const trace = [{ type: 'step_finish', part: { reason: 'tool-calls' } }, { type: 'error', error: { message: 'failed' } }];
  assert.equal(parseTrace(trace.map((item) => JSON.stringify(item)).join('\n')).stopReason, 'error');
  assert.equal(parseTrace('{"type":').stopReason, 'trace_incomplete');
});
