"""Bounded native MLX HTTP qualification. Never reads task checks or loads another model."""
import datetime
import hashlib
import json
import os
import pathlib
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

raw=pathlib.Path(__file__).resolve().parent
root=raw.parents[4]
sys.path.insert(0,str(root/'experiments/common'))
from local_resources import sample
runtime=json.loads((raw/'runtime-manifest.json').read_text())
python=runtime['pins']['environment']+'/bin/python'
site=pathlib.Path(runtime['pins']['environment'])/'lib/python3.12/site-packages'
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','USER','LANG'] if k in os.environ}
env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',
           no_proxy='127.0.0.1,localhost,::1',PYTHONDONTWRITEBYTECODE='1')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def http(url):
    with opener.open(url,timeout=5) as response:return json.load(response)
def safe(row):
    return all(c['returncode']==0 for c in row['commands'].values()) and row['pressure_level']==1 and row['pressure_free_percentage']>=50 and row['free_speculative_bytes']>=8*2**30 and row['swap_used_bytes']==0 and row['on_ac_power'] and row['ac_power_mode']==0
def update(id,status,reason=None,evidence=()):
    m=json.loads((raw.parent/'manifest.json').read_text());a=next(a for a in m['planned_attempts'] if a['id']==id);a.update(status=status,reason=reason,evidence_files=list(evidence));m['evidence_files']=sorted(str(f.relative_to(raw.parent)) for f in raw.rglob('*') if f.is_file());save(raw.parent/'manifest.json',m)

# Reverify registered full binaries and model files, before tokenizer or native process.
pins=json.loads((raw/'prestart-pins.json').read_text())
sys.path.insert(0,str(root/'experiments/local-models/apple'))
from artifacts import select_artifact,missing_artifact_pins
artifact=select_artifact(json.loads((raw/'artifact-manifest.json').read_text()),format='MLX/safetensors',repository='mlx-community/Qwen3.5-9B-MLX-4bit',revision=runtime['model_revision'])
assert not missing_artifact_pins(artifact,pins), 'Required MLX prestart model pins missing'
assert all(str(pathlib.Path(f['local_path']).parent)==runtime['model_path'] for f in artifact['files']), 'Artifact root differs from server model path'
host=dict(macos=subprocess.check_output(['sw_vers','-productVersion'],text=True).strip(),build=subprocess.check_output(['sw_vers','-buildVersion'],text=True).strip(),ram_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)))
assert host==dict(macos='26.5',build='25F71',ram_bytes=128*2**30)
save(raw/'host-before.json',host)
verified=[]
for pin in pins['files']:
    path=pathlib.Path(pin['path']);assert path.stat().st_size==pin['bytes'] and digest(path)==pin['sha256'], 'Registered file pin changed'
    verified.append(pin)
