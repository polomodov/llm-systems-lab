# -*- coding: utf-8 -*-
"""Registered, sequential loopback cases on one owned native Metal server."""
import copy
import datetime
import hashlib
import json
import os
import pathlib
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

RAW = pathlib.Path(__file__).resolve().parent
MANIFEST = RAW.parent/'manifest.json'
BASE = pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a')
BIN = BASE/'build-metal-tensor-tile16-arm64/bin'
MODEL = '/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf'
URL = 'http://127.0.0.1:8080'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):
    (RAW/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def register_result(case,accepted,files,reason=None):
    manifest=json.loads(MANIFEST.read_text())
    attempt=next(a for a in manifest['planned_attempts'] if a['id']==case)
    assert attempt['status']=='planned',case
    attempt.update(status='completed' if accepted else 'failed',reason=None if accepted else reason or 'Admission failed',evidence_files=sorted(set(files)))
    manifest['evidence_files']=sorted('raw/'+p.name for p in RAW.iterdir() if p.is_file())
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

def request(route,payload=None,timeout=30):
    req=urllib.request.Request(URL+route,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with OPENER.open(req,timeout=timeout) as response:return response.status,json.load(response)

def sample():
    row={'timestamp':now(),'commands':{}}
    for label,args in [('vm_stat',['vm_stat']),('swap',['sysctl','vm.swapusage']),('pressure',['memory_pressure','-Q']),('power_source',['pmset','-g','batt']),('power_mode',['pmset','-g','custom'])]:
        p=subprocess.run(args,capture_output=True,text=True,timeout=10)
        row['commands'][label]={'argv':args,'returncode':p.returncode,'stdout':re.sub(r'\(id=\d+\)','(battery identity omitted)',p.stdout),'stderr':p.stderr}
    vm=row['commands']['vm_stat']['stdout'];swap=row['commands']['swap']['stdout']
    pages=re.search(r'page size of (\d+) bytes',vm);free=re.search(r'Pages free:\s+(\d+)',vm);used=re.search(r'used = ([0-9.]+)([KMG])',swap)
    row['free_pages_bytes']=int(pages[1])*int(free[1]) if pages and free else None
    row['swap_used_bytes']=int(float(used[1])*{'K':1024,'M':1024**2,'G':1024**3}[used[2]]) if used else None
    row['on_ac_power']="Now drawing from 'AC Power'" in row['commands']['power_source']['stdout']
    ac=row['commands']['power_mode']['stdout'].split('AC Power:',1)[-1];mode=re.search(r'powermode\s+(\d+)',ac)
    row['ac_power_mode']=int(mode[1]) if mode else None
    return row

def safe(row):
    return row['free_pages_bytes'] is not None and row['free_pages_bytes']>=16*2**30 and row['swap_used_bytes']==0 and row['on_ac_power'] and row['ac_power_mode']==0

def preflight():
    assert safe(sample())
    h=hashlib.sha256()
    with open(MODEL,'rb') as stream:
        for b in iter(lambda:stream.read(8*1024*1024),b''):h.update(b)
    assert h.hexdigest()=='91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59'
    expected={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (RAW/'baseline-binaries.sha256').read_text().splitlines()}
    binaries={path:hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for path in expected}
    assert all(expected[path]==sha for path,sha in binaries.items())
    arch=subprocess.check_output(['file',str(BIN/'llama-server')],text=True);assert 'arm64' in arch
    runtime=json.loads((RAW/'baseline-runtime-manifest.json').read_text())
    runtime.update(protocol='LAB32',model_sha256=h.hexdigest(),binaries=binaries,architecture=arch,contexts=[32768],prefix_cache=False,
        reasoning='auto',server_reasoning_budget=-1,thinking_budget_tokens=128,cancel_release_timeout_seconds=60,temperature=0,seed=1,source_docs=str(BASE/'source-tensor-tile16/tools/server/README.md'))
    write('hardware-snapshot.json',{'timestamp':now(),'memory_power':sample(),'hardware':{name:subprocess.check_output(cmd,text=True).strip() for name,cmd in [('chip',['sysctl','-n','machdep.cpu.brand_string']),('ram_bytes',['sysctl','-n','hw.memsize']),('macos',['sw_vers','-productVersion']),('build',['sw_vers','-buildVersion']),('architecture',['uname','-m'])]}})
    write('runtime-manifest.json',runtime);write('preflight-execution.json',{'timestamp':now(),'accepted':True,'binaries':binaries,'gguf_sha256':h.hexdigest(),'architecture':arch,'memory_power':sample()})
    help=subprocess.run([str(BIN/'llama-server'),'--help'],capture_output=True,text=True)
    (RAW/'server-help.txt').write_text(help.stdout+help.stderr)
    register_result('preflight',True,['raw/preflight-execution.json','raw/runtime-manifest.json','raw/server-help.txt','raw/hardware-snapshot.json'])
    valid={'role':'assistant','content':'','tool_calls':[{'id':'call_lab_alpha','type':'function','function':{'name':'lookup_lab_value','arguments':'{"key":"alpha"}'}}]}
    fixtures={'valid':copy.deepcopy(valid),'unknown-name':copy.deepcopy(valid),'wrong-key':copy.deepcopy(valid),'missing-id':copy.deepcopy(valid)}
    fixtures['unknown-name']['tool_calls'][0]['function']['name']='execute_shell'
    fixtures['wrong-key']['tool_calls'][0]['function']['arguments']='{"key":"beta"}'
    fixtures['missing-id']['tool_calls'][0]['id']=''
    results=[]
    for label,message in fixtures.items():
        write('offline-'+label+'.json',message);prefix=RAW/('offline-'+label)
        p=subprocess.run([sys.executable,str(RAW/'http_probe.py'),'--validate-tool-message',str(prefix)+'.json','--out',str(prefix)],capture_output=True,text=True)
        expected_code=0 if label=='valid' else 1
        reason=json.loads(pathlib.Path(str(prefix)+'.tool-rejected.json').read_text())['reason'] if label!='valid' else None
        assert p.returncode==expected_code and (label=='valid' or reason in ['tool/arguments rejected by allowlist','missing tool call id'])
        results.append({'case':label,'exit_code':p.returncode,'expected_code':expected_code,'reason':reason})
    write('offline-validator-results.json',{'evidence_class':'synthetic','results':results,'model_executed':False})
    register_result('offline-validator',True,['raw/offline-validator-results.json']+['raw/'+p.name for p in RAW.glob('offline-*.json')])

class Server:
    def __init__(self,ctx):
        self.ctx=ctx;self.server_pid=None;self.stop=threading.Event();self.guard_reason=None
        with socket.socket() as test:
            test.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            test.bind(('127.0.0.1',8080))
        self.before=sample();assert safe(self.before)
        write(f'ctx{ctx}-memory-before.json',self.before)
        self.log=RAW/f'server-{ctx}.txt';self.handle=self.log.open('x')
        command=['/usr/bin/time','-l',str(BIN/'llama-server'),'-m',MODEL,'--host','127.0.0.1','--port','8080','--alias','lab-model',
            '-ngl','999','-c',str(ctx),'-np','1','-t','8','-b','512','-ub','256','-ctk','f16','-ctv','f16','-fa','on','--jinja','--no-context-shift',
            '--reasoning','auto','--reasoning-budget','-1','--chat-template-kwargs','{"enable_thinking":true}','--no-cache-prompt','--slots','--metrics']
        env=os.environ.copy();env.update(no_proxy='127.0.0.1,localhost,::1',NO_PROXY='127.0.0.1,localhost,::1')
        for key in ['GGML_METAL_TENSOR_DISABLE','GGML_METAL_TENSOR_ENABLE']:env.pop(key,None)
        self.record={'command':command,'started_at':now(),'returncode':None,'sampling_interval_seconds':2}
        write(f'ctx{ctx}-server-execution.json',self.record)
        self.process=subprocess.Popen(command,stdout=self.handle,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        self.monitor=threading.Thread(target=self.observe,daemon=True);self.monitor.start()
    def observe(self):
        with (RAW/f'ctx{self.ctx}-memory.jsonl').open('x') as timeline:
            while not self.stop.is_set():
                row=sample();pids=subprocess.run(['pgrep','-P',str(self.process.pid)],capture_output=True,text=True).stdout.split()
                rss=[]
                for pid in pids:
                    p=subprocess.run(['ps','-o','rss=','-p',pid],capture_output=True,text=True)
                    if p.stdout.strip().isdigit():rss.append(int(p.stdout)*1024)
                row['observed_rss_bytes']=max(rss) if rss else None
                timeline.write(json.dumps(row)+'\n');timeline.flush()
                if not safe(row) or rss and max(rss)>24*2**30:
                    self.guard_reason='Memory/power admission changed or RSS ceiling exceeded'
                    if self.process.poll() is None:os.killpg(self.process.pid,signal.SIGTERM)
                    return
                self.stop.wait(2)
    def ready(self):
        start=time.monotonic();attempts=[]
        while time.monotonic()-start<120:
            if self.process.poll() is not None or self.guard_reason:raise RuntimeError('Server died or resource guard failed')
            try:
                status,health=request('/health',timeout=2);attempts.append({'status':status,'body':health})
                if status==200:break
            except (urllib.error.URLError,TimeoutError,ConnectionError) as e:attempts.append({'error':type(e).__name__})
            time.sleep(1)
        else:raise RuntimeError('Startup timeout')
        for name,route in [('health','/health'),('props','/props'),('models','/v1/models'),('slots','/slots')]:
            status,value=request(route);write(f'ctx{self.ctx}-{name}.json',{'http_status':status,'body':value})
        props=json.loads((RAW/f'ctx{self.ctx}-props.json').read_text())['body'];slots=json.loads((RAW/f'ctx{self.ctx}-slots.json').read_text())['body']
        children=subprocess.run(['pgrep','-P',str(self.process.pid)],capture_output=True,text=True).stdout.split()
        for child in children:
            comm=subprocess.run(['ps','-o','comm=','-p',child],capture_output=True,text=True).stdout.strip()
            if comm.endswith('llama-server'):
                self.server_pid=int(child);assert os.getpgid(self.server_pid)==self.process.pid
        assert self.server_pid is not None
        self.record['verified_server_pid']=self.server_pid
        log=self.log.read_text();layers=re.findall(r'offloaded (\d+)/(\d+) layers to GPU',log)
        assert layers and all(a==b=='33' for a,b in layers) and 'has tensor            = true' in log and 'Apple M5 Max' in log
        assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==self.ctx and len(slots)==1 and slots[0]['n_ctx']==self.ctx
        write(f'ctx{self.ctx}-startup-execution.json',{'accepted':True,'timestamp':now(),'readiness':attempts,'offloaded_layers':layers,'context':self.ctx,'tensor_api':True})
        register_result(f'ctx{self.ctx}-startup',True,[f'raw/ctx{self.ctx}-{name}.json' for name in ['health','props','models','slots','startup-execution']]+[f'raw/server-{self.ctx}.txt',f'raw/ctx{self.ctx}-server-execution.json'])
    def ensure(self):
        if self.guard_reason or self.process.poll() is not None:raise RuntimeError(self.guard_reason or 'Server exited')
    def shutdown(self):
        if self.process.poll() is None:
            if self.server_pid is None:raise RuntimeError('Owned server PID not observed')
            os.kill(self.server_pid,signal.SIGINT)
            try:self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait();self.guard_reason=self.guard_reason or 'Shutdown timeout'
        self.stop.set();self.monitor.join(timeout=15);self.handle.close()
        self.record.update(returncode=self.process.returncode,ended_at=now(),guard_reason=self.guard_reason,shutdown='single SIGINT to verified owned llama-server child')
        rss=re.search(r'(\d+)\s+maximum resident set size',self.log.read_text());self.record['max_rss_bytes']=int(rss[1]) if rss else None
        write(f'ctx{self.ctx}-server-execution.json',self.record);write(f'ctx{self.ctx}-memory-after.json',sample())
        shutdown_ok=self.guard_reason is None and self.record['returncode']==0 and 'GGML_ASSERT' not in self.log.read_text()
        register_result(f'ctx{self.ctx}-shutdown',shutdown_ok,[f'raw/ctx{self.ctx}-server-execution.json',f'raw/server-{self.ctx}.txt',f'raw/ctx{self.ctx}-memory.jsonl',f'raw/ctx{self.ctx}-memory-after.json'],self.guard_reason or ('Native shutdown failed' if not shutdown_ok else None))

def probe(server,case,fixture,expected,tool=False,expected_tokens=None):
    server.ensure();prefix=RAW/case;log_offset=server.log.stat().st_size
    command=[sys.executable,str(RAW/'http_probe.py'),'--url',URL,'--request',str(fixture),'--out',str(prefix)]
    if tool:command.append('--follow-tool')
    started=now();begin=time.monotonic();before=sample()
    try:
        with (RAW/(case+'-probe.txt')).open('x') as f:p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=600 if '-long-' in case else 180,env={**os.environ,'no_proxy':'127.0.0.1,localhost,::1','NO_PROXY':'127.0.0.1,localhost,::1'})
        returncode=p.returncode
    except subprocess.TimeoutExpired:returncode=None
    after=sample();reason=None;accepted=False;metrics=None;follow=None
    try:
        assert returncode==0,'Probe execution failed'
        final=json.loads(pathlib.Path(str(prefix)+'.final.json').read_text())
        metrics=json.loads(pathlib.Path(str(prefix)+'.metrics.json').read_text())
        assert final.get('content','').strip()==expected and not final.get('tool_calls'),'Final marker/tool mismatch'
        payload=json.loads(fixture.read_text())
        if tool:
            follow=json.loads(pathlib.Path(str(prefix)+'.followup.metrics.json').read_text());assert metrics['finish_reason']=='tool_calls' and follow['finish_reason']=='stop'
            initial=json.loads(pathlib.Path(str(prefix)+('.assembled.json' if payload['stream'] else '.response.json')).read_text())
            message=initial if payload['stream'] else initial['choices'][0]['message']
            call=message['tool_calls'][0];assert len(message['tool_calls'])==1 and call['id'] and call['function']['name']=='lookup_lab_value' and json.loads(call['function']['arguments'])=={'key':'alpha'}
            followreq=json.loads(pathlib.Path(str(prefix)+'.followup.request.json').read_text());assert followreq['messages'][-1]['tool_call_id']==call['id'] and followreq['messages'][-1]['content']=='LAB_VALUE_42'
        else:assert metrics['finish_reason']=='stop','Non-stop final'
        assert metrics['http_status']==200 and metrics['usage'] and metrics['usage']['prompt_tokens']>0,'Missing usage/status'
        if follow:assert follow['http_status']==200 and follow['usage'],'Missing followup usage'
        if payload['stream']:assert metrics['stream_done'] and (not follow or follow['stream_done']),'SSE incomplete'
        if expected_tokens is not None:assert metrics['usage']['prompt_tokens']==expected_tokens,'Input-token count mismatch'
        # Reasoning is a registered part of this condition; content timing is separate.
        assert safe(before) and safe(after),'Memory/power condition changed'
        server.ensure();accepted=True
    except (AssertionError,OSError,ValueError,KeyError,RuntimeError) as e:reason=str(e) or type(e).__name__
    record={'case':case,'command':command,'started_at':started,'ended_at':now(),'returncode':returncode,'accepted':accepted,'reason':reason,
        'wall_seconds':time.monotonic()-begin,'metrics':metrics,'followup_metrics':follow,'before':before,'after':after,'expected_final':expected,'expected_prompt_tokens':expected_tokens}
    write(case+'-execution.json',record)
    (RAW/(case+'-server-fragment.txt')).write_text(server.log.read_bytes()[log_offset:].decode('utf-8',errors='replace'))
    files=['raw/'+p.name for p in RAW.glob(case+'*') if p.is_file()]
    register_result(case,accepted,files,reason)
    print(json.dumps({'case':case,'accepted':accepted,'reason':reason,'duration_s':metrics.get('duration_s') if metrics else None}),flush=True)
    if not accepted:raise RuntimeError(case+': '+str(reason))

def prepare_long(ctx):
    def candidate(rows,text_suffix='Верни только контрольное значение из первой строки.'):
        text='Контрольное значение: LAB_SENTINEL_42.\n'+''.join(f'Строка {i}: нейтральные данные измерения.\n' for i in range(rows))+text_suffix
        messages=[{'role':'user','content':text}]
        _,templ=request('/apply-template',{'messages':messages,'chat_template_kwargs':{'enable_thinking':True}})
        _,tokens=request('/tokenize',{'content':templ['prompt'],'add_special':False,'parse_special':True})
        return messages,templ['prompt'],len(tokens['tokens'])
    low,high,best=0,ctx,None
    while low<=high:
        mid=(low+high)//2;messages,prompt,count=candidate(mid)
        if count<=ctx-4096:best=(messages,prompt,count,mid);low=mid+1
        else:high=mid-1
    assert best and best[2]>ctx-4192
    messages,prompt,count,rows=best
    payload=json.loads((RAW/'chat-stream-request.json').read_text());payload.update(messages=messages,max_tokens=2048)
    write(f'ctx{ctx}-long-request.json',payload);(RAW/f'ctx{ctx}-long-prompt.txt').write_text(prompt)
    write(f'ctx{ctx}-long-count.json',{'context':ctx,'input_tokens':count,'input_budget':ctx-4096,'rows':rows,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'output_cap':2048})
    cancel_messages,cancel_prompt,cancel_count=candidate(max(0,rows-2),'Выводи последовательность натуральных чисел через пробел без остановки.')
    cancel=copy.deepcopy(payload);cancel.update(messages=cancel_messages,max_tokens=4096,ignore_eos=True)
    assert cancel_count+4096<=ctx
    write(f'ctx{ctx}-cancel-request.json',cancel);write(f'ctx{ctx}-cancel-count.json',{'input_tokens':cancel_count,'context':ctx,'output_cap':4096})
    overflow=copy.deepcopy(payload);text=messages[0]['content']
    for _ in range(8):
        text+='\n'+text;overflow['messages'][0]['content']=text
        _,templ=request('/apply-template',{'messages':overflow['messages'],'chat_template_kwargs':{'enable_thinking':True}})
        _,tokens=request('/tokenize',{'content':templ['prompt'],'add_special':False,'parse_special':True})
        overcount=len(tokens['tokens'])
        if overcount>ctx:break
    else:raise RuntimeError('Overflow construction failed')
    overflow.update(max_tokens=128,stream=False);overflow.pop('stream_options',None)
    write(f'ctx{ctx}-overflow-request.json',overflow);write(f'ctx{ctx}-overflow-count.json',{'input_tokens':overcount,'context':ctx,'output_cap':128})
    return count

def cancel(server):
    ctx=server.ctx;case=f'ctx{ctx}-cancel';start=time.monotonic();observations=[]
    command=['curl','--noproxy','*','--no-buffer','--max-time','1','-sS','-H','Content-Type: application/json','--data-binary','@'+str(RAW/f'ctx{ctx}-cancel-request.json'),URL+'/v1/chat/completions']
    offset=server.log.stat().st_size;client_done=threading.Event();client={}
    def watch(process):
        client['exit_code']=process.wait();client['ended_monotonic']=time.monotonic();client['ended_at']=now();client_done.set()
    with (RAW/(case+'.sse')).open('xb') as stdout,(RAW/(case+'-curl.txt')).open('x') as stderr:
        process=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        watcher=threading.Thread(target=watch,args=(process,),daemon=True);watcher.start()
        while not client_done.is_set():
            began=time.monotonic();alive_at_start=not client_done.is_set()
            try:
                status,slots=request('/slots',timeout=2)
                observations.append({'request_elapsed_s':began-start,'elapsed_s':time.monotonic()-start,'client_alive_at_request':alive_at_start,'client_alive':not client_done.is_set(),'slots':slots})
            except Exception as e:observations.append({'elapsed_s':time.monotonic()-start,'error':str(e)})
            client_done.wait(.05)
        watcher.join(timeout=3)
    ended=client['ended_monotonic'];idle=False;released=None;release_timeout=60
    while time.monotonic()-ended<release_timeout:
        _,slots=request('/slots',timeout=2);received=time.monotonic()
        observations.append({'elapsed_s':received-start,'client_alive':False,'slots':slots})
        if slots and not any(slot['is_processing'] for slot in slots):idle=True;released=received;break
        time.sleep(.05)
    log=server.log.read_bytes()[offset:].decode('utf-8',errors='replace');(RAW/(case+'-server-fragment.txt')).write_text(log)
    active=[o for o in observations if o.get('client_alive') and any(s.get('is_processing') for s in o.get('slots',[]))]
    done=b'[DONE]' in (RAW/(case+'.sse')).read_bytes()
    cancellation_ids=re.findall(r'cancel task, id_task = ([0-9]+)',log)
    canceled_log=bool(cancellation_ids) and 'stop processing' in log and 'all slots are idle' in log
    release_after=None if released is None else released-ended
    accepted=client['exit_code']==28 and not done and bool(active) and idle and release_after<=release_timeout and canceled_log
    write(case+'-execution.json',{'case':case,'timestamp':now(),'command':command,'exit_code':client['exit_code'],'client_exit_observed_at':client['ended_at'],'client_wall_seconds':ended-start,'client_exit_elapsed_s':ended-start,'release_timeout_seconds':release_timeout,'done_received':done,'active_slot_observed':bool(active),'idle_after':idle,'release_after_client_s':release_after,'server_cancellation_log':canceled_log,'canceled_task_ids':cancellation_ids,'observations':observations,'accepted':accepted})
    register_result(case,accepted,['raw/'+p.name for p in RAW.glob(case+'*') if p.is_file()],None if accepted else 'Cancellation/slot release not fully proven within registered60s')
    if not accepted:raise RuntimeError('Cancel inconclusive')
    probe(server,f'ctx{ctx}-cancel-recovery',RAW/'chat-request.json','LAB_READY')

def overflow(server):
    ctx=server.ctx;case=f'ctx{ctx}-overflow';payload=json.loads((RAW/(case+'-request.json')).read_text());start=time.monotonic()
    try:status,response=request('/v1/chat/completions',payload,timeout=30)
    except urllib.error.HTTPError as e:status=e.code;response=e.read().decode()
    accepted=400<=status<500 and bool(re.search(r'context|exceed|too (?:large|long)',str(response),re.I))
    write(case+'-execution.json',{'case':case,'timestamp':now(),'status':status,'response':response,'wall_seconds':time.monotonic()-start,'accepted':accepted})
    register_result(case,accepted,[f'raw/{case}-execution.json',f'raw/{case}-request.json',f'raw/{case}-count.json'],None if accepted else 'Overflow not rejected by context limit')
    probe(server,f'ctx{ctx}-overflow-recovery',RAW/'chat-request.json','LAB_READY')
    if not accepted:raise RuntimeError('Overflow admission failed')

def context(ctx):
    assert ctx==32768,'This registered session is only a scoped32K qualification'
    prior=json.loads((RAW/'prior-diagnostic-diagnostic-summary.json').read_text())
    assert prior['diagnostic_condition_admission']['budget128'] and prior['context_tokens']==32768
    server=Server(ctx)
    try:
        server.ready();count=prepare_long(ctx)
        for kind in ['chat','chat-stream','tool','tool-stream','long']:
            fixture=RAW/(f'ctx{ctx}-long-request.json' if kind=='long' else kind+'-request.json')
            for repeat in ['warmup','r1','r2','r3']:
                probe(server,f'ctx{ctx}-{kind}-{repeat}',fixture,'LAB_SENTINEL_42' if kind=='long' else 'LAB_VALUE_42' if kind.startswith('tool') else 'LAB_READY',tool=kind.startswith('tool'),expected_tokens=count if kind=='long' else None)
        cancel(server);overflow(server)
        print('context admitted',ctx,flush=True)
    finally:server.shutdown()

if __name__=='__main__':
    if sys.argv[1]=='preflight':preflight()
    else:context(int(sys.argv[1]))
