import datetime,json,os,pathlib,re,signal,subprocess,sys,time
raw=pathlib.Path(__file__).resolve().parent
case=sys.argv[1]
manifest_path=raw.parent/'manifest.json'
registered=json.loads(manifest_path.read_text())
assert case in {'warmup','r1','r2','r3'} and case in {a['id'] for a in registered['planned_attempts']}
python='/Users/lab/local-model-lab-artifacts/engines/mlx-lm/0.32.0-mlx-0.32.3/venv/bin/python'
model='/Users/lab/local-model-lab-artifacts/mlx-community/Qwen3.5-9B-MLX-4bit/938d8919941c6e7efd3c7150eff7fe9d12afa631'
prompt=(raw/'prompt.txt').read_text().strip()
command=['/usr/bin/time','-l',python,str(raw/'cli_entry.py'),case,'generate','--model',model,'--prompt',prompt,'--max-tokens','128','--temp','0','--seed','1','--chat-template-config','{"enable_thinking":false}']
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
assert before['free_pages_bytes'] is not None and before['free_pages_bytes']>=16*2**30 and before['swap_used_bytes']==0 and before['on_ac_power'] and before['ac_power_mode']==0, 'Memory/power admission failed'
env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
record={'case':case,'command':command,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'returncode':None,'stop_reason':None,'sample_interval_seconds':2,'timeout_seconds':600,'environment':{k:env[k] for k in ['HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','TOKENIZERS_PARALLELISM']}}
(raw/(case+'-execution.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
start=time.monotonic()
with (raw/(case+'-generate.txt')).open('x') as stdout,(raw/(case+'-process.txt')).open('x') as stderr,(raw/(case+'-memory.jsonl')).open('x') as timeline:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
    while process.poll() is None:
        current=sample();timeline.write(json.dumps(current)+'\n');timeline.flush()
        if process.poll() is not None:break
        if current['swap_used_bytes'] is not None and current['swap_used_bytes']>before['swap_used_bytes']:record['stop_reason']='Swap growth'
        if current['free_pages_bytes'] is not None and current['free_pages_bytes']<16*2**30:record['stop_reason']='Free-page floor'
        if not current['on_ac_power'] or current['ac_power_mode']!=0:record['stop_reason']='Power condition changed'
        if time.monotonic()-start>600:record['stop_reason']='Timeout'
        # Observe interpreter RSS while it runs, in addition to macOS time's final peak.
        children=subprocess.run(['pgrep','-P',str(process.pid)],capture_output=True,text=True)
        rss=[]
        for pid in children.stdout.split():
            p=subprocess.run(['ps','-o','rss=','-p',pid],capture_output=True,text=True)
            if p.stdout.strip().isdigit():rss.append(int(p.stdout.strip())*1024)
        if rss and max(rss)>24*2**30:record['stop_reason']='Observed process RSS ceiling'
        if record['stop_reason']:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            break
        time.sleep(2)
    record['returncode']=process.wait()
record['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();record['observed_wall_seconds']=time.monotonic()-start
record['after']=sample();(raw/(case+'-memory-after.json')).write_text(json.dumps(record['after'],indent=2)+'\n')
text=(raw/(case+'-generate.txt')).read_text();log=(raw/(case+'-process.txt')).read_text()
prompt_stats=re.search(r'Prompt: (\d+) tokens, ([0-9.]+) tokens-per-sec',text)
gen_stats=re.search(r'Generation: (\d+) tokens, ([0-9.]+) tokens-per-sec',text)
peak=re.search(r'Peak memory: ([0-9.]+) GB',text)
rss=re.search(r'(\d+)\s+maximum resident set size',log);wall=re.search(r'([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys',log)
record.update(prompt_tokens=int(prompt_stats[1]) if prompt_stats else None,prompt_tokens_per_second=float(prompt_stats[2]) if prompt_stats else None,
 output_tokens=int(gen_stats[1]) if gen_stats else None,generation_tokens_per_second=float(gen_stats[2]) if gen_stats else None,
 reported_peak_memory_gb=float(peak[1]) if peak else None,max_rss_bytes=int(rss[1]) if rss else None,time_wall_seconds=float(wall[1]) if wall else None)
parts=text.split('==========');record['generated_text']=parts[1].strip() if len(parts)>=3 else None
try:device=json.loads((raw/(case+'-device.json')).read_text())
except (OSError,ValueError):device={}
record['gpu_confirmed']=device.get('default_device')=='Device(gpu, 0)' and device.get('default_device_after')=='Device(gpu, 0)' and device.get('device',{}).get('device_name')=='Apple M5 Max' and device.get('peak_memory_bytes',0)>2**30
record['runtime_peak_memory_bytes']=device.get('peak_memory_bytes')
expected=json.loads((raw/'tokenizer-runtime.json').read_text())['prompt_token_count']
record['accepted']=record['returncode']==0 and not record['stop_reason'] and record['gpu_confirmed'] and record['prompt_tokens']==expected and record['output_tokens'] is not None and 0<record['output_tokens']<=128 and record['generation_tokens_per_second']>0 and bool(record['generated_text']) and record['runtime_peak_memory_bytes']<=24*2**30 and record['max_rss_bytes'] is not None and record['max_rss_bytes']<=24*2**30 and record['after']['swap_used_bytes']==0
(raw/(case+'-execution.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
m=json.loads(manifest_path.read_text());a=next(a for a in m['planned_attempts'] if a['id']==case);a.update(status='completed' if record['accepted'] else 'failed',reason=None if record['accepted'] else record['stop_reason'] or 'Native result failed admission',evidence_files=['raw/'+case+s for s in ['-generate.txt','-process.txt','-execution.json','-device.json','-memory.jsonl','-memory-before.json','-memory-after.json'] if (raw/(case+s)).exists()])
m['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file());manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['case','returncode','accepted','prompt_tokens','output_tokens','prompt_tokens_per_second','generation_tokens_per_second','runtime_peak_memory_bytes','max_rss_bytes','time_wall_seconds','generated_text','stop_reason']},ensure_ascii=False,indent=2))
if not record['accepted']:raise SystemExit(1)