save(raw/'verified-before-preparation.json',dict(timestamp=stamp(),files=verified))
subprocess.run([python,'-B',str(raw/'prepare_inputs.py')],env=env,check=True,timeout=120,stdout=(raw/'tokenizer-preparation.txt').open('x'),stderr=subprocess.STDOUT)
requests={p.name:digest(p) for p in raw.glob('*request.json')}
save(raw/'request-hashes.json',requests)
# Synthetic allowlist validation is separate from model observations.
valid=dict(role='assistant',content=None,tool_calls=[dict(id='synthetic-call',type='function',function=dict(name='lookup_lab_value',arguments='{"key":"alpha"}'))])
negative={}
for name in ('valid','unknown-name','wrong-key','missing-id'):
    message=json.loads(json.dumps(valid))
    if name=='unknown-name':message['tool_calls'][0]['function']['name']='unexpected_tool'
    if name=='wrong-key':message['tool_calls'][0]['function']['arguments']='{"key":"beta"}'
    if name=='missing-id':del message['tool_calls'][0]['id']
    save(raw/(name+'-message.json'),message)
    result=subprocess.run([sys.executable,'-B',str(raw/'http_probe.py'),'--validate-tool-message',str(raw/(name+'-message.json')),'--out',str(raw/name)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    negative[name]=dict(exit_code=result.returncode,expected=0 if name=='valid' else 1)
save(raw/'allowlist.json',negative)
assert all(v['exit_code']==v['expected'] for v in negative.values())
update('allowlist','completed',evidence=['raw/allowlist.json'])

failure=None
for ctx in (8192,16384,32768):
    directory=raw/f'ctx{ctx}';directory.mkdir();(directory/'phase.txt').write_text('startup')
    summary=dict(input_budget_label=ctx,hard_context_cap=None,started_at=stamp(),accepted=False,error=None,command=None)
    process=None;assertion=None;stop=threading.Event();guards=[];active=None;sigints=0;monitor=None
    started=time.time();last=[started];before=sample();save(directory/'memory-before.json',before)
    def interrupt():
        global sigints
        if process is not None and process.poll() is None and sigints==0:
            sigints+=1
            try:os.killpg(process.pid,signal.SIGINT)
            except ProcessLookupError:pass
    def monitor_resources():
        with (directory/'memory.jsonl').open('x') as out:
            while not stop.wait(2):
                try:
                    wall=time.time()
                    if wall<last[0] or wall-last[0]>15:raise RuntimeError('stale resource timeline or clock backwards')
                    if wall-started>900:raise RuntimeError('context absolute wall deadline900s')
                    if assertion.poll() is not None:raise RuntimeError('idle-sleep assertion exited')
                    row=sample();last[0]=time.time()
                    rss=subprocess.check_output(['ps','-o','rss=','-p',str(process.pid)],text=True,timeout=5).strip()
                    if not rss:raise RuntimeError('native PID RSS unavailable')
                    row['server_rss_bytes']=int(rss)*1024;out.write(json.dumps(row)+'\n');out.flush()
                    if not safe(row) or row['server_rss_bytes']>24*2**30:raise RuntimeError('resource/power guard')
                except Exception as error:
                    guards.append(dict(timestamp=stamp(),reason=str(error)));save(directory/'guard.json',guards);interrupt();return
    def check():
        if guards or process.poll() is not None:raise RuntimeError('owned native process stopped: '+str(guards))
        if time.time()<last[0] or time.time()-last[0]>15:raise RuntimeError('resource timeline stale at request boundary')
    def probe(case,repeat,request=None,expected=None,tool=False):
        global active
        check();label=f'ctx{ctx}-{case}-{repeat}';prefix=directory/(case+'-'+repeat);(directory/'phase.txt').write_text(label)
        request=request or raw/(case+'-request.json')
        command=[sys.executable,'-B',str(raw/'http_probe.py'),'--url','http://127.0.0.1:8081','--request',str(request),'--out',str(prefix)]
        if tool:command.append('--follow-tool')
        with (prefix.with_suffix('.driver.txt')).open('x') as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        check();assert result.returncode==0,'HTTP probe failed'
        final=json.loads(pathlib.Path(str(prefix)+'.final.json').read_text());assert final['content']==expected, 'Exact final mismatch: '+repr(final['content'])
        metrics=json.loads(pathlib.Path(str(prefix)+('.followup' if tool else '')+'.metrics.json').read_text());assert metrics['http_status']==200 and metrics['finish_reason']=='stop' and metrics['usage'] is not None
        if 'stream' in case or case in ['long','recovery']:assert metrics.get('stream_done') is True
        if tool:
            initial=json.loads(pathlib.Path(str(prefix)+'.metrics.json').read_text());assert initial['finish_reason']=='tool_calls'
        assert metrics['usage'].get('prompt_tokens_details',{}).get('cached_tokens')==0, 'Unexpected prompt cache usage'
        if case=='long':
            count=json.loads((raw/f'ctx{ctx}-long-count.json').read_text());assert metrics['usage']['prompt_tokens']==count['input_tokens'],'Actual input count differs from pinned tokenizer'
        if case!='recovery':update(label,'completed',evidence=[str(pathlib.Path(str(prefix)+'.final.json').relative_to(raw.parent)),str(pathlib.Path(str(prefix)+('.followup' if tool else '')+'.metrics.json').relative_to(raw.parent))])
    try:
        assert safe(before), 'Memory/power admission failed'
        assert json.loads(subprocess.check_output(['/opt/homebrew/bin/lms','ps','--json'],text=True,timeout=10))==[], 'Foreign LM Studio model'
        assert http('http://127.0.0.1:11434/api/ps')['models']==[], 'Foreign Ollama model'
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind(('127.0.0.1',8081));sock.listen(1)
        # Full pins again immediately before each native launch; no post-hoc identity claim.
        for pin in pins['files']:assert digest(pathlib.Path(pin['path']))==pin['sha256']
        command=[python,'-B',str(raw/'server_entry.py'),str(ctx),'--model',runtime['model_path'],'--host','127.0.0.1','--port','8081','--max-tokens','2048','--temp','0','--top-p','1','--chat-template-args','{"enable_thinking":false}','--decode-concurrency','1','--prompt-concurrency','1','--prompt-cache-size','0','--prefill-step-size','2048']
        summary.update(command=command,verified_before_popen=True,verified_at=stamp(),popen_invoked_at=stamp())
        with (directory/'server.txt').open('x') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        assertion=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        summary.update(pid=process.pid,idle_sleep_assertion_pid=assertion.pid);save(directory/'execution.json',summary)
        last[0]=time.time();monitor=threading.Thread(target=monitor_resources,daemon=True);monitor.start()
        ready=False
        for _ in range(60):
            check()
            try:
                models=http('http://127.0.0.1:8081/v1/models');save(directory/'models.json',models)
                if any(m['id']==runtime['model_path'] for m in models['data']):ready=True;break
            except (OSError,ValueError):pass
            time.sleep(2)
        assert ready,'Native readiness deadline'
        update(f'ctx{ctx}-startup','completed',evidence=[str((directory/'execution.json').relative_to(raw.parent)),str((directory/'models.json').relative_to(raw.parent))])
        for case in ('chat','chat-stream','tool','tool-stream','long'):
            for repeat in ('warmup','1','2','3'):
                active=f'ctx{ctx}-{case}-{repeat}'
                probe(case,repeat,request=raw/f'ctx{ctx}-long-request.json' if case=='long' else None,expected='LAB_SENTINEL_42' if case=='long' else 'LAB_VALUE_42' if case.startswith('tool') else 'LAB_READY',tool=case.startswith('tool'))
        for repeat in ('warmup','1','2','3'):
            check();active=f'ctx{ctx}-cancel-recovery-{repeat}';(directory/'phase.txt').write_text(active);prefix=directory/('cancel-'+repeat);begin=time.time()
            with pathlib.Path(str(prefix)+'.sse').open('xb') as body,pathlib.Path(str(prefix)+'.stderr.txt').open('x') as err:
                result=subprocess.run(['/usr/bin/curl','--silent','--show-error','--no-buffer','--max-time','1','--noproxy','*','-H','Content-Type: application/json','--data-binary','@'+str(raw/f'ctx{ctx}-cancel-request.json'),'http://127.0.0.1:8081/v1/chat/completions'],stdout=body,stderr=err,timeout=10)
            canceled=time.time();proof=dict(client_exit=result.returncode,client_wall_seconds=canceled-begin,client_ended_at=stamp(),generation_end=None,stop_requested=None)
            assert result.returncode==28,'Cancellation did not occur'
            assert b'[DONE]' not in pathlib.Path(str(prefix)+'.sse').read_bytes(),'Stream already completed; no cancellation measurement'
            while time.time()-canceled<60:
                check()
                events=[json.loads(line) for line in (directory/'server-events.jsonl').read_text().splitlines()]
                selected=[e for e in events if e['phase']==active]
                stops=[e for e in selected if e['event']=='stop_requested'];ends=[e for e in selected if e['event']=='generation_end']
                if stops and ends and ends[-1].get('stop_flag') is True and stops[-1]['context_object']==ends[-1]['context_object'] and stops[-1]['timestamp']<=ends[-1]['timestamp']:
                    proof.update(generation_end=ends[-1],stop_requested=stops[-1],release_observed_seconds=time.time()-canceled);break
                time.sleep(.25)
            save(pathlib.Path(str(prefix)+'.proof.json'),proof)
            assert proof['generation_end'] and proof['stop_requested'],'Native generation release not observed'
            probe('recovery',repeat,request=raw/'chat-stream-request.json',expected='LAB_READY')
            update(active,'completed',evidence=[str(pathlib.Path(str(prefix)+'.proof.json').relative_to(raw.parent)),str((directory/('recovery-'+repeat+'.final.json')).relative_to(raw.parent))])
        summary['accepted']=True
    except Exception as error:
        summary['error']=type(error).__name__+': '+str(error);failure=summary['error']
        save(directory/'execution.json',summary)
        update(active or f'ctx{ctx}-startup','failed',failure,evidence=[str((directory/'execution.json').relative_to(raw.parent))])
    finally:
        stop.set()
        if monitor:monitor.join(timeout=20)
        interrupt()
        if process:
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait();guards.append({'reason':'shutdown deadline'})
            summary['returncode']=process.returncode
        if assertion:assertion.terminate();assertion.wait(timeout=5)
        summary.update(ended_at=stamp(),total_wall_seconds=time.time()-started,sigint_count=sigints,guards=guards,memory_after=sample())
        if process is None or process.returncode!=0 or guards:summary['accepted']=False;failure=failure or 'Native cleanup/guard failure'
        save(directory/'execution.json',summary)
    if not summary['accepted']:break
m=json.loads((raw.parent/'manifest.json').read_text())
for a in m['planned_attempts']:
    if a['status']=='planned':a.update(status='not-run',reason=failure or 'No execution evidence',evidence_files=[])
m['status']='blocked';m['unavailable']['completion']=failure or 'Hard context cap/overflow and physical GPU release unavailable; measured input-budget qualification only.'
m['conclusion']='Input-budget qualification finished; see each attempt and execution.json. Full LAB32 admission limited by unavailable hard cap.'
m['evidence_files']=sorted(str(f.relative_to(raw.parent)) for f in raw.rglob('*') if f.is_file());save(raw.parent/'manifest.json',m)
print(json.dumps(dict(failure=failure),ensure_ascii=False))
if failure:sys.exit(1)
