import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';

const jsonl = (...events) => events.map((event) => JSON.stringify(event)).join('\n');
const request = { model: 'google/gemini-2.5-pro', prompt: 'Inspect $(literal)\nwithout shell interpolation' };

test('antigravity constructs literal argv for agy runtime and explicit model', () => {
  const { command, env } = buildCommand(request);
  assert.deepEqual(command.slice(0, 2), ['node', '/control/run-cli.mjs']);
  assert.equal(command[command.indexOf('--model') + 1], 'gemini-2.5-pro');
  assert.equal(command.at(-1), request.prompt);
  assert.ok(command.includes('stream-json'));
  assert.deepEqual(env, {});
});

test('antigravity rejects unsupported limits and providers', () => {
  for (const patch of [{ budget: 1 }, { turns: 2 }, { provider: 'openai' }, { model: 'openai/model' }, { prompt: '' }, { model: '' }]) {
    assert.throws(() => buildCommand({ ...request, ...patch }));
  }
});

test('antigravity uses final aggregate rather than summing streamed and cumulative counters', () => {
  const parsed = parseTrace(jsonl(
    { event: 'init', init: { model: request.model } },
    { event: 'step_update', step_update: { usage: { output_tokens: 10 } } },
    { event: 'result', result: { conversation_id: 'session', status: 'SUCCESS', num_turns: 1, usage: { input_tokens: 30, cache_read_tokens: 10, output_tokens: 10 } } },
    { event: 'result', result: { conversation_id: 'session', status: 'SUCCESS', num_turns: 2, usage: { input_tokens: 40, cache_read_tokens: 20, output_tokens: 15 } } },
  ));
  assert.deepEqual(parsed.loop, { tokens_out: 15 });
  assert.equal(parsed.stopReason, 'completed');
  assert.equal(parsed.sessionId, 'session');
  assert.equal(parsed.modelId, null);
  assert.ok(parsed.metrics_unavailable['loop.tokens_in']);
  assert.ok(parsed.metrics_unavailable['loop.turns']);
});

test('antigravity incomplete/error traces retain unknown counters', () => {
  for (const trace of ['', 'null\n[]', '{"event":', jsonl({ event: 'init' }), jsonl({ event: 'result', result: { status: 'ERROR' } })]) {
    assert.deepEqual(parseTrace(trace).loop, {});
  }
  assert.equal(parseTrace(jsonl({ event: 'result', result: { status: 'ERROR' } })).stopReason, 'error');
  const partial = parseTrace(jsonl({ event: 'result', result: { status: 'SUCCESS', usage: { output_tokens: 10 } } }) + '\n{"event":');
  assert.equal(partial.stopReason, 'trace_incomplete');
  assert.deepEqual(partial.loop, {});
});

test('antigravity rejects invalid counters and distinguishes nonterminal statuses', () => {
  for (const value of [-1, 0.5, '2']) {
    assert.deepEqual(parseTrace(jsonl({ event: 'result', result: { status: 'SUCCESS', usage: { output_tokens: value } } })).loop, {});
  }
  for (const status of ['WAITING', 'RUNNING']) {
    assert.equal(parseTrace(jsonl({ event: 'result', result: { status } })).stopReason, 'trace_incomplete');
  }
  assert.deepEqual(parseTrace(jsonl({ event: 'result', result: { status: 'SUCCESS', usage: { output_tokens: 0 } } })).loop, { tokens_out: 0 });
});
