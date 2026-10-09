# -*- coding: utf-8 -*-
"""Registered, bounded native load campaign; owns only its child server."""
import datetime, hashlib, json, os, pathlib, re, signal, socket
import statistics, subprocess, sys, threading, time, urllib.request
from resources import sample, safe

RAW=pathlib.Path(__file__).resolve().parent
ROOT=RAW.parent
MANIFEST=ROOT/'manifest.json'
VARIANT=''
EXPECTED_TENSOR=True
RUNTIME_LABEL=''
REQUEST='load-request.json'
PORT=18080
URL=f'http://127.0.0.1:{PORT}'
BUILD=pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a/build-metal-tensor-tile16-arm64')
MODEL=pathlib.Path('/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf')
MODEL_SHA='91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59'
SERVER_SHA='916660e9bfe7f4d2fda420136f6bd192688def8cbd6581f23d08b06ead2e571f'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):
    (RAW/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def verify_build_reference(build,reference):
    pins=reference['binaries'];directory=build/'bin'
    families=['libggml','libggml-base','libggml-cpu','libggml-metal','libggml-blas','libllama','libmtmd']
    required={str(directory/(family+'.dylib')) for family in families}
    observed={str(path) for path in directory.glob('*.dylib')}
    assert required<=observed, 'Required bundled dylibs missing from build'
    assert observed<=pins.keys(), 'Unpinned bundled dylibs: '+str(sorted(observed-pins.keys()))
    assert str(directory/'llama-server') in pins, 'Server executable pin missing'
    for name,expected in pins.items():
        assert digest(pathlib.Path(name))==expected, 'Build hash mismatch: '+name
    return dict(pins)

def api(base,route):
    with OPENER.open(base+route,timeout=3) as response:return json.load(response)
def result(case,ok,reason=None):
    m=json.loads(MANIFEST.read_text());identifier=VARIANT+'-'+case if VARIANT else case
    attempt=next(a for a in m['planned_attempts'] if a['id']==identifier)
    assert attempt['status']=='planned'
    evidence=sorted('raw/'+(VARIANT+'/' if VARIANT else '')+str(p.relative_to(RAW)) for p in RAW.glob(case+'*') for p in ([p] if p.is_file() else p.rglob('*')) if p.is_file())
    assert evidence
    attempt.update(status='completed' if ok else 'failed',reason=reason,evidence_files=evidence)
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'case':identifier,'accepted':ok,'reason':reason}),flush=True)

def foreign_models():
    p=subprocess.run(['/opt/homebrew/bin/lms','ps','--json'],capture_output=True,text=True,timeout=10)
    assert p.returncode==0
    lms=json.loads(p.stdout)
    ollama=api('http://127.0.0.1:11434','/api/ps')['models']
    return {'lm_studio':lms,'ollama':ollama}

