# -*- coding: utf-8 -*-
"""Export only existing primary observations; recompute accepted contracts."""
import csv,hashlib,json,math,pathlib,statistics,collections
RAW=pathlib.Path(__file__).resolve().parent
LAB=RAW.parent
M=json.loads((LAB/'manifest.json').read_text())
ROWS=[]
def read(name):
 import gzip
 path=RAW/name
 return json.loads(path.read_bytes() if path.exists() else gzip.decompress((RAW/(name+'.gz')).read_bytes()))
def write(name,v):(RAW/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def add(config,metric,value,unit,evidence,repeat=None,status='measured',reason=''):
 if value is not None:assert isinstance(value,(int,float)) and math.isfinite(value),metric
 else:assert reason;status='unavailable' if status=='measured' else status
 ROWS.append({'observation_id':'o'+str(len(ROWS)+1),'configuration_id':config,'model_id':'Qwen3.5-9B','engine':'mlx-llm' if 'lms-mlx' in config else 'llama.cpp','backend':'metal','context_tokens':8192,'repeat':repeat or '', 'metric':metric,'value':value if value is not None else '', 'unit':unit,'status':status,'evidence_path':'raw/'+evidence,'unavailable_reason':reason})
def verify(case):
 x=read(case+'-execution.json');assert x['accepted'],case
 req=read(case+'.request.json');initial=read(case+'.metrics.json');final=read(case+'.final.json');tool='lookup_lab_value' in json.dumps(req.get('tools',[]));expected='LAB_VALUE_42' if tool else 'LAB_READY'
 assert final['content'].strip()==expected and not final.get('tool_calls'),case
 message=read(case+'.assembled.json') if req['stream'] else read(case+'.response.json')['choices'][0]['message']
 if tool:
  assert len(message['tool_calls'])==1;call=message['tool_calls'][0];assert call['id'] and call['type']=='function' and call['function']['name']=='lookup_lab_value' and json.loads(call['function']['arguments'])=={'key':'alpha'}
  follow=read(case+'.followup.request.json');assert follow['messages'][-1]['tool_call_id']==call['id'] and follow['messages'][-1]['content']=='LAB_VALUE_42';assert initial['finish_reason']=='tool_calls'
  metrics=[initial,read(case+'.followup.metrics.json')];assert metrics[-1]['finish_reason']=='stop'
 else:metrics=[initial];assert initial['finish_reason']=='stop'
 for mm in metrics:
  assert mm['http_status']==200 and mm['usage']['prompt_tokens']>0 and mm['usage']['completion_tokens']>=0 and mm['duration_s']>0
  if req['stream']:assert mm['stream_done']
 return x,metrics
summary={'attempt_counts':dict(collections.Counter(a['status'] for a in M['planned_attempts'])),'short_cells':{},'memory':{},'cancellation':{},'overhead_seconds':None,'overhead_unavailable':'Commits/builds/threads/templates/cache/defaults differ; no pure wrapper overhead isolation.','gpu_budget_gib':None,'gpu_budget_unavailable':'No validated GPU allocation ceiling in LAB33.'}
for dep in ['ollama','direct','lms-metal']:
 for kind in ['chat','chat-stream','tool','tool-stream']:
  values=[]
  for rep in ['warmup','r1','r2','r3']:
   case=dep+'-'+kind+'-'+rep;x,metrics=verify(case);a=next(a for a in M['planned_attempts'] if a['id']==case);assert a['status']=='completed'
   repeat=1 if rep=='warmup' else int(rep[1:]);config=a['configuration_id'];total=sum(mm['duration_s'] for mm in metrics);values.append(total)
   add(config,'warmup_round_trip_s' if rep=='warmup' else 'round_trip_s',total,'s',case+'-execution.json',repeat)
   for i,mm in enumerate(metrics):
    prefix=('warmup_' if rep=='warmup' else '')+('initial_' if i==0 else 'followup_');ev=case+('.metrics.json' if i==0 else '.followup.metrics.json')
    for field in ['prompt_tokens','completion_tokens']:add(config,prefix+field,mm['usage'][field],'tokens',ev,repeat)
    cached=mm['usage'].get('prompt_tokens_details',{}).get('cached_tokens');add(config,prefix+'cached_tokens',cached,'tokens',ev,repeat,reason='Runtime did not report cached tokens.' if cached is None else '')
    for key in ['ttft_content_s','ttft_reasoning_s']:
     v=mm.get(key);add(config,prefix+key,v,'s',ev,repeat,reason='JSON has no arrival timing; or this SSE phase has no corresponding content/reasoning delta.' if v is None else '')
   assert all(mm['duration_s']<=x['wall_seconds'] for mm in metrics)
  summary['short_cells'][dep+'-'+kind]={'accepted_attempts':4,'warmup_round_trip_s':values[0],'measured_round_trip_s':values[1:],'median_round_trip_s':statistics.median(values[1:]),'warmup_excluded':True}
 for suffix in ['-memory.jsonl']:
  rs=[json.loads(line) for line in (RAW/(dep+suffix)).read_text().splitlines()];assert rs and all(r['swap_used_bytes']==0 and r['on_ac_power'] and r['ac_power_mode']==0 for r in rs)
  v={'samples':len(rs),'min_free_pages_bytes':min(r['free_pages_bytes'] for r in rs),'max_observed_tree_rss_bytes':max(r['aggregate_rss_bytes'] for r in rs if r['aggregate_rss_bytes'] is not None),'swap_used_bytes_max':max(r['swap_used_bytes'] for r in rs),'rss_definition':'Sampled sum of process-tree RSS; pages can overlap; LM Studio includes GUI/helper. Not Metal allocation or comparable pure model memory.'};summary['memory'][dep]=v
  for key,unit in [('min_free_pages_bytes','bytes'),('max_observed_tree_rss_bytes','bytes'),('swap_used_bytes_max','bytes')]:add(dep+'-8k',key,v[key],unit,dep+suffix)
 if dep!='direct':
  c=read(dep+'-cancel-execution.json');w=read(dep+'-cancel-recovery-window.json');assert c['accepted'] and c['exit_code']==28 and not c['done_received'] and c['cancellation_log'] and w['within_60_seconds'] and w['client_exit_to_recovery_end_seconds']<=60
  verify(dep+'-cancel-recovery');summary['cancellation'][dep]={'client_timeout_seconds':c['duration_s'],'client_exit_to_recovery_end_seconds':w['client_exit_to_recovery_end_seconds'],'gpu_slot_release_seconds':None}
  add(dep+'-8k','client_timeout_seconds',c['duration_s'],'s',dep+'-cancel-execution.json');add(dep+'-8k','client_exit_to_recovery_end_seconds',w['client_exit_to_recovery_end_seconds'],'s',dep+'-cancel-recovery-window.json');add(dep+'-8k','gpu_slot_release_seconds',None,'s',dep+'-cancel-execution.json',reason='No verified native GPU slot monitor; cancel log and recovery do not measure GPU release.')
# Preserve actual failed duration separately; unknown usage/throughput stays blank.
a=next(a for a in M['planned_attempts'] if a['id']=='lms-mlx-chat-warmup');assert a['status']=='failed'
mm=read('lms-mlx-chat-warmup.metrics.json');assert mm.get('error') and mm['usage'] is None
add(a['configuration_id'],'failed_request_duration_s',mm['duration_s'],'s','lms-mlx-chat-warmup.metrics.json',1)
add(a['configuration_id'],'round_trip_s',None,'s','lms-mlx-chat-warmup.metrics.json',1,status='failed',reason=mm['error'])
for attempt in M['planned_attempts']:
 assert attempt['status'] in ['completed','failed','not-run'],attempt['id']
 if attempt['status']!='completed':
  assert attempt['reason'] and attempt['evidence_files'];add(attempt['configuration_id'],'attempt_'+attempt['id'],None,'status',attempt['evidence_files'][0][4:],status='failed' if attempt['status']=='failed' else 'not-run',reason=attempt['reason'])
 summary['attempt_counts']=dict(collections.Counter(a['status'] for a in M['planned_attempts']))
write('summary.json',summary)
actual={'scope':'Measured deployments; preflight runtime-manifest contains inherited LAB32 source/binary metadata, not actual direct settings.', 'ollama':{'app_version':'0.40.1','source_commit':'cf2a313a298066d572c36812e5ad30a21c0db13b','runner_version':(RAW/'ollama-bundled-runner-version.txt').read_text(),'model_identity':read('ollama-startup-weights.json'),'show': 'raw/ollama-startup-show.json.gz','show_preview':'raw/ollama-startup-show-preview.json','actual_context':8192,'threads':8,'slots':1,'loopback':'127.0.0.1:11435','cache':'Native prefix/prompt cache enabled; usage cached_tokens evidence.','reasoning_effort':'low / boolean thinking true; no budget128','native_backend_evidence':'raw/ollama-server.txt','gpu_offload_evidence':'33/33 layers to GPU / Apple M5 Max / Metal in startup log'},'direct':{'base_commit':'312cf03328496df9c56fe843952cf02a8964c59a','patch_sha256':'561c77562a5caad4772bfc0fcf078f9b1c354296e310300c7b460e635f368863','actual_command':read('direct-server-execution.json')['command'],'actual_context':8192,'threads':8,'slots':1,'reasoning':'auto, enable_thinking true, no request thinking_budget_tokens','kv':'f16/f16','cache':'disabled','props':'raw/direct-startup-props.json','native_backend_evidence':'raw/direct-server.txt'},'lms-metal':{'app_version':'0.4.25+1','cli_commit':'69d945a','runtime':'llama.cpp2.54.0','version_after':(RAW/'lms-metal-runtime-version-after.txt').read_text(),'binary_hashes':'raw/lms-metal-startup-runtime.json','loaded_identity':read('lms-metal-startup-loaded.txt'),'actual_runtime':'runtime logs engineName llama.cpp-mac-arm64-apple-metal-advsimd2.54.0 / PID8586','threads_observed':13,'kv_cache_dtype':None,'gpu_device_and_offload':None,'unknown_reason':'Runtime package Metal identified in actual logs, but per-device/offload lines not captured by app runtime stream. --gpu max is request, not independent allocation proof.','template_cache_reasoning':'native defaults; prompt cache LCP in logs, template not exported; output reasoning observed','evidence':'raw/lms-metal-server.txt'},'lms-mlx':{'runtime':'mlx-llm-mac-arm64-apple-metal-nax-advsimd1.13.1','binary_hashes':'raw/lms-mlx-startup-runtime.json','artifact':'raw/lms-mlx-startup-weights.json','loaded':'raw/lms-mlx-startup-loaded.txt','native_log':'raw/lms-mlx-server.txt','context':8192,'slots':1,'resource_condition':'lms-mlx-cache-aware; separate amendment','first_chat':'failed: RemoteDisconnected, original GUI process disappeared','cause':None,'cause_evidence':'raw/lms-mlx-lifecycle-observation.json','gpu_execution_verified':False},'comparison':'Different deployments; pure overhead unavailable; no GGUF estimate transferred to MLX.'}
write('deployment-manifest.json',actual)
M['conditions']['runtime_manifest']=RAW.relative_to(pathlib.Path.cwd()).as_posix()+'/deployment-manifest.json';M['status']='blocked'
M['unavailable'].pop('conditions.runtime_manifest',None)
M['unavailable'].update(completion='MLX loaded but first chat connection closed and original app process disappeared; no stable MLX protocol admission. LMS GGUF per-device/offload proof remains incomplete.',overhead='Different commits/builds/templates/cache and threads13 vs8; pure wrapper overhead not isolated.',gpu_budget='No validated allocation ceiling; recommendedMaxWorkingSet/engine reported available VRAM not free GPU heap.',mlx_failure_cause='Unknown: no evidence establishing crash, OOM or user quit; separate owner question pending.')
M['conclusion']='Ollama/Metal GGUF and direct16/16 short cases passed; LM Studio/GGUF16/16 passed with runtime Metal package identified but incomplete device/offload evidence. Both wrappers cancel/recovery passed. MLX first chat failed due connection/process interruption, preserved; entire LAB33 blocked pending that branch.'
M['evidence_files']=sorted('raw/'+p.name for p in RAW.iterdir() if p.is_file())
write('evidence-sha256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file() and p.name!='evidence-sha256.json'})
M['evidence_files']=sorted(set(M['evidence_files']+['raw/evidence-sha256.json']))
(LAB/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n')
headers='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
with (LAB/'measurements.tsv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=headers,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(ROWS)
print(json.dumps({'attempts':summary['attempt_counts'],'observations':len(ROWS),'status':M['status']}))
