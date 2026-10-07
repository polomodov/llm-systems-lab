import json,os,pathlib,signal,socket,subprocess,time
import lab32_runner as lab
raw=pathlib.Path(__file__).resolve().parent
case='shutdown-single-signal-diagnostic'
assert lab.safe(lab.sample())
with socket.socket() as test:test.bind(('127.0.0.1',8080))
command=json.loads((raw/'ctx8192-server-execution.json').read_text())['command']
record={'case':case,'command':command,'started_at':lab.now(),'before':lab.sample()}
with (raw/'single-signal-server.txt').open('x') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'no_proxy':'127.0.0.1,localhost,::1'})
    server_pid=None
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
        else:raise RuntimeError('Server not ready')
        request=json.loads((raw/'chat-request.json').read_text())
        status,response=lab.request('/v1/chat/completions',request)
        lab.write('single-signal-chat-response.json',response)
        assert status==200 and response['choices'][0]['message']['content'].strip()=='LAB_READY'
        _,slots=lab.request('/slots');assert not any(slot['is_processing'] for slot in slots)
        record.update(server_pid=server_pid,time_pid=process.pid,signal_target='verified owned llama-server child only')
        os.kill(server_pid,signal.SIGINT)
        process.wait(timeout=20)
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        record['returncode']=process.returncode
record['after']=lab.sample();record['ended_at']=lab.now()
text=(raw/'single-signal-server.txt').read_text()
record['accepted']=record['returncode']==0 and 'Received second interrupt' not in text and 'GGML_ASSERT' not in text and lab.safe(record['after'])
lab.write('single-signal-execution.json',record)
lab.register_result(case,record['accepted'],['raw/single-signal-execution.json','raw/single-signal-server.txt','raw/single-signal-chat-response.json'],None if record['accepted'] else 'Native single-signal shutdown failed')
print(json.dumps({k:record[k] for k in ['returncode','accepted','signal_target']},indent=2))
if not record['accepted']:raise SystemExit(1)
