import datetime
import importlib.util
import json
import os
import pathlib
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

raw = pathlib.Path(__file__).resolve().parent
manifest_path = raw.parent/'manifest.json'
assert next(a for a in json.loads(manifest_path.read_text())['planned_attempts'] if a['id']=='r3')['status']=='completed'
# Import only the bounded telemetry function, not the CLI case driver.
namespace = dict(datetime=datetime,json=json,re=re,subprocess=subprocess)
source = (raw/'run_case.py').read_text().split('def sample():',1)[1].split('\nbefore=sample()',1)[0]
exec('def sample():'+source, namespace)
sample = namespace['sample']
with socket.socket() as test:
    test.bind(('127.0.0.1',8081))
python = '/Users/lab/local-model-lab-artifacts/engines/mlx-lm/0.32.0-mlx-0.32.3/venv/bin/python'
model = '/Users/lab/local-model-lab-artifacts/mlx-community/Qwen3.5-9B-MLX-4bit/938d8919941c6e7efd3c7150eff7fe9d12afa631'
command = ['/usr/bin/time','-l',python,str(raw/'server_entry.py'),'server','--model',model,
    '--host','127.0.0.1','--port','8081','--max-tokens','64','--temp','0',
    '--chat-template-args','{"enable_thinking":false}','--decode-concurrency','1','--prompt-concurrency','1']
cache = pathlib.Path('/Users/lab/local-model-lab-artifacts/engines/mlx-lm/0.32.0-mlx-0.32.3/offline-hf/hub')
cache.mkdir(parents=True,exist_ok=True)
env = os.environ.copy()
env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
    TOKENIZERS_PARALLELISM='false',HF_HUB_CACHE=str(cache),no_proxy='127.0.0.1,localhost,::1')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
before = sample()
assert before['free_pages_bytes']>=16*2**30 and before['swap_used_bytes']==0 and before['on_ac_power'] and before['ac_power_mode']==0
(raw/'server-memory-before.json').write_text(json.dumps(before,indent=2)+'\n')
record = dict(command=command,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    environment={k:env[k] for k in ['HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','HF_HUB_CACHE']},
    readiness_attempts=[],returncode=None,stop_reason=None,shutdown_method=None)
(raw/'server-execution.json').write_text(json.dumps(record,indent=2)+'\n')
accepted = False
start = time.monotonic()
with (raw/'server.txt').open('x') as stdout,(raw/'server-process.txt').open('x') as stderr,(raw/'server-memory.jsonl').open('x') as timeline:
    process = subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
    try:
        ready = False
        while time.monotonic()-start<120:
            if process.poll() is not None:raise RuntimeError('Server exited before readiness')
            current = sample();timeline.write(json.dumps(current)+'\n');timeline.flush()
            if current['swap_used_bytes']>before['swap_used_bytes'] or current['free_pages_bytes']<16*2**30 or not current['on_ac_power'] or current['ac_power_mode']!=0:
                raise RuntimeError('Server memory/power admission failed')
            try:
                request_start = time.monotonic()
                with opener.open('http://127.0.0.1:8081/v1/models',timeout=5) as response:
                    status = response.status;body = response.read().decode()
                (raw/'server-models.json').write_text(body+'\n')
                record['readiness_attempts'].append(dict(status=status,wall_seconds=time.monotonic()-request_start))
                models = json.loads(body)
                assert status==200 and any(x['id']==model for x in models['data'])
                ready = True;break
            except (urllib.error.URLError,TimeoutError,ConnectionError) as error:
                record['readiness_attempts'].append(dict(error=type(error).__name__))
            time.sleep(2)
        if not ready:raise RuntimeError('Readiness timeout')
        body = {'model':model,'messages':[{'role':'user','content':(raw/'prompt.txt').read_text().strip()}],
                'temperature':0,'max_tokens':64,'seed':1,'stream':False,'chat_template_kwargs':{'enable_thinking':False}}
        (raw/'server-chat-request.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
        request = urllib.request.Request('http://127.0.0.1:8081/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        request_start = time.monotonic()
        with opener.open(request,timeout=120) as response:
            status = response.status;response_body = response.read().decode()
        record['chat_http_status'] = status;record['chat_wall_seconds'] = time.monotonic()-request_start
        (raw/'server-chat-response.json').write_text(response_body+'\n')
        parsed = json.loads(response_body)
        record['response_model'] = parsed['model'];record['usage'] = parsed.get('usage');record['finish_reason'] = parsed['choices'][0].get('finish_reason')
        assert status==200 and parsed['choices'][0]['message']['content'] and parsed['model']==model
        accepted = True
        after_chat = sample();timeline.write(json.dumps(after_chat)+'\n');timeline.flush()
        assert after_chat['swap_used_bytes']==0 and after_chat['free_pages_bytes']>=16*2**30 and after_chat['on_ac_power'] and after_chat['ac_power_mode']==0
    except Exception as error:
        accepted = False;record['stop_reason'] = type(error).__name__+': '+str(error)
    finally:
        if process.poll() is None:
            record['shutdown_method'] = 'SIGINT to owned process group'
            os.killpg(process.pid,signal.SIGINT)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                record['shutdown_method'] += '; SIGKILL after20s';os.killpg(process.pid,signal.SIGKILL);process.wait();accepted=False
        record['returncode'] = process.wait()
record.update(ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),total_wall_seconds=time.monotonic()-start)
record['after'] = sample();(raw/'server-memory-after.json').write_text(json.dumps(record['after'],indent=2)+'\n')
log = (raw/'server-process.txt').read_text();rss = re.search(r'(\d+)\s+maximum resident set size',log)
record['max_rss_bytes'] = int(rss[1]) if rss else None
try:
    device = json.loads((raw/'server-device-after.json').read_text())
except (OSError,ValueError):device={}
record['runtime_peak_memory_bytes'] = device.get('peak_memory_bytes')
record['gpu_confirmed'] = device.get('default_device')=='Device(gpu, 0)' and device.get('device',{}).get('device_name')=='Apple M5 Max' and device.get('peak_memory_bytes',0)>2**30
record['accepted'] = accepted and record['gpu_confirmed'] and record['after']['swap_used_bytes']==0 and record['runtime_peak_memory_bytes']<=24*2**30 and record['max_rss_bytes'] is not None and record['max_rss_bytes']<=24*2**30
(raw/'server-execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
manifest = json.loads(manifest_path.read_text());attempt = next(a for a in manifest['planned_attempts'] if a['id']=='server-smoke')
attempt.update(status='completed' if record['accepted'] else 'failed',reason=None if record['accepted'] else record['stop_reason'] or 'Server smoke failed admission',evidence_files=['raw/'+p.name for p in raw.glob('server*') if p.is_file()])
manifest['evidence_files'] = sorted('raw/'+p.name for p in raw.iterdir() if p.is_file());manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
if not record['accepted']:sys.exit(1)
