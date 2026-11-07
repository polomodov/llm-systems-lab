"""Freeze lab images without the Harbor synthetic task's baked public input."""
from pathlib import Path
import hashlib,importlib.util,json
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2];NATIVE=BASE.with_name('harbor-native-2026-11')
spec=importlib.util.spec_from_file_location('model_runtime_build',NATIVE/'build-runtime.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
lock=json.loads((NATIVE/'runtime-lock.json').read_text());images={}
recipe='ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nUSER root\nRUN rm -f /app/input.json\nUSER 1000:1000\n'
(BASE/'lab.Dockerfile').write_text(recipe)
for name,row in lock['images'].items():
 image=m.build('lab-'+name,row['image_id'],recipe,{},'none');image['version']=row['version'];images[name]=image
 assert m.h.probe(m.D,image['image_id'],'test ! -e /app/input.json; id -u')=='1000'
result={'schema_version':1,'kind':'lab-model-refresh-immutable-images','images':images,'native_runtime_lock_sha256':m.sha(NATIVE/'runtime-lock.json'),'build_network':'none','provider_requests':0,'source_sha256':{str(p.relative_to(ROOT)):m.sha(p) for p in [Path(__file__),BASE/'lab.Dockerfile',ROOT/'experiments/mini-swe-agent/Dockerfile']},'note':'The Harbor normalization input is not preloaded into campaign images; the offline instrument copies its own public input for protocol tests. Lab coordinator must use these IDs explicitly; old tags remain unchanged.'}
(BASE/'lab-runtime-lock.json').write_text(json.dumps(result,indent=2)+'\n')
