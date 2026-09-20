import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';

test('Claude: итоговый usage не суммируется повторно с modelUsage', () => {
  const result = {
    type: 'result', subtype: 'success', num_turns: 2, total_cost_usd: 0.12,
    usage: { input_tokens: 9, cache_creation_input_tokens: 10, cache_read_input_tokens: 11, output_tokens: 12 },
    modelUsage: { pinned: { inputTokens: 10, cacheCreationInputTokens: 20, cacheReadInputTokens: 30, outputTokens: 40 } },
    session_id: 'session-1',
  };
  const trace = [
    { type: 'assistant', message: { model: 'pinned' } },
    { type: 'assistant', parent_tool_use_id: 'tool-1', message: { model: 'subagent-model' } },
    result,
  ].map((item) => JSON.stringify(item)).join('\n');
  const parsed = parseTrace(trace);
  assert.deepEqual(parsed.loop, { turns: 2, cost_usd: 0.12, tokens_in: 60, tokens_out: 40 });
  assert.deepEqual(parsed.metrics_unavailable, {});
  assert.equal(parsed.modelId, 'pinned');
  assert.equal(parsed.sessionId, 'session-1');
});

test('Claude: обрыв и отсутствующие cache buckets не превращаются в нули', () => {
  const parsed = parseTrace('{"type":"assistant","message":{"model":"pinned"}}\n{"type":');
  assert.deepEqual(parsed.loop, {});
  assert.equal(parsed.stopReason, 'trace_incomplete');
  assert.ok(parsed.metrics_unavailable['loop.cost_usd']);
  const partial = parseTrace(JSON.stringify({ type: 'result', usage: { input_tokens: 5, output_tokens: 6 } }));
  assert.equal(partial.loop.tokens_out, 6);
  assert.equal(partial.loop.tokens_in, undefined);
});

test('Claude: model drift и error subtype видны даже при exit 0', () => {
  const parsed = parseTrace(JSON.stringify([
    { type: 'assistant', message: { model: 'first' } },
    { type: 'assistant', message: { model: 'second' } },
    { type: 'result', is_error: true, subtype: 'error_max_turns', num_turns: 3 },
  ]));
  assert.equal(parsed.modelId, null);
  assert.deepEqual(parsed.modelIds, ['first', 'second']);
  assert.equal(parsed.stopReason, 'error_max_turns');
  assert.equal(parseTrace(JSON.stringify({ type: 'result', is_error: true, subtype: 'success', terminal_reason: 'completed' })).stopReason, 'error');
});

test('Claude: prompt остаётся одним аргументом, лимиты обязательны при задании', () => {
  const prompt = '--help\n$(anything)';
  const built = buildCommand({ model: 'pinned', turns: 4, budget: 3, prompt });
  assert.equal(built.command.at(-1), prompt);
  assert.equal(built.command.at(-2), '--');
  assert.ok(built.command.includes('--max-budget-usd'));
  assert.throws(() => buildCommand({ model: 'pinned', turns: 0, prompt }), /turns/);
});
