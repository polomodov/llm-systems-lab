import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCommand, parseTrace } from './adapter.mjs';
const input = { model: 'claude-sonnet-4-20250514', turns: 2, budget: null, prompt: 'literal `$(x)`\ntext' };
test('OpenHands selects the exact model and native Conversation iteration cap', () => {
  const launch=buildCommand(input), args=JSON.parse(launch.command[2]);
  assert.deepEqual(launch.command.slice(0,2), ['python','/control/run.py']);
  assert.equal(args.model,'anthropic/'+input.model); assert.equal(args.prompt,input.prompt); assert.equal(args.turns,2);
  assert.equal(JSON.parse(buildCommand({...input,provider:'openai',model:'gpt-4.1-2025-04-14'}).command[2]).provider,'openai');
  for(const change of [{budget:1},{turns:0},{turns:null},{provider:'other'},{model:''},{model:'openai/gpt-4.1'},{prompt:''}]) assert.throws(()=>buildCommand({...input,...change}));
});
test('OpenHands reports complete SDK metrics, without claiming configured identity was observed', () => {
  const result=parseTrace(JSON.stringify({type:'lab_openhands_result',metrics:{accumulated_cost:0.02,costs:[{cost:0.01},{cost:0.01}],token_usages:[{prompt_tokens:10,completion_tokens:5},{prompt_tokens:20,completion_tokens:3}]},stopReason:'finished',sessionId:'oh-session',error:false}));
  assert.deepEqual(result.loop,{turns:2,tokens_in:30,tokens_out:8,cost_usd:0.02});
  assert.equal(result.stopReason,'finished'); assert.equal(result.modelId,null); assert.equal(result.sessionId,'oh-session');
});
test('OpenHands failures and absent pricing cannot become zero-cost completed runs', () => {
  const result=parseTrace('null\ninvalid\n'+JSON.stringify({type:'lab_openhands_result',metrics:{accumulated_cost:0,token_usages:[{prompt_tokens:10,completion_tokens:5}]},stopReason:'error',error:true}));
  assert.deepEqual(result.loop,{}); assert.ok(result.metrics_unavailable['loop.cost_usd']);
  assert.equal(parseTrace('invalid').stopReason,'trace_incomplete');
  assert.deepEqual(parseTrace(JSON.stringify({type:'lab_openhands_result',metrics:{accumulated_cost:0,token_usages:[]}})).loop,{});
  const partialPrice = parseTrace(JSON.stringify({type:'lab_openhands_result',metrics:{accumulated_cost:0.01,costs:[{cost:0.01},{cost:0}],token_usages:[{prompt_tokens:10,completion_tokens:2},{prompt_tokens:20,completion_tokens:3}]},error:false}));
  assert.equal(partialPrice.loop.tokens_in,30); assert.equal(partialPrice.loop.cost_usd,undefined);
});
