"""Exercise real lab SDK entry points with loopback-only model fixtures.

Pi transport is redirected by a test fetch shim; all containers have network
none, no mounts, fake auth, and fresh HOME. This never calls a provider.
"""
from pathlib import Path
import sys
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2];NATIVE=BASE.with_name('harbor-native-2026-11')
import argparse,asyncio,hashlib,importlib.util,json,os,shlex,socket,uuid
spec=importlib.util.spec_from_file_location('migration_native_smoke',NATIVE/'offline_smoke.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(condition, message):
 if not condition:raise ValueError(message)

async def main():
 parser=argparse.ArgumentParser();parser.add_argument('--docker-host',required=True);args=parser.parse_args()
 if not args.docker_host.startswith('unix://'):raise ValueError('Local Docker only')
 path=os.environ.get('PATH','/usr/local/bin:/usr/bin:/bin');os.environ.clear();os.environ.update(PATH=path,HOME=str(BASE/'.cache/sdk-host-home'),LITELLM_LOCAL_MODEL_COST_MAP='True')
 Path(os.environ['HOME']).mkdir(parents=True,exist_ok=True)
 def no_ip(event,args):
  if event=='socket.connect' and args[0].family!=socket.AF_UNIX:raise RuntimeError('Host IP connections forbidden')
 sys.addaudithook(no_ip)
 lock=json.loads((NATIVE/'runtime-lock.json').read_text());lab_lock=json.loads((BASE/'lab-runtime-lock.json').read_text());lock['images']=lab_lock['images'];run=BASE/'.cache/sdk-smoke'/uuid.uuid4().hex;run.mkdir(parents=True)
 cases=[('pi','anthropic','claude-sonnet-5-5'),('pi','openai','gpt-6.1-sol'),('mini-swe-agent','openai','gpt-6.1-sol'),('claude-code','anthropic','claude-sonnet-5-5'),('opencode','anthropic','claude-sonnet-5-5'),('codex','openai','gpt-6.1-sol')];results=[]
 for harness,provider,model in cases:
  name='model-refresh-sdk-'+uuid.uuid4().hex;out=run/(harness+'-'+provider);out.mkdir()
  env={'HOME':'/home/agent','OPENAI_API_KEY':'offline-fixture-not-a-secret','ANTHROPIC_API_KEY':'offline-fixture-not-a-secret','ANTHROPIC_BASE_URL':'http://127.0.0.1:8768','CODEX_API_KEY':'offline-fixture-not-a-secret','OPENAI_API_BASE':'http://127.0.0.1:8768/v1','OPENAI_BASE_URL':'http://127.0.0.1:8768/v1','LITELLM_LOCAL_MODEL_COST_MAP':'True','MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT':'1'}
  e=s.OfflineEnvironment(name,args.docker_host,env);record={'harness':harness,'provider':provider,'model':model,'status':'failed','image_id':lock['images'][harness]['image_id'],'raw_directory':str(out.relative_to(BASE)),'provider_requests':0}
  try:
   r=await e.docker('run','-d','--rm','--pull=never','--name',name,'--network','none','--user','1000:1000','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','DAC_OVERRIDE','--cap-add','FOWNER','--security-opt','no-new-privileges','--cpus','1','--memory','2g','--entrypoint','sleep',record['image_id'],'infinity');require(r.return_code==0, r.stderr)
   metadata=await e.docker('inspect',name,'--format','{{json .Mounts}} {{json .HostConfig.NetworkMode}}');require(metadata.stdout.strip()=='[] "none"', 'SDK qualification check failed')
   r=await e.exec('mkdir -p /control; chown 1000:1000 /control',user='root');require(r.return_code==0, r.stderr)
   await e.upload_file(NATIVE/'task/environment/input.json','/app/input.json')
   await e.upload_file(NATIVE/'mock-provider.mjs','/control/mock-provider.mjs')
   await e.exec('node /control/mock-provider.mjs > /logs/agent/mock-server.log 2>&1 &');await asyncio.sleep(0.2)
   launch={'model':model if harness=='pi' else provider+'/'+model,'provider':provider,'turns':8,'prompt':(NATIVE/'task/instruction.md').read_text()}
   sources=['run.mjs','adapter.mjs'] if harness=='pi' else (['run.py'] if harness=='mini-swe-agent' else [])
   for f in sources:await e.upload_file(ROOT/'experiments'/harness/f,'/control/'+f)
   if harness=='pi':
    shim=out/'fetch-shim.mjs';shim.write_text("const nativeFetch=globalThis.fetch;globalThis.fetch=(url,options)=>nativeFetch('http://127.0.0.1:8768'+new URL(typeof url==='string'?url:(url.url??url.href)).pathname,options);await import('/control/run.mjs');\n")
    await e.upload_file(shim,'/control/fetch-shim.mjs');cmd=['node','/control/fetch-shim.mjs',json.dumps(launch)]
   elif harness=='mini-swe-agent':cmd=['/home/agent/.local/share/uv/tools/mini-swe-agent/bin/python','/control/run.py',json.dumps(launch)]
   else:
    import subprocess
    js="import {buildCommand} from "+json.dumps(str(ROOT/'experiments'/harness/'adapter.mjs'))+";console.log(JSON.stringify(buildCommand("+json.dumps({'model':model,'provider':provider,'turns':None if harness=='codex' else 8,'budget':None,'prompt':launch['prompt']})+")));"
    built=json.loads(subprocess.check_output(['node','--input-type=module','-e',js],text=True));e.extra_env.update(built['env']);cmd=built['command']
    if harness=='codex':cmd=cmd[:-2]+['-c','model_provider="fixture"','-c','model_providers.fixture={name="Offline fixture",base_url="http://127.0.0.1:8768/v1",env_key="CODEX_API_KEY",wire_api="responses"}']+cmd[-2:]
    if harness=='claude-code':await e.upload_file(ROOT/'experiments/claude-code/settings.example.json','/control/settings.json')
    if harness=='opencode':
     await e.upload_file(ROOT/'experiments/opencode/opencode.json','/control/opencode.json')
     config=json.loads(e.extra_env['OPENCODE_CONFIG_CONTENT']);config['provider']['anthropic']['options']={'baseURL':'http://127.0.0.1:8768/v1'};e.extra_env['OPENCODE_CONFIG_CONTENT']=json.dumps(config)
   r=await e.exec(shlex.join(cmd),timeout_sec=100);(out/'stdout.jsonl').write_text(r.stdout);(out/'stderr.txt').write_text(r.stderr);require(r.return_code==0, r.stderr)
   artifact=await e.exec('cat /app/output/result.json; cat /app/output/model-tool.json');rows=artifact.stdout.splitlines();require(artifact.return_code==0 and json.loads(rows[0])==json.loads((NATIVE/'task/tests/expected.json').read_text()), 'SDK qualification check failed');require(json.loads(rows[1])['uid']==1000, 'SDK qualification check failed')
   await e.download_dir('/logs/agent',out/'agent')
   requests=[json.loads(l) for l in (out/'agent/mock-requests.jsonl').read_text().splitlines()];require(len(requests)>=2 and {r['model'] for r in requests}=={model}, 'SDK qualification check failed')
   require(not (out/'agent/mock-rejections.jsonl').exists(), 'Strict request validator rejected SDK call')
   if provider=='openai':require({r['path'] for r in requests}=={'/v1/responses'}, 'SDK qualification check failed')
   # Parse through the actual lab normalizer, retaining fixture-only usage.
   js="import fs from 'node:fs';import {parseTrace} from "+json.dumps(str(ROOT/'experiments'/harness/'adapter.mjs'))+";console.log(JSON.stringify(parseTrace(fs.readFileSync(0,'utf8'))));"
   import subprocess
   parsed=subprocess.run(['node','--input-type=module','-e',js],input=r.stdout,text=True,capture_output=True,check=True)
   trace=json.loads(parsed.stdout);require(trace['stopReason'] not in ['error','trace_incomplete','RepeatedFormatError'], 'SDK qualification check failed');(out/'parsed.json').write_text(json.dumps(trace,indent=2)+'\n')
   record.update(status='passed',fixture_calls=len(requests),request_settings=[r['settings'] for r in requests],parsed=trace,synthetic_usage_not_billing=True,transport_deviation='Fixture-only transport: Pi fetch redirection, mini/Claude API-base env, OpenCode provider baseURL, Codex CLI provider base_url; no real provider route qualification')
  except Exception as error:record['error']=str(error) or type(error).__name__
  finally:
   try:await e.download_dir('/logs/agent',out/'agent')
   except Exception as error:record['log_collection_error']=str(error)
   removed=await e.docker('rm','-f',name);record['cleanup_confirmed']=removed.return_code==0 or 'No such container' in removed.stderr
   if not record['cleanup_confirmed']:record['status']='failed'
  record['raw_sha256']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()};results.append(record);print(json.dumps(record),flush=True)
 report={'schema_version':1,'kind':'lab-sdk-model-migration-offline-fixture','provider_requests':0,'credentials_read':False,'runtime_lock_sha256':sha(NATIVE/'runtime-lock.json'),'lab_runtime_lock_sha256':sha(BASE/'lab-runtime-lock.json'),'sources_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'experiments/pi/run.mjs',ROOT/'experiments/pi/adapter.mjs',ROOT/'experiments/mini-swe-agent/run.py',ROOT/'experiments/mini-swe-agent/adapter.mjs',ROOT/'experiments/claude-code/adapter.mjs',ROOT/'experiments/opencode/adapter.mjs',ROOT/'experiments/codex/adapter.mjs',NATIVE/'mock-provider.mjs']},'cases':results}
 (BASE/'sdk-smoke-evidence.json').write_text(json.dumps(report,indent=2)+'\n');return 0 if all(r['status']=='passed' for r in results) else 1
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
