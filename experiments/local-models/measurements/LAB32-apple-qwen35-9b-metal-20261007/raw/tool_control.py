import json,os,pathlib,signal,socket,subprocess,sys,time
import lab32_runner as lab
raw=pathlib.Path(__file__).resolve().parent
mode=sys.argv[1];assert mode in ['fresh-no-thinking','fresh-thinking-auto','fresh-thinking-auto-retry']
case='control-'+mode
assert lab.safe(lab.sample())
with socket.socket() as test:
    test.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    test.bind(('127.0.0.1',8080))
command=json.loads((raw/'ctx8192-server-execution.json').read_text())['command']
payload=json.loads((raw/'tool-request.json').read_text())
if mode.startswith('fresh-thinking-auto'):
    command[command.index('--reasoning')+1]='auto'
    command[command.index('--chat-template-kwargs')+1]='{"enable_thinking":true}'
    payload['chat_template_kwargs']['enable_thinking']=True
lab.write(case+'-request.json',payload)
record={'case':case,'command':command,'started_at':lab.now(),'before':lab.sample(),'error':None,'accepted':False}
server_pid=None
with (raw/(case+'-server.txt')).open('x') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'no_proxy':'127.0.0.1,localhost,::1'})
    try:
        start=time.monotonic()
        while time.monotonic()-start<120:
            assert process.poll() is None and lab.safe(lab.sample())
            children=subprocess.run(['pgrep','-P',str(process.pid)],capture_output=True,text=True).stdout.split()
            for child in children:
                comm=subprocess.run(['ps','-o','comm=','-p',child],capture_output=True,text=True).stdout.strip()
                if comm.endswith('llama-server'):
                    server_pid=int(child);assert os.getpgid(server_pid)==process.pid
            try:
                status,health=lab.request('/health',timeout=2)
                if status==200 and server_pid:break
            except Exception:pass
            time.sleep(1)
        else:raise RuntimeError('Startup timeout')
        probe=[sys.executable,str(raw/'http_probe.py'),'--url',lab.URL,'--request',str(raw/(case+'-request.json')),'--out',str(raw/case),'--follow-tool']
        record['probe_command']=probe
        with (raw/(case+'-probe.txt')).open('x') as out:
            result=subprocess.run(probe,stdout=out,stderr=subprocess.STDOUT,timeout=180,env={**os.environ,'no_proxy':'127.0.0.1,localhost,::1'})
        record['probe_returncode']=result.returncode
        record['accepted']=result.returncode==0 and json.loads((raw/(case+'.final.json')).read_text())['content'].strip()=='LAB_VALUE_42'
        if not record['accepted']:
            rejection=raw/(case+'.tool-rejected.json')
            record['error']=json.loads(rejection.read_text())['reason'] if rejection.exists() else 'Probe/final rejected'
    except Exception as error:
        record['error']=str(error);record['accepted']=False
    finally:
        if process.poll() is None and server_pid:
            os.kill(server_pid,signal.SIGINT)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait();record['error']='Shutdown timeout';record['accepted']=False
        elif process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait();record['accepted']=False
        record['native_returncode']=process.returncode
record['after']=lab.sample();record['ended_at']=lab.now()
record['accepted']=record['accepted'] and record['native_returncode']==0 and lab.safe(record['after'])
lab.write(case+'-execution.json',record)
lab.register_result(case,record['accepted'],['raw/'+p.name for p in raw.glob(case+'*') if p.is_file()],record['error'] or 'Native/tool admission failed')
print(json.dumps({k:record[k] for k in ['case','accepted','error','probe_returncode','native_returncode'] if k in record},indent=2))
