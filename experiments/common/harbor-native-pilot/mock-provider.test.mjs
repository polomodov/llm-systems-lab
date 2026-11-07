import assert from 'node:assert/strict';
import { once } from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { createFixtureServer } from './mock-provider.mjs';

async function fixture(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'harbor-local-fixture-'));
  const log = path.join(dir, 'requests.jsonl');
  const server = createFixtureServer(log);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(async () => { server.closeAllConnections(); await new Promise(r => server.close(r)); await fs.rm(dir, { recursive: true }); });
  return {
    log,
    post: (route, body) => fetch(`http://127.0.0.1:${server.address().port}/v1/${route}`, {
      method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer test-do-not-log' }, body: JSON.stringify(body),
    }),
  };
}

test('Anthropic fixture preserves model and requires a tool before completion', async t => {
  const f = await fixture(t);
  await f.post('messages', {model: 'exact-anthropic-id', messages:[{role:'user',content:'Generate a conversation title'}]});
  const body = { model: 'exact-anthropic-id', tools: [{name: 'Bash', input_schema: {properties: {command: {type: 'string'}}}}] };
  const first = await (await f.post('messages', body)).json();
  assert.equal(first.model, body.model);
  assert.equal(first.stop_reason, 'tool_use');
  assert.match(first.content[0].input.command, /model-tool.json/);
  const second = await (await f.post('messages', body)).json();
  assert.equal(second.stop_reason, 'end_turn');
  const log = await fs.readFile(f.log, 'utf8');
  assert.doesNotMatch(log, /test-do-not-log|authorization/i);
  assert.equal(JSON.parse(log.split('\n')[0]).synthetic_usage, true);
});

test('Responses SSE has a function call and completed terminal event', async t => {
  const f = await fixture(t);
  const response = await f.post('responses', { model:'exact-openai-id',stream:true,tools:[{type:'function',name:'exec_command',parameters:{properties:{cmd:{type:'string'}}}}] });
  const data = await response.text();
  assert.match(data, /response.function_call_arguments.done/);
  assert.match(data, /response.completed/);
  assert.match(data, /exact-openai-id/);
  const events = data.split('\n').filter(x=>x.startsWith('data: ')).map(x=>JSON.parse(x.slice(6)));
  const call = events.at(-1).response.output[0];
  assert.equal(call.name, 'exec_command');
  assert.match(JSON.parse(call.arguments).cmd, /process.getuid/);
});

test('mini text protocol terminates, count_tokens does not consume tool turn, requests bounded', async t => {
  const f = await fixture(t);
  await f.post('messages/count_tokens', {model:'exact-id'});
  const first = await (await f.post('chat/completions', {model:'exact-id'})).json();
  assert.match(first.choices[0].message.content, /```bash\nnode /);
  const second = await (await f.post('chat/completions', {model:'exact-id'})).json();
  assert.match(second.choices[0].message.content, /COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT/);
  for(let i=0;i<14;i++) await f.post('chat/completions', {model:'exact-id'});
  assert.equal((await f.post('chat/completions', {model:'exact-id'})).status, 429);
});

test('mini Responses tool protocol finishes with a submit command', async t => {
  const f = await fixture(t);
  const body={model:'exact-id',tools:[{type:'function',name:'bash',parameters:{properties:{command:{type:'string'}}}}],input:[{role:'user',content:'Finish using COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'}]};
  const first=await (await f.post('responses',body)).json();
  assert.match(JSON.parse(first.output[0].arguments).command,/model-tool.json/);
  const second=await (await f.post('responses',body)).json();
  assert.equal(JSON.parse(second.output[0].arguments).command,'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT');
  assert.notEqual(first.output[0].call_id,second.output[0].call_id);
});
