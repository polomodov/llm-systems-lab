# -*- coding: utf-8 -*-
"""Pinned native LAB33, sequential deployments, raw evidence preserved."""
import datetime,hashlib,json,os,pathlib,re,signal,socket,subprocess,sys,threading,time,urllib.request
from resources import sample,safe
RAW=pathlib.Path(__file__).resolve().parent
MANIFEST=RAW.parent/'manifest.json'
OLL=pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/ollama/v0.40.1')
DIRECT=pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a/build-metal-tensor-tile16-arm64/bin/llama-server')
MODEL=pathlib.Path('/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf')
ALIAS='lab-apple-qwen35-9b-q6-k'
SHA='91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):(RAW/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def result(case,ok,reason=None):
 m=json.loads(MANIFEST.read_text());a=next(a for a in m['planned_attempts'] if a['id']==case);assert a['status']=='planned'
 a.update(status='completed' if ok else 'failed',reason=None if ok else reason,evidence_files=sorted('raw/'+p.name for p in RAW.glob(case+'*') if p.is_file()))
 assert a['evidence_files'],case
 MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'case':case,'accepted':ok,'reason':reason}),flush=True)
def env_ollama():
 env={k:v for k,v in os.environ.items() if k in ['HOME','PATH','TMPDIR','USER','LOGNAME','LANG','LC_ALL']}
 env.update(OLLAMA_HOST='127.0.0.1:11434',OLLAMA_MODELS=str(OLL/'models'),OLLAMA_NO_CLOUD='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_CONTEXT_LENGTH='8192',OLLAMA_FLASH_ATTENTION='1',OLLAMA_KV_CACHE_TYPE='f16',OLLAMA_KEEP_ALIVE='10m',OLLAMA_DEBUG='1',NO_PROXY='127.0.0.1,localhost,::1',no_proxy='127.0.0.1,localhost,::1')
 return env
def api(url,route,payload=None,timeout=30):
 req=urllib.request.Request(url+route,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
 with OPENER.open(req,timeout=timeout) as r:return {'http_status':r.status,'body':json.load(r)}
def preflight():
 assert safe(sample()),'Preflight memory/power'
 assert digest(MODEL)==SHA
 version=subprocess.run(['sw_vers'],capture_output=True,text=True);chip=subprocess.run(['sysctl','hw.memsize','machdep.cpu.brand_string'],capture_output=True,text=True)
 write('preflight-hardware.json',{'time':now(),'sw_vers':version.stdout,'sysctl':chip.stdout,'resources':sample()})
 runtime={'ollama':{'version':'0.40.1','source_commit':'cf2a313a298066d572c36812e5ad30a21c0db13b','archive_sha256':digest(OLL/'ollama-darwin.tgz'),'bundled_runner_version':(RAW/'ollama-bundled-runner-version.txt').read_text(),'files':{str(p):digest(p) for p in OLL.iterdir() if p.is_file() and p.suffix!='.tgz'},'environment':{k:v for k,v in env_ollama().items() if k.startswith('OLLAMA_')},'cache_policy':'native default; prefix reuse not disabled; observed logs archived'},'direct':json.loads((RAW/'baseline-runtime-manifest.json').read_text()),'model_sha256':SHA,'context_tokens':8192,'slots':1,'reasoning':'enabled; Ollama low for boolean model, direct enable_thinking true; no budget128','comparison':'different engine commits/templates/cache policy; pure overhead unavailable'}
 assert digest(DIRECT)=='916660e9bfe7f4d2fda420136f6bd192688def8cbd6581f23d08b06ead2e571f'
 write('runtime-manifest.json',runtime);write('preflight-execution.json',{'accepted':True,'time':now(),'gguf_sha256':SHA,'runtime':'raw/runtime-manifest.json'})
 result('preflight',True)
 inventory={'timestamp':now(),'lms_cli':subprocess.run(['zsh','-c','command -v lms'],capture_output=True,text=True).stdout.strip(),'paths':{p:pathlib.Path(p).exists() for p in ['/Applications/LM Studio.app',str(pathlib.Path.home()/'Applications/LM Studio.app'),str(pathlib.Path.home()/'.lmstudio/bin/lms')]}}
 write('lm-studio-inventory.json',inventory)
 assert not inventory['lms_cli'] and not any(inventory['paths'].values()),'LM Studio inventory changed'
 for kind in ['metal','mlx']:
  case='lm-studio-'+kind;write(case+'-blocker.json',{'available':False,'reason':'LM Studio app/CLI/runtime отсутствуют в проверенных местах; version/backend/API не измерены.','inventory':'raw/lm-studio-inventory.json'});result(case,False,'Приложение, CLI и runtime отсутствуют; evidence blocker.')
 valid={'role':'assistant','content':'','tool_calls':[{'id':'call_alpha','type':'function','function':{'name':'lookup_lab_value','arguments':'{"key":"alpha"}'}}]}
 results=[]
 import copy
 for label in ['valid','unknown-name','wrong-key','missing-id']:
  v=copy.deepcopy(valid)
  if label=='unknown-name':v['tool_calls'][0]['function']['name']='execute_shell'
  if label=='wrong-key':v['tool_calls'][0]['function']['arguments']='{"key":"beta"}'
  if label=='missing-id':v['tool_calls'][0]['id']=''
  write('offline-validator-'+label+'.json',v);prefix=RAW/('offline-validator-'+label)
  p=subprocess.run([sys.executable,str(RAW/'http_probe.py'),'--validate-tool-message',str(prefix)+'.json','--out',str(prefix)],capture_output=True,text=True)
  assert p.returncode==(0 if label=='valid' else 1);results.append({'case':label,'exit_code':p.returncode})
 write('offline-validator-results.json',{'evidence_class':'synthetic','model_executed':False,'results':results});result('offline-validator',True)
class Server:
 def __init__(self,dep):
  self.dep=dep;self.url='http://127.0.0.1:'+('11434' if dep=='ollama' else '8080');self.stop=threading.Event();self.guard=None
  with socket.socket() as s:s.bind(('127.0.0.1',11434 if dep=='ollama' else 8080))
  assert safe(sample())
  command=[str(OLL/'ollama'),'serve'] if dep=='ollama' else [str(DIRECT),'-m',str(MODEL),'--host','127.0.0.1','--port','8080','--alias',ALIAS,'-ngl','999','-c','8192','-np','1','-t','8','-b','512','-ub','256','-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto','--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots','--metrics']
  self.log=RAW/(dep+'-server.txt');self.handle=self.log.open('x');self.record={'command':command,'started_at':now(),'resources_before':sample(),'pid':None,'returncode':None}
  env=env_ollama() if dep=='ollama' else {k:v for k,v in os.environ.items() if k in ['HOME','PATH','TMPDIR','USER','LOGNAME','LANG','LC_ALL']}
  self.process=subprocess.Popen(command,stdout=self.handle,stderr=subprocess.STDOUT,env=env,start_new_session=True);self.record['pid']=self.process.pid;write(dep+'-server-execution.json',self.record)
  self.monitor=threading.Thread(target=self.observe,daemon=True);self.monitor.start()
 def observe(self):
  with (RAW/(self.dep+'-memory.jsonl')).open('x') as f:
   while not self.stop.is_set():
    row=sample();table=subprocess.run(['ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True).stdout
    processes=[tuple(map(int,line.split())) for line in table.splitlines() if len(line.split())==3];owned={self.process.pid}
    for _ in range(10):
     new=owned|{pid for pid,ppid,rss in processes if ppid in owned}
     if new==owned:break
     owned=new
    observed=[{'pid':pid,'rss_bytes':rss*1024} for pid,ppid,rss in processes if pid in owned]
    row.update(processes=observed,aggregate_rss_bytes=sum(p['rss_bytes'] for p in observed) if observed else None)
    f.write(json.dumps(row)+'\n');f.flush()
    if not safe(row) or (row['aggregate_rss_bytes'] or 0)>24*2**30:
     self.guard='Memory/power guard failed'
     if self.process.poll() is None:os.killpg(self.process.pid,signal.SIGTERM)
     return
    self.stop.wait(2)
 def ensure(self):
  if self.guard or self.process.poll() is not None:raise RuntimeError(self.guard or 'Owned server exited')
 def ready(self):
  case=self.dep+'-startup'
  for _ in range(120):
   self.ensure()
   try:health=api(self.url,'/api/version' if self.dep=='ollama' else '/health',timeout=2);break
   except Exception:time.sleep(1)
  else:raise RuntimeError('Startup timeout')
  write(case+'-health.json',health)
  if self.dep=='ollama':
   assert health['body']['version']=='0.40.1'
   p=subprocess.run([str(OLL/'ollama'),'create',ALIAS,'-f',str(RAW/'Modelfile')],capture_output=True,text=True,env=env_ollama(),timeout=180)
   (RAW/(case+'-import.txt')).write_text(p.stdout+p.stderr);assert p.returncode==0,'Import failed'
   show=api(self.url,'/api/show',{'model':ALIAS,'verbose':True});write(case+'-show.json',show)
   write(case+'-models.json',api(self.url,'/v1/models'))
   blobs=[]
   for path in (OLL/'models/manifests').rglob('*'):
    if path.is_file():
     content=json.loads(path.read_text());write(case+'-import-manifest.json',{'path':str(path),'body':content})
     for layer in content['layers']:
      if layer['mediaType']=='application/vnd.ollama.image.model':
       blob=OLL/'models/blobs'/layer['digest'].replace(':','-');blobs.append({'path':str(blob),'sha256':digest(blob),'bytes':blob.stat().st_size})
   assert len(blobs)==1 and blobs[0]['sha256']==SHA and digest(MODEL)==SHA
   write(case+'-weights.json',{'source_sha256':SHA,'imported_model_blobs':blobs,'source_after_import_sha256':digest(MODEL)})
  else:
   for name,route in [('props','/props'),('slots','/slots'),('models','/v1/models')]:write(case+'-'+name+'.json',api(self.url,route))
   props=json.loads((RAW/(case+'-props.json')).read_text())['body'];assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==8192
   assert 'offloaded 33/33 layers to GPU' in self.log.read_text()
  write(case+'-execution.json',{'accepted':True,'timestamp':now(),'note':'Ollama model load occurs on first warmup; backend proof checked before next repeat.'})
  result(case,True)
 def shutdown(self):
  error=None
  if self.dep=='ollama' and self.process.poll() is None:
   try:write('ollama-shutdown-unload.json',api(self.url,'/api/generate',{'model':ALIAS,'keep_alive':0,'stream':False},timeout=60));write('ollama-shutdown-models.json',api(self.url,'/api/ps'))
   except Exception as e:error=str(e)
  if self.process.poll() is None:
   os.killpg(self.process.pid,signal.SIGINT)
   try:self.process.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait();error='Shutdown timeout'
  self.stop.set();self.monitor.join(timeout=15);self.handle.close();self.record.update(ended_at=now(),returncode=self.process.returncode,guard_reason=self.guard,resources_after=sample(),error=error)
  write(self.dep+'-server-execution.json',self.record);write(self.dep+'-shutdown-execution.json',self.record)
  ok=self.process.returncode==0 and not self.guard and not error;result(self.dep+'-shutdown',ok,error or self.guard or (None if ok else 'Native shutdown nonzero'))
def probe(server,case,kind):
 server.ensure();payload=json.loads((RAW/(kind+'-request.json')).read_text())
 if server.dep=='direct':payload.pop('reasoning_effort');payload.update(cache_prompt=False,chat_template_kwargs={'enable_thinking':True})
 fixture=RAW/(case+'-input.json');write(fixture.name,payload)
 command=[sys.executable,str(RAW/'http_probe.py'),'--url',server.url,'--request',str(fixture),'--out',str(RAW/case)]
 if kind.startswith('tool'):command.append('--follow-tool')
 offset=server.log.stat().st_size;before=sample();start=time.monotonic();reason=None;metrics=None;follow=None
 env={**os.environ,'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
 try:
  with (RAW/(case+'-probe.txt')).open('x') as f:p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=180)
  assert p.returncode==0,'Probe failed'
  final=json.loads((RAW/(case+'.final.json')).read_text());metrics=json.loads((RAW/(case+'.metrics.json')).read_text());expected='LAB_VALUE_42' if kind.startswith('tool') else 'LAB_READY'
  assert final['content'].strip()==expected and not final.get('tool_calls'),'Final marker/tool mismatch'
  assert metrics['http_status']==200 and metrics['usage']['prompt_tokens']>0
  if kind.startswith('tool'):
   follow=json.loads((RAW/(case+'.followup.metrics.json')).read_text());assert metrics['finish_reason']=='tool_calls' and follow['finish_reason']=='stop' and follow['usage']['prompt_tokens']>0 and follow['http_status']==200
  else:assert metrics['finish_reason']=='stop'
  if payload['stream']:assert metrics['stream_done'] and (not follow or follow['stream_done'])
  if server.dep=='ollama':
   ps=api(server.url,'/api/ps');write(case+'-loaded.json',ps)
   loaded=ps['body']['models'];assert len(loaded)==1 and loaded[0]['context_length']==8192 and loaded[0]['size_vram']>0
   log=server.log.read_text();assert 'Metal' in log and 'Apple M5 Max' in log,'Metal device not proven'
  assert safe(before) and safe(sample());server.ensure()
 except Exception as e:reason=str(e) or type(e).__name__
 (RAW/(case+'-server-fragment.txt')).write_bytes(server.log.read_bytes()[offset:])
 write(case+'-execution.json',{'command':command,'timestamp':now(),'accepted':reason is None,'reason':reason,'wall_seconds':time.monotonic()-start,'metrics':metrics,'followup_metrics':follow,'before':before,'after':sample()});result(case,reason is None,reason)
 if reason:raise RuntimeError(case+': '+reason)
def cancel(server):
 case='ollama-cancel';payload=json.loads((RAW/'chat-stream-request.json').read_text());payload['messages']=[{'role':'user','content':''.join('Нейтральная строка %d.\n'%i for i in range(350))+'Пиши целые числа от 1 до 10000, не останавливайся.'}];write(case+'-request.json',payload)
 write(case+'-loaded-before.json',api(server.url,'/api/ps'));offset=server.log.stat().st_size;start=time.monotonic()
 command=['curl','--noproxy','*','--max-time','1','-sS','-N',server.url+'/v1/chat/completions','-H','Content-Type: application/json','--data-binary','@'+str(RAW/(case+'-request.json'))]
 with (RAW/(case+'.sse')).open('xb') as out,(RAW/(case+'-curl.txt')).open('x') as err:p=subprocess.run(command,stdout=out,stderr=err,timeout=10)
 ended=time.monotonic();time.sleep(2);fragment=server.log.read_bytes()[offset:];(RAW/(case+'-server-fragment.txt')).write_bytes(fragment)
 ok=p.returncode==28 and b'[DONE]' not in (RAW/(case+'.sse')).read_bytes() and bool(re.search(rb'cancel|disconnect',fragment,re.I))
 write(case+'-execution.json',{'timestamp':now(),'command':command,'exit_code':p.returncode,'duration_s':ended-start,'done_received':b'[DONE]' in (RAW/(case+'.sse')).read_bytes(),'cancellation_log':bool(re.search(rb'cancel|disconnect',fragment,re.I)),'gpu_slot_release_seconds':None,'gpu_slot_release_unavailable':'Ollama API не предоставляет проверенного slot monitor; cancellation log не измеряет освобождение GPU.','accepted':ok});result(case,ok,None if ok else 'Client cancellation/native cancellation log not jointly proven')
 recovery_start=time.monotonic();probe(server,'ollama-cancel-recovery','chat');elapsed=time.monotonic()-ended;write('ollama-cancel-recovery-window.json',{'within_60_seconds':elapsed<=60,'client_exit_to_recovery_end_seconds':elapsed,'recovery_probe_seconds':time.monotonic()-recovery_start,'same_owned_server_pid':server.process.pid});assert elapsed<=60,'Recovery window exceeded'
 if not ok:raise RuntimeError('Cancellation inconclusive; recovery preserved')
def deployment(dep):
 server=None
 try:
  server=Server(dep);server.ready()
  for kind in ['chat','chat-stream','tool','tool-stream']:
   for repeat in ['warmup','r1','r2','r3']:probe(server,dep+'-'+kind+'-'+repeat,kind)
  if dep=='ollama':cancel(server)
 except Exception as e:
  write(dep+'-fatal.json',{'timestamp':now(),'reason':str(e)});print(dep+' STOP: '+str(e),flush=True)
  m=json.loads(MANIFEST.read_text())
  for a in m['planned_attempts']:
   if a['status']=='planned' and a['id'].startswith(dep+'-') and a['id']!=dep+'-shutdown':a.update(status='not-run',reason='Stopped deployment: '+str(e),evidence_files=['raw/'+dep+'-fatal.json'])
  MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 finally:
  if server:server.shutdown()
if __name__=='__main__':
 if sys.argv[1]=='preflight':preflight()
 else:deployment(sys.argv[1])
