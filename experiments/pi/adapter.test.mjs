import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace, resolveModel } from './adapter.mjs';
const input = { model: 'claude-sonnet-4-20250514', turns: 2, budget: null, prompt: 'literal `$(x)`\ntext' };
const jsonl = (...events) => events.map(JSON.stringify).join('\n');
test('Pi launch uses exact SDK model and transports literal prompt without a shell', () => {
  const launch = buildCommand(input);
  assert.deepEqual(launch.command.slice(0,2), ['node','/control/run.mjs']);
  assert.equal(JSON.parse(launch.command[2]).prompt, input.prompt);
  assert.equal(JSON.parse(buildCommand({ ...input, provider:'openai', model:'gpt-4.1-2025-04-14' }).command[2]).provider, 'openai');
  for (const change of [{ budget: 1 }, { turns: 0 }, { turns: null }, { provider:'other' }, { model:'' }, { model:'openai/gpt-4.1' }, { prompt:'' }]) assert.throws(() => buildCommand({ ...input,...change }));
});
test('Pi sums complete message_end usage once, including input cache; configured model is not observed identity', () => {
  const message = { role:'assistant', model:input.model, stopReason:'stop', usage:{input:10, output:5, cacheRead:3, cacheWrite:2, cost:{total:0.01}} };
  const result = parseTrace(jsonl({type:'message_update',message}, {type:'message_end',message}, {type:'turn_end',message}, {type:'lab_pi_result',turns:1,compactions:0,stopReason:'stop',sessionId:'pi-session'}));
  assert.deepEqual(result.loop, {turns:1,compactions:0,tokens_in:15,tokens_out:5,cost_usd:0.01});
  assert.equal(result.modelId,null); assert.equal(result.sessionId,'pi-session');
});
test('Pi interrupted/error traces do not invent complete usage or zero cost', () => {
  for (const trace of ['null\ninvalid\n', jsonl({type:'message_end',message:{role:'assistant',usage:{input:1,output:2}}}), jsonl({type:'lab_pi_result',turns:0,stopReason:'error'})]) {
    const result=parseTrace(trace); assert.equal(result.loop.cost_usd,undefined); assert.equal(result.loop.tokens_in,undefined);
    assert.ok(result.metrics_unavailable['loop.tokens_in']);
  }
});
test('Pi OpenAI snapshot requests preserve exact ID even when catalog only has the family', () => {
  const registry={find:(provider,id)=>provider==='openai' && id==='gpt-4.1' ? {id,api:'openai-responses',baseUrl:'https://api.openai.com/v1'} : undefined};
  const model=resolveModel(registry,'openai','gpt-4.1-2025-04-14');
  assert.equal(model.id,'gpt-4.1-2025-04-14'); assert.equal(model.api,'openai-responses');
  assert.throws(()=>resolveModel(registry,'openai','unknown-2025-04-14'));
  assert.throws(()=>resolveModel(registry,'anthropic','gpt-4.1-2025-04-14'));
});
