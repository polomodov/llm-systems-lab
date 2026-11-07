"""Prepare pinned public CLI packages, then freeze/probe runtime images offline.

Only npm installation preparation uses public registry networking. No credentials
or model endpoints are used. Final image assembly/probes use network none.
"""
import sys
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
sys.path=[p for p in sys.path if Path(p).resolve()!=BASE]
import hashlib,importlib.util,json,os,shutil,subprocess
from datetime import datetime,timezone
OLD=BASE.with_name('harbor-native-pilot')
spec=importlib.util.spec_from_file_location('frozen_image_helpers',OLD/'build-images.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
D=['docker','--context','colima']
CACHE=BASE/'.cache/builds';CACHE.mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):return subprocess.check_output(args,text=True).strip()
def build(name,base,dockerfile,files,network):
 alias='model-refresh-input/'+name+':'+base.removeprefix('sha256:');subprocess.run(D+['tag',base,alias],check=True)
 assert json.loads(run(D+['image','inspect',alias]))[0]['Id']==base
 context=CACHE/name;context.mkdir(exist_ok=True)
 for dest,source in files.items():shutil.copyfile(source,context/dest)
 (context/'Dockerfile').write_text(dockerfile)
 tag='model-refresh-2026-11/'+name+':frozen'
 r=subprocess.run(D+['build','--network',network,'--pull=false','--build-arg','BASE_IMAGE='+alias,'-t',tag,str(context)],capture_output=True,text=True,env={**os.environ,'DOCKER_BUILDKIT':'0'},timeout=600)
 (CACHE/(name+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('Build failed: '+name+'; inspect local build log')
 image=json.loads(run(D+['image','inspect',tag]))[0]
 print(json.dumps({'built':name,'image_id':image['Id']}),flush=True)
 return {'image_id':image['Id'],'tag':tag,'base_image_id':base,'platform':'linux/arm64','container_config':{k:image['Config'].get(k) for k in ['User','WorkingDir','Entrypoint','Cmd']}}

def main():
 old=json.loads((OLD/'runtime-lock.json').read_text());old_evidence=json.loads((OLD/'runtime-evidence.json').read_text())
 pins={'claude-code':('@anthropic-ai/claude-code','claude --version'),'codex':('@openai/codex','codex --version'),'opencode':('opencode-ai','opencode --version')}
 images={};evidence={};inventories={};registry={};sources=[Path(__file__),ROOT/'experiments/pi/model-refresh.mjs',BASE/'runtime/pi/models.json',BASE/'runtime/pi/settings.json',OLD/'build-images.py']
 for name,row in old['images'].items():
  sources.append(ROOT/'experiments'/name/'harness.json')
  version=json.loads((ROOT/'experiments'/name/'harness.json').read_text())['version'];base=row['image_id'];files={};steps=''
  if name in pins and version != row['version']:
   package,version_cmd=pins[name];registry[name]=json.loads(run(['/Users/apolomodov/.local/bin/mise','exec','--','npm','view',package+'@'+version,'dist','--json']))
   script_flag='--ignore-scripts' if name=='codex' else ''
   recipe='ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nUSER root\nRUN npm install --global '+script_flag+' '+package+'@'+version+' && '+version_cmd+'\nUSER 1000:1000\n'
   (BASE/'images').mkdir(exist_ok=True);(BASE/'images'/(name+'-package.Dockerfile')).write_text(recipe);sources.append(BASE/'images'/(name+'-package.Dockerfile'))
   base=build(name+'-package',base,recipe,{},'default')['image_id']
  if name=='pi':
   files={'model-refresh.mjs':ROOT/'experiments/pi/model-refresh.mjs','models.json':BASE/'runtime/pi/models.json','settings.json':BASE/'runtime/pi/settings.json'}
   steps='USER root\nCOPY model-refresh.mjs /opt/model-refresh.mjs\nRUN node /opt/model-refresh.mjs\nCOPY models.json settings.json /home/agent/.pi/agent/\nRUN chown -R 1000:1000 /home/agent/.pi\n'
  recipe='ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n'+steps+'USER root\nRUN chown -R 1000:1000 /home/agent\nUSER 1000:1000\n'
  (BASE/'images').mkdir(exist_ok=True);path=BASE/'images'/(name+'.Dockerfile');path.write_text(recipe);sources.append(path)
  image=build(name,base,recipe,files,'none');image.update(version=version,lab_base_image_id=row['lab_base_image_id']);images[name]=image
  cmd=pins[name][1] if name in pins else ('. ~/.nvm/nvm.sh; pi --version' if name=='pi' else 'uv tool list')
  observed=h.probe(D,image['image_id'],cmd,stderr=True)
  assert version in observed
  common=h.probe(D,image['image_id'],'id -u; node --version; test -w /app/output; test -w /logs/agent; test ! -e /tests; test ! -e /opt/verifier-fixtures; test ! -e /var/run/docker.sock')
  assert common.splitlines()==['1000','v24.13.1']
  item={**old_evidence['images'][name],'version_output':observed,'runtime_details':{}}
  if name=='pi':
   js="import {ModelRegistry} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/model-registry.js';import {AuthStorage} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/auth-storage.js';import {SettingsManager} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/settings-manager.js';const r=ModelRegistry.create(AuthStorage.inMemory()),s=SettingsManager.create('/app');console.log(JSON.stringify({model:r.find('openai','gpt-6.1-sol'),anthropic:r.find('anthropic','claude-sonnet-5-5'),compaction:s.getCompactionEnabled(),retry:s.getRetryEnabled()}));"
   import shlex
   item['runtime_details']=json.loads(h.probe(D,image['image_id'],'node --input-type=module -e '+shlex.quote(js)))
   expected=json.loads((BASE/'runtime/pi/models.json').read_text())
   for provider,key in [('openai','model'),('anthropic','anthropic')]:
    for k,v in expected['providers'][provider]['models'][0].items():assert item['runtime_details'][key][k]==v
  if name=='mini-swe-agent':
   item['runtime_details']=old_evidence['images'][name]['runtime_details'];assert h.probe(D,image['image_id'],'python -m pip check')=='No broken requirements found.'
  evidence[name]=item;inventories[name]=h.inventory(D,image['image_id'],python='/home/agent/.local/share/uv/tools/mini-swe-agent/bin/python' if name=='mini-swe-agent' else None)
 verifier=old['verifier'];evidence['verifier']=old_evidence['images']['verifier'];inventories['verifier']=json.loads((OLD/'runtime-inventories.json').read_text())['verifier']
 assert h.probe(D,verifier['image_id'],'id -u; test ! -w /opt/verifier-fixtures')=='1000'
 (BASE/'npm-artifacts.json').write_text(json.dumps(registry,indent=2)+'\n');sources.append(BASE/'npm-artifacts.json')
 (BASE/'runtime-inventories.json').write_text(json.dumps(inventories,indent=2)+'\n')
 lock={'schema_version':1,'kind':'local-immutable-model-refresh-images','created_at':datetime.now(timezone.utc).isoformat(),'harbor_commit':old['harbor_commit'],'images':images,'verifier':verifier,'build_network':'none','public_package_preparation_network':'npm registry only; prior to immutable final image assembly','provider_requests':0,'credential_files_read':False,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sources},'limitations':old['limitations']+['Pi upstream version stays0.73.1, with explicit hash-bound Sonnet5.5 adaptive/empty-thinking patch; image ID identifies this changed condition.']}
 (BASE/'runtime-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
 (BASE/'runtime-evidence.json').write_text(json.dumps({'kind':'offline-runtime-evidence','images':evidence,'package_inventory_file':'runtime-inventories.json','package_inventory_sha256':sha(BASE/'runtime-inventories.json'),'checked_at':datetime.now(timezone.utc).isoformat(),'model_requests':0},indent=2)+'\n')
if __name__=='__main__':main()
