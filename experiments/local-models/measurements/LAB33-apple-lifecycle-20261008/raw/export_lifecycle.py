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
  follow=read(case+'.followup.request.json');assert follow['messages']==req['messages']+[message,{'role':'tool','tool_call_id':call['id'],'content':'LAB_VALUE_42'}];assert initial['finish_reason']=='tool_calls'
  metrics=[initial,read(case+'.followup.metrics.json')];assert metrics[-1]['finish_reason']=='stop'
 else:metrics=[initial];assert initial['finish_reason']=='stop'
 for mm in metrics:
  assert mm['http_status']==200 and mm['usage']['prompt_tokens']>0 and mm['usage']['completion_tokens']>=0 and mm['duration_s']>0
  if req['stream']:assert mm['stream_done']
 return x,metrics
summary={'attempt_counts':dict(collections.Counter(a['status'] for a in M['planned_attempts'])),'short_cells':{},'memory':{},'cancellation':{},'prior_failure_cause':None,'prior_failure_cause_unavailable':'Original GUI interruption not reproduced; user quit/crash/OOM not established.'}
for dep in ['lms-mlx','lms-metal','lms-metal-existing']:
 for kind in ['chat','chat-stream','tool','tool-stream']:
  values=[]
  for rep in ['warmup','r1','r2','r3']:
   case=dep+'-'+kind+'-'+rep;a=next(a for a in M['planned_attempts'] if a['id']==case)
   if a['status']!='completed':continue
   x,metrics=verify(case);total=sum(mm['duration_s'] for mm in metrics);values.append((rep,total))
   add(a['configuration_id'],'warmup_round_trip_s' if rep=='warmup' else 'round_trip_s',total,'s',case+'-execution.json',None if rep=='warmup' else int(rep[1:]))
   for i,mm in enumerate(metrics):
    ev=case+('.metrics.json' if i==0 else '.followup.metrics.json');prefix='initial_' if i==0 else 'followup_'
    for field in ['prompt_tokens','completion_tokens']:add(a['configuration_id'],prefix+field,mm['usage'][field],'tokens',ev,None if rep=='warmup' else int(rep[1:]))
    for key in ['ttft_content_s','ttft_reasoning_s']:
     v=mm.get(key);add(a['configuration_id'],prefix+key,v,'s',ev,None if rep=='warmup' else int(rep[1:]),reason='Non-streaming response or SSE without that channel.' if v is None else '')
  if values:summary['short_cells'][dep+'-'+kind]={'accepted_attempts':len(values),'warmup_excluded':True,'median_round_trip_s':statistics.median(v for rep,v in values if rep!='warmup'),'values':dict(values)}
 memory=RAW/(dep+'-memory.jsonl')
 if memory.exists():
  rows=[json.loads(line) for line in memory.read_text().splitlines()]
  v={'samples':len(rows),'app_pids':sorted(set(p['pid'] for row in rows for p in row['processes'][:1])),'app_alive_all_samples':all(row['app_alive'] for row in rows),'min_free_pages_bytes':min(row['free_pages_bytes'] for row in rows),'max_tree_rss_bytes':max(row['aggregate_rss_bytes'] or 0 for row in rows),'swap_max_bytes':max(row['swap_used_bytes'] for row in rows),'guard':read(dep+'-shutdown-execution.json')['guard_reason']}
  summary['memory'][dep]=v
  for metric in ['min_free_pages_bytes','max_tree_rss_bytes','swap_max_bytes']:add(dep.replace('-existing','')+'-ctx8192-service',metric,v[metric],'bytes',dep+'-memory.jsonl')
 cancel=RAW/(dep+'-cancel-execution.json')
 if cancel.exists():
  c=read(cancel.name);w=read(dep+'-cancel-recovery-window.json');verify(dep+'-cancel-recovery')
  assert c['exit_code']==28 and not c['done_received'] and w['within_60_seconds'] and w['client_exit_to_recovery_end_seconds']<=60
  assert not c['accepted'] and not c['cancellation_log']
  summary['cancellation'][dep]={'client_timeout_seconds':c['duration_s'],'recovery_seconds':w['client_exit_to_recovery_end_seconds'],'native_cancel_verified':False,'gpu_slot_release_seconds':None}
  add(dep+'-ctx8192-service','client_timeout_seconds',c['duration_s'],'s',cancel.name)
  add(dep+'-ctx8192-service','client_exit_to_recovery_end_seconds',w['client_exit_to_recovery_end_seconds'],'s',dep+'-cancel-recovery-window.json')
  add(dep+'-ctx8192-service','gpu_slot_release_seconds',None,'s',cancel.name,reason='Client timeout/recovery is observed; native cancellation log and GPU release are not verified.')
for a in M['planned_attempts']:
 assert a['status'] in ['completed','failed','not-run']
 if a['status']!='completed':add(a['configuration_id'],'attempt-'+a['id'],None,'status',a['evidence_files'][0][4:],status=a['status'],reason=a['reason'])
write('summary.json',summary)
M.update(status='blocked',conclusion='MLX service process completed16/16 short chat/tool cases and recovery without app disappearance; native cancellation remains unverified. GGUF startup/import/resource failures preserved; original interruption cause remains unknown.')
M['unavailable']['completion']='MLX native cancellation/GPU release not proven; GGUF retry stopped at free-only resource guard before chat; no complete new serving admission.'
M['unavailable'].pop('conditions.runtime_manifest',None)
M['conditions']['runtime_manifest']=str(RAW.relative_to(pathlib.Path.cwd())/'lms-mlx-startup-runtime.json')
M['evidence_files']=sorted('raw/'+p.name for p in RAW.iterdir() if p.is_file())
write('evidence-sha256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file() and p.name!='evidence-sha256.json'})
M['evidence_files']=sorted(set(M['evidence_files']+['raw/evidence-sha256.json']));(LAB/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n')
headers='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
with (LAB/'measurements.tsv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=headers,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(ROWS)
print(json.dumps({'attempts':summary['attempt_counts'],'observations':len(ROWS),'status':M['status']}))
