# -*- coding: utf-8 -*-
"""LM Studio native defaults: separate GGUF / MLX deployment conditions."""
import os,pathlib,json,subprocess,threading,time,sys,socket,copy
import lab33_runner as lab
RAW=lab.RAW
MLX=pathlib.Path('/Users/lab/local-model-lab-artifacts/mlx-community/Qwen3.5-9B-MLX-4bit/938d8919941c6e7efd3c7150eff7fe9d12afa631')
class AppProcess:
 def __init__(self,pid):self.pid=pid
 def poll(self):
  try:os.kill(self.pid,0);return None
  except ProcessLookupError:return 1
class LMS:
 def __init__(self,dep):
  self.dep=dep;self.url='http://127.0.0.1:1234';self.guard=None;self.stop=threading.Event();self.loaded=False;self.server_started=False
  assert lab.safe(lab.sample())
  assert json.loads(subprocess.check_output(['lms','ps','--json'],text=True))==[],'Other model loaded'
  with socket.socket() as s:s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',1234))
  processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines();pids=[int(line.split()[0]) for line in processes if line.strip().split(None,1)[-1] in ['/Applications/LM Studio.app/Contents/MacOS/LM Studio','/Applications/LM Studio.app/Contents/MacOS/LM Studio --run-as-service']];assert len(pids)==1
  self.process=AppProcess(pids[0]);self.log=RAW/(dep+'-server.txt');self.handle=self.log.open('x')
  self.logger=subprocess.Popen(['lms','log','stream','--source','runtime','--json'],stdout=self.handle,stderr=subprocess.STDOUT,start_new_session=True)
  self.monitor=threading.Thread(target=self.observe,daemon=True);self.monitor.start()
  self.record={'started_at':lab.now(),'app_pid':self.process.pid,'runtime_log_command':['lms','log','stream','--source','runtime','--json'],'resources_before':lab.sample(),'commands':[]}
 def observe(self):
  with (RAW/(self.dep+'-memory.jsonl')).open('x') as f:
   while not self.stop.is_set():
    row=lab.sample();rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True).splitlines()
    table=[tuple(map(int,line.split())) for line in rows if len(line.split())==3];owned={self.process.pid}
    for _ in range(10):
     updated=owned|{pid for pid,ppid,rss in table if ppid in owned}
     if updated==owned:break
     owned=updated
    row['processes']=[{'pid':pid,'rss_bytes':rss*1024} for pid,ppid,rss in table if pid in owned]
    row['aggregate_rss_bytes']=sum(p['rss_bytes'] for p in row['processes']) if row['processes'] else None
    row['app_alive']=self.process.poll() is None
    f.write(json.dumps(row)+'\n');f.flush()
    if not lab.safe(row) or (row['aggregate_rss_bytes'] or 0)>24*2**30:
     self.guard='Memory/power guard failed; own alias will be unloaded, application is not killed'
     if self.loaded:
      subprocess.run(['lms','unload',lab.ALIAS],capture_output=True,timeout=30)
     return
    self.stop.wait(2)
 def ensure(self):
  if self.guard or self.process.poll() is not None:raise RuntimeError(self.guard or 'App exited')
 def cli(self,args,label,timeout=120):
  command=['lms']+args;p=subprocess.run(command,capture_output=True,text=True,timeout=timeout);(RAW/(self.dep+'-'+label+'.txt')).write_text(p.stdout+p.stderr);self.record['commands'].append({'command':command,'returncode':p.returncode,'evidence':'raw/'+self.dep+'-'+label+'.txt'});assert p.returncode==0,label+' failed';return p.stdout
 def ready(self):
  case=self.dep+'-startup';backend_name='llama.cpp-mac-arm64-apple-metal-advsimd-2.54.0' if self.dep=='lms-metal' else 'mlx-llm-mac-arm64-apple-metal-nax-advsimd-1.13.1'
  backend=pathlib.Path.home()/'.lmstudio/extensions/backends'/backend_name;assert backend.is_dir()
  runtime={'path':str(backend),'manifest':json.loads((backend/'backend-manifest.json').read_text()),'files':{str(p.relative_to(backend)):lab.digest(p) for p in backend.rglob('*') if p.is_file()},'selected_inventory':self.cli(['runtime','ls'],'startup-runtimes'),'reasoning':'native default; requested effort omitted as unsupported/unverified','kv_cache_dtype':None,'cache_policy':None,'unavailable':'CLI does not pin all KV/cache/default-reasoning parameters; actual logs retained'};lab.write(case+'-runtime.json',runtime)
  if self.dep=='lms-metal':
   self.cli(['import',str(lab.MODEL),'--symbolic-link','--user-repo','unsloth/Qwen3.5-9B-GGUF','--yes'],'startup-import')
   assert lab.digest(lab.MODEL)==lab.SHA
  else:
   artifact=next(a for a in json.loads((RAW/'mlx-artifact-manifest.json').read_text())['artifacts'] if a['format']=='MLX/safetensors');verified=[]
   for entry in artifact['files']:
    p=pathlib.Path(entry['local_path']);assert lab.digest(p)==entry['sha256'];verified.append({'path':str(p),'sha256':entry['sha256'],'bytes':p.stat().st_size})
   target=pathlib.Path.home()/'.lmstudio/models/mlx-community/Qwen3.5-9B-MLX-4bit';target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists():target.symlink_to(MLX,target_is_directory=True)
   assert target.resolve()==MLX;lab.write(case+'-weights.json',{'revision':artifact['revision'],'files':verified,'registry_symlink':str(target),'quantization':artifact['quantization']})
  models=json.loads(self.cli(['ls','--json'],'startup-models'));format='gguf' if self.dep=='lms-metal' else 'safetensors';matches=[m for m in models if m.get('format')==format and 'Qwen3.5-9B' in m.get('path','')];assert len(matches)==1,repr(matches)
  model=matches[0];lab.write(case+'-selected-model.json',model)
  if self.dep=='lms-metal':
   imported=pathlib.Path.home()/'.lmstudio/models'/model['path'];assert lab.digest(imported)==lab.SHA;lab.write(case+'-weights.json',{'source_sha256':lab.digest(lab.MODEL),'imported_sha256':lab.digest(imported),'imported_path':str(imported),'symlink_target':str(imported.resolve())})
  self.cli(['load',model['modelKey'],'--identifier',lab.ALIAS,'--context-length','8192','--parallel','1','--gpu','max','--ttl','600','--yes'],'startup-load');self.loaded=True
  loaded=json.loads(self.cli(['ps','--json'],'startup-loaded'));assert len(loaded)==1 and loaded[0]['format']==format and loaded[0]['path']==model['path'] and loaded[0]['contextLength']==8192 and loaded[0]['parallel']==1,'Loaded deployment differs from registered artifact/config'
  self.cli(['server','start','--port','1234','--bind','127.0.0.1'],'startup-server');self.server_started=True
  for label,route in [('models','/v1/models'),('native-models','/api/v0/models')]:lab.write(case+'-'+label+'.json',lab.api(self.url,route))
  lab.write(case+'-execution.json',{'accepted':True,'timestamp':lab.now(),'app_pid':self.process.pid,'model':model,'loaded':loaded,'engine_package':backend_name,'runtime':'raw/'+case+'-runtime.json','backend_evidence_pending':'Actual load/inference logs archived; GPU proof assessed after cases.'});lab.result(case,True)
 def shutdown(self):
  error=None
  try:
   if self.loaded:self.cli(['unload',lab.ALIAS],'shutdown-unload')
   if self.server_started:self.cli(['server','stop'],'shutdown-server')
  except Exception as e:error=str(e)
  self.stop.set();self.monitor.join(timeout=15)
  if self.logger.poll() is None:
   self.logger.terminate()
   try:self.logger.wait(timeout=10)
   except subprocess.TimeoutExpired:self.logger.kill();self.logger.wait()
  self.handle.close();self.record.update(ended_at=lab.now(),error=error,guard_reason=self.guard,resources_after=lab.sample(),models_after=json.loads(subprocess.check_output(['lms','ps','--json'],text=True)));lab.write(self.dep+'-shutdown-execution.json',self.record)
  ok=not error and not self.guard and not self.record['models_after'];lab.result(self.dep+'-shutdown',ok,error or self.guard or (None if ok else 'Model unload unconfirmed'))