class Campaign:
    def __init__(self):
        self.process=None;self.client=None;self.guard=None;self.stop=threading.Event()
        self.monitor=None;self.handle=None;self.caffeinate=None
        self.interrupt_sent=False;self.interrupt_lock=threading.Lock()
        self.record={'started_at':now(),'command':None,'pid':None,'interrupts':[]}
    def interrupt(self,reason):
        with self.interrupt_lock:
            if not self.interrupt_sent and self.process and self.process.poll() is None:
                self.interrupt_sent=True
                self.record['interrupts'].append({'timestamp':now(),'reason':reason,'signal':'SIGINT'})
                os.killpg(self.process.pid,signal.SIGINT)
    def ensure(self):
        if self.guard or (self.process and self.process.poll() is not None):
            raise RuntimeError(self.guard or 'Own server exited')
    def observe(self):
        with (RAW/'memory-timeline.jsonl').open('x') as output:
            i=0
            while not self.stop.is_set():
                try:row=sample()
                except Exception as error:
                    self.guard='Resource sampler failed: '+str(error)
                    write('resource-sampler-error.json',{'timestamp':now(),'reason':self.guard})
                    self.interrupt('resource sampler failed');return
                p=subprocess.run(['ps','-o','rss=','-p',str(self.process.pid)],capture_output=True,text=True)
                row['server_pid']=self.process.pid
                row['server_rss_bytes']=int(p.stdout.strip())*1024 if p.returncode==0 and p.stdout.strip() else None
                if i%10==0:
                    try:
                        row['foreign_models']=foreign_models()
                        if any(row['foreign_models'].values()):self.guard='Foreign model loaded; stop own campaign'
                    except Exception as error:self.guard='Foreign-model inventory unavailable: '+str(error)
                output.write(json.dumps(row)+'\n');output.flush()
                if not safe(row) or (row['server_rss_bytes'] or 0)>24*2**30:
                    self.guard='Memory/power admission failed'
                if self.guard:
                    write('guard-trigger.json',{'row':row,'reason':self.guard,'owned_pid':self.process.pid})
                    self.interrupt('resource guard')
                    return
                i+=1;self.stop.wait(2)
    def startup(self):
        assert safe(sample()),'Memory/power preflight failed'
        assert not any(foreign_models().values()),'Foreign model loaded'
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',PORT))
        assert digest(MODEL)==MODEL_SHA and digest(BUILD/'bin/llama-server')==SERVER_SHA
        reference=json.loads((RAW/'build-reference.json').read_text())
        pinned=verify_build_reference(BUILD,reference)
        command=[str(BUILD/'bin/llama-server'),'-m',str(MODEL),'--host','127.0.0.1','--port',str(PORT),
            '--alias','lab-model','-ngl','999','-c','8192','-np','1','-t','8','-b','512','-ub','256',
            '-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto',
            '--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots','--metrics']
        env={k:v for k,v in os.environ.items() if k in ['HOME','PATH','TMPDIR','USER','LOGNAME','LANG','LC_ALL']}
        self.record.update(command=command,resources_before=sample(),pinned_binaries=pinned,model_sha256=MODEL_SHA,binaries_verified_at=now())
        self.handle=(RAW/'server.txt').open('x')
        self.record['popen_invoked_at']=now()
        self.process=subprocess.Popen(command,stdout=self.handle,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        self.record['pid']=self.process.pid;write('startup-process.json',self.record)
        self.caffeinate=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())])
        write('sleep-assertion.json',{'command':['caffeinate','-i','-w',str(os.getpid())],'pid':self.caffeinate.pid,'scope':'process-bound idle-sleep assertion; no pmset setting changes'})
        self.monitor=threading.Thread(target=self.observe,daemon=True);self.monitor.start()
        for _ in range(120):
            self.ensure()
            try:
                health=api(URL,'/health')
                if health['status']=='ok':break
            except Exception:pass
            time.sleep(1)
        else:raise RuntimeError('Server readiness deadline exceeded')
        props=api(URL,'/props');slots=api(URL,'/slots')
        write('startup-props.json',props);write('startup-slots.json',slots)
        assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==8192
        log=(RAW/'server.txt').read_text()
        assert 'offloaded 33/33 layers to GPU' in log and 'Apple M5 Max' in log
        assert re.search(r'has tensor\s*=\s*'+str(EXPECTED_TENSOR).lower(),log), 'Unexpected tensor capability'
        write('startup-execution.json',{'accepted':True,'timestamp':now(),'health':health,'pid':self.process.pid,'device':'Apple M5 Max','offload':'33/33','tensor_capability':EXPECTED_TENSOR})
        write('runtime-manifest.json',{'command':command,'version_commit':RUNTIME_LABEL,
            'context_per_slot':8192,'server_slots':1,'client_concurrency':[1],'prefix_cache':False,'thinking_budget_tokens':None,
            'request_timeout_seconds':300,'latency_p95_limit_seconds':240,'memory_condition':'free+spec>=8GiB, pressurelevel1, pressurefree>=50%,swap0,RSS<=24GiB,AC/mode0',
            'output_cap':2048,'temperature':0,'seed':1,'top_p':1,'kv_dtype':['f16','f16'],'binary_sha256':SERVER_SHA,
            'model_sha256':MODEL_SHA,'device_evidence':'raw/'+VARIANT+'/server.txt','comparison':'client concurrency with fixed single GPU slot; includes server queue'})
        result('startup',True)
    def block(self,name,concurrency,requests=12):
        self.ensure()
        # A stopped/timed-out request may not leave hidden work before the next block.
        assert all(not s['is_processing'] for s in api(URL,'/slots'))
        command=[sys.executable,'-B',str(ROOT/'raw/concurrency_driver.py'),'--endpoint',URL+'/v1/chat/completions',
            '--request',str(RAW/REQUEST),'--concurrency',str(concurrency),'--requests',str(requests),
            '--timeout','300','--out',str(RAW/name)]
        started=now()
        with (RAW/(name.replace('/','-')+'-driver.txt')).open('x') as output:
            self.client=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=self.client.wait(timeout=requests*300+30)
            except subprocess.TimeoutExpired:
                os.killpg(self.client.pid,signal.SIGINT);self.client.wait(timeout=310);code=self.client.returncode
            except BaseException:
                if self.client.poll() is None:
                    os.killpg(self.client.pid,signal.SIGTERM)
                    try:self.client.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(self.client.pid,signal.SIGKILL);self.client.wait()
                raise
            finally:self.client=None
        summary=json.loads((RAW/name/'summary.json').read_text())
        ok=(code==0 and summary['failed']==0 and summary['success_latency_p95_seconds']<=240 and not self.guard)
        write(name.replace('/','-')+'-execution.json',{'command':command,'started_at':started,'ended_at':now(),'exit_code':code,'accepted':ok,
            'guard_reason':self.guard,'summary':'raw/'+VARIANT+'/'+name+'/summary.json'})
        self.ensure()
        return summary,ok
    def shutdown(self):
        if self.process and self.process.poll() is None:
            self.interrupt('normal shutdown')
            try:self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid,signal.SIGKILL);self.process.wait();self.guard=self.guard or 'Native shutdown deadline exceeded'
        self.stop.set()
        if self.monitor:self.monitor.join(timeout=15)
        if self.handle:self.handle.close()
        if self.caffeinate and self.caffeinate.poll() is None:self.caffeinate.terminate();self.caffeinate.wait()
        self.record.update(ended_at=now(),returncode=self.process.returncode if self.process else None,guard_reason=self.guard,resources_after=sample())
        write('shutdown-execution.json',self.record)
        result('shutdown',self.process is not None and self.process.returncode==0 and not self.guard,self.guard or (None if self.process and self.process.returncode==0 else 'Native shutdown nonzero or server never started'))

