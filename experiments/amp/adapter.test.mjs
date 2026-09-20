import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';
const trace = events => events.map(event => JSON.stringify(event)).join('\n');

test('Amp: явный managed mode, локальный executor, literal prompt и запрет hard USD', () => {
  const prompt = '--help\n$(touch /tmp/injected)';
  const { command } = buildCommand({ model: 'medium', provider: 'amp', turns: null, budget: null, prompt });
  assert.equal(command.at(-1), `--execute=${prompt}`);
  assert.equal(command[command.indexOf('--mode') + 1], 'medium');
  assert.equal(command[command.indexOf('--executor') + 1], 'local');
  assert.equal(command[command.indexOf('--visibility') + 1], 'private');
  assert.throws(() => buildCommand({ model: 'claude-sonnet-4-6', prompt }), /управляемый режим/);
  assert.throws(() => buildCommand({ model: 'medium', budget: 1, prompt }), /observed/);
  assert.throws(() => buildCommand({ model: 'medium', turns: -1, prompt }), /turns/);
  assert.throws(() => buildCommand({ model: 'medium', provider: 'anthropic', prompt }), /provider/);
});

test('Amp: только result usage, без повторного суммирования assistant usage', () => {
  const parsed = parseTrace(trace([
    { type: 'system', subtype: 'init', agent_mode: 'medium', session_id: 'T-test' },
    { type: 'assistant', message: { usage: { input_tokens: 999, output_tokens: 999 } }, session_id: 'T-test' },
    { type: 'result', subtype: 'success', is_error: false, num_turns: 2, session_id: 'T-test',
      usage: { input_tokens: 10, cache_creation_input_tokens: 20, cache_read_input_tokens: 30, output_tokens: 40 } },
  ]));
  assert.deepEqual(parsed.loop, { turns: 2, tokens_in: 60, tokens_out: 40 });
  assert.ok(parsed.metrics_unavailable['loop.cost_usd']);
  assert.equal(parsed.modelId, null);
  assert.deepEqual(parsed.modelIds, []);
  assert.equal(parsed.sessionId, 'T-test');
  assert.equal(parsed.stopReason, 'completed');
});

test('Amp: документированный результат без usage не превращает неизвестное в нули', () => {
  const parsed = parseTrace(trace([{ type: 'result', subtype: 'success', num_turns: 1, is_error: false }]));
  assert.deepEqual(parsed.loop, { turns: 1 });
  assert.equal(Object.keys(parsed.metrics_unavailable).length, 3);
  const partial = parseTrace(trace([{ type: 'result', subtype: 'success', usage: { input_tokens: 3, output_tokens: 5 } }]));
  assert.equal(partial.loop.tokens_in, undefined);
  assert.equal(partial.loop.tokens_out, 5);
  const incomplete = parseTrace('null\n[]\n{"type":"assistant","message":{}}\n{"type":');
  assert.deepEqual(incomplete.loop, {});
  assert.equal(incomplete.stopReason, 'trace_incomplete');
});

test('Amp: ошибки system/result сохраняют причину, смешанные сессии неоднозначны', () => {
  assert.equal(parseTrace(trace([{ type: 'system', subtype: 'error_during_execution', error: 'failed' }])).stopReason, 'error_during_execution');
  assert.equal(parseTrace(trace([{ type: 'result', subtype: 'error_max_turns', is_error: true }])).stopReason, 'error_max_turns');
  assert.equal(parseTrace(trace([{ type: 'result', subtype: 'success', is_error: true }])).stopReason, 'error');
  assert.equal(parseTrace(trace([{ session_id: 'one' }, { session_id: 'two' }])).sessionId, null);
});
