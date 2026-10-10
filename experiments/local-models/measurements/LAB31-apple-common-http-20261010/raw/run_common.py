"""One native deployment at a time; identical public inputs and HTTP sampling."""
import datetime,hashlib,json,os,pathlib,re,signal,socket,subprocess,sys,threading,time,urllib.request
raw=pathlib.Path(__file__).resolve().parent;root=raw.parents[4];sys.path.insert(0,str(root/'experiments/common'));from local_resources import sample,safe
sys.path.insert(0,str(root/'experiments/local-models/apple'));from artifacts import select_artifact,missing_artifact_pins
runtime=json.loads((raw/'runtime-manifest.json').read_text());gguf=json.loads((raw/'gguf-reference.json').read_text());pins=json.loads((raw/'prestart-pins.json').read_text());artifact=select_artifact(json.loads((raw/'artifact-manifest.json').read_text()),format='MLX/safetensors',repository='mlx-community/Qwen3.5-9B-MLX-4bit',revision=runtime['model_revision']);assert not missing_artifact_pins(artifact,pins)
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','USER','LANG'] if k in os.environ};env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',no_proxy='127.0.0.1,localhost,::1',PYTHONDONTWRITEBYTECODE='1');opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));base='http://127.0.0.1:18080'
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def digest(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for c in iter(lambda:f.read(2**20),b''):h.update(c)
 return h.hexdigest()
def api(url):
 with opener.open(url,timeout=5) as response:return json.load(response)
def foreign():return json.loads(subprocess.check_output(['/opt/homebrew/bin/lms','ps','--json'],text=True,timeout=10)) or api('http://127.0.0.1:11434/api/ps')['models']
def update(id,status,reason=None,evidence=()):
 m=json.loads((raw.parent/'manifest.json').read_text());a=next(a for a in m['planned_attempts'] if a['id']==id);a.update(status=status,reason=reason,evidence_files=list(evidence));save(raw.parent/'manifest.json',m)
class Deployment:
 def __init__(self,id):
  self.id=id;self.folder=raw/id;self.folder.mkdir();(self.folder/'phase.txt').write_text('startup');self.process=None;self.client=None;self.assertion=None;self.monitor=None;self.stop=threading.Event();self.lock=threading.Lock();self.sigints=0;self.guard=None;self.last=time.time();self.started=self.last;self.record=dict(started_at=stamp(),deployment=id,accepted=False)
 def interrupt(self):
  with self.lock:
   if self.process and self.process.poll() is None and not self.sigints:
    self.sigints=1;os.killpg(self.process.pid,signal.SIGINT)
 def check(self):
  wall=time.time()
  assert not self.guard and self.process.poll() is None,self.guard or 'Native process exited'
  assert wall>=self.last and wall-self.last<=15 and wall-self.started<=900,'Stale resource/wall deadline'
 def resources(self):
  count=0
  with (self.folder/'memory.jsonl').open('x') as out:
   while not self.stop.wait(2):
    row=None
    try:
     self.check();row=sample();rss=subprocess.check_output(['ps','-o','rss=','-p',str(self.process.pid)],text=True,timeout=5).strip();assert rss.isdigit() and int(rss)>0,'Owned RSS unavailable';row['server_rss_bytes']=int(rss)*1024;out.write(json.dumps(row)+'\n');out.flush();self.last=time.time();assert safe(row) and row['server_rss_bytes']<=24*2**30,'Memory/power guard';assert self.assertion.poll() is None,'Idle-sleep assertion exited'
     if count%10==0:assert not foreign(),'Foreign model appeared'
     count+=1
    except Exception as e:self.guard=str(e) or type(e).__name__;save(self.folder/'guard.json',dict(reason=self.guard,sample=row,timestamp=stamp()));self.interrupt();return
 def startup(self):
  host=dict(macos=subprocess.check_output(['sw_vers','-productVersion'],text=True).strip(),build=subprocess.check_output(['sw_vers','-buildVersion'],text=True).strip(),ram_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),architecture=subprocess.check_output(['uname','-m'],text=True).strip());save(self.folder/'host-before.json',host);assert host==dict(macos='26.5',build='25F71',ram_bytes=128*2**30,architecture='arm64'),'Host differs from registered condition'
  r=sample();save(self.folder/'admission.json',r);assert safe(r) and not foreign(),'Memory/foreign model admission failed'
  with socket.socket() as probe:probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',18080));probe.listen(1)
  selected=pins['files'] if self.id=='mlx' else [*gguf['engine']['files'],*gguf['model']['files'],gguf['hardware']['passport']]
  if self.id=='gguf':assert all(str(p) in {v['path'] for v in gguf['engine']['files']} for p in pathlib.Path(gguf['engine']['executable']).parent.glob('*.dylib')),'Unpinned bundled dylib'
  for pin in selected:assert pathlib.Path(pin['path']).stat().st_size==pin['bytes'] and digest(pin['path'])==pin['sha256'],'Pin changed'
  after=sample();save(self.folder/'admission-after-pins.json',after);assert safe(after) and not foreign(),'Admission changed during hashing'
  if self.id=='gguf':
   self.alias='lab-common-qwen35';command=[gguf['engine']['executable'],'-m',gguf['model']['files'][0]['path'],'--host','127.0.0.1','--port','18080','--alias',self.alias,'-ngl','999','-c','8192','-np','1','-t','8','-b','512','-ub','256','-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto','--chat-template-kwargs','{"enable_thinking":false}','--no-cache-prompt','--cache-ram','0','--slots']
  else:
   self.alias=runtime['model_path'];command=[runtime['pins']['environment']+'/bin/python','-B',str(raw/'server_entry.py'),'8192','--model',self.alias,'--host','127.0.0.1','--port','18080','--max-tokens','256','--temp','0','--top-p','1','--chat-template-args','{"enable_thinking":false}','--decode-concurrency','1','--prompt-concurrency','1','--prompt-cache-size','0','--prefill-step-size','2048']
  self.record.update(command=command,pins=selected,verified_before_popen=True,verified_at=stamp(),popen_invoked_at=stamp())
  begin=time.perf_counter()
  with (self.folder/'server.txt').open('x') as out:self.process=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
  self.assertion=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);self.record.update(pid=self.process.pid,assertion_pid=self.assertion.pid);self.last=time.time();self.started=self.last;self.monitor=threading.Thread(target=self.resources,daemon=True);self.monitor.start()
  for _ in range(120):
   self.check()
   try:
    models=api(base+'/v1/models')
    if any(x['id']==self.alias for x in models['data']):save(self.folder/'models.json',models);break
   except (OSError,ValueError):pass
   time.sleep(1)
  else:raise RuntimeError('Readiness deadline')
  self.record['cold_ready_seconds']=time.perf_counter()-begin
  if self.id=='gguf':
   props=api(base+'/props');slots=api(base+'/slots');save(self.folder/'props.json',props);save(self.folder/'slots.json',slots);assert props['total_slots']==1 and len(slots)==1 and slots[0]['n_ctx']==8192;assert hashlib.sha256(props['chat_template'].encode()).hexdigest()==gguf['model']['chat_template_sha256'];text=(self.folder/'server.txt').read_text();assert 'offloaded 33/33 layers to GPU' in text and 'Apple M5 Max' in text and re.search(r'has tensor\s*=\s*true',text)
  save(self.folder/'execution.json',self.record);update(self.id+'-startup','completed',evidence=[str((self.folder/'execution.json').relative_to(raw.parent))])
 def probe(self,input,repeat):
  self.check();id=self.id+'-'+input['id']+'-'+repeat;(self.folder/'phase.txt').write_text(id);prefix=self.folder/(input['id']+'-'+repeat);request=dict(model=self.alias,messages=input['messages'],max_tokens=256,temperature=0,seed=1,top_p=1,stream=True,stream_options=dict(include_usage=True));save(pathlib.Path(str(prefix)+'.input.json'),request)
  with pathlib.Path(str(prefix)+'.driver.txt').open('x') as out:
   self.client=subprocess.Popen([sys.executable,'-B',str(raw/'http_probe.py'),'--url',base,'--request',str(prefix)+'.input.json','--out',str(prefix)],env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
   try:code=self.client.wait(timeout=120)
   except subprocess.TimeoutExpired:
    os.killpg(self.client.pid,signal.SIGINT)
    try:self.client.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(self.client.pid,signal.SIGKILL);self.client.wait()
    raise
   finally:self.client=None
  self.check();assert code==0,'HTTP probe failed';final=json.loads(pathlib.Path(str(prefix)+'.final.json').read_text());metric=json.loads(pathlib.Path(str(prefix)+'.metrics.json').read_text());assert final['content']==input['expected'],'Exact final mismatch: '+repr(final['content']);assert metric['http_status']==200 and metric['stream_done'] and metric['finish_reason']=='stop' and metric['usage'] is not None,'Missing complete primary response';update(id,'completed',evidence=[str(pathlib.Path(str(prefix)+'.metrics.json').relative_to(raw.parent)),str(pathlib.Path(str(prefix)+'.final.json').relative_to(raw.parent))]);print(id+' passed',flush=True)
 def close(self):
  self.stop.set()
  if self.monitor:self.monitor.join(timeout=20)
  self.interrupt()
  if self.process:
   try:self.process.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait();self.guard=self.guard or 'Shutdown deadline'
  if self.assertion:self.assertion.terminate();self.assertion.wait(timeout=5)
  ok=self.process is not None and self.process.returncode==0 and self.sigints==1 and not self.guard;self.record.update(ended_at=stamp(),returncode=self.process.returncode if self.process else None,sigint_count=self.sigints,guard=self.guard,memory_after=sample());save(self.folder/'execution.json',self.record);update(self.id+'-cleanup','not-run' if self.process is None else 'completed' if ok else 'failed','No native process' if self.process is None else None if ok else 'Cleanup/guard failed',evidence=[str((self.folder/'execution.json').relative_to(raw.parent))]);return ok
failure=None
for id in ('gguf','mlx'):
 dep=Deployment(id);current=id+'-startup'
 try:
  dep.startup()
  for input in json.loads((raw/'shared-inputs.json').read_text()):
   for repeat in ('warmup','1','2','3'):current=id+'-'+input['id']+'-'+repeat;dep.probe(input,repeat)
 except BaseException as e:failure=str(e) or type(e).__name__;dep.record['error']=failure;save(dep.folder/'error.json',dict(case=current,reason=failure,timestamp=stamp()));update(current,'failed',failure,evidence=[str((dep.folder/'error.json').relative_to(raw.parent))])
 finally:
  ok=dep.close()
  if dep.process and not ok:failure=failure or 'Cleanup/guard failure'
 if failure:break
m=json.loads((raw.parent/'manifest.json').read_text())
for a in m['planned_attempts']:
 if a['status']=='planned':a.update(status='not-run',reason=failure or 'No execution evidence',evidence_files=[])
m.update(status='blocked' if failure else 'completed',conclusion='Common HTTP deployment comparison '+('stopped: '+failure if failure else 'completed; difference applies to whole quantized deployments.'))
if failure:m['unavailable']['completion']=failure
m['evidence_files']=sorted(str(f.relative_to(raw.parent)) for f in raw.rglob('*') if f.is_file());save(raw.parent/'manifest.json',m)
