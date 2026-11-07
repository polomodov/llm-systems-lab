import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';
const input = { model: 'claude-sonnet-4-20250514', turns: 2, budget: null, prompt: 'literal `$(x)`\ntext' };
test('mini-SWE-agent launches the upstream SDK with exact provider model and native step limit', () => {
  const launch=buildCommand(input), args=JSON.parse(launch.command[2]);
  assert.deepEqual(launch.command.slice(0,2), ['python','/control/run.py']);
  assert.equal(args.model, 'anthropic/'+input.model); assert.equal(args.prompt,input.prompt); assert.equal(args.turns,2);
  assert.equal(JSON.parse(buildCommand({...input,provider:'openai',model:'gpt-4.1-2025-04-14'}).command[2]).model,'openai/gpt-4.1-2025-04-14');
  for (const change of [{budget:1},{turns:0},{turns:null},{provider:'other'},{model:''},{model:'openai/gpt-4.1'},{prompt:''}]) assert.throws(() => buildCommand({...input,...change}));
});
test('mini-SWE-agent extracts provider response identity and complete trajectory totals', () => {
  const trajectory={info:{model_stats:{api_calls:2,instance_cost:0.04},exit_status:'Submitted'}, messages:[1,2].map(n=>({role:'assistant',extra:{response:{model:'actual-model',usage:{prompt_tokens:10*n,completion_tokens:3*n}}}}))};
  const result=parseTrace(JSON.stringify({type:'lab_mini_result',trajectory}));
  assert.deepEqual(result.loop,{turns:2,tokens_in:30,tokens_out:9,cost_usd:0.04});
  assert.deepEqual(result.modelIds,['actual-model']); assert.equal(result.stopReason,'Submitted');
});
test('mini-SWE-agent rejects partial accounting on failed/missing calls and preserves multiple models', () => {
  const trace={type:'lab_mini_result',trajectory:{info:{model_stats:{api_calls:3,instance_cost:0.04},exit_status:'error'},messages:['a','b'].map(model=>({role:'assistant',extra:{response:{model,usage:{prompt_tokens:10,completion_tokens:2}}}}))}};
  const result=parseTrace('null\ninvalid\n'+JSON.stringify(trace));
  assert.equal(result.loop.turns,3); assert.equal(result.loop.tokens_in,undefined); assert.equal(result.loop.cost_usd,undefined);
  assert.equal(result.modelId,null); assert.deepEqual(result.modelIds,['a','b']);
  assert.deepEqual(parseTrace('invalid').loop,{}); assert.equal(parseTrace('invalid').stopReason,'trace_incomplete');
});
test('mini Responses trajectories retain provider identity and reject partial usage', () => {
  const message={object:'response',model:'gpt-6.1-sol',usage:{input_tokens:100,output_tokens:20}};
  const event={type:'lab_mini_result',trajectory:{messages:[message],info:{model_stats:{api_calls:1,instance_cost:0.0004},exit_status:'Submitted'}}};
  const complete=parseTrace(JSON.stringify(event));assert.equal(complete.modelId,'gpt-6.1-sol');
  assert.equal(complete.loop.tokens_in,100);assert.equal(complete.loop.tokens_out,20);
  delete message.usage.output_tokens;
  const partial=parseTrace(JSON.stringify(event));assert.equal(partial.loop.tokens_in,undefined);assert.equal(partial.loop.cost_usd,undefined);
});
