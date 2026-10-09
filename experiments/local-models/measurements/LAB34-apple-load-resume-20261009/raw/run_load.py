# -*- coding: utf-8 -*-
"""Registered, bounded native load campaign; owns only its child server."""
import datetime, hashlib, json, os, pathlib, re, signal, socket
import statistics, subprocess, sys, threading, time, urllib.request
from resources import sample, safe

RAW=pathlib.Path(__file__).resolve().parent
ROOT=RAW.parent
MANIFEST=ROOT/'manifest.json'
PORT=18080
URL=f'http://127.0.0.1:{PORT}'
BUILD=pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a/build-metal-tensor-tile16-arm64')
MODEL=pathlib.Path('/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf')
MODEL_SHA='91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59'
SERVER_SHA='916660e9bfe7f4d2fda420136f6bd192688def8cbd6581f23d08b06ead2e571f'
ORDER=[(2,4),(2,1),(3,4),(3,1),(3,2)]
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):
    (RAW/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def api(base,route):
    with OPENER.open(base+route,timeout=3) as response:return json.load(response)
def result(case,ok,reason=None):
    m=json.loads(MANIFEST.read_text());a=next(a for a in m['planned_attempts'] if a['id']==case)
    assert a['status']=='planned'
    a.update(status='completed' if ok else 'failed',reason=reason,
        evidence_files=sorted('raw/'+str(p.relative_to(RAW)) for p in RAW.glob(case+'*') for p in ([p] if p.is_file() else p.rglob('*')) if p.is_file()))
    assert a['evidence_files']
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'case':case,'accepted':ok,'reason':reason}),flush=True)

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
        pinned={}
        for name,expected in reference['binaries'].items():
            path=pathlib.Path(name)
            assert digest(path)==expected
            pinned[name]=expected
        command=[str(BUILD/'bin/llama-server'),'-m',str(MODEL),'--host','127.0.0.1','--port',str(PORT),
            '--alias','lab-load-qwen35-9b','-ngl','999','-c','8192','-np','1','-t','8','-b','512','-ub','256',
            '-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift','--reasoning','auto',
            '--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots','--metrics']
        env={k:v for k,v in os.environ.items() if k in ['HOME','PATH','TMPDIR','USER','LOGNAME','LANG','LC_ALL']}
        self.record.update(command=command,resources_before=sample(),pinned_binaries=pinned,model_sha256=MODEL_SHA)
        self.handle=(RAW/'server.txt').open('x')
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
        assert re.search(r'has tensor\s*=\s*true',log), 'Native tensor capability not observed'
        write('startup-execution.json',{'accepted':True,'timestamp':now(),'health':health,'pid':self.process.pid,'device':'Apple M5 Max','offload':'33/33','tensor_capability':True})
        write('runtime-manifest.json',{'command':command,'version_commit':'b8407/312cf03328496df9c56fe843952cf02a8964c59a+tile16',
            'context_per_slot':8192,'server_slots':1,'client_concurrency':[1,2,4],'prefix_cache':False,'thinking_budget_tokens':None,
            'request_timeout_seconds':300,'latency_p95_limit_seconds':240,'memory_condition':'free+spec>=8GiB, pressurelevel1, pressurefree>=50%,swap0,RSS<=24GiB,AC/mode0',
            'output_cap':2048,'temperature':0,'seed':1,'top_p':1,'kv_dtype':['f16','f16'],'binary_sha256':SERVER_SHA,
            'model_sha256':MODEL_SHA,'device_evidence':'raw/server.txt','comparison':'client concurrency with fixed single GPU slot; includes server queue'})
        result('startup',True)
    def block(self,name,concurrency,requests=12):
        self.ensure()
        # A stopped/timed-out request may not leave hidden work before the next block.
        assert all(not s['is_processing'] for s in api(URL,'/slots'))
        command=[sys.executable,'-B',str(RAW/'concurrency_driver.py'),'--endpoint',URL+'/v1/chat/completions',
            '--request',str(RAW/'load-request.json'),'--concurrency',str(concurrency),'--requests',str(requests),
            '--timeout','300','--out',str(RAW/name)]
        started=now()
        with (RAW/(name.replace('/','-')+'-driver.txt')).open('x') as output:
            self.client=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=self.client.wait(timeout=requests*300+30)
            except subprocess.TimeoutExpired:
                os.killpg(self.client.pid,signal.SIGINT);self.client.wait(timeout=310);code=self.client.returncode
            finally:self.client=None
        summary=json.loads((RAW/name/'summary.json').read_text())
        ok=(code==0 and summary['failed']==0 and summary['success_latency_p95_seconds']<=240 and not self.guard)
        write(name.replace('/','-')+'-execution.json',{'command':command,'started_at':started,'ended_at':now(),'exit_code':code,'accepted':ok,
            'guard_reason':self.guard,'summary':'raw/'+name+'/summary.json'})
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

