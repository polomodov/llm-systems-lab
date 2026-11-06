"""Matched messages compare whole deployments, never infer an isolated backend effect."""
import datetime,json,pathlib,statistics,sys
from preregistration import verify_preregistration
root=pathlib.Path(__file__).resolve().parents[3];directory=(root/sys.argv[1]).resolve();raw=directory/'raw';m=json.loads((directory/'manifest.json').read_text());rows=[];table=[];summary={}
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
registration=json.loads((raw/'source-registration.json').read_text())
starts=[json.loads(f.read_text())['started_at'] for f in raw.glob('*/execution.json')]
receipt=verify_preregistration(root,registration.get('preregistration_commit'),registration.get('registered_files',{}),min(starts))
save(raw/'preregistration-audit.json',receipt)
if not receipt['verified']:
 m['status']='blocked';m['unavailable']['completion']='Preregistration history/blob verification failed: '+str(receipt['errors']);m['conclusion']='Matched HTTP observations preserved; preregistration not verified.'
def add(id,config,dep,repeat,metric,value,unit,path):rows.append([id+'-'+metric,config,'qwen35-9b-'+('q6' if dep=='gguf' else 'mlx-4bit'),'llama.cpp' if dep=='gguf' else 'mlx-lm','metal','8192',repeat if repeat!='warmup' else '',metric,str(value) if value is not None else '',unit,'measured' if value is not None else 'unavailable',str(path.relative_to(directory)),'' if value is not None else 'Primary field absent; no estimate.'])
for dep in ('gguf','mlx'):
 folder=raw/dep
 if not folder.exists():continue
 execution=json.loads((folder/'execution.json').read_text());memory=[json.loads(l) for l in (folder/'memory.jsonl').read_text().splitlines()] if (folder/'memory.jsonl').exists() else [];summary[dep]=dict(cold_ready_seconds=execution.get('cold_ready_seconds'),max_rss_gib=max((r['server_rss_bytes'] for r in memory),default=None),min_free_spec_gib=min((r['free_speculative_bytes'] for r in memory),default=None),max_swap_bytes=max((r['swap_used_bytes'] for r in memory),default=None),samples=len(memory),cleanup_returncode=execution.get('returncode'),sigint_count=execution.get('sigint_count'),guard=execution.get('guard'))
 summary[dep]['protocol_accepted']=all(a['status']=='completed' for a in m['planned_attempts'] if a['id'].startswith(dep+'-')) and execution.get('returncode')==0 and execution.get('sigint_count')==1 and execution.get('guard') is None
 summary[dep]['sampling_period_seconds']=2
 summary[dep]['rss_peak_coverage']='Sampled RSS only; very short series has one sample, true peak unmeasured.'
 summary[dep]['cold_ready_scope']='Popen to /v1/models API readiness, not a model-load or cold filesystem measurement.'
 for metric in ('max_rss_gib','min_free_spec_gib'):
  if summary[dep][metric] is not None:summary[dep][metric]/=2**30
 for f in sorted(folder.glob('*.metrics.json')):
  r=json.loads(f.read_text());case,repeat=f.name.removesuffix('.metrics.json').rsplit('-',1);id=f'{dep}-{case}-{repeat}';attempt=next(a for a in m['planned_attempts'] if a['id']==id);usage=r.get('usage') or {};final=folder/(case+'-'+repeat+'.final.json');content=json.loads(final.read_text()).get('content') if final.exists() else None
  table.append(f'| {dep}/{case}/{repeat} | {attempt["status"]} | {repr(content)} | {r.get("ttft_content_s")} | {r.get("duration_s")} | {usage.get("prompt_tokens")}/{usage.get("completion_tokens")} |')
  for metric,value,unit in [('ttft_content_s',r.get('ttft_content_s'),'s'),('duration_s',r.get('duration_s'),'s'),('prompt_tokens',usage.get('prompt_tokens'),'tokens'),('completion_tokens',usage.get('completion_tokens'),'tokens')]:add(id,attempt['configuration_id'],dep,repeat,metric,value,unit,f)
