import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';
const trace = events => events.map(event => JSON.stringify(event)).join('\n');

test('Copilot: argv сохраняет prompt и выбирает автономный локальный CLI', () => {
  const prompt = '--help\n$(touch /tmp/injected)';
  const { command, env } = buildCommand({ model: 'gpt-5.4', provider: 'copilot', turns: null, budget: null, prompt });
  assert.equal(command.at(-1), `--prompt=${prompt}`);
  assert.ok(command.includes('--no-ask-user'));
  assert.ok(command.includes('--disable-builtin-mcps'));
  assert.ok(command.includes('--no-remote-export'));
  assert.equal(env.COPILOT_AUTO_UPDATE, 'false');
  assert.throws(() => buildCommand({ model: 'gpt-5.4', budget: 1, prompt }), /observed/);
  assert.throws(() => buildCommand({ model: 'auto', prompt }), /model ID/);
  assert.throws(() => buildCommand({ model: 'gpt-5.4', turns: 0, prompt }), /turns/);
  assert.throws(() => buildCommand({ model: 'gpt-5.4', provider: 'openai', prompt }), /provider/);
});

test('Copilot: CLI result завершает поток; premium requests не подменяют USD', () => {
  const parsed = parseTrace(trace([
    { type: 'session.start', data: { sessionId: 'session-1', selectedModel: 'requested-only' } },
    { type: 'assistant.turn_start', data: { turnId: 'a' } },
    { type: 'assistant.usage', data: { model: 'gpt-5.4', inputTokens: 99, outputTokens: 8, cost: 1 } },
    { type: 'assistant.usage', agentId: 'child', data: { model: 'helper' } },
    { type: 'assistant.turn_end', data: { turnId: 'a' } },
    { type: 'assistant.turn_end', data: { turnId: 'a' } },
    { type: 'result', sessionId: 'session-1', exitCode: 0, usage: { premiumRequests: 1, totalApiDurationMs: 100 } },
  ]));
  assert.deepEqual(parsed.loop, { turns: 1 });
  assert.ok(parsed.metrics_unavailable['loop.cost_usd']);
  assert.ok(parsed.metrics_unavailable['loop.tokens_in']);
  assert.equal(parsed.modelId, null);
  assert.equal(parsed.sessionId, 'session-1');
  assert.equal(parsed.stopReason, 'completed');
});

test('Copilot: обрыв, пустые и частичные агрегаты не дают нулей или успеха', () => {
  const parsed = parseTrace('null\n[]\n{"type":"session.start","data":{"selectedModel":"configured"}}\n{"type":');
  assert.deepEqual(parsed.loop, {});
  assert.equal(parsed.modelId, null);
  assert.equal(parsed.stopReason, 'trace_incomplete');
  const partial = parseTrace(trace([{ type: 'session.shutdown', data: { shutdownType: 'routine', modelMetrics: { first: { usage: { inputTokens: 2 } }, second: {} } } }]));
  assert.equal(partial.loop.tokens_in, undefined);
  assert.equal(partial.loop.turns, undefined);
});

test('Copilot: session.error не скрывается успешным result, exitCode проверяется', () => {
  const parsed = parseTrace(trace([
    { type: 'assistant.usage', data: { model: 'first' } },
    { type: 'assistant.usage', data: { model: 'second' } },
    { type: 'session.error', data: { message: 'network failed' } },
    { type: 'result', exitCode: 0 },
  ]));
  assert.equal(parsed.stopReason, 'error');
  assert.equal(parsed.modelId, null);
  assert.deepEqual(parsed.modelIds, []);
  assert.equal(parseTrace(trace([{ type: 'result', exitCode: 1 }])).stopReason, 'error');
  assert.equal(parseTrace(trace([{ type: 'result', exitCode: '0' }])).stopReason, 'trace_incomplete');
});
