import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { randomBytes } from 'node:crypto';
import { spawn,spawnSync } from 'node:child_process';
import { homedir } from 'node:os';
import { mkdtempSync,mkdirSync,writeFileSync,readFileSync,copyFileSync,rmSync } from 'node:fs';
import { join } from 'node:path';
import { containerArgs, execute } from '../scripts/run.mjs';
import { startWorker,requestLocal } from '../experiments/common/local-runtime.mjs';
import { deployment,stream } from '../experiments/common/local-fixture.mjs';
const enabled=process.env.HARNESS_LOCAL_DOCKER_TEST==='1';
const image='harness-lab/pi:0.73.1',proxyImage='node:24.13.1-bookworm-slim';
const repository=new URL('../',import.meta.url).pathname;
const docker=(argv,env=process.env)=>{const r=spawnSync('docker',argv,{encoding:'utf8',env,timeout:30000});assert.equal(r.status,0,r.stderr||r.error?.message);return r.stdout.trim();};
const run=argv=>new Promise((resolve,reject)=>{const child=spawn('docker',argv,{stdio:['ignore','pipe','pipe']});let stdout='',stderr='';const timer=setTimeout(()=>child.kill('SIGTERM'),60000);child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);child.on('error',reject);child.on('close',code=>{clearTimeout(timer);resolve({code,stdout,stderr});});});
test('Docker B01–B04: native Pi round-trip, isolated agent and private reverse control', {skip:!enabled},async t=>{
  docker(['image','inspect',image]);docker(['image','inspect',proxyImage]);
  const dir=mkdtempSync(join(homedir(),'.lab08-docker-'));const control=join(dir,'control'),workspace=join(dir,'workspace');mkdirSync(control);mkdirSync(join(workspace,'sample'),{recursive:true});mkdirSync(join(workspace,'artifacts'));
  const suffix=randomBytes(6).toString('hex'),network='lab08-test-'+suffix,broker=network+'-broker',agent=network+'-agent';const capability=randomBytes(32).toString('hex');
  let worker;const bodies=[];let canceled=0;const upstream=http.createServer(async(req,res)=>{let bytes='';for await(const chunk of req)bytes+=chunk;const body=JSON.parse(bytes);bodies.push(body);if(body.messages[0]?.content==='Synthetic cancel fixture'){res.on('close',()=>canceled++);return;}assert.equal(req.url,'/v1/chat/completions');assert.equal(req.headers.authorization,undefined);res.writeHead(200,{'content-type':'text/event-stream'});res.end(stream({tool:bodies.length===1}));});upstream.listen(0,'127.0.0.1');await once(upstream,'listening');const d=deployment();d.endpoint.port=upstream.address().port;
  t.after(async()=>{await worker?.close();for(const name of [agent,broker])spawnSync('docker',['rm','-f',name],{timeout:15000});spawnSync('docker',['network','rm',network],{timeout:15000});upstream.closeAllConnections();await new Promise(resolve=>upstream.close(resolve));rmSync(dir,{recursive:true,force:true});});
  writeFileSync(join(control,'local-deployment.json'),JSON.stringify(d));copyFileSync(join(repository,'scripts/lib/local-inference.mjs'),join(control,'local-inference.mjs'));writeFileSync(join(control,'local-broker.mjs'),readFileSync(join(repository,'experiments/common/local-broker.mjs'),'utf8').replace("'../../scripts/lib/local-inference.mjs'","'./local-inference.mjs'"));
  for(const file of ['adapter.mjs','run.mjs'])copyFileSync(join(repository,'experiments/pi',file),join(control,file));
  docker(['network','create','--internal',network]);docker(['run','-d','--name',broker,'--network','bridge','--publish','127.0.0.1::8081','--env','LAB_BRIDGE_TOKEN','--user',`${process.getuid()}:${process.getgid()}`,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',`type=bind,src=${control},dst=/control,readonly`,proxyImage,'node','/control/local-broker.mjs'],{...process.env,LAB_BRIDGE_TOKEN:capability});
  docker(['network','connect','--alias','egress',network,broker]);
  const port=docker(['port',broker,'8081/tcp']);assert.match(port,/^127\.0\.0\.1:\d+$/);const url='http://'+port;let ready=false;for(let i=0;i<40;i++){try{const r=await requestLocal(url+'/lease',{headers:{authorization:'Bearer '+capability},timeout:1000});if(r.status===200){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}assert.equal(ready,true,'Private reverse broker control reachable from host');
  worker=startWorker(url,capability,d);
  writeFileSync(join(control,'entrypoint.mjs'),`
import assert from 'node:assert/strict';import net from 'node:net';
import http from 'node:http';import {spawn} from 'node:child_process';import {existsSync,writeFileSync} from 'node:fs';
for(const path of ['/var/run/docker.sock','/run.json','/.env','/repository'])assert.equal(existsSync(path),false);
assert.notEqual(process.getuid(),0);assert.equal(process.env.LAB_BRIDGE_TOKEN,undefined);assert.equal(process.env.OPENAI_API_KEY,undefined);
const get=(port,path,host='egress:8080')=>new Promise((resolve,reject)=>{const req=http.request({hostname:'egress',port,path,headers:{host}},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});req.on('error',reject);req.end();});
assert.equal(await get(8081,'/lease'),403);assert.equal(await get(8080,'/slots'),403);assert.equal(await get(8080,'/health','egress:1234'),403);
for(const host of ['1.1.1.1','192.168.5.2','::1']){const outcome=await new Promise(resolve=>{const socket=net.connect({host,port:${d.endpoint.port}});socket.once('connect',()=>{socket.destroy();resolve('connected');});socket.once('error',()=>resolve('denied'));socket.setTimeout(1000,()=>{socket.destroy();resolve('timeout');});});assert.notEqual(outcome,'connected');}
const child=spawn('node',['/control/run.mjs',JSON.stringify({model:'lab-model',provider:'local',turns:3,prompt:'Synthetic SDK round trip. Execute the supplied tool then answer.'})],{stdio:'inherit'});child.on('close',code=>{console.log(JSON.stringify({type:'lab_boundary',isolated:true}));process.exitCode=code;});
`);
  const output=await run(containerArgs({name:agent,network,image,workspace,control,readOnlyWorkspace:false,uid:process.getuid(),gid:process.getgid(),credentialKeys:[]}));
  assert.equal(output.code,0,output.stderr+'\n'+output.stdout);const events=output.stdout.split('\n').flatMap(line=>{try{return [JSON.parse(line)];}catch{return [];}});
  assert.equal(bodies.length,2);assert.ok(bodies[1].messages.some(m=>m.role==='tool' && m.content.includes('BRIDGE_TOOL_READY')));
  assert.ok(events.some(e=>e.type==='tool_execution_end' && JSON.stringify(e).includes('BRIDGE_TOOL_READY')));
  assert.ok(events.some(e=>e.type==='message_end' && JSON.stringify(e).includes('BRIDGE_FINAL')));
  assert.equal(events.findLast(e=>e.type==='lab_pi_result').turns,2);assert.equal(output.stdout.includes(capability),false);assert.equal(output.stderr.includes(capability),false);
  docker(['rm','-f',agent]);
  writeFileSync(join(control,'entrypoint.mjs'),`
const body={model:'lab-model',messages:[{role:'user',content:'Synthetic cancel fixture'}],stream:true,stream_options:{include_usage:true},max_tokens:2048,temperature:0};
try{await fetch('http://egress:8080/v1/chat/completions',{method:'POST',body:JSON.stringify(body),signal:AbortSignal.timeout(500)});process.exitCode=1;}catch(error){console.log(JSON.stringify({canceled:true,type:error.name}));}
`);
  const canceledClient=await run(containerArgs({name:agent,network,image,workspace,control,readOnlyWorkspace:false,uid:process.getuid(),gid:process.getgid(),credentialKeys:[]}));assert.equal(canceledClient.code,0);await new Promise(resolve=>setTimeout(resolve,500));assert.equal(canceled,1);assert.equal(upstream.listening,true);
  docker(['rm','-f',agent]);writeFileSync(join(control,'entrypoint.mjs'),'setInterval(()=>{},1000);');
  const timed=await execute(containerArgs({name:agent,network,image,workspace,control,readOnlyWorkspace:false,uid:process.getuid(),gid:process.getgid(),credentialKeys:[]}),{env:process.env,timeout:1,name:agent});assert.equal(timed.timedOut,true);assert.equal(docker(['inspect','--format','{{.State.Running}}',agent]),'false');assert.equal(upstream.listening,true);
  console.log(JSON.stringify({acceptance:'B01/B02/B03/B04/B06',sdk_version:'0.73.1',sdk_requests:2,canceled_requests:canceled,native_tool_result:true,cloud_requests:0,isolated:true,control_denied:true}));
});