def cancel(s):
 case=s.dep+'-cancel';payload=json.loads((RAW/'chat-stream-request.json').read_text());payload.pop('reasoning_effort',None);payload['messages']=[{'role':'user','content':''.join('Нейтральная строка %d.\n'%i for i in range(350))+'Пиши целые числа от1 до10000, не останавливайся.'}];lab.write(case+'-request.json',payload);offset=s.log.stat().st_size;command=['curl','--noproxy','*','--max-time','1','-sS','-N',s.url+'/v1/chat/completions','-H','Content-Type: application/json','--data-binary','@'+str(RAW/(case+'-request.json'))];start=time.monotonic()
 with (RAW/(case+'.sse')).open('xb') as out,(RAW/(case+'-curl.txt')).open('x') as err:p=subprocess.run(command,stdout=out,stderr=err,timeout=10)
 ended=time.monotonic();time.sleep(2);fragment=s.log.read_bytes()[offset:];(RAW/(case+'-server-fragment.txt')).write_bytes(fragment)
 import re
 logged=bool(re.search(rb'cancel|disconnect|abort',fragment,re.I));ok=p.returncode==28 and b'[DONE]' not in (RAW/(case+'.sse')).read_bytes() and logged
 lab.write(case+'-execution.json',{'timestamp':lab.now(),'command':command,'exit_code':p.returncode,'duration_s':ended-start,'done_received':b'[DONE]' in (RAW/(case+'.sse')).read_bytes(),'cancellation_log':logged,'gpu_slot_release_seconds':None,'gpu_slot_release_unavailable':'No verified native slot monitor in app API','accepted':ok});lab.result(case,ok,None if ok else 'Client cancellation/native cancellation log not jointly proven')
 lab.probe(s,s.dep+'-cancel-recovery','chat');elapsed=time.monotonic()-ended;lab.write(s.dep+'-cancel-recovery-window.json',{'within_60_seconds':elapsed<=60,'client_exit_to_recovery_end_seconds':elapsed,'same_app_pid':s.process.pid});assert elapsed<=60,'Recovery window exceeded'
 if not ok:raise RuntimeError('Cancellation inconclusive; recovery preserved')
