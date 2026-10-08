import datetime
import hashlib
import importlib.metadata
import json
import pathlib
import platform
import subprocess

import mlx.core as mx
from mlx_lm.utils import load_tokenizer

raw = pathlib.Path(__file__).resolve().parent
model = pathlib.Path('/Users/lab/local-model-lab-artifacts/mlx-community/Qwen3.5-9B-MLX-4bit/938d8919941c6e7efd3c7150eff7fe9d12afa631')
assert platform.machine() == 'arm64'
assert mx.default_device() == mx.gpu
device = mx.device_info()
assert device['device_name'] == 'Apple M5 Max'
a = mx.ones((128, 128), dtype=mx.float16, stream=mx.gpu)
b = mx.matmul(a, a, stream=mx.gpu)
mx.eval(b)
assert b[0, 0].item() == 128
device_record = dict(device_info=device, default_device=str(mx.default_device()),
                     gpu_matmul_checked=True, active_memory_bytes=mx.get_active_memory(),
                     peak_memory_bytes=mx.get_peak_memory(), cache_memory_bytes=mx.get_cache_memory(),
                     memory_limit_bytes=mx.get_memory_limit(), wired_limit_bytes=mx.get_wired_limit() if hasattr(mx, 'get_wired_limit') else None,
                     wired_limit_unavailable_reason='No read-only get_wired_limit in pinned mlx.core; not queried through setter')
(raw / 'mlx-device.json').write_text(json.dumps(device_record, indent=2)+'\n')
config = json.loads((model / 'config.json').read_text())
tokenizer = load_tokenizer(model, {'trust_remote_code': False}, eos_token_ids=config.get('eos_token_id'))
prompt = (raw / 'prompt.txt').read_text().strip()
rendered = tokenizer.apply_chat_template([{'role':'user', 'content':prompt}], tokenize=False,
                                         add_generation_prompt=True, enable_thinking=False)
tokens = tokenizer.encode(rendered, add_special_tokens=False)
(raw / 'rendered-prompt.txt').write_text(rendered)
tokenizer_record = dict(model_type=config['model_type'], text_model_type=config.get('text_config',{}).get('model_type'),
    effective_eos_token_ids=sorted(tokenizer.eos_token_ids),
    effective_eos_texts={str(i):tokenizer.convert_ids_to_tokens(i) for i in sorted(tokenizer.eos_token_ids)},
    config_eos_token_id=config.get('eos_token_id'),
    prompt_tokens=tokens, prompt_token_count=len(tokens),
    prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
    rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    effective_template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
    template_kwargs={'enable_thinking':False}, trust_remote_code=False,
    has_thinking=tokenizer.has_thinking)
(raw / 'tokenizer-runtime.json').write_text(json.dumps(tokenizer_record, ensure_ascii=False, indent=2)+'\n')
hardware = {'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'architecture':platform.machine(), 'python':platform.python_version(), 'macos':platform.mac_ver()[0],
    'physical_memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),
    'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
    'gpu':device, 'baseline_source':'LAB28-apple-first-20261007'}
(raw / 'hardware-snapshot.json').write_text(json.dumps(hardware,indent=2)+'\n')
pins = json.loads((raw / 'source-pins.json').read_text())
packages = {name:importlib.metadata.version(name) for name in ['mlx','mlx-metal','mlx-lm','transformers','tokenizers','huggingface-hub','numpy']}
assert packages['mlx']=='0.32.3' and packages['mlx-metal']=='0.32.3' and packages['mlx-lm']=='0.32.0'
provenance = {name:hashlib.sha256(pathlib.Path(__import__('mlx_lm.'+name,fromlist=['__file__']).__file__).read_bytes()).hexdigest() for name in ['utils','generate','server','models.qwen3_5']}
runtime = dict(python=platform.python_version(), architecture=platform.machine(), packages=packages,
    pins=pins, installed_module_sha256=provenance, model_path=str(model), model_revision=model.name,
    device=device_record, tokenizer=tokenizer_record, offline_environment={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'},
    sampling={'temperature':0,'seed':1,'max_tokens':128}, operator_memory_tuning=False,
    runtime_wired_policy='Unmodified mlx-lm generate.wired_limit: process-local device recommendation, restored after generation',
    comparison='MLX4-bit VLM artifact text-only vs GGUF Q6_K synthetic llama-bench: distinct deployments/inputs')
(raw / 'runtime-manifest.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n')
manifest_path = raw.parent / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
for case, files in [('install',['install-exit.txt','install-report.json','python-lock.txt','pip-check.txt']),
                    ('preflight-retry',['artifact-verification.json','mlx-device.json','hardware-snapshot.json','tokenizer-runtime.json','runtime-manifest.json'])]:
    attempt = next(a for a in manifest['planned_attempts'] if a['id']==case)
    attempt.update(status='completed', evidence_files=['raw/'+f for f in files])
manifest['evidence_files'] = sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'device':device_record,'packages':packages,'prompt_tokens':len(tokens),
                  'effective_eos_ids':sorted(tokenizer.eos_token_ids)},indent=2))
