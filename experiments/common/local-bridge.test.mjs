import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { mkdtempSync,writeFileSync,rmSync,mkdirSync,readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createLocalBroker } from './local-broker.mjs';
import { startWorker,requestLocal,verifyFiles,parseMeminfo,linuxResourceRow,startNative } from './local-runtime.mjs';
import { deployment,request,stream } from './local-fixture.mjs';
import { validateDeployment,validateLocalResponse,fingerprint,localRecordErrors } from '../../scripts/lib/local-inference.mjs';
const token='synthetic-private-control-capability-0123456789';
async function setup(t,handler,{timeoutMs=3000,...options}={}) {
  const d=deployment();let calls=0;
  const upstream=http.createServer((req,res)=>{calls++;handler(req,res);});upstream.listen(0,'127.0.0.1');await once(upstream,'listening');d.endpoint.port=upstream.address().port;
  const broker=createLocalBroker(d,token,{timeoutMs,...options});broker.agent.listen(0,'127.0.0.1');broker.control.listen(0,'127.0.0.1');await Promise.all([once(broker.agent,'listening'),once(broker.control,'listening')]);
  const url='http://127.0.0.1:'+broker.agent.address().port,control='http://127.0.0.1:'+broker.control.address().port;
  t.after(async()=>{await worker?.close();await broker.close();upstream.closeAllConnections();await new Promise(resolve=>upstream.close(resolve));});let worker;
  return {d,url,control,broker,calls:()=>calls,start:options=>worker=startWorker(control,token,d,options),send:(body=request(),headers={})=>requestLocal(url+'/v1/chat/completions',{method:'POST',body:JSON.stringify(body),headers:{host:'egress:8080',...headers},timeout:5000}),controlCall:(path,body)=>requestLocal(control+path,{method:body?'POST':'GET',body:body?JSON.stringify(body):undefined,headers:{authorization:'Bearer '+token}})};
}
test('B01 bridge preserves fragmented streaming tool call and tool-result round trip',async t=>{
  const bodies=[];const x=await setup(t,async(req,res)=>{let text='';for await(const c of req)text+=c;const body=JSON.parse(text);bodies.push(body);res.writeHead(200,{'content-type':'text/event-stream'});res.end(stream({tool:bodies.length===1}));});const rows=[];x.start({audit:row=>rows.push(row)});
  const first=await x.send();assert.equal(first.status,200);assert.match(first.body.toString(),/call_bridge_1/);
  const second=request();second.messages.push({role:'tool',content:'BRIDGE_TOOL_READY',tool_call_id:'call_bridge_1'});const final=await x.send(second);assert.match(final.body.toString(),/BRIDGE_FINAL/);assert.equal(bodies[1].messages[1].content,'BRIDGE_TOOL_READY');assert.equal(rows.length,2);assert.ok(rows.every(r=>r.accepted && r.usage.input===20));
});
test('B02/B03 forbidden destination fields, Host, admin/query paths and control access never reach upstream',async t=>{
  const x=await setup(t,(_req,res)=>res.end('must not be reached'));x.start();
  for(const host of ['egress:18081','192.168.1.10:8080','[::1]:8080','api.openai.com:443'])assert.equal((await x.send(request(),{host})).status,403);
  for(const path of ['/slots','/props','/v1/chat/completions?target=evil'])assert.equal((await requestLocal(x.url+path,{headers:{host:'egress:8080'}})).status,403);
  const absolute=await new Promise((resolve,reject)=>{const req=http.request(x.url,{path:'http://192.168.1.2:9000/v1/chat/completions',headers:{host:'egress:8080'}},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});req.on('error',reject);req.end();});assert.equal(absolute,403);
  assert.equal((await x.send({...request(),target:'http://127.0.0.1:9'})).status,400);
  assert.equal((await x.send(request(),{'x-target-url':'http://127.0.0.1:9'})).status,403);
  assert.equal((await requestLocal(x.control+'/lease')).status,403);assert.equal(x.calls(),0);
});
test('B03/B04 upstream redirect never invokes other destination or cloud fallback',async t=>{
  let forbidden=0;const other=http.createServer((_req,res)=>{forbidden++;res.end('forbidden');});other.listen(0,'127.0.0.1');await once(other,'listening');t.after(()=>other.close());
  const x=await setup(t,(_req,res)=>{res.writeHead(302,{location:`http://127.0.0.1:${other.address().port}/cloud`});res.end();});x.start();assert.equal((await x.send()).status,502);assert.equal(x.calls(),1);assert.equal(forbidden,0);
});
for(const [name,handler] of [['invalid JSON',(_q,r)=>{r.writeHead(200,{'content-type':'text/event-stream'});r.end('data: not-json\n\ndata: [DONE]\n\n');}],['truncated SSE',(_q,r)=>{r.writeHead(200,{'content-type':'text/event-stream'});r.end(stream().replace('data: [DONE]\n\n',''));}],['oversized response',(_q,r)=>{r.writeHead(200,{'content-type':'text/event-stream'});r.end('x'.repeat(4*1024*1024+1));}],['4xx',(_q,r)=>{r.writeHead(400);r.end('rejected');}],['5xx',(_q,r)=>{r.writeHead(500);r.end('rejected');}]])test('B05 '+name+' yields bounded failure',async t=>{const x=await setup(t,handler);const rows=[];x.start({audit:row=>rows.push(row)});assert.equal((await x.send()).status,502);assert.equal(rows[0].accepted,false);assert.equal(rows[0].usage,null);});
test('B06 deadline and disconnect cancel upstream without stopping shared mock service',async t=>{
  let disconnect=false;const x=await setup(t,(_req,res)=>{res.on('close',()=>disconnect=true);},{timeoutMs:150});x.start();assert.equal((await x.send()).status,504);await new Promise(resolve=>setTimeout(resolve,500));assert.equal(disconnect,true);
  assert.equal((await x.send()).status,504);assert.equal(x.calls(),2);
});
test('B07 weights/template/backend/context change fingerprints and corrupt record is rejected',()=>{
  const d=deployment(),base=fingerprint(d);
  for(const change of [d=>d.model.files[0].sha256='0'.repeat(64),d=>d.model.chat_template_sha256='1'.repeat(64),d=>d.engine.backend='rocm',d=>d.protocol.context_tokens=16384]){const altered=structuredClone(d);change(altered);assert.notEqual(fingerprint(altered),base);}
  assert.ok(localRecordErrors({status:'prepared',model:{provider:'local',id:d.alias},local_inference:{schema_version:1,deployment_sha256:'2'.repeat(64),fingerprint:'3'.repeat(64),deployment:d,observed:null}}).length);
});
test('B08 missing primary usage stays null; stream with wrong alias is rejected',()=>{assert.equal(validateLocalResponse(Buffer.from(stream({usage:false})),deployment()).usage,null);assert.throws(()=>validateLocalResponse(Buffer.from(stream({model:'other'})),deployment()),/identity/);});
test('B09 artifact tamper rejects pre-start identity',async t=>{
  const dir=mkdtempSync(join(tmpdir(),'local-pins-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));const d=deployment();d.engine.backend='vulkan';
  const rows=[...d.model.files,...d.engine.files,d.hardware.passport];for(const [index,row] of rows.entries()){row.path=join(dir,index===0?'model.gguf':String(index));writeFileSync(row.path,'x');row.bytes=1;row.sha256='0'.repeat(64);}d.engine.executable=d.engine.files[0].path;
  await assert.rejects(verifyFiles(d),/hash mismatch/);
});
test('B02 private/LAN/IPv6 deployment endpoints are rejected before worker connection',()=>{for(const host of ['localhost','192.168.0.1','::1','127.0.0.2']){const d=deployment();d.endpoint.host=host;assert.throws(()=>validateDeployment(d),/loopback/);}});

test('B11 linux native resource row derives memory, pressure and power fields',()=>{
  const meminfo=['MemTotal:       131072000 kB','MemAvailable:   114000000 kB','SwapTotal:      0 kB','SwapFree:       0 kB'].join('\n');
  assert.equal(parseMeminfo(meminfo).MemAvailable,114000000*1024);
  const row=linuxResourceRow({meminfo,swaps:'',pressure:'some avg10=0.00 avg60=0.00 avg300=0.00 total=0',power:{onAc:true,listing:'AC0'}});
  assert.equal(row.pressure_level,1);assert.equal(row.pressure_free_percentage,86);
  assert.equal(row.swap_used_bytes,0);assert.equal(row.on_ac_power,true);assert.equal(row.ac_power_mode,0);
  assert.ok(row.free_speculative_bytes>=8*2**30);
  const noMains=linuxResourceRow({meminfo,power:{onAc:null,listing:''}});
  assert.equal(noMains.on_ac_power,null);assert.equal(Object.values(noMains.commands).every(c=>c.returncode===0),true);
  const busy=linuxResourceRow({meminfo:['MemTotal:       131072000 kB','MemAvailable:   20000000 kB','SwapTotal: 1000 kB','SwapFree: 0 kB'].join('\n'),pressure:'some avg10=20.00'});
  assert.notEqual(busy.pressure_level,1);
});
test('B12 native supervisor admits only the matching platform/backend before any process start',async()=>{
  const d=deployment();
  if(process.platform==='linux'){
    const wrong=structuredClone(d);wrong.engine.backend='metal';
    await assert.rejects(startNative(wrong,join(tmpdir(),'b12-'+Date.now())),/requires the ROCm or Vulkan backend/);
  } else if(process.platform==='darwin'){
    const wrong=structuredClone(d);wrong.engine.backend='rocm';
    await assert.rejects(startNative(wrong,join(tmpdir(),'b12-'+Date.now())),/requires the Metal backend/);
  }
});
test('B05 oversized agent body cannot reach upstream',async t=>{const x=await setup(t,(_q,r)=>r.end('forbidden'),{maxBody:100});x.start();try{const result=await x.send({...request(),messages:[{role:'user',content:'x'.repeat(500)}]});assert.equal(result.status,400);}catch(error){assert.match(error.message,/reset|socket hang up/);}assert.equal(x.calls(),0);});
