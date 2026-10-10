"""Fixed 8K per actual server slot; all processes and artifact pins owned."""
import datetime,hashlib,json,os,pathlib,re,signal,socket,subprocess,sys,threading,time,urllib.request
raw=pathlib.Path(__file__).resolve().parent;root=raw.parents[4]
sys.path.insert(0,str(root/'experiments/common'));from local_resources import sample
d=json.loads((raw/'deployment-reference.json').read_text());server=d['engine']['executable'];model=d['model']['files'][0]['path'];alias='lab-slot-load-qwen35';base='http://127.0.0.1:18080'
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','USER','LANG'] if k in os.environ};env.update(PYTHONDONTWRITEBYTECODE='1',no_proxy='127.0.0.1,localhost,::1')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def api(route):
 with opener.open(base+route,timeout=3) as response:return json.load(response)
def safe(r,minimum=8):return all(c['returncode']==0 for c in r['commands'].values()) and r['pressure_level']==1 and r['pressure_free_percentage']>=50 and r['free_speculative_bytes']>=minimum*2**30 and r['swap_used_bytes']==0 and r['on_ac_power'] and r['ac_power_mode']==0
def digest(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  for c in iter(lambda:f.read(2**20),b''):h.update(c)
 return h.hexdigest()
def result(id,status,reason=None,evidence=()):
 m=json.loads((raw.parent/'manifest.json').read_text());a=next(a for a in m['planned_attempts'] if a['id']==id);a.update(status=status,reason=reason,evidence_files=list(evidence));m['evidence_files']=sorted(str(f.relative_to(raw.parent)) for f in raw.rglob('*') if f.is_file());save(raw.parent/'manifest.json',m)
def foreign():
 lms=json.loads(subprocess.check_output(['/opt/homebrew/bin/lms','ps','--json'],env=env,text=True,timeout=10))
 with opener.open('http://127.0.0.1:11434/api/ps',timeout=5) as response:ollama=json.load(response)['models']
 return dict(lms=lms,ollama=ollama)

class Campaign:
 def __init__(self,slots):
  self.slots=slots;self.folder=raw/f'slots{slots}';self.folder.mkdir();self.process=None;self.client=None;self.assertion=None;self.monitor=None;self.slot_monitor=None;self.stop=threading.Event();self.signal_lock=threading.Lock();self.guard=None;self.sigint_count=0;self.last=time.time();self.phase='startup';self.phase_max={};self.started=time.time();self.deadline=self.started+900;self.record=dict(started_at=now(),server_slots=slots,context_per_slot=8192,total_context=slots*8192,output_cap=512,error=None)
 def interrupt(self,reason):
  with self.signal_lock:
   if self.process and self.process.poll() is None and self.sigint_count==0:
    self.sigint_count=1;self.record['interrupt']=dict(timestamp=now(),reason=reason,signal='SIGINT');os.killpg(self.process.pid,signal.SIGINT)
 def fail(self,reason,row=None):
  if self.guard is None:self.guard=reason;save(self.folder/'guard.json',dict(timestamp=now(),reason=reason,sample=row))
  self.interrupt('guard')
 def ensure(self):
  wall=time.time()
  if self.guard or self.process.poll() is not None:raise RuntimeError(self.guard or 'Own native process exited')
  if wall<self.last or wall-self.last>15 or wall>self.deadline:raise RuntimeError('Stale resource/absolute wall deadline')
 def memory(self):
  count=0
  with (self.folder/'memory.jsonl').open('x') as out:
   while not self.stop.wait(2):
    row=None
    try:
     wall=time.time()
     if wall<self.last or wall-self.last>15 or wall>self.deadline:raise RuntimeError('Stale/backwards/wall deadline')
     row=sample();self.last=time.time();rss=subprocess.check_output(['ps','-o','rss=','-p',str(self.process.pid)],text=True,timeout=5).strip()
     if not rss.isdigit() or int(rss)<=0:raise RuntimeError('Owned PID RSS unavailable')
     row['server_rss_bytes']=int(rss)*1024;out.write(json.dumps(row)+'\n');out.flush()
     if not safe(row) or row['server_rss_bytes']>24*2**30:raise RuntimeError('Memory/power guard')
     if self.assertion.poll() is not None:raise RuntimeError('Idle-sleep assertion exited')
     if count%10==0 and any(foreign().values()):raise RuntimeError('Foreign model appeared')
     count+=1
    except Exception as error:self.fail(str(error),row);return
 def observe_slots(self):
  with (self.folder/'slots.jsonl').open('x') as out:
   while not self.stop.wait(.05):
    try:
     rows=api('/slots');busy=sum(bool(r['is_processing']) for r in rows);self.phase_max[self.phase]=max(self.phase_max.get(self.phase,0),busy)
     out.write(json.dumps(dict(timestamp=now(),phase=self.phase,busy=busy,slots=rows))+'\n');out.flush()
    except Exception:
     if self.process.poll() is not None or self.guard:return
 def startup(self):
  baseline=sample();other=foreign();save(self.folder/'admission.json',dict(timestamp=now(),minimum_free_spec_gib=24,sample=baseline,foreign=other))
  assert safe(baseline,8) and not any(other.values()),'Baseline running safety/foreign model admission failed'
  with socket.socket() as probe:probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',18080));probe.listen(1)
  pins=[*d['model']['files'],*d['engine']['files'],d['hardware']['passport']]
  listed={p['path'] for p in d['engine']['files']};directory=pathlib.Path(server).parent
  assert all(str(p) in listed for p in directory.glob('*.dylib')),'Unpinned bundled dylib'
  assert d['model']['format']=='GGUF'
  for pin in pins:assert pathlib.Path(pin['path']).stat().st_size==pin['bytes'] and digest(pin['path'])==pin['sha256'],'Pin changed'
  stats={p['path']:(pathlib.Path(p['path']).stat().st_ino,pathlib.Path(p['path']).stat().st_size,pathlib.Path(p['path']).stat().st_mtime_ns) for p in pins}
  start=time.time();stable=None;last=start
  with (self.folder/'admission-window.jsonl').open('x') as out:
   while time.time()-start<600:
    wall=time.time();assert wall>=last and wall-last<=15,'Admission clock gap';last=wall
    after_pins=sample();out.write(json.dumps(after_pins)+'\n');out.flush()
    if safe(after_pins,24):stable=stable or wall
    else:stable=None
    if stable and wall-stable>=120:break
    time.sleep(2)
   else:raise RuntimeError('No stable 24GiB admission within 600 seconds')
  save(self.folder/'admission-after-pins.json',after_pins)
  assert not any(foreign().values()),'Foreign model appeared during admission'
  assert all(stats[p['path']]==(pathlib.Path(p['path']).stat().st_ino,pathlib.Path(p['path']).stat().st_size,pathlib.Path(p['path']).stat().st_mtime_ns) for p in pins),'Pinned file changed during admission'
  self.deadline=time.time()+900
  command=[server,'-m',model,'--host','127.0.0.1','--port','18080','--alias',alias,'-ngl','999','-c',str(self.slots*8192),'-np',str(self.slots),'-t','8','-b','512','-ub','256','-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto','--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--cache-ram','0','--slots','--metrics']
  self.record.update(command=command,verified_before_popen=True,verified_at=now(),popen_invoked_at=now(),pins=pins)
  log=(self.folder/'server.txt').open('x');self.process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True);log.close();self.record['pid']=self.process.pid
  self.assertion=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);self.record['assertion_pid']=self.assertion.pid
  self.last=time.time();self.monitor=threading.Thread(target=self.memory,daemon=True);self.monitor.start();save(self.folder/'execution.json',self.record)
  for _ in range(120):
   self.ensure()
   try:
    if api('/health')['status']=='ok':break
   except OSError:pass
   time.sleep(1)
  else:raise RuntimeError('Native readiness deadline')
  props=api('/props');slots=api('/slots');save(self.folder/'props.json',props);save(self.folder/'startup-slots.json',slots)
  assert props['model_alias']==alias and props['model_path']==model and props['total_slots']==self.slots
  assert len(slots)==self.slots and all(s['n_ctx']==8192 for s in slots),'Actual context per slot differs'
  assert hashlib.sha256(props['chat_template'].encode()).hexdigest()==d['model']['chat_template_sha256']
  text=(self.folder/'server.txt').read_text();assert 'Apple M5 Max' in text and 'offloaded 33/33 layers to GPU' in text and re.search(r'has tensor\s*=\s*true',text)
  self.slot_monitor=threading.Thread(target=self.observe_slots,daemon=True);self.slot_monitor.start();result(f'slots{self.slots}-startup','completed',evidence=[str((self.folder/'props.json').relative_to(raw.parent)),str((self.folder/'execution.json').relative_to(raw.parent))])
 def block(self,label,requests,required_busy):
  self.ensure();assert all(not s['is_processing'] for s in api('/slots')),'Previous requests still processing'
  self.phase=label;directory=self.folder/label
  command=[sys.executable,'-B',str(raw/'concurrency_driver.py'),'--endpoint',base+'/v1/chat/completions','--request',str(raw/'load-request.json'),'--concurrency',str(self.slots),'--requests',str(requests),'--timeout','90','--out',str(directory)]
  with (self.folder/(label.replace('/','-')+'-driver.txt')).open('x') as out:
   self.client=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
   try:code=self.client.wait(timeout=requests*90+30)
   except subprocess.TimeoutExpired:
    os.killpg(self.client.pid,signal.SIGINT)
    try:self.client.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(self.client.pid,signal.SIGKILL);self.client.wait()
    raise
   finally:self.client=None
  summary=json.loads((directory/'summary.json').read_text());self.ensure()
  proof=dict(timestamp=now(),exit_code=code,requests=requests,client_concurrency=self.slots,server_slots=self.slots,max_busy_slots=self.phase_max.get(label,0),summary=str((directory/'summary.json').relative_to(raw.parent)))
  ok=code==0 and summary['failed']==0 and summary['success_latency_p95_seconds']<=90 and proof['max_busy_slots']>=required_busy
  proof['accepted']=ok;save(directory/'slot-proof.json',proof)
  if not ok:raise RuntimeError('Protocol/latency/actual busy slots criterion failed')
  return directory,summary
 def sustained(self):
  self.deadline=time.time()+2100;start=time.time();blocks=[];folder=self.folder/'sustained';folder.mkdir()
  try:
   while time.time()-start<1800:
    label=f'sustained/block-{len(blocks)+1:04d}';directory,summary=self.block(label,12,4);blocks.append(str(directory.relative_to(raw.parent)))
    save(folder/'progress.json',dict(elapsed_seconds=time.time()-start,blocks=blocks,last_summary=summary));print(json.dumps(dict(sustained_seconds=time.time()-start,blocks=len(blocks))),flush=True)
   save(folder/'series.json',dict(accepted=True,planned_seconds=1800,actual_seconds=time.time()-start,blocks=blocks));result('slots4-sustained','completed',evidence=[str((folder/'series.json').relative_to(raw.parent)),str((folder/'progress.json').relative_to(raw.parent))])
  except BaseException as error:
   save(folder/'series.json',dict(accepted=False,planned_seconds=1800,actual_seconds=time.time()-start,blocks=blocks,reason=str(error) or type(error).__name__));raise
 def close(self):
  self.stop.set()
  if self.monitor:self.monitor.join(timeout=20)
  if self.slot_monitor:self.slot_monitor.join(timeout=5)
  if self.client and self.client.poll() is None:
   os.killpg(self.client.pid,signal.SIGINT)
   try:self.client.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(self.client.pid,signal.SIGKILL);self.client.wait()
  if self.process and self.process.poll() is None:
   self.interrupt('normal cleanup')
   try:self.process.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait();self.guard=self.guard or 'Shutdown deadline'
  if self.assertion:self.assertion.terminate();self.assertion.wait(timeout=5)
  self.record.update(ended_at=now(),returncode=self.process.returncode if self.process else None,sigint_count=self.sigint_count,guard=self.guard,memory_after=sample(),max_busy_slots=self.phase_max);save(self.folder/'execution.json',self.record)
  ok=self.process is not None and self.process.returncode==0 and self.sigint_count==1 and not self.guard
  result(f'slots{self.slots}-cleanup','not-run' if self.process is None else 'completed' if ok else 'failed','No native process started' if self.process is None else None if ok else 'Native startup/cleanup/guard failed',evidence=[str((self.folder/'execution.json').relative_to(raw.parent))])

