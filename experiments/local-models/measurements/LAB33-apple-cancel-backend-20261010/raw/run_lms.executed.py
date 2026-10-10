"""Own alias/server only; never kills the central application or foreign models."""
import datetime,hashlib,json,os,pathlib,re,socket,subprocess,sys,threading,time,urllib.request
raw=pathlib.Path(__file__).resolve().parent;root=raw.parents[4]
sys.path.insert(0,str(root/'experiments/common'));from local_resources import sample
python='/Users/lab/local-model-lab-artifacts/engines/lmstudio-sdk/1.5.0/venv/bin/python'
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','USER','LANG'] if k in os.environ};env.update(PYTHONDONTWRITEBYTECODE='1',no_proxy='127.0.0.1,localhost,::1')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(2**20),b''):h.update(c)
 return h.hexdigest()
def http(route):
 with opener.open('http://127.0.0.1:1234'+route,timeout=5) as r:return json.load(r)
def cli(args,label,folder,timeout=120):
 p=subprocess.run(['/opt/homebrew/bin/lms',*args],env=env,capture_output=True,text=True,timeout=timeout)
 (folder/(label+'.txt')).write_text(p.stdout+p.stderr);assert p.returncode==0,label+' failed';return p.stdout
def loaded():return json.loads(subprocess.check_output(['/opt/homebrew/bin/lms','ps','--json'],env=env,text=True,timeout=10))
def app_roots():
 rows=[]
 for line in subprocess.check_output(['ps','-axo','pid=,comm='],text=True,timeout=5).splitlines():
  parts=line.strip().split(None,1)
  if len(parts)==2 and (parts[1]=='/Applications/LM Studio.app/Contents/MacOS/LM Studio' or pathlib.Path(parts[1]).name=='llmster'):rows.append(int(parts[0]))
 return sorted(rows)
def safe(row,minimum=8):return all(c['returncode']==0 for c in row['commands'].values()) and row['pressure_level']==1 and row['pressure_free_percentage']>=50 and row['free_speculative_bytes']>=minimum*2**30 and row['swap_used_bytes']==0 and row['on_ac_power'] and row['ac_power_mode']==0
def update(id,status,reason=None,evidence=()):
 m=json.loads((raw.parent/'manifest.json').read_text());a=next(a for a in m['planned_attempts'] if a['id']==id);a.update(status=status,reason=reason,evidence_files=list(evidence));m['evidence_files']=sorted(str(p.relative_to(raw.parent)) for p in raw.rglob('*') if p.is_file());save(raw.parent/'manifest.json',m)
# No model until two minutes of stable admission.
start=time.time();last=start;admitted=True
with (raw/'admission.jsonl').open('x') as out:
 while time.time()-start<120:
  row=sample();wall=time.time();out.write(json.dumps(row)+'\n');out.flush()
  if not safe(row,16) or wall<last or wall-last>15:admitted=False;break
  last=wall;time.sleep(2)