def main(dep):
 lab.ALIAS='lab-lifecycle-qwen35-mlx' if dep=='lms-mlx' else 'lab-lifecycle-qwen35-gguf'
 if dep=='lms-mlx':
  import re
  base_sample=lab.sample
  def cache_sample():
   row=base_sample();vm=row['commands']['vm_stat']['stdout'];page=re.search(r'page size of (\d+) bytes',vm);spec=re.search(r'Pages speculative:\s+(\d+)',vm);pressure=re.search(r'free percentage: (\d+)%',row['commands']['pressure']['stdout'])
   row['speculative_pages_bytes']=int(page[1])*int(spec[1]) if page and spec else None
   row['free_speculative_bytes']=row['free_pages_bytes']+row['speculative_pages_bytes'] if row['free_pages_bytes'] is not None and row['speculative_pages_bytes'] is not None else None
   row['pressure_free_percentage']=int(pressure[1]) if pressure else None;row['resource_condition']='free+speculative>=16GiB;pressure-free>=50%;swap0;AC/powermode0;app treeRSS<=24GiB'
   return row
  def cache_safe(row):return row['free_speculative_bytes'] is not None and row['free_speculative_bytes']>=16*2**30 and row['pressure_free_percentage'] is not None and row['pressure_free_percentage']>=50 and row['swap_used_bytes']==0 and row['on_ac_power'] and row['ac_power_mode']==0
  lab.sample=cache_sample;lab.safe=cache_safe
 s=None
 try:
  s=LMS(dep);s.ready()
  for kind in ['chat','chat-stream','tool','tool-stream']:
   for rep in ['warmup','r1','r2','r3']:lab.probe(s,dep+'-'+kind+'-'+rep,kind)
  cancel(s)
 except Exception as e:
  reason=str(e) or type(e).__name__;lab.write(dep+'-fatal.json',{'timestamp':lab.now(),'reason':reason});print(dep+' STOP '+reason,flush=True);m=json.loads(lab.MANIFEST.read_text())
  for a in m['planned_attempts']:
   if a['id'].startswith(dep+'-') and a['status']=='planned' and a['id']!=dep+'-shutdown':a.update(status='failed' if a['id']==dep+'-startup' else 'not-run',reason='Stopped deployment: '+reason,evidence_files=['raw/'+dep+'-fatal.json'])
  lab.MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 finally:
  if s:s.shutdown()
if __name__=='__main__':main(sys.argv[1])