failure=None
for slots in (1,2,4):
 campaign=Campaign(slots);current=f'slots{slots}-startup'
 try:
  campaign.startup()
  for label,requests in [('warmup',slots),('r1',3*slots),('r2',3*slots),('r3',3*slots)]:
   current=f'slots{slots}-{label}';directory,summary=campaign.block(label,requests,slots);result(current,'completed',evidence=[str((directory/'summary.json').relative_to(raw.parent)),str((directory/'slot-proof.json').relative_to(raw.parent))])
  if slots==4:current='slots4-sustained';campaign.sustained()
 except BaseException as error:
  failure=str(error) or type(error).__name__;campaign.record['error']=failure;save(campaign.folder/'error.json',dict(timestamp=now(),case=current,reason=failure));result(current,'failed',failure,evidence=[str((campaign.folder/'error.json').relative_to(raw.parent))])
 finally:campaign.close()
 if failure:break
m=json.loads((raw.parent/'manifest.json').read_text())
for a in m['planned_attempts']:
 if a['status']=='planned':a.update(status='not-run',reason=failure or 'No execution evidence',evidence_files=[])
m.update(status='blocked' if failure else 'completed',conclusion='Actual server-slot campaign '+('stopped: '+failure if failure else 'completed including 30 minutes on slots4'))
if failure:m['unavailable']['completion']=failure
m['evidence_files']=sorted(str(f.relative_to(raw.parent)) for f in raw.rglob('*') if f.is_file());save(raw.parent/'manifest.json',m);print(json.dumps(dict(failure=failure)))