save(raw/'admission.json',dict(accepted=admitted,wall_seconds=time.time()-start))
update('admission','completed' if admitted else 'failed',None if admitted else 'Stable baseline free+spec16GiB/AC/pressure/swap admission failed',evidence=['raw/admission.json','raw/admission.jsonl'])
deployments=json.loads((raw/'deployments.json').read_text());pins=json.loads((raw/'prestart-pins.json').read_text())
failure=None
for dep in deployments if admitted else []:
 folder=raw/dep['id'];folder.mkdir();alias=dep['alias'];state=dict(started_at=now(),alias=alias,loaded=False,server_started=False,error=None,guards=[],own_logger_pid=None,app_root_pids_before=app_roots())
 stop=threading.Event();monitor=None;logger=None;assertion=None;active=None;events=[];timeline=None
 def check():
  if state['guards']:raise RuntimeError('resource/identity guard')
  wall=time.time();last=state.get('last_sample_wall',wall)
  if wall<last or wall-last>15:raise RuntimeError('Stale timeline at request boundary')
 def guard():
  last=time.time();start=last
  with (folder/'memory.jsonl').open('x') as out:
   while not stop.wait(2):
    try:
     wall=time.time()
     if wall<last or wall-last>15 or wall-start>600:raise RuntimeError('stale/backwards/deployment wall deadline')
     row=sample();last=time.time();state['last_sample_wall']=last;models=loaded()
     if state['app_root_pids_before'] and app_roots()!=state['app_root_pids_before']:raise RuntimeError('Central application PID changed')
     if any(m.get('identifier',m.get('id'))!=alias for m in models):raise RuntimeError('Foreign model appeared')
     if state['loaded']:
      query=subprocess.run(['/usr/sbin/lsof','-t',dep['resource_library']],capture_output=True,text=True,timeout=10)
      pids=sorted(set(p for p in query.stdout.split() if p.isdigit()))
      if not pids:raise RuntimeError('Backend PID RSS unavailable')
      rss=subprocess.check_output(['ps','-o','rss=','-p',','.join(pids)],text=True,timeout=5)
      values=[int(v) for v in rss.split()];row['backend_pids']=list(map(int,pids));row['backend_process_rss_bytes']=sum(values)*1024
      if len(values)!=len(pids) or any(v<=0 for v in values) or row['backend_process_rss_bytes']>24*2**30:raise RuntimeError('Backend RSS guard')
     out.write(json.dumps(row)+'\n');out.flush()
     if not safe(row):raise RuntimeError('Memory/power guard')
     if assertion.poll() is not None:raise RuntimeError('Idle-sleep assertion exited')
    except Exception as error:
     state['guards'].append(dict(timestamp=now(),reason=str(error)));save(folder/'guard.json',state['guards'])
     if state['loaded']:
      unloaded=subprocess.run(['/opt/homebrew/bin/lms','unload',alias],env=env,capture_output=True,timeout=30)
      if unloaded.returncode==0:state['loaded']=False
     return
 def log_stream():
  with (folder/'runtime-events.jsonl').open('x') as out:
   for line in logger.stdout:
    try:r=json.loads(line)
    except ValueError:continue
    if r.get('data',{}).get('modelIdentifier')==alias:
     events.append(r);out.write(json.dumps(r)+'\n');out.flush()
     if out.tell()>4*2**20:state['guards'].append({'reason':'Runtime log cap'});break
 def sdk(case,repeat,kind):
  check();name=f'{dep["id"]}-{case}-{repeat}';directory=folder/(case+'-'+repeat);directory.mkdir()
  with (directory/'driver.txt').open('x') as out:p=subprocess.run([python,'-B',str(raw/'sdk_probe.py'),str(directory),alias,kind],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=180)
  record=json.loads((directory/'sdk-result.json').read_text());accepted=p.returncode==0 and record['accepted'] and not state['guards'];update(name,'completed' if accepted else 'failed',None if accepted else record.get('error') or 'Native SDK result/guard did not meet criterion',evidence=[str((directory/'sdk-result.json').relative_to(raw.parent))]);return accepted
 try:
  assert safe(sample(),16) and loaded()==[],'Resource or foreign-model admission'
  with opener.open('http://127.0.0.1:11434/api/ps',timeout=5) as response:assert json.load(response)['models']==[],'Foreign Ollama model'
  with socket.socket() as probe:
   probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',1234));probe.listen(1)
  for pin in pins['files']:assert digest(pathlib.Path(pin['path']))==pin['sha256'],'Registered pin changed'
  save(folder/'prestart-verified.json',dict(timestamp=now(),verified_before_load=True,files=pins['files']))
  logger=subprocess.Popen(['/opt/homebrew/bin/lms','log','stream','--source','runtime','--json'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True);state['own_logger_pid']=logger.pid
  pump=threading.Thread(target=log_stream,daemon=True);pump.start()
  assertion=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);state['assertion_pid']=assertion.pid
  monitor=threading.Thread(target=guard,daemon=True);monitor.start()
  cli(['load',dep['model_key'],'--identifier',alias,'--context-length','8192','--parallel','1','--gpu','max','--ttl','600','--yes'],'load',folder);state['loaded']=True
  check()
  snapshot=loaded();save(folder/'loaded.json',snapshot);assert len(snapshot)==1 and snapshot[0]['format']==dep['format'] and snapshot[0]['contextLength']==8192 and snapshot[0]['parallel']==1
  cli(['server','start','--port','1234','--bind','127.0.0.1'],'server-start',folder);state['server_started']=True
  assert any(m['id']==alias for m in http('/v1/models')['data'])
  save(folder/'models.json',http('/v1/models'));save(folder/'native-models.json',http('/api/v0/models'))
  save(folder/'execution.json',state)
  update(dep['id']+'-startup','completed',evidence=[str((folder/'loaded.json').relative_to(raw.parent)),str((folder/'prestart-verified.json').relative_to(raw.parent))])
  for repeat in ['warmup','1','2','3']:
   assert sdk('chat',repeat,'chat'),'SDK chat failed'
  if dep['id']=='lms-mlx':
   for repeat in ['warmup','1','2','3']:
    assert sdk('sdk-cancel',repeat,'cancel'),'Native SDK cancellation failed'
    assert sdk('sdk-recovery',repeat,'chat'),'SDK cancellation recovery failed'
   for repeat in ['warmup','1','2','3']:
    check();name=f'lms-mlx-http-cancel-{repeat}';directory=folder/('http-cancel-'+repeat);directory.mkdir();payload=dict(model=alias,messages=[dict(role='user',content='Пиши целые числа от 1 до 10000, каждое на новой строке, не останавливайся.')],max_tokens=2048,temperature=0,stream=True);save(directory/'request.json',payload);offset=len(events)
    with (directory/'response.sse').open('xb') as out,(directory/'curl.txt').open('x') as err:p=subprocess.run(['/usr/bin/curl','--noproxy','*','--silent','--show-error','--no-buffer','--max-time','1','-H','Content-Type: application/json','--data-binary','@'+str(directory/'request.json'),'http://127.0.0.1:1234/v1/chat/completions'],stdout=out,stderr=err,timeout=10)
    canceled=time.time();assert sdk('http-recovery',repeat,'chat'),'HTTP cancellation recovery failed';fragment=events[offset:];save(directory/'events.json',fragment)
    # Deprecated stop-without-id or mere client disconnect are negative evidence.
    native=[e for e in fragment if re.search(r'cancel|abort|stop',e['data'].get('message',''),re.I)]
    proof=dict(client_exit=p.returncode,no_done=b'[DONE]' not in (directory/'response.sse').read_bytes(),recovery_end_seconds=time.time()-canceled,native_events=native,native_cancel_proven=False,physical_gpu_release=None,reason='No independently attributable native request-id cancellation/physical GPU release monitor for HTTP interface')
    save(directory/'proof.json',proof);update(name,'failed',proof['reason'],evidence=[str((directory/'proof.json').relative_to(raw.parent))])
  else:
   # A one-second OS stack sample during a controlled long prediction can prove
   # a Metal call path; it cannot count offloaded layers or physical GPU pages.
   for repeat in ['warmup','1','2','3']:
    check();directory=folder/('backend-'+repeat);directory.mkdir();payload=dict(model=alias,messages=[dict(role='user',content='Пиши целые числа от 1 до 10000, каждое на новой строке, не останавливайся.')],max_tokens=2048,temperature=0,stream=True);save(directory/'request.json',payload)
    with (directory/'response.sse').open('xb') as out,(directory/'curl.txt').open('x') as err:
     client=subprocess.Popen(['/usr/bin/curl','--noproxy','*','--fail-with-body','--silent','--show-error','--no-buffer','--max-time','120','-H','Content-Type: application/json','--data-binary','@'+str(directory/'request.json'),'http://127.0.0.1:1234/v1/chat/completions'],stdout=out,stderr=err)
     time.sleep(2);query=subprocess.run(['/usr/sbin/lsof','-t',dep['resource_library']],capture_output=True,text=True,timeout=10);pids=sorted(set(query.stdout.split()));samples=[]
     for pid in pids:
      if not pid.isdigit():continue
      path=directory/('sample-'+pid+'.txt');p=subprocess.run(['/usr/bin/sample',pid,'1','10','-file',str(path)],capture_output=True,text=True,timeout=15);samples.append(dict(pid=int(pid),returncode=p.returncode,file=str(path.relative_to(raw.parent))))
     code=client.wait(timeout=130)
    symbols=[]
    for row in samples:
     path=raw.parent/row['file']
     if path.exists():symbols+=re.findall(r'.*(?:ggml.*metal|Metal.*(?:commit|dispatch|wait)|AGX.*(?:command|submit)).*',path.read_text(errors='replace'),re.I)
    frames=[];done=False
    for line in (directory/'response.sse').read_text().splitlines():
     if not line.startswith('data:'):continue
     data=line[5:].strip()
     if data=='[DONE]':done=True;continue
     if data:frames.append(json.loads(data))
    finishes=[choice['finish_reason'] for frame in frames for choice in frame.get('choices',[]) if choice.get('finish_reason')]
    complete=done and bool(frames) and all(frame.get('model')==alias and not frame.get('error') for frame in frames) and finishes and finishes[-1] in ['stop','length']
    proof=dict(curl_exit=code,stream_complete=bool(complete),samples=samples,metal_call_path_lines=symbols,metal_call_path_observed=bool(symbols),all_layer_offload=None,reason='A sampled Metal call path does not count all 33 layers or measure GPU physical release')
    save(directory/'proof.json',proof);accepted=bool(symbols and code==0 and complete and not state['guards']);update(f'lms-gguf-backend-{repeat}','completed' if accepted else 'failed',None if accepted else 'Metal call path/complete controlled inference not observed; backend execution conditional',evidence=[str((directory/'proof.json').relative_to(raw.parent))])
 except Exception as error:
  state['error']=type(error).__name__+': '+str(error);failure=state['error']
  if not state['loaded']:save(folder/'execution.json',state);update(dep['id']+'-startup','failed',failure,evidence=[str((folder/'execution.json').relative_to(raw.parent))])
 finally:
  stop.set()
  if monitor:monitor.join(timeout=20)
  if state['loaded']:
   try:cli(['unload',alias],'unload',folder,30)
   except Exception as e:state['unload_error']=str(e)
  if state['server_started'] and loaded()==[]:
   try:cli(['server','stop'],'server-stop',folder,30)
   except Exception as e:state['server_stop_error']=str(e)
  if logger:
   logger.terminate();logger.wait(timeout=10);pump.join(timeout=5)
  if assertion:assertion.terminate();assertion.wait(timeout=5)
  state.update(ended_at=now(),models_after=loaded(),memory_after=sample(),app_root_pids_after=app_roots());save(folder/'execution.json',state)
  clean=not state['models_after'] and not any(k in state for k in ['unload_error','server_stop_error']) and (not state['app_root_pids_before'] or state['app_root_pids_before']==state['app_root_pids_after'])
  update(dep['id']+'-cleanup','completed' if clean else 'failed',None if clean else 'Own alias/server cleanup or central application PID continuity not confirmed',evidence=[str((folder/'execution.json').relative_to(raw.parent))])
 if failure:break
m=json.loads((raw.parent/'manifest.json').read_text())
for a in m['planned_attempts']:
 if a['status']=='planned':a.update(status='not-run',reason=failure or 'Admission failed before model; no result',evidence_files=[])
m.update(status='blocked',conclusion='SDK/HTTP cancellation and backend evidence retained; physical GPU release and all-layer offload require separate proof.')
m['unavailable']['completion']=failure or ('Memory admission failed before model' if not admitted else 'Physical GPU release/all-layer offload not instrumented; HTTP cancellation not proven')
m['evidence_files']=sorted(str(p.relative_to(raw.parent)) for p in raw.rglob('*') if p.is_file());save(raw.parent/'manifest.json',m)
print(json.dumps(dict(admitted=admitted,failure=failure)))