def finish(stopped=None):
    m=json.loads(MANIFEST.read_text())
    for attempt in m['planned_attempts']:
        if attempt['status']=='planned':attempt.update(status='not-run',reason='Earlier failure: '+str(stopped),evidence_files=['raw/pin-audit-execution.json'])
    complete=all(a['status']=='completed' for a in m['planned_attempts'])
    m['status']='completed' if complete else 'blocked'
    m['conclusion']='Fresh tensor chat/load qualification completed with bundled library pins checked before Popen; full LAB35 still needs Ryzen/LAB08/LAB09.' if complete else 'Fresh pinned tensor attempt blocked; all evidence and not-run steps retained.'
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')

def main():
    global RAW,VARIANT,BUILD,SERVER_SHA,EXPECTED_TENSOR,RUNTIME_LABEL,REQUEST
    base=RAW;config=json.loads((base/'variants.json').read_text())['metal-tensor']
    try:
        for name,expected in json.loads((base/'registered-source-hashes.json').read_text()).items():assert digest(base/name)==expected,name
        from concurrency_driver import load_request
        for variant in ['', 'metal-tensor']:
            for filename in ['chat-request.json','load-request.json']:load_request(base/variant/filename)
        admission=[json.loads(line) for line in (base/'preflight-power.jsonl').read_text().splitlines()]
        assert len(admission)==13 and all(safe(row) for row in admission)
        assert (datetime.datetime.fromisoformat(admission[-1]['timestamp'])-datetime.datetime.fromisoformat(admission[0]['timestamp'])).total_seconds()>=120
        reference=json.loads((base/'metal-tensor/build-reference.json').read_text());assert reference['binaries']==config['binaries']
        verified=verify_build_reference(pathlib.Path(config['build']),reference)
        assert len(verified)==23 and sum(name.endswith('.dylib') for name in verified)==21
        write('pin-audit-execution.json',{'timestamp':now(),'accepted':True,'verified_binaries':verified,'gpu_process_started':False,'phase':'after preregistration, before native startup'})
        result('pin-audit',True)
    except BaseException as error:
        reason=str(error) or type(error).__name__
        write('pin-audit-execution.json',{'timestamp':now(),'accepted':False,'reason':reason,'gpu_process_started':False})
        result('pin-audit',False,reason);finish(reason);return
    VARIANT='metal-tensor';RAW=base/VARIANT;BUILD=pathlib.Path(config['build']);SERVER_SHA=config['server_sha256'];EXPECTED_TENSOR=True;RUNTIME_LABEL=config['source_label']
    campaign=Campaign();current='startup';stopped=None
    try:
        campaign.startup()
        for fixture in ['chat','load']:
            REQUEST=fixture+'-request.json'
            for repeat in ['warmup','r1','r2','r3']:
                current=fixture+'-'+repeat;summary,ok=campaign.block(current,1,1)
                contract=True
                if fixture=='chat':
                    response=json.loads((RAW/current/'request-0001.response.bin').read_bytes())
                    contract=response.get('choices',[{}])[0].get('message',{}).get('content','').strip()=='LAB_READY'
                write(current+'-contract.json',{'accepted':bool(ok and contract),'chat_exact_final':contract if fixture=='chat' else None,'fixture':fixture,'repeat':repeat})
                result(current,bool(ok and contract),None if ok and contract else 'HTTP/latency/resource/final contract failed')
                if not (ok and contract):raise RuntimeError('Qualification failed: '+current)
    except BaseException as error:
        stopped=str(error) or type(error).__name__
        write('campaign-error.json',{'timestamp':now(),'case':current,'reason':stopped,'guard':campaign.guard})
        m=json.loads(MANIFEST.read_text());attempt=next(a for a in m['planned_attempts'] if a['id']==VARIANT+'-'+current)
        if attempt['status']=='planned':attempt.update(status='failed',reason=stopped,evidence_files=['raw/'+VARIANT+'/campaign-error.json'])
        MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    finally:campaign.shutdown()
    finish(stopped)

if __name__=='__main__':main()
