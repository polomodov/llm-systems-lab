import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';

const jsonl = (...events) => events.map((event) => JSON.stringify(event)).join('\n');
const request = { model: 'openai/gpt-5-2025-08-07', prompt: 'Inspect $(literal)\nwithout shell interpolation' };

test('codex constructs literal argv and explicit sandbox/approval/model settings', () => {
  const { command, env } = buildCommand(request);
  assert.equal(command[command.indexOf('--model') + 1], 'gpt-5-2025-08-07');
  assert.equal(command.at(-1), request.prompt);
  assert.ok(command.includes('--json'));
  assert.ok(command.includes('approval_policy="never"'));
  assert.deepEqual(env, {});
});

test('codex rejects unsupported budgets/providers before invoking CLI', () => {
  for (const patch of [{ budget: 1 }, { turns: 2 }, { provider: 'anthropic' }, { model: 'anthropic/model' }, { prompt: '' }, { model: '' }]) {
    assert.throws(() => buildCommand({ ...request, ...patch }));
  }
});

test('codex reads usage without double counting cached tokens or inferring model from request', () => {
  const parsed = parseTrace(jsonl(
    { type: 'thread.started', thread_id: 'session', model: request.model },
    { type: 'turn.started' },
    { type: 'turn.completed', usage: { input_tokens: 100, cached_input_tokens: 80, output_tokens: 20 } },
  ));
  assert.deepEqual(parsed.loop, { tokens_in: 100, tokens_out: 20 });
  assert.equal(parsed.stopReason, 'completed');
  assert.equal(parsed.sessionId, 'session');
  assert.equal(parsed.modelId, null);
  assert.ok(parsed.metrics_unavailable['loop.turns']);
});

test('codex incomplete/error traces never substitute missing usage with zero', () => {
  for (const trace of ['', 'null\n[]', '{"type":', jsonl({ type: 'turn.started' }), jsonl({ type: 'turn.completed', usage: { input_tokens: -1, output_tokens: 1.5 } })]) {
    assert.deepEqual(parseTrace(trace).loop, {});
  }
  const failed = parseTrace(jsonl({ type: 'turn.failed', error: { message: 'failed' } }));
  assert.equal(failed.stopReason, 'error');
  const partial = parseTrace(jsonl({ type: 'turn.completed', usage: { input_tokens: 12, output_tokens: 2 } }) + '\n{"type":');
  assert.equal(partial.stopReason, 'trace_incomplete');
  assert.deepEqual(partial.loop, {});
});

test('codex zero usage is preserved only when it is explicitly reported', () => {
  const parsed = parseTrace(jsonl({ type: 'turn.completed', usage: { input_tokens: 0, output_tokens: 0 } }));
  assert.deepEqual(parsed.loop, { tokens_in: 0, tokens_out: 0 });
});
