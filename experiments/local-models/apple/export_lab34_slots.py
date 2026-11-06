"""Export actual slot evidence, preserving admission refusal and unknown metrics."""
import datetime,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[3];directory=(root/sys.argv[1]).resolve();raw=directory/'raw';m=json.loads((directory/'manifest.json').read_text());rows=[];table=[]
for key in ('created_at','protocol_recorded_at'):m[key]=datetime.datetime.fromisoformat(m[key].replace('Z','+00:00')).astimezone(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def observation(id,config,metric,value,unit,evidence,repeat=''):
 rows.append([id,config,'qwen35-9b-q6','llama.cpp','metal','8192',repeat,metric,str(value) if value is not None else '',unit,'measured' if value is not None else 'unavailable',str(evidence.relative_to(directory)),'' if value is not None else 'Primary field absent; no estimate.'])
for slots in (1,2,4):
 folder=raw/f'slots{slots}';config=next(a['configuration_id'] for a in m['planned_attempts'] if a['id']==f'slots{slots}-startup')
 for name in ('admission.json','admission-after-pins.json'):
  f=folder/name
  if f.exists():
   r=json.loads(f.read_text());r=r.get('sample',r);value=r['free_speculative_bytes']/2**30;observation(f's{slots}-{name}-free',config,'free_speculative_gib',value,'GiB',f);table.append(f'| {slots} | {name} | free+spec {value:.3f} GiB | — | — | — |')
 for f in sorted(folder.glob('**/slot-proof.json')):
  proof=json.loads(f.read_text());s=json.loads((directory/proof['summary']).read_text());name=f.parent.name;repeat=name[1:] if name in ('r1','r2','r3') else '';prefix=f's{slots}-{f.parent.relative_to(folder)}'
  table.append(f'| {slots} | {f.parent.relative_to(folder)} | {s["successful"]}/{s["requests"]}, busy {proof["max_busy_slots"]} | {s["success_latency_p95_seconds"]} | {s["successful_completion_tokens_per_second"]} | {proof["accepted"]} |')
  for metric,unit in [('success_latency_p95_seconds','s'),('batch_wall_seconds','s'),('successful_completion_tokens_per_second','tokens/s'),('failed','requests')]:observation(prefix+'-'+metric,config,metric,s[metric],unit,directory/proof['summary'],repeat)
  observation(prefix+'-busy',config,'max_busy_slots',proof['max_busy_slots'],'slots',f,repeat)
  for request_path in sorted(f.parent.glob('request-*.json')):
   record=json.loads(request_path.read_text());stem=request_path.stem;observation(prefix+'-'+stem+'-latency',config,'request_latency_seconds',record['latency_seconds'],'s',request_path,repeat)
   response_path=request_path.with_name(stem+'.response.bin')
   try:response=json.loads(response_path.read_bytes())
   except (ValueError,OSError):continue
   usage=response.get('usage') or {}
   for metric in ('prompt_tokens','completion_tokens'):
    value=usage.get(metric);value=value if type(value) is int and value>=0 else None
    observation(prefix+'-'+stem+'-'+metric,config,'primary_'+metric,value,'tokens',response_path,repeat)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split();(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(r)+'\n' for r in rows))
m['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file());m['unavailable'].update(energy='No energy collector.',temperature='No temperature collector.',gpu_budget_gib='Maximum GPU allocation not measured.',ttft='Non-streaming complete-response probe.');save(directory/'manifest.json',m)
counts={s:sum(a['status']==s for a in m['planned_attempts']) for s in ('completed','failed','not-run')}
(directory/'report.md').write_text(f'''# LAB34 — actual server slots

Session `{m['session_id']}`, status **{m['status']}**. {m['conclusion']}

## Run profile

Apple M5 Max / 128 GiB / macOS 26.5, AC/mode 0. Qwen3.5-9B GGUF Q6_K, revision 3885219b6810b007914f3a7950a8d1b469d598a5, llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a / Metal tensor tile16. [Exact hashes and runtime](raw/deployment-reference.json). MLX is not used. This is HTTP load, not an agent episode; run_ids is empty.

## Hypothesis and protocol before execution

[Protocol](raw/protocol.md) and [source registration](raw/source-registration.json) are committed before execution. Server slots 1/2/4, total context slots×8192, and actual context 8192 per slot. Parameters: KV f16/f16, FA on, threads 8, batch 512, ubatch 256, reasoning auto; thinking={'false' if 'thinkingfalse' in m['planned_attempts'][0]['configuration_id'] else 'true'}, cache-ram 0, no-cache-prompt. HTTP output cap 512, temp 0, seed 1, top_p 1. Warmup + three cohorts per condition; 30 minutes at slots4 only after all short checks. Baseline free+spec ≥24 GiB, runtime ≥8 GiB, swap 0, pressure level 1, AC/mode 0. Thresholds are not relaxed after rejection.

## Execution log

The [controller](raw/run_slots.py) verifies the artifact and all bundled dylibs before Popen, then checks readiness/props/template/logs/actual slots. The [driver](raw/concurrency_driver.py) saves every JSON request/response without retries. Cleanup affects only owned process groups. Admission rejection means no model was loaded, not OOM. Future not-run attempts and the primary error are preserved.

## Results

Attempts: {json.dumps(counts)}. Latency covers the complete response; throughput is primary completion tokens / cohort wall time. Observed busy slots indicate logical server concurrency.

| Slots | Condition | Responses / admission | p95, s | Throughput, tokens/s | Accepted |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Not run | — | — | — | — |'}

## Errors and limitations

{m['unavailable'].get('completion','All registered attempts were completed.')} Full GPU budget, temperature, energy, and TTFT are unknown. Output cap 512 differs from the earlier single-slot client queue with cap 2048; direct latency comparison between these series is invalid. Actual-slot evidence and logs are mandatory regardless of CLI parameters.

## Hypothesis conclusion

{m['conclusion']} Rejection before model launch yields no throughput data. Successful report submission does not imply a successful experiment or universal hardware support.

## Answers to review questions

1. Client concurrency may queue on one slot; processing slots establish logical concurrency, not simultaneous GPU kernels.
2. Short cohorts provide few p95 observations: this describes those requests, not a stable tail SLA.
3. Overall throughput is the sum of primary completion tokens / sum of block wall times; an unweighted average of individual tokens/s is wrong.
4. A throttling conclusion requires measured temperature/power/frequency and a load timeline; these collectors are absent, so a throughput decrease alone is insufficient.

## Submission bundle

Manifest v2, protocol/source registration, pin reference, primary admission/execution/errors, and TSV are retained. Every attempt is listed. lab:check submission checks completeness; reviewer decision **unverified**.
''')