save(raw/'runtime-summary.json',summary);m['unavailable'].update(energy='No energy collector.',temperature='No temperature collector.',gpu_budget_gib='Maximum GPU allocation not measured.',mlx_hard_context_cap='MLX labels an input budget, not a reserved KV context or hard cap.')
m['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file());save(directory/'manifest.json',m)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split();(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(r)+'\n' for r in rows))
counts={s:sum(a['status']==s for a in m['planned_attempts']) for s in ('completed','failed','not-run')}
(directory/'report.md').write_text(f'''# LAB31 — identical HTTP inputs for GGUF and MLX

Session `{m['session_id']}`, status **{m['status']}**. {m['conclusion']}

## Run profile

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. GGUF Q6_K revision 3885219b6810b007914f3a7950a8d1b469d598a5 / llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a tensor tile16 Metal versus MLX affine 4-bit/group64 revision 938d8919941c6e7efd3c7150eff7fe9d12afa631 / MLX-LM 0.32.0 / MLX 0.32.3. Exact paths/bytes/hashes: [GGUF](raw/gguf-reference.json), [MLX runtime](raw/runtime-manifest.json), [artifacts](raw/artifact-manifest.json), [full MLX prestart pins](raw/prestart-pins.json). The two MLX safetensors shards are not estimated from GGUF size. The VLM artifact is used only for text. No agent episodes.

## Hypothesis and protocol before execution

[Protocol](raw/protocol.md) and source registration are committed before execution: `64d17b0cf302e606206b3b8c29022b9b6071da49`, a retained ancestor of the current branch. The [audit](raw/preregistration-audit.json) verifies 10 exact blobs and recorded commit time 11:31:31Z before GGUF started at 11:31:31.819526Z. `parent_commit=efab7f2` means the preparation parent, not registration proof. Git timestamps are not independent clock attestation. A missing ancestor or file, mismatching bytes, or late commit makes the exporter mark the session blocked. Order: GGUF → MLX, one owned server. [Inputs](raw/shared-inputs.json) have identical messages; temp 0, seed 1, top_p 1, output cap 256, thinking false, streaming/include_usage. Each input has one warmup and three repeats. Final content is compared literally, without trimming or normalization. Internal templates, token IDs, and quantization may differ: whole deployments are evaluated.

## Execution log

The [controller](raw/run_common.py) checks model/native pins before Popen, absence of foreign models, and the port. GGUF logs/props/slots establish M5/tensor/offload 33/33/context 8192. The MLX observer checks the actual default GPU, loaded native images, and allocator. Resource guard every 2 s: free+spec ≥8 GiB, pressure level 1, swap 0, AC/mode 0, RSS ≤24 GiB, gap ≤15 s, deadline 900 s. HTTP client limit: 120 s. Shutdown: one owned SIGINT, 30 s, then kill the owned process if needed. The OS and other users’ applications are unchanged.

## Results

Attempts: {json.dumps(counts)}. API readiness from Popen is recorded separately in the [runtime summary](raw/runtime-summary.json). TTFT is the first nonempty content delta; total is time to complete SSE; usage comes from the primary response.

| Deployment/case/repeat | Status | Raw final | TTFT, s | Total, s | Input/output tokens |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Not performed | — | — | — | — |'}

## Errors and limitations

{m['unavailable'].get('completion','All registered attempts were completed.')} Identical messages do not imply identical prompt-token counts. /v1/models readiness does not establish complete MLX loading: the model provider loads weights on the first request, so warmup includes loading. Hashing warms the filesystem cache beforehand; cold cache was not measured. These are short series, with one resource-collector sample each: sampled RSS is not called a true peak. execution.accepted remained false because of an unused controller initial value; the original file is retained. Final protocol_accepted in the runtime summary is derived from the full attempt register, exit/SIGINT, and absence of guards, not this field. GGUF reserves context 8192; the MLX short-input budget 8192 is not a hard cap. Three repeats do not establish statistical equivalence. Energy, temperature, and maximum GPU budget are unknown. Different formats and quantization prevent isolating the Metal/MLX backend effect.

## Hypothesis conclusion

{m['conclusion']} The conclusion is limited to these inputs, settings, versions, and memory state. HTTP primitive speed does not establish autonomous-agent quality.

## Answers to review questions

1. A new CLI command starts a new process and may include loading weights; this uses a resident HTTP server, with cold readiness separated.
2. 4-bit MLX and GGUF Q6_K use different quantization schemes, packing, kernels, and templates; the engine effect is not isolated.
3. RSS measures the owned server PID; MLX allocator active/cache/peak are observed separately. Do not sum overlapping pages.
4. /v1/models reports an alias but does not verify bytes/revision/runtime. Full prestart hashes, actual model path, native loaded images, and pinned source are required.

## Submission bundle

Manifest v2, protocol, source registration, full model/native pins, raw inputs/SSE/finals/metrics, continuous resource observations, and cleanup are retained. TSV stores individual observations with conditions. lab:check submission checks the bundle; reviewer decision **unverified**.
''')
