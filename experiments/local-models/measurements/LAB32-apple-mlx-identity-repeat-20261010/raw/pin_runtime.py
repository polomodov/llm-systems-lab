"""Offline pin registration; no model/MLX imports and no downloads."""
import datetime
import hashlib
import json
import pathlib
import subprocess
raw=pathlib.Path(__file__).resolve().parent
runtime=json.loads((raw/'runtime-manifest.json').read_text())
venv=pathlib.Path(runtime['pins']['environment'])
site=venv/'lib/python3.12/site-packages'
python=(venv/'bin/python').resolve()
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(2**20),b''):h.update(c)
    return h.hexdigest()
files=set(raw.glob('*.py'))|{raw/'runtime-manifest.json',raw/'artifact-manifest.json',venv/'bin/python'}
files.update(site.rglob('*.so'));files.update(site.rglob('*.dylib'));files.update(site.rglob('*.metallib'))
files.update((site/'mlx_lm').rglob('*.py'));files.update((site/'mlx').rglob('*.py'))
files.update((python.parent.parent/'lib').glob('*.dylib'))
files.update((python.parent.parent/'lib/python3.12/lib-dynload').glob('*.so'))
for name,sha in runtime['installed_module_sha256'].items():
    path=site/'mlx_lm'/('/'.join(name.split('.'))+'.py');assert digest(path)==sha
import sys
sys.path.insert(0,str(raw.parents[4]/'experiments/local-models/apple'))
from artifacts import select_artifact,missing_artifact_pins
files.add(raw.parents[4]/'experiments/local-models/apple/artifacts.py')
artifact=select_artifact(json.loads((raw/'artifact-manifest.json').read_text()),format='MLX/safetensors',repository='mlx-community/Qwen3.5-9B-MLX-4bit',revision=runtime['model_revision'])
for pin in artifact['files']:
    path=pathlib.Path(pin['local_path']);assert path.stat().st_size==pin['bytes'] and digest(path)==pin['sha256'];files.add(path)
records=[dict(path=str(path.resolve()) if path==venv/'bin/python' else str(path),bytes=path.stat().st_size,sha256=digest(path)) for path in sorted(files)]
packages=json.loads(subprocess.check_output([str(venv/'bin/python'),'-B','-c',
    'import json,importlib.metadata as m;print(json.dumps({k:m.version(k) for k in '+repr(list(runtime['packages']))+'}))'],text=True))
assert packages==runtime['packages']
registered=dict(registered_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=records,packages=packages,
    model=runtime['model_path'],scope='All venv native so/dylib/metallib, MLX/MLX-LM sources, Python core dylibs/dynload, model files and experiment sources; Apple system frameworks fixed by macOS build, not file hashes')
assert not missing_artifact_pins(artifact,registered)
registered['model_artifact']=dict(format=artifact['format'],repository=artifact['repository'],revision=artifact['revision'],files=len(artifact['files']),missing_pins=[])
(raw/'prestart-pins.json').write_text(json.dumps(registered,indent=2)+'\n')
print(json.dumps(dict(files=len(records),packages=packages)))
