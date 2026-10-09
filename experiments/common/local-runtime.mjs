// Trusted native supervisor and reverse worker; never mounted into the agent.
import http from 'node:http';
import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream, readFileSync, writeFileSync, mkdirSync, statSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { validateDeployment, fingerprint, validateLocalResponse } from '../../scripts/lib/local-inference.mjs';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const now=()=>new Date().toISOString();
export function requestLocal(url,{method='GET',body,headers={},signal,timeout=300000,maxBytes=4*1024*1024}={}) {
  const u=new URL(url);if(u.protocol!=='http:' || u.hostname!=='127.0.0.1' || u.username || u.password)throw new Error('Worker only connects to literal IPv4 loopback');
  return new Promise((resolve,reject)=>{
    const req=http.request(u,{method,headers,agent:false,signal},res=>{
      const chunks=[];let bytes=0;
      res.on('data',chunk=>{bytes+=chunk.length;if(bytes>maxBytes)res.destroy(new Error('Response limit exceeded'));else chunks.push(chunk);});
      res.on('error',reject);res.on('aborted',()=>reject(new Error('Truncated upstream response')));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));
    });const timer=setTimeout(()=>req.destroy(new Error('Upstream deadline')),timeout);req.on('close',()=>clearTimeout(timer));req.on('error',reject);req.end(body);
  });
}
export async function verifyFiles(d) {
  validateDeployment(d);const dir=dirname(d.engine.executable),pins=new Set(d.engine.files.map(f=>f.path));
  if(d.engine.backend==='metal') {
    for(const family of ['libggml','libggml-base','libggml-cpu','libggml-metal','libggml-blas','libllama','libmtmd'])if(!pins.has(join(dir,family+'.dylib')))throw new Error('Missing canonical library pin');
    for(const file of readdirSync(dir).filter(name=>name.endsWith('.dylib')))if(!pins.has(join(dir,file)))throw new Error('Unpinned bundled dylib');
  }
  const verified={};
  for(const f of [...d.model.files,...d.engine.files,d.hardware.passport]) {
    if(statSync(f.path).size!==f.bytes)throw new Error('Artifact bytes mismatch');
    const h=createHash('sha256');for await(const chunk of createReadStream(f.path))h.update(chunk);const digest=h.digest('hex');
    if(digest!==f.sha256)throw new Error('Artifact hash mismatch');verified[f.path]=digest;
  }return verified;
}
export function nativeCommand(d) {
  validateDeployment(d);const p=d.protocol;
  return [d.engine.executable,'-m',d.model.files[0].path,'--host','127.0.0.1','--port',String(d.endpoint.port),'--alias',d.alias,'-ngl',String(p.offload),'-c',String(p.context_tokens),'-np','1','-t',String(p.threads),'-b',String(p.batch),'-ub',String(p.ubatch),'-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto','--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots'];
}
export async function startNative(d,trace) {
  validateDeployment(d);if(process.platform!=='darwin' || d.engine.backend!=='metal')throw new Error('Native local supervisor currently admitted only on macOS/Metal');
  mkdirSync(trace,{recursive:true});const output=(name,value)=>writeFileSync(join(trace,name),JSON.stringify(value,null,2)+'\n');
  const safe=row=>Object.values(row.commands).every(c=>c.returncode===0) && row.pressure_level===1 && row.pressure_free_percentage>=50 && row.free_speculative_bytes>=8*2**30 && row.swap_used_bytes===0 && row.on_ac_power===true && row.ac_power_mode===0;
  const sample=()=>JSON.parse(execFileSync('python3',['-B','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(import.meta.dirname)});from local_resources import sample;print(json.dumps(sample()))`],{encoding:'utf8',timeout:15000,env:{PATH:process.env.PATH,HOME:process.env.HOME,PYTHONDONTWRITEBYTECODE:'1'}}));
  if(process.arch!=='arm64' || Number(execFileSync('sysctl',['-n','hw.memsize'],{encoding:'utf8'}).trim())!==128*2**30 || execFileSync('sw_vers',['-productVersion'],{encoding:'utf8'}).trim()!=='26.5' || execFileSync('sw_vers',['-buildVersion'],{encoding:'utf8'}).trim()!=='25F71')throw new Error('Native supervisor requires admitted M5 macOS/RAM conditions');
  const before=sample();if(!safe(before))throw new Error('Native resource/power admission failed');
  const loaded=JSON.parse(execFileSync('/opt/homebrew/bin/lms',['ps','--json'],{encoding:'utf8',timeout:10000}));const ollama=JSON.parse((await requestLocal('http://127.0.0.1:11434/api/ps',{timeout:5000})).body);
  if(loaded.length || ollama.models.length)throw new Error('Foreign model loaded; refusing native startup');
  const net=await import('node:net');await new Promise((resolve,reject)=>{const socket=net.createServer();socket.once('error',reject);socket.listen(d.endpoint.port,'127.0.0.1',()=>socket.close(resolve));});
  const verified=await verifyFiles(d),command=nativeCommand(d),proof={fingerprint:fingerprint(d),verified_files:verified,verified_before_popen:true,verified_at:now(),popen_invoked_at:now(),command,pid:null,properties:null,resources_before:before};
  const log=createWriteStream(join(trace,'native-server.txt'),{flags:'wx'});const child=spawn(command[0],command.slice(1),{cwd:dirname(command[0]),env:Object.fromEntries(['PATH','HOME','TMPDIR','USER','LANG'].filter(k=>process.env[k]).map(k=>[k,process.env[k]])),detached:true,stdio:['ignore','pipe','pipe']});
  proof.pid=child.pid;output('startup-process.json',proof);let exit=null,error=null,bytes=0,interrupted=false,closed=false,guard=null,busy=false;
  const exited=new Promise(resolve=>{child.once('error',e=>{error=e.message;resolve();});child.once('close',(code,signal)=>{exit={code,signal};resolve();});});
  const interrupt=()=>{if(!interrupted && !exit && child.pid){interrupted=true;try{process.kill(-child.pid,'SIGINT');}catch(e){if(e.code!=='ESRCH')throw e;}}};
  const onInterrupt=()=>{guard='Coordinator interrupted';interrupt();};process.on('SIGINT',onInterrupt);process.on('SIGTERM',onInterrupt);
  const collect=chunk=>{bytes+=chunk.length;if(bytes>16*1024*1024){guard='Native log limit';interrupt();}else log.write(chunk);};child.stdout.on('data',collect);child.stderr.on('data',collect);
  const assertion=spawn('/usr/bin/caffeinate',['-i','-w',String(process.pid)],{stdio:'ignore'});
  const base=`http://127.0.0.1:${d.endpoint.port}`;
  const check=async()=>{
    if(exit || error || guard)throw new Error(guard || error || 'Owned native process exited');
    const response=await requestLocal(base+'/props',{timeout:5000});if(response.status!==200)throw new Error('Native identity endpoint failed');const props=JSON.parse(response.body);
    if(props.model_alias!==d.alias || props.model_path!==d.model.files[0].path || props.total_slots!==1 || !props.build_info.includes(d.engine.commit.slice(0,7)) || props.default_generation_settings.n_ctx!==d.protocol.context_tokens || createHash('sha256').update(props.chat_template).digest('hex')!==d.model.chat_template_sha256)throw new Error('Observed native identity differs from sealed deployment');
    return props;
  };
  const timeline=createWriteStream(join(trace,'native-memory.jsonl'),{flags:'wx'});
  const timer=setInterval(()=>{if(busy || closed)return;busy=true;try{const row=sample();const rss=Number(execFileSync('ps',['-o','rss=','-p',String(child.pid)],{encoding:'utf8'}).trim())*1024;row.server_rss_bytes=rss;timeline.write(JSON.stringify(row)+'\n');if(!safe(row) || !Number.isFinite(rss) || rss>24*2**30){guard='Native memory/power guard';interrupt();}}catch{guard='Resource collector failed';interrupt();}finally{busy=false;}},2000);
  const close=async()=>{if(closed)return;closed=true;clearInterval(timer);interrupt();let timeout;await Promise.race([exited,new Promise(resolve=>{timeout=setTimeout(resolve,30000);})]);clearTimeout(timeout);if(!exit && child.pid){process.kill(-child.pid,'SIGKILL');await exited;guard=guard??'Native shutdown deadline';}assertion.kill('SIGTERM');process.removeListener('SIGINT',onInterrupt);process.removeListener('SIGTERM',onInterrupt);log.end();timeline.end();output('shutdown-process.json',{timestamp:now(),pid:child.pid,exit,error,guard,sigint_count:interrupted?1:0});};
  try {
    for(let i=0;i<120;i++){if(exit || error || guard)throw new Error('Native startup stopped');try{const r=await requestLocal(base+'/health',{timeout:2000});if(r.status===200 && JSON.parse(r.body).status==='ok')break;}catch{}if(i===119)throw new Error('Native readiness deadline');await delay(1000);}
    proof.properties=await check();const nativeLog=readFileSync(join(trace,'native-server.txt'),'utf8');if(!nativeLog.includes('Apple M5 Max') || !nativeLog.includes('offloaded 33/33 layers to GPU') || !/has tensor\s*=\s*true/.test(nativeLog))throw new Error('Native Metal/tensor device evidence missing');proof.device='Apple M5 Max';proof.offload='33/33';proof.tensor_capability=true;proof.ready_at=now();output('startup-process.json',proof);
    return {proof,base,verify:async()=>{await verifyFiles(d);await check();},close};
  }catch(e){await close();throw e;}
}
export function startWorker(control,token,d,{verify=async()=>{},audit=()=>{},trace}={}) {
  if(trace)mkdirSync(trace,{recursive:true});let stopped=false,active=null,sequence=0;
  const controlCall=async(path,body)=>{const response=await requestLocal(control+path,{method:body?'POST':'GET',body:body?JSON.stringify(body):undefined,headers:{authorization:'Bearer '+token,...(body?{'content-type':'application/json'}:{})},timeout:5000,maxBytes:2*1024*1024});if(response.status!==200)throw new Error('Broker control error');return JSON.parse(response.body);};
  const run=(async()=>{
    while(!stopped) {
      const {job}=await controlCall('/lease');if(!job){await delay(100);continue;}const index=++sequence;active=new AbortController();let checking=false;
      const timer=setInterval(async()=>{if(checking)return;checking=true;try{if((await controlCall('/state/'+job.id)).canceled)active?.abort();}catch{active?.abort();}finally{checking=false;}},250);
      try {
        await verify();if(active.signal.aborted)throw new Error('Client canceled');
        const body=Buffer.from(JSON.stringify(job.body));if(trace)writeFileSync(join(trace,`${index}-request.json`),body);
        const response=await requestLocal(`http://127.0.0.1:${d.endpoint.port}/v1/chat/completions`,{method:'POST',body,headers:{'content-type':'application/json'},signal:active.signal});
        if(trace)writeFileSync(join(trace,`${index}-response.bin`),response.body);
        if(response.status!==200 || !String(response.headers['content-type']).startsWith('text/event-stream'))throw new Error('Upstream HTTP/content-type error');
        const parsed=validateLocalResponse(response.body,d);await verify();if(active.signal.aborted)throw new Error('Client canceled');
        const row={id:job.id,index,accepted:true,usage:parsed.usage,usage_unavailable:parsed.usage_unavailable,timestamp:now()};audit(row);
        if(trace)writeFileSync(join(trace,`${index}-record.json`),JSON.stringify(row,null,2)+'\n');
        await controlCall('/result',{id:job.id,status:200,body:response.body.toString('base64')});
      }catch(error){const row={id:job.id,index,accepted:false,usage:null,usage_unavailable:'Inference failed or canceled; complete usage unavailable.',error:String(error.message),timestamp:now()};audit(row);if(trace)writeFileSync(join(trace,`${index}-record.json`),JSON.stringify(row,null,2)+'\n');try{await controlCall('/result',{id:job.id,status:502,body:Buffer.from('{"error":"Local inference failed; no fallback"}').toString('base64')});}catch{}}
      finally{clearInterval(timer);active=null;}
    }
  })();run.catch(()=>{});
  return {done:run,close:async()=>{stopped=true;active?.abort();await run.catch(()=>{});}};
}
