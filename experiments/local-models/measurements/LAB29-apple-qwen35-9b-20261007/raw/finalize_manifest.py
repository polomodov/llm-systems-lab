# -*- coding: utf-8 -*-
import csv,importlib.metadata,json,pathlib,subprocess
from gguf import GGMLQuantizationType
raw=pathlib.Path(__file__).resolve().parent
report=raw.parent
acquisition=json.loads((raw/'acquisition-http-status.json').read_text())
verification=json.loads((raw/'offline-verification.json').read_text())
assert acquisition['completed'] and verification['all_match']
summary=json.loads((raw/'gguf-summary.json').read_text())
summary['tensor_types']={GGMLQuantizationType(int(k)).name if k.isdigit() else k:v for k,v in summary['tensor_types'].items()}
(raw/'gguf-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
comparison=json.loads((raw/'protocol-comparison.json').read_text())
mlxindex=json.loads((raw/'mlx-index-verification.json').read_text())
artifacts=[]
for variant in ['gguf','mlx']:
    files=[f for f in acquisition['files'] if f['variant']==variant]
    suffix='.gguf' if variant=='gguf' else '.safetensors'
    size=sum(f['bytes'] for f in files if f['path'].endswith(suffix))
    artifact={'format':'GGUF' if variant=='gguf' else 'MLX/safetensors','repository':files[0]['repository'],
        'revision':files[0]['revision'],'weights_bytes':size,'weights_gib':size/2**30,'files':files,
        'checksum_status':'publisher-and-local-sha256-verified','license':'Apache-2.0',
        'chat_template_sha256':comparison[variant+'_chat_template_sha256']}
    if variant=='gguf':
        artifact.update(quantization='Q6_K; mixed Q6_K/Q8_0/F32 tensors',matches_ryzen_lab03=True,
            architecture='qwen35',tensor_count=summary['tensor_count'],tokenizer_evidence='gguf-tokenizer-hashes.json')
    else:
        artifact.update(quantization=mlxindex['quantization'],tensor_count=mlxindex['tensor_count'],
            source_conversion_revision=None,published_conversion_tool='mlx-vlm',published_conversion_version=None,
            published_conversion_command='python3 -m mlx_vlm convert --hf-path Qwen/Qwen3.5-9B --mlx-path ./mlx_models/Qwen3.5-9B-MLX-4bit -q --q-bits 4 --q-group-size 64',
            runtime_support='Archived MLX-LM qwen3_5 source has text/vision sanitization; model/hardware smoke pending.')
    artifacts.append(artifact)
    (raw/(variant+'-files.json')).write_text(json.dumps({'files':files,'total_bytes':sum(f['bytes'] for f in files)},indent=2)+'\n')
manifest={'schema_version':1,'kind':'verified-model-artifacts','source_reference':{
    'repository':'Qwen/Qwen3.5-9B','revision':'c202236235762e1c871ad0ccb60c8ee5ba337b9a',
    'purpose':'Pinned config/tokenizer/license reference; not asserted as MLX conversion source commit.'},
    'artifacts':artifacts,'license_evidence':'source-LICENSE','protocol_comparison':'protocol-comparison.json',
    'offline_verification':'offline-verification.json','hardware_fit_verified':False,
    'limitations':['MLX conversion source commit and exact conversion tool version not published.',
        'Quantization, templates and EOS metadata differ; compare deployments.',
        'GGUF has 243 padded vocabulary entries; existing MLX token IDs and merges match.',
        'No inference or GPU allocation test was executed.']}
(raw/'artifact-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
runtime={'python':'3.12.14 arm64','tools':{k:importlib.metadata.version(k) for k in ['huggingface_hub','gguf']},
    'curl':subprocess.run(['curl','--version'],capture_output=True,text=True).stdout.splitlines()[0],
    'successful_transport':'curl HTTP/1.1, bounded ranges, 2 workers; complete SHA256 and offline recheck',
    'failed_transports':['Xet','HTTP single stream stopped by operator','Python ranges/TLS','HF metadata SDK TLS'],
    'lock':'tools-lock.txt','inference_runtime':None,
    'mlx_lm_source_candidate':json.loads((raw/'mlx-lm-source-pin.json').read_text())}
(raw/'operator-runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
m=json.loads((report/'manifest.json').read_text())
evidence={
'acquisition-curl':['gguf-Qwen3.5-9B-Q6_K.gguf-curl-status.json','curl-gguf-exit.txt','acquisition-http-status.json'],
'acquisition-mlx':['mlx-model-00001-of-00002.safetensors-curl-status.json','mlx-model-00002-of-00002.safetensors-curl-status.json','curl-mlx-shard1-exit.txt','curl-mlx-shard2-exit.txt'],
'offline-verification':['offline-verification.json','mlx-index-verification.json','offline-inspection-exit.txt'],
'metadata-comparison':['gguf-summary.json','gguf-tokenizer-hashes.json','protocol-comparison.json','metadata-curl-status.json','artifact-manifest.json']}
for attempt in m['planned_attempts']:
    if attempt['status']=='failed':continue
    attempt.update(status='completed',evidence_files=['raw/'+f for f in evidence[attempt['id']]])
prefix=report.relative_to(pathlib.Path.cwd()).as_posix()
m.update(status='completed',conditions={'hardware_snapshot':prefix+'/raw/hardware-snapshot.json',
    'model_artifact_manifest':prefix+'/raw/artifact-manifest.json','runtime_manifest':prefix+'/raw/operator-runtime.json','harness_profile':None},
    conclusion='Закреплены и дважды проверены GGUF Q6_K и MLX 4-bit Qwen3.5-9B: 19 файлов, hashes совпали с издателем. GGUF идентичен Ryzen; MLX index/shards согласованы. Шаблоны и EOS metadata отличаются; source conversion commit MLX неизвестен. Инференс/вместимость не проверялись.',
    unavailable={'conditions.harness_profile':'Подготовка весов без агентского harness.',
        'mlx_conversion_source_revision':'В карточке нет immutable source commit конверсии.',
        'mlx_conversion_version':'В выбранной карточке нет точной версии mlx-vlm.',
        'gpu_budget_gib':'LAB28 сохранила null; GPU allocations модели не проверены.'})
columns=(report/'measurements.tsv').read_text().splitlines()[0].split('\t');rows=[]
def observation(id,configuration,metric,value,unit,file):
    row={c:'' for c in columns}
    row.update(observation_id=id,configuration_id=configuration,model_id='Qwen/Qwen3.5-9B',metric=metric,value=str(value),unit=unit,status='measured',evidence_path='raw/'+file)
    rows.append(row)
for variant,artifact in zip(['gguf','mlx'],artifacts):observation(variant+'-bytes',variant,'weights_size',artifact['weights_bytes'],'bytes',variant+'-files.json')
for id,metric,value,unit,file in [
    ('offline-files','verified_file_count',len(acquisition['files']),'count','offline-verification.json'),
    ('offline-duration','verification_wall_time',verification['elapsed_seconds'],'seconds','offline-verification.json'),
    ('gguf-tensors','gguf_tensor_count',summary['tensor_count'],'count','gguf-summary.json'),
    ('mlx-tensors','mlx_tensor_count',mlxindex['tensor_count'],'count','mlx-index-verification.json'),
    ('extra-padding','gguf_extra_vocabulary_entries',comparison['gguf_extra_vocabulary_entries'],'count','protocol-comparison.json')]:
    observation(id,'artifacts',metric,value,unit,file)
for variant,name,id in [('gguf','Qwen3.5-9B-Q6_K.gguf','gguf-transfer'),('mlx','model-00001-of-00002.safetensors','mlx-transfer-1'),('mlx','model-00002-of-00002.safetensors','mlx-transfer-2')]:
    file=variant+'-'+name+'-curl-status.json'
    observation(id,variant,'successful_transfer_wall_time',json.loads((raw/file).read_text())['elapsed_seconds'],'seconds',file)
with (report/'measurements.tsv').open('w',newline='',encoding='utf-8') as out:
    writer=csv.DictWriter(out,fieldnames=columns,delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
m['evidence_files']=['raw/'+f.name for f in sorted(raw.iterdir()) if f.is_file()]
(report/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print({'gguf_gib':artifacts[0]['weights_gib'],'mlx_gib':artifacts[1]['weights_gib'],'attempts':[(a['id'],a['status']) for a in m['planned_attempts']]})
