// Adapter around the upstream Pi agent loop, not a replacement agent.
import { AuthStorage, createAgentSession, ModelRegistry, SessionManager, SettingsManager } from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/index.js';
import { readFileSync } from 'node:fs';
import { resolveModel } from './adapter.mjs';
if (process.argv.includes('--help')) {
  console.log('Pi SDK adapter: run.mjs <JSON: model, provider, turns, prompt>');
  process.exit(0);
}
const smoke = process.argv.includes('--smoke');
const { model, provider, turns: limit, prompt } = smoke ? { model: 'gpt-4.1-2025-04-14', provider: 'openai', turns: 1 } : JSON.parse(process.argv[2]);
const authStorage = AuthStorage.create();
const modelRegistry = ModelRegistry.inMemory(authStorage);
if(provider==='local') {
  const d=JSON.parse(readFileSync('/control/local-deployment.json','utf8'));
  if(model!==d.alias)throw new Error('Local model differs from sealed deployment');
  modelRegistry.registerProvider('local',{baseUrl:'http://egress:8080/v1',api:'openai-completions',apiKey:'harness-local-dummy',models:[{id:model,name:model,reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:d.protocol.context_tokens,maxTokens:d.protocol.output_tokens,compat:{supportsDeveloperRole:false,supportsReasoningEffort:false,supportsUsageInStreaming:true,supportsStrictMode:false,maxTokensField:'max_tokens'}}]});
}
const selected = resolveModel(modelRegistry, provider, model);
const { session } = await createAgentSession({
  cwd: process.cwd(), model: selected, authStorage, modelRegistry,
  sessionManager: SessionManager.inMemory(),
  // No additional model calls for retry/compaction outside the bounded agent turns.
  settingsManager: SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: false } }),
});
if(provider==='local') {
  const d=JSON.parse(readFileSync('/control/local-deployment.json','utf8'));
  const stream=session.agent.streamFn;
  session.agent.streamFn=(model,context,options)=>stream(model,context,{...options,maxRetries:0,timeoutMs:300000});
  session.agent.onPayload=payload=>({model:d.alias,messages:payload.messages,...(payload.tools?{tools:payload.tools}:{}),...(payload.tool_choice?{tool_choice:payload.tool_choice}:{}),stream:true,stream_options:{include_usage:true},max_tokens:d.protocol.output_tokens,temperature:d.protocol.temperature,top_p:d.protocol.top_p,seed:d.protocol.seed,parallel_tool_calls:false});
}
if (smoke) {
  try {
    const bash = session.agent.state.tools.find(tool => tool.name === 'bash');
    const result = await bash.execute('offline-smoke', { command: 'printf sdk-ready' });
    if (!result.content.some(item => item.text?.includes('sdk-ready'))) throw new Error('Native bash tool smoke failed');
    console.log('Pi SDK session and native bash initialized offline; no model call');
  } finally { session.dispose(); }
  process.exit(0);
}
let turns = 0, compactions = 0, limitReached = false;
const emit = event => process.stdout.write(JSON.stringify(event) + '\n');
session.subscribe(emit);
session.agent.subscribe(event => {
  if (event.type === 'turn_end') {
    turns++;
    if (turns >= limit && event.message.content?.some(item => item.type === 'toolCall')) {
      limitReached = true;
      session.agent.abort();
    }
  }
});
session.subscribe(event => { if (event.type === 'compaction_end' && event.result) compactions++; });
let stopReason = 'completed';
try {
  await session.prompt(prompt);
  const last = session.messages.findLast(message => message.role === 'assistant');
  stopReason = limitReached ? 'max_turns' : last?.stopReason ?? 'completed';
  if (['error','aborted'].includes(stopReason)) process.exitCode = 1;
} catch (error) {
  stopReason = 'error'; process.exitCode = 1; console.error(error.message);
} finally {
  emit({ type: 'lab_pi_result', turns, compactions, sessionId: session.sessionId, stopReason });
  session.dispose();
}
