import { createHash } from 'node:crypto';
const hash = value => createHash('sha256').update(value).digest('hex');
export const canonical = value => JSON.stringify(sort(value));
function sort(value) { return Array.isArray(value) ? value.map(sort) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,sort(value[key])])) : value; }
export const fingerprint = value => hash(canonical(validateDeployment(value)));
const assert = (condition,message) => { if (!condition) throw new Error(`Local deployment: ${message}`); };
const text = value => typeof value==='string' && !!value.trim() && !/[\0\r\n]/.test(value);
const sha = value => typeof value==='string' && /^[a-f0-9]{64}$/.test(value);
function keys(value,required) { assert(value && typeof value==='object' && !Array.isArray(value),'object required'); assert(Object.keys(value).sort().join()===required.split(' ').sort().join(),'unknown or missing fields'); }
function files(rows) {
  assert(Array.isArray(rows) && rows.length>0 && rows.length<=64,'files required');
  const names=new Set();
  for(const row of rows) { keys(row,'path bytes sha256'); assert(text(row.path) && row.path.startsWith('/') && !row.path.split('/').includes('..'),'absolute artifact path required'); assert(Number.isSafeInteger(row.bytes) && row.bytes>0 && sha(row.sha256),'file bytes/SHA-256 required'); assert(!names.has(row.path),'duplicate file path'); names.add(row.path); }
}
export function validateDeployment(d) {
  keys(d,'schema_version kind endpoint alias model engine hardware protocol');
  assert(d.schema_version===1 && d.kind==='local-llama-cpp','unsupported deployment version/kind');
  keys(d.endpoint,'host port transport'); assert(d.endpoint.host==='127.0.0.1' && d.endpoint.transport==='http' && Number.isInteger(d.endpoint.port) && d.endpoint.port>=1024 && d.endpoint.port<=65535,'only fixed IPv4 loopback HTTP endpoint');
  assert(text(d.alias) && /^[a-zA-Z0-9_.-]+$/.test(d.alias),'invalid model alias');
  keys(d.model,'repository revision format quantization files tokenizer_sha256 chat_template_sha256');
  assert(text(d.model.repository) && /^[a-f0-9]{40}$/.test(d.model.revision) && d.model.format==='GGUF' && text(d.model.quantization),'pinned GGUF repository/revision/quant required'); files(d.model.files);assert(d.model.files.length===1 && d.model.files[0].path.endsWith('.gguf'),'one GGUF required');
  assert(sha(d.model.tokenizer_sha256) && sha(d.model.chat_template_sha256),'tokenizer/template SHA required');
  keys(d.engine,'id version commit backend build_flags executable files'); assert(d.engine.id==='llama-cpp' && text(d.engine.version) && /^[a-f0-9]{40}$/.test(d.engine.commit) && ['metal','vulkan','rocm'].includes(d.engine.backend),'pinned llama.cpp engine required');
  assert(Array.isArray(d.engine.build_flags) && d.engine.build_flags.length>0 && d.engine.build_flags.every(text),'build flags required');files(d.engine.files); assert(d.engine.files.some(f=>f.path===d.engine.executable),'executable must be pinned');
  keys(d.hardware,'id passport driver power_mode');assert(text(d.hardware.id) && text(d.hardware.driver) && d.hardware.power_mode===0,'hardware/driver and power mode required');files([d.hardware.passport]);
  keys(d.protocol,'context_tokens output_tokens temperature seed top_p reasoning thinking kv batch ubatch threads slots offload prefix_cache tool_protocol');const p=d.protocol;
  assert(Number.isInteger(p.context_tokens) && p.context_tokens>=8192 && p.context_tokens<=32768 && Number.isInteger(p.output_tokens) && p.output_tokens>0 && p.output_tokens<=2048,'context/output limits invalid');
  assert(p.temperature===0 && Number.isInteger(p.seed) && p.top_p===1 && p.reasoning==='auto' && p.thinking===true && canonical(p.kv)==='["f16","f16"]' && p.slots===1 && p.offload===999 && p.prefix_cache===false && p.tool_protocol==='openai-chat','unsupported execution protocol');
  assert(['batch','ubatch','threads'].every(k=>Number.isInteger(p[k]) && p[k]>0) && p.ubatch<=p.batch,'batch/thread limits invalid');return d;
}
export function localRecordErrors(record) {
  const local=record.local_inference;
  if(record.model?.provider!=='local') return local==null ? [] : ['local metadata requires local provider'];
  if(record.status==='planned' && local==null)return [];
  try {
    keys(local,'schema_version deployment_sha256 fingerprint deployment observed');assert(local.schema_version===1 && sha(local.deployment_sha256),'invalid local record version/hash');
    assert(local.fingerprint===fingerprint(local.deployment),'local fingerprint differs from deployment');
    assert(record.model.id===local.deployment.alias,'record alias differs from deployment');
    if(['awaiting_review','completed'].includes(record.status))assert(local.observed && local.observed.fingerprint===local.fingerprint && local.observed.verified_before_popen===true,'observed controlled process proof required');
    return [];
  } catch(error) { return [error.message]; }
}
const requestFields=new Set(['model','messages','tools','tool_choice','stream','stream_options','max_tokens','temperature','top_p','seed','parallel_tool_calls']);
export function validateLocalRequest(body,d) {
  validateDeployment(d);assert(body && typeof body==='object' && !Array.isArray(body),'request object required');
  assert(Object.keys(body).every(key=>requestFields.has(key)),'unknown request field/target');
  assert(body.model===d.alias,'unknown model alias');assert(body.stream===true,'streaming request required');
  assert(Array.isArray(body.messages) && body.messages.length>0 && body.messages.length<=256,'messages required');
  assert(body.messages.every(m=>m && ['system','user','assistant','tool'].includes(m.role) && (typeof m.content==='string' || m.content===null || Array.isArray(m.content) && m.content.every(c=>c && c.type==='text' && typeof c.text==='string' && Object.keys(c).every(k=>['type','text'].includes(k)))) && Object.keys(m).every(k=>['role','content','tool_calls','tool_call_id','name','reasoning_content'].includes(k))),'unsupported messages');
  assert(body.max_tokens===d.protocol.output_tokens && body.temperature===d.protocol.temperature,'output/sampling differs from deployment');
  for(const key of ['top_p','seed'])assert(body[key]===undefined || body[key]===d.protocol[key],`${key} differs from deployment`);
  if(body.stream_options!==undefined)assert(canonical(body.stream_options)==='{"include_usage":true}','unsupported stream options');
  if(body.tools!==undefined)assert(Array.isArray(body.tools) && body.tools.length<=32 && body.tools.every(t=>t.type==='function' && t.function && text(t.function.name)),'invalid tools');
  if(body.tool_choice!==undefined)assert(['auto','none','required'].includes(body.tool_choice),'unsupported tool choice');
  assert(body.parallel_tool_calls===undefined || body.parallel_tool_calls===false,'parallel tools not accepted');
  return {...body,messages:body.messages.map(m=>({...m,content:Array.isArray(m.content)?m.content.map(c=>c.text).join('\n'):m.content})),seed:d.protocol.seed,top_p:d.protocol.top_p};
}
export function validateLocalResponse(bytes,d) {
  const text=Buffer.from(bytes).toString('utf8');let done=false,finished=false,usage=null,frames=0;
  for(const event of text.split(/\r?\n\r?\n/)) {
    if(!event.trim())continue;
    const lines=event.split(/\r?\n/);assert(lines.every(line=>line.startsWith('data:') || !line.trim()),'unsupported SSE framing');
    const data=lines.filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');
    assert(!done,'SSE content after DONE');if(data==='[DONE]'){done=true;continue;}
    const chunk=JSON.parse(data);assert(chunk && chunk.model===d.alias && !chunk.error && Array.isArray(chunk.choices),'invalid stream/model identity');frames++;
    for(const choice of chunk.choices)if(choice.finish_reason!==null && choice.finish_reason!==undefined) { assert(['stop','length','tool_calls'].includes(choice.finish_reason),'unsupported finish reason');finished=true; }
    if(chunk.usage!=null) { const u=chunk.usage; assert(Number.isSafeInteger(u.prompt_tokens) && u.prompt_tokens>=0 && Number.isSafeInteger(u.completion_tokens) && u.completion_tokens>=0,'invalid usage');usage={input:u.prompt_tokens,output:u.completion_tokens}; }
  }
  assert(done && finished && frames>0,'truncated SSE: finish/DONE required');
  return {usage,usage_unavailable:usage ? null : 'Primary upstream stream did not report usage; SDK default zero is not a measurement.'};
}
