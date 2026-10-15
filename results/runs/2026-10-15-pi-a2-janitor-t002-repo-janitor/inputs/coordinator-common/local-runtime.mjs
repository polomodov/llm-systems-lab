// Trusted native supervisor and reverse worker; never mounted into the agent.
import http from 'node:http';
import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream, readFileSync, writeFileSync, mkdirSync, statSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { validateDeployment, fingerprint, validateLocalResponse } from '../coordinator/lib/local-inference.mjs';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const now=()=>new Date().toISOString();
const GIB=2**30;
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
export function assertResourceFresh(last,now=Date.now()) {if(now-last>15000 || now<last)throw new Error('Resource timeline stale or clock moved backwards');}
export function nativeCommand(d) {
  validateDeployment(d);const p=d.protocol;
  return [d.engine.executable,'-m',d.model.files[0].path,'--host','127.0.0.1','--port',String(d.endpoint.port),'--alias',d.alias,'-ngl',String(p.offload),'-c',String(p.context_tokens),'-np','1','-t',String(p.threads),'-b',String(p.batch),'-ub',String(p.ubatch),'-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto','--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots'];
}
// macOS resource sampling (vm_stat / memory_pressure / pmset) stays unchanged.
function sampleMacos(){
  return JSON.parse(execFileSync('python3',['-B','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(import.meta.dirname)});from local_resources import sample;print(json.dumps(sample()))`],{encoding:'utf8',timeout:15000,env:{PATH:process.env.PATH,HOME:process.env.HOME,PYTHONDONTWRITEBYTECODE:'1'}}));
}
const macosSafe=row=>Object.values(row.commands).every(c=>c.returncode===0) && row.pressure_level===1 && row.pressure_free_percentage>=50 && row.free_speculative_bytes>=8*GIB && row.swap_used_bytes===0 && row.on_ac_power===true && row.ac_power_mode===0;
// Linux resource sampling from /proc and /sys; no Python dependency.
export function parseMeminfo(text){const out={};for(const line of text.split(/\r?\n/)){const m=/^(\w+):\s+(\d+)\s*kB$/.exec(line);if(m)out[m[1]]=Number(m[2])*1024;}return out;}
export function parseOsRelease(text){const out={};for(const line of text.split(/\r?\n/)){const m=/^([A-Z0-9_]+)=(.*)$/.exec(line.trim());if(m)out[m[1]]=m[2].replace(/^"(.*)"$/,'$1');}return out;}
const normalizeText=value=>String(value??'').toLowerCase().replace(/\s+/g,' ').trim();
// Live host identity is compared with the sealed passport so measurements from a
// different machine can never be attributed to the pinned Ryzen conditions.
export function linuxHostIdentity({osRelease='',cpuinfo='',meminfo='',kernel='',devices={}}={}){
  const os=parseOsRelease(osRelease),info=parseMeminfo(meminfo);
  const cpu=(/^model name\s*:\s*(.+)$/m.exec(cpuinfo)?.[1]??'').trim();
  return {os_id:os.ID??null,os_version_id:os.VERSION_ID??null,os_pretty_name:os.PRETTY_NAME??null,kernel:(kernel||'').trim()||null,cpu:cpu||null,mem_total_bytes:info.MemTotal??null,devices:{kfd:devices.kfd===true,renderD128:devices.renderD128===true}};
}
export function assertLinuxHostMatchesPassport(passport,identity){
  if(!passport || passport.kind!=='hardware-passport')throw new Error('Native supervisor requires a sealed hardware passport');
  const problems=[];
  if(passport.kernel && identity.kernel!==passport.kernel)problems.push(`kernel ${identity.kernel} != ${passport.kernel}`);
  const os=normalizeText(passport.os);
  if(os){
    const pretty=normalizeText(identity.os_pretty_name);
    const idOk=identity.os_id && os.includes(normalizeText(identity.os_id));
    const versionOk=identity.os_version_id && new RegExp(`\\b${String(identity.os_version_id).split('.').slice(0,2).join('\\.')}\\b`).test(os);
    if(pretty!==os && !(idOk && versionOk))problems.push(`OS ${identity.os_pretty_name} != ${passport.os}`);
  }
  const cpu=normalizeText(passport.cpu),liveCpu=normalizeText(identity.cpu);
  if(cpu && liveCpu && liveCpu!==cpu && !liveCpu.includes(cpu) && !cpu.includes(liveCpu))problems.push(`CPU ${identity.cpu} != ${passport.cpu}`);
  const expected=passport.memory?.MemTotal_bytes,live=identity.mem_total_bytes;
  if(expected && live!=null && Math.abs(live-expected)>Math.max(expected*0.02,64*2**20))problems.push(`MemTotal ${live} != ${expected}`);
  for(const device of passport.gpu?.devices??[]){
    if(device==='/dev/kfd' && !identity.devices.kfd)problems.push('missing /dev/kfd');
    if(device==='/dev/dri/renderD128' && !identity.devices.renderD128)problems.push('missing /dev/dri/renderD128');
  }
  if(problems.length)throw new Error('Live Linux host differs from sealed hardware passport: '+problems.join('; '));
  return identity;
}
export function linuxResourceRow({meminfo='',swaps='',pressure='',power={onAc:null,listing:''}}={}){
  const info=parseMeminfo(meminfo),total=info.MemTotal??null,available=info.MemAvailable??null;
  const swapUsed=(info.SwapTotal??0)-(info.SwapFree??0);
  const pct=total&&available!=null?Math.floor(available/total*100):null;
  const some=/^some\s+avg10=([0-9.]+)/m.exec(pressure);const someValue=some?Number(some[1]):null;
  const level=pct===null?null:(someValue!==null&&someValue>=10)?3:(pct>=50?1:pct>=25?2:3);
  // A missing /proc read must stay visible: the empty string is a read failure,
  // not a sampled value, and linuxSafe() rejects any command with a nonzero code.
  return {
    timestamp:now(),
    commands:{
      meminfo:{argv:['cat','/proc/meminfo'],returncode:meminfo?0:1,stdout:meminfo,stderr:meminfo?'':'meminfo unavailable'},
      swaps:{argv:['cat','/proc/swaps'],returncode:swaps?0:1,stdout:swaps,stderr:swaps?'':'swaps unavailable'},
      pressure_memory:{argv:['cat','/proc/pressure/memory'],returncode:pressure?0:1,stdout:pressure,stderr:pressure?'':'PSI memory pressure unavailable'},
      power_supply:{argv:['ls','/sys/class/power_supply'],returncode:0,stdout:power.listing??'',stderr:''}
    },
    free_pages_bytes:available,
    free_speculative_bytes:available,
    pressure_free_percentage:pct,
    pressure_level:level,
    swap_used_bytes:swapUsed,
    on_ac_power:power.onAc??null,
    ac_power_mode:0
  };
}
function readLinuxPower(){
  const base='/sys/class/power_supply';let names=[];
  try{names=existsSync(base)?readdirSync(base):[];}catch{}
  let onAc=null;
  for(const name of names){try{const type=readFileSync(join(base,name,'type'),'utf8').trim();if(type==='Mains')onAc=readFileSync(join(base,name,'online'),'utf8').trim()==='1';}catch{}}
  return {onAc,listing:names.join('\n')};
}
function sampleLinux(){
  const read=path=>{try{return readFileSync(path,'utf8');}catch{return '';}};
  return linuxResourceRow({meminfo:read('/proc/meminfo'),swaps:read('/proc/swaps'),pressure:read('/proc/pressure/memory'),power:readLinuxPower()});
}
function readLinuxHost(){
  const read=path=>{try{return readFileSync(path,'utf8');}catch{return '';}};
  let kernel='';try{kernel=execFileSync('uname',['-r'],{encoding:'utf8'});}catch{}
  return linuxHostIdentity({osRelease:read('/etc/os-release'),cpuinfo:read('/proc/cpuinfo'),meminfo:read('/proc/meminfo'),kernel,devices:{kfd:existsSync('/dev/kfd'),renderD128:existsSync('/dev/dri/renderD128')}});
}
const linuxSafe=row=>Object.values(row.commands).every(c=>c.returncode===0) && row.pressure_level===1 && row.pressure_free_percentage!==null && row.pressure_free_percentage>=50 && row.free_speculative_bytes!==null && row.free_speculative_bytes>=8*GIB && row.swap_used_bytes!==null && row.swap_used_bytes<=1*GIB && row.on_ac_power!==false;
export async function startNative(d,trace) {
  validateDeployment(d);
  const macos=process.platform==='darwin',linux=process.platform==='linux';
  if(!macos && !linux)throw new Error('Native local supervisor supports macOS/Metal or Linux/ROCm|Vulkan only');
  if(macos && d.engine.backend!=='metal')throw new Error('macOS native supervisor requires the Metal backend');
  if(linux && !['rocm','vulkan'].includes(d.engine.backend))throw new Error('Linux native supervisor requires the ROCm or Vulkan backend');
  mkdirSync(trace,{recursive:true});const output=(name,value)=>writeFileSync(join(trace,name),JSON.stringify(value,null,2)+'\n');
  const safe=macos?macosSafe:linuxSafe,sample=macos?sampleMacos:sampleLinux;
  if(macos){
    if(process.arch!=='arm64' || Number(execFileSync('sysctl',['-n','hw.memsize'],{encoding:'utf8'}).trim())!==128*GIB || execFileSync('sw_vers',['-productVersion'],{encoding:'utf8'}).trim()!=='26.5' || execFileSync('sw_vers',['-buildVersion'],{encoding:'utf8'}).trim()!=='25F71')throw new Error('Native supervisor requires admitted M5 macOS/RAM conditions');
  }
  const before=sample();if(!safe(before))throw new Error('Native resource/power admission failed');
  let hostIdentity=null;
  if(linux){
    const passport=JSON.parse(readFileSync(d.hardware.passport.path,'utf8'));
    hostIdentity=assertLinuxHostMatchesPassport(passport,readLinuxHost());
  }
  if(macos){
    const loaded=JSON.parse(execFileSync('/opt/homebrew/bin/lms',['ps','--json'],{encoding:'utf8',timeout:10000}));const ollama=JSON.parse((await requestLocal('http://127.0.0.1:11434/api/ps',{timeout:5000})).body);
    if(loaded.length || ollama.models.length)throw new Error('Foreign model loaded; refusing native startup');
  } else {
    let foreign='';try{foreign=execFileSync('pgrep',['-x','llama-server'],{encoding:'utf8'}).trim();}catch(error){if(error.status!==1 && error.code!=='ENOENT')throw error;}
    if(foreign)throw new Error('Foreign llama-server process present; refusing native startup');
  }
  const net=await import('node:net');await new Promise((resolve,reject)=>{const socket=net.createServer();socket.once('error',reject);socket.listen(d.endpoint.port,'127.0.0.1',()=>socket.close(resolve));});
  const verified=await verifyFiles(d),command=nativeCommand(d),proof={fingerprint:fingerprint(d),verified_files:verified,verified_before_popen:true,verified_at:now(),popen_invoked_at:now(),command,pid:null,properties:null,resources_before:before,host_identity:hostIdentity};
  const env=Object.fromEntries(['PATH','HOME','TMPDIR','USER','LANG'].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));
  if(linux)env.LD_LIBRARY_PATH=dirname(command[0]);
  const log=createWriteStream(join(trace,'native-server.txt'),{flags:'wx'});const child=spawn(command[0],command.slice(1),{cwd:dirname(command[0]),env,detached:true,stdio:['ignore','pipe','pipe']});
  proof.pid=child.pid;output('startup-process.json',proof);let exit=null,error=null,bytes=0,interrupted=false,closed=false,guard=null,busy=false;
  const exited=new Promise(resolve=>{child.once('error',e=>{error=e.message;resolve();});child.once('close',(code,signal)=>{exit={code,signal};resolve();});});
  const interrupt=()=>{if(!interrupted && !exit && child.pid){interrupted=true;try{process.kill(-child.pid,'SIGINT');}catch(e){if(e.code!=='ESRCH')throw e;}}};
  const setGuard=(reason,details={})=>{if(guard===null){guard=reason;output('resource-guard.json',{timestamp:now(),reason,...details});}interrupt();};
  const onInterrupt=()=>setGuard('Coordinator interrupted');process.on('SIGINT',onInterrupt);process.on('SIGTERM',onInterrupt);
  const collect=chunk=>{bytes+=chunk.length;if(bytes>16*1024*1024)setGuard('Native log limit');else log.write(chunk);};child.stdout.on('data',collect);child.stderr.on('data',collect);
  let assertion=null;
  if(macos){
    assertion=spawn('/usr/bin/caffeinate',['-i','-w',String(process.pid)],{stdio:'ignore'});proof.idle_sleep_assertion={command:['/usr/bin/caffeinate','-i','-w',String(process.pid)],pid:assertion.pid,scope:'process-bound idle-sleep assertion; no pmset changes'};assertion.on('error',()=>setGuard('Idle sleep assertion failed'));assertion.on('exit',()=>{if(!closed)setGuard('Idle sleep assertion exited unexpectedly');});
  } else {
    proof.idle_sleep_assertion=null;proof.idle_sleep_note='Linux host: no process-bound idle-sleep assertion; power mode recorded as 0 (not applicable)';
  }
  const base=`http://127.0.0.1:${d.endpoint.port}`;let lastSampleWall=Date.now();
  const check=async()=>{
    assertResourceFresh(lastSampleWall);
    if(exit || error || guard)throw new Error(guard || error || 'Owned native process exited');
    const response=await requestLocal(base+'/props',{timeout:5000});if(response.status!==200)throw new Error('Native identity endpoint failed');const props=JSON.parse(response.body);
    if(props.model_alias!==d.alias || props.model_path!==d.model.files[0].path || props.total_slots!==1 || !props.build_info.includes(d.engine.commit.slice(0,7)) || props.default_generation_settings.n_ctx!==d.protocol.context_tokens || createHash('sha256').update(props.chat_template).digest('hex')!==d.model.chat_template_sha256)throw new Error('Observed native identity differs from sealed deployment');
    return props;
  };
  const timeline=createWriteStream(join(trace,'native-memory.jsonl'),{flags:'wx'});
  const timer=setInterval(()=>{if(busy || closed || guard)return;busy=true;try{assertResourceFresh(lastSampleWall);const row=sample();lastSampleWall=Date.now();const value=execFileSync('ps',['-o','rss=','-p',String(child.pid)],{encoding:'utf8'}).trim();if(!/^\d+$/.test(value) || Number(value)<=0)throw new Error('Owned PID RSS unavailable');const rss=Number(value)*1024;row.server_rss_bytes=rss;timeline.write(JSON.stringify(row)+'\n');if(!safe(row) || !Number.isFinite(rss) || rss>24*GIB)setGuard('Native memory/power guard',{sample:row});}catch(error){setGuard('Resource collector failed: '+error.message,{last_sample_wall:lastSampleWall});}finally{busy=false;}},2000);
  const close=async()=>{if(closed)return;closed=true;clearInterval(timer);interrupt();let timeout;await Promise.race([exited,new Promise(resolve=>{timeout=setTimeout(resolve,30000);})]);clearTimeout(timeout);if(!exit && child.pid){process.kill(-child.pid,'SIGKILL');await exited;guard=guard??'Native shutdown deadline';}assertion?.kill('SIGTERM');process.removeListener('SIGINT',onInterrupt);process.removeListener('SIGTERM',onInterrupt);log.end();timeline.end();output('shutdown-process.json',{timestamp:now(),pid:child.pid,exit,error,guard,sigint_count:interrupted?1:0});};
  try {
    for(let i=0;i<120;i++){if(exit || error || guard)throw new Error('Native startup stopped');try{const r=await requestLocal(base+'/health',{timeout:2000});if(r.status===200 && JSON.parse(r.body).status==='ok')break;}catch{}if(i===119)throw new Error('Native readiness deadline');await delay(1000);}
    proof.properties=await check();const nativeLog=readFileSync(join(trace,'native-server.txt'),'utf8');
    if(macos){
      if(!nativeLog.includes('Apple M5 Max') || !nativeLog.includes('offloaded 33/33 layers to GPU') || !/has tensor\s*=\s*true/.test(nativeLog))throw new Error('Native Metal/tensor device evidence missing');proof.device='Apple M5 Max';proof.offload='33/33';proof.tensor_capability=true;
    } else {
      const offload=/load_tensors:\s+offloaded (\d+)\/(\d+) layers to GPU/.exec(nativeLog);
      if(!offload || offload[1]!==offload[2])throw new Error('Native full GPU offload evidence missing');
      const marker=d.engine.backend==='rocm'?'ROCm0':'Vulkan0';
      if(!nativeLog.includes(marker))throw new Error(`Native ${d.engine.backend} device evidence missing`);
      proof.device=marker;proof.offload=`${offload[1]}/${offload[2]}`;proof.full_gpu_offload=true;
    }
    proof.ready_at=now();output('startup-process.json',proof);
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
