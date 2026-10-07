"""One registered native Metal case with bounded execution and memory observations."""
import datetime,json,os,pathlib,re,signal,subprocess,sys,time
raw=pathlib.Path(__file__).resolve().parent
case=sys.argv[1]
registered=json.loads((raw.parent/'manifest.json').read_text())
if case not in {a['id'] for a in registered['planned_attempts']}:raise ValueError('Case not registered')
binary='/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a/build-metal-arm64/bin/llama-bench'
model='/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf'
if case=='smoke':workload=['-p','512','-n','64']
elif case=='warmup-pp' or case.startswith('pp-'):workload=['-p','2048','-n','0']
elif case=='warmup-tg' or case.startswith('tg-'):workload=['-p','0','-n','128','-d','4096']
else:raise ValueError('Unregistered case')
command=['/usr/bin/time','-l',binary,'-m',model,'-ngl','999','-t','8','-b','512','-ub','256',
 '-ctk','f16','-ctv','f16','-fa','1','-v']+workload+['-r','1','-o','json']

def sample():
    value={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':{}}
    for label,args in [('vm_stat',['vm_stat']),('swap',['sysctl','vm.swapusage']),('pressure',['memory_pressure','-Q']),('power_source',['pmset','-g','batt']),('power_mode',['pmset','-g','custom'])]:
        p=subprocess.run(args,capture_output=True,text=True,timeout=10)
        value['commands'][label]={'argv':args,'exit_code':p.returncode,'stdout':re.sub(r'\(id=\d+\)','(battery identity omitted)',p.stdout),'stderr':p.stderr}
    memory=value['commands']['vm_stat']['stdout'];swap=value['commands']['swap']['stdout']
    pages=re.search(r'page size of (\d+) bytes',memory);free=re.search(r'Pages free:\s+(\d+)',memory)
    used=re.search(r'used = ([0-9.]+)([KMG])',swap)
    value['free_pages_bytes']=int(pages[1])*int(free[1]) if pages and free else None
    value['swap_used_bytes']=int(float(used[1])*{'K':1024,'M':1024**2,'G':1024**3}[used[2]]) if used else None
    value['on_ac_power']="Now drawing from 'AC Power'" in value['commands']['power_source']['stdout']
    ac=value['commands']['power_mode']['stdout'].split('AC Power:',1)[-1]
    mode=re.search(r'powermode\s+(\d+)',ac)
    value['ac_power_mode']=int(mode[1]) if mode else None
    return value

before=sample();(raw/(case+'-memory-before.json')).write_text(json.dumps(before,indent=2)+'\n')
if before['free_pages_bytes'] is None or before['swap_used_bytes'] is None or before['free_pages_bytes']<16*2**30 or not before['on_ac_power'] or before['ac_power_mode']!=0:
    raise SystemExit('Memory admission failed before execution')
record={'case':case,'command':command,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'returncode':None,'stop_reason':None,'memory_sample_interval_seconds':2,'timeout_seconds':600}
(raw/(case+'-execution.json')).write_text(json.dumps(record,indent=2)+'\n')
start=time.monotonic()
with (raw/(case+'-bench.json')).open('x') as stdout, (raw/(case+'-process.txt')).open('x') as stderr, (raw/(case+'-memory.jsonl')).open('x') as timeline:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
    while process.poll() is None:
        current=sample();timeline.write(json.dumps(current)+'\n');timeline.flush()
        if current['swap_used_bytes'] is not None and current['swap_used_bytes']>before['swap_used_bytes']:
            record['stop_reason']='Swap usage increased'
        if current['free_pages_bytes'] is not None and current['free_pages_bytes']<16*2**30:
            record['stop_reason']='Free pages below registered 16 GiB floor'
        if not current['on_ac_power'] or current['ac_power_mode']!=0:record['stop_reason']='Registered AC power condition changed'
        if time.monotonic()-start>600:record['stop_reason']='Registered timeout exceeded'
        if record['stop_reason']:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            break
        time.sleep(2)
    record['returncode']=process.wait()
record['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
record['observed_wall_seconds']=time.monotonic()-start
record['after']=sample();(raw/(case+'-memory-after.json')).write_text(json.dumps(record['after'],indent=2)+'\n')
log=(raw/(case+'-process.txt')).read_text()
rss=re.search(r'(\d+)\s+maximum resident set size',log)
wall=re.search(r'([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys',log)
record['max_rss_bytes']=int(rss[1]) if rss else None
record['time_wall_seconds']=float(wall[1]) if wall else None
record['gpu_log_confirmed']='ggml_metal' in log
record['tensor_api_supported']='has tensor            = true' in log
try:
    rows=json.loads((raw/(case+'-bench.json')).read_text())
    record['benchmark_rows']=rows
    expected=[(512,0,0),(0,64,0)] if case=='smoke' else [(2048,0,0)] if 'pp' in case else [(0,128,4096)]
    record['workload_confirmed']=[(row['n_prompt'],row['n_gen'],row['n_depth']) for row in rows]==expected and all(row['avg_ts']>0 and row['flash_attn'] is True and row['n_batch']==512 and row['n_ubatch']==256 for row in rows)
    record['metal_backend_confirmed']=bool(rows) and all(any(code in str(row.get('backends',row.get('backend',''))).split(',') for code in ['MTL','Metal']) and row.get('gpu_info')=='Apple M5 Max' and row.get('n_gpu_layers')==999 for row in rows)
except (ValueError,TypeError) as error:
    record['parse_error']=type(error).__name__;record['metal_backend_confirmed']=False
record['offloaded_layers']=re.findall(r'offloaded (\d+)/(\d+) layers to GPU',log)
record['accepted']=record.get('workload_confirmed',False) and bool(record['offloaded_layers']) and all(a==b for a,b in record['offloaded_layers']) and record['returncode']==0 and not record['stop_reason'] and record['metal_backend_confirmed'] and record['gpu_log_confirmed']
(raw/(case+'-execution.json')).write_text(json.dumps(record,indent=2)+'\n')
manifest_path=raw.parent/'manifest.json'
m=json.loads(manifest_path.read_text())
a=next(a for a in m['planned_attempts'] if a['id']==case)
a.update(status='completed' if record['accepted'] else 'failed', reason=None if record['accepted'] else record['stop_reason'] or 'Native result failed admission check', evidence_files=['raw/'+case+suffix for suffix in ['-bench.json','-process.txt','-execution.json','-memory.jsonl','-memory-before.json','-memory-after.json']])
m['evidence_files']=sorted(set(m['evidence_files']+['raw/'+f.name for f in raw.iterdir() if f.is_file()]))
manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'case':case,'returncode':record['returncode'],'accepted':record['accepted'],
    'max_rss_gib':record['max_rss_bytes']/2**30 if record['max_rss_bytes'] else None,
    'benchmark_rows':record.get('benchmark_rows'),'stop_reason':record['stop_reason']},indent=2))
if not record['accepted']:raise SystemExit(1)