def main():
    campaign=Campaign();current='startup';blocks=[]
    try:
        current='prior-evidence-audit'
        for name,expected in json.loads((RAW/'registered-source-hashes.json').read_text()).items():
            assert digest(RAW/name)==expected,name
        reference=json.loads((RAW/'prior-short-reference.json').read_text())
        prior_rows=[]
        for name,expected in reference['sha256'].items():assert digest(RAW/name)==expected,name
        for case in reference['copied_blocks']:
            summary=json.loads((RAW/'prior-short'/case/'summary.json').read_text())
            assert summary['failed']==0 and summary['requests']==12 and summary['success_latency_p95_seconds']<=240
            assert json.loads((RAW/'prior-short'/case/'request.json').read_text())==json.loads((RAW/'load-request.json').read_text())
            prior_rows.append(summary)
        write('prior-evidence-audit-execution.json',{'accepted':True,'timestamp':now(),'prior_rows':reference['copied_blocks'],'original_failure_preserved':True,'new_model_execution':False})
        result(current,True)
        current='startup';campaign.startup();current='warmup'
        summary,ok=campaign.block('warmup',1,2);result(current,ok,None if ok else 'Warmup protocol/latency failed');assert ok
        rows=prior_rows
        for repeat,concurrency in ORDER:
            current=f'r{repeat}-c{concurrency}'
            summary,ok=campaign.block(current,concurrency)
            result(current,ok,None if ok else 'Short protocol/latency/memory failed')
            rows.append(summary);assert ok
        medians={c:statistics.median(s['successful_requests_per_second'] for s in rows if s['concurrency']==c) for c in [1,2,4]}
        chosen=min(c for c,value in medians.items() if value>=0.95*max(medians.values()))
        write('sustained-selection.json',{'timestamp':now(),'concurrency':chosen,'median_short_requests_per_second':medians,
            'rule':'lowest passing concurrency within 95% of maximum median short throughput','planned_seconds':1800,'server_slots_unchanged':1,'matrix_sessions':['apple-load-complete-20261008','apple-load-resume-20261009'],'historical_failed_r2_c4_not_erased':True})
        (RAW/'sustained').mkdir();current='sustained';start=time.monotonic();series_start=now();status='completed';reason=None
        try:
            while time.monotonic()-start<1800:
                name=f'sustained/block-{len(blocks)+1:04d}'
                summary,ok=campaign.block(name,chosen)
                blocks.append({'directory':name,'accepted':ok,'requests':summary['requests'],'summary':'raw/'+name+'/summary.json'})
                write('sustained-progress.json',{'elapsed_seconds':time.monotonic()-start,'blocks':len(blocks),'concurrency':chosen,'last_summary':summary})
                print(json.dumps({'sustained_elapsed_seconds':round(time.monotonic()-start,2),'blocks':len(blocks),'concurrency':chosen}),flush=True)
                if not ok:raise RuntimeError('Sustained HTTP/protocol/latency/memory failure')
        except BaseException as error:
            status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed';reason=str(error) or type(error).__name__
            raise
        finally:
            write('sustained/series.json',{'planned_seconds':1800,'actual_seconds':time.monotonic()-start,'started_at':series_start,
                'ended_at':now(),'status':status,'reason':reason,'blocks':blocks,'concurrency':chosen})
        result(current,True)
    except BaseException as error:
        reason=str(error) or type(error).__name__
        write('campaign-error.json',{'timestamp':now(),'case':current,'reason':reason,'guard':campaign.guard})
        m=json.loads(MANIFEST.read_text());attempt=next(a for a in m['planned_attempts'] if a['id']==current)
        if attempt['status']=='planned':attempt.update(status='failed',reason=reason,evidence_files=['raw/campaign-error.json'])
        for attempt in m['planned_attempts']:
            if attempt['status']=='planned' and attempt['id']!='shutdown':attempt.update(status='not-run',reason='Earlier failure: '+reason,evidence_files=['raw/campaign-error.json'])
        MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
        print('STOP '+reason,flush=True)
    finally:campaign.shutdown()

if __name__=='__main__':main()
