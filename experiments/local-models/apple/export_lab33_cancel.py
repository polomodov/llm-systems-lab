"""Offline exporter; SDK stop status and Metal call path do not invent GPU page release."""
import datetime,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[3];directory=(root/sys.argv[1]).resolve();raw=directory/'raw'
assert directory.parent==root/'experiments/local-models/measurements' and directory.name.startswith('LAB33-apple-')
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
m=json.loads((directory/'manifest.json').read_text());rows=[];table=[];summaries=[]
for dep in ['lms-gguf','lms-mlx']:
 folder=raw/dep
 if not folder.exists():continue
 execution=json.loads((folder/'execution.json').read_text()) if (folder/'execution.json').exists() else None
 memory=[json.loads(l) for l in (folder/'memory.jsonl').read_text().splitlines()] if (folder/'memory.jsonl').exists() else []
 stamps=[datetime.datetime.fromisoformat(r['timestamp']).timestamp() for r in memory]
 summaries.append(dict(deployment=dep,execution=execution,samples=len(memory),max_gap_seconds=max((b-a for a,b in zip(stamps,stamps[1:])),default=None),
    min_free_spec_gib=min((r['free_speculative_bytes'] for r in memory),default=0)/2**30 if memory else None,
    max_backend_rss_gib=max((r.get('backend_process_rss_bytes',0) for r in memory),default=0)/2**30 if any('backend_process_rss_bytes' in r for r in memory) else None,
    max_swap_bytes=max((r['swap_used_bytes'] for r in memory),default=None)))
 for path in sorted(folder.glob('*/sdk-result.json')):
  record=json.loads(path.read_text());case,repeat=path.parent.name.rsplit('-',1);id=dep+'-'+case+'-'+repeat;plan=next(a for a in m['planned_attempts'] if a['id']==id);stats=record.get('stats') or {}
  table.append(f'| {dep}/{case}/{repeat} | {plan["status"]} | {stats.get("stopReason")} | {repr(record.get("final_content"))} | {record.get("total_seconds")} |')
  for metric,value,unit in [('sdk_total_seconds',record.get('total_seconds'),'s'),('sdk_input_tokens',stats.get('promptTokensCount'),'tokens'),('sdk_output_tokens',stats.get('predictedTokensCount'),'tokens')]:
   rows.append([id+'-'+metric,plan['configuration_id'],'qwen35-9b-q6' if dep=='lms-gguf' else 'qwen35-9b-mlx-4bit','lm-studio','metal','',repeat if repeat!='warmup' else '',metric,str(value) if value is not None else '',unit,'measured' if value is not None else 'unavailable',str(path.relative_to(directory)),'' if value is not None else 'Primary SDK field absent; no zero estimate.'])
 lifecycle=folder/'lifecycle-audit.json'
 if lifecycle.exists():summaries[-1]['lifecycle_audit']=json.loads(lifecycle.read_text())
 for path in sorted(folder.glob('backend-*/active-metal-proof.json')):
  proof=json.loads(path.read_text());table.append(f'| {dep}/{path.parent.name} | Metal call path: {proof.get("metal_call_path_observed")} | stream complete: {proof.get("stream_complete")} | all layers: null | — |')
 for path in sorted(folder.glob('http-cancel-*/proof.json')):
  proof=json.loads(path.read_text());table.append(f'| {dep}/{path.parent.name} | HTTP native cancel unverified | exit {proof.get("client_exit")} | physical GPU release: null | recovery {proof.get("recovery_end_seconds")} |')
save(raw/'runtime-summary.json',summaries)
m.update(status='blocked',conclusion='API cancellation/backend observations recorded; full LAB33 admission still requires attributable native HTTP cancellation and physical GPU/all-layer evidence.')
m['unavailable'].setdefault('completion','Native HTTP cancellation, physical GPU release/all-layer offload not fully proven.')
m['unavailable'].update(energy='No energy collector.',temperature='No thermal collector.',gpu_budget_gib='Maximum GPU allocation not measured.')
if not rows:m['unavailable']['measurements']='No completed SDK/HTTP inference; model phase did not start. Admission/resource observations are in raw files.'
m['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file());save(directory/'manifest.json',m)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(r)+'\n' for r in rows))
counts={s:sum(a['status']==s for a in m['planned_attempts']) for s in ['completed','failed','not-run','planned']}
(directory/'report.md').write_text(f'''# LAB33 — LM Studio: explicit cancellation and actual backend

Session `{m['session_id']}`, status **blocked**. {m['unavailable']['completion']}

## Run profile

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. Existing central LM Studio 0.4.25+1 and selected runtimes llama.cpp/Metal 2.54.0, MLX/Metal 1.13.1. [Runtime](raw/runtime-manifest.json), [deployments](raw/deployments.json). GGUF Q6_K and MLX 4-bit are different artifacts. SDK 1.5.0 is installed in a separate venv; its wheels/dependencies are pinned by hashes. No weights were downloaded and the central app was not reinstalled.

Loader context 8192/parallel 1/gpu max are requested settings, not evidence of a hard cap or all 33 layers. SDK temperature 0/top_p 1/output cap 2048; seed, reasoning, KV, and cache use application defaults with explicit limitations. This session’s raw directory holds exact source and pins; a missing pinfile in a failed preparation session means there was no model phase, not a successful check.

## Hypothesis and protocol before execution

[Protocol](raw/protocol.md) and source registration are committed before model execution. Only owned aliases, one server at 127.0.0.1:1234, and one loaded model are accepted. Admission requires 120 stable seconds of free+spec ≥16 GiB, pressure level 1, swap 0, AC/mode 0. The resource guard retains a minimum 8 GiB, mapped-backend RSS ≤24 GiB, samples every 2 s / gap ≤15 s, and bounded wall/request time. Thresholds were not relaxed.

SDK chat/cancel/recovery and HTTP disconnect/recovery are separate conditions, with warmup and three repeats. SDK cancellation occurs after start and 1 s; iteration continues to primary stats, with userStopped and recovery as criteria. Final content is extracted only by declared fragment reasoning_type, without trimming/Markdown normalization. HTTP timeout and recovery do not replace an attributable request-ID native stop. Physical GPU-page release is evaluated separately and remains unknown without a collector.

## Execution log

SDK schema/wheel verification → model/registry/backend pins → stable admission → controlled load → SDK/HTTP observations → owned unload/server stop. Root PID and foreign models are observed; other users’ processes are not terminated. [Controller](raw/run_lms.py), [client](raw/sdk_probe.py), [summary](raw/runtime-summary.json).

The first prototype retained an SDK KeyError identifier after a real LAB_READY response. Result.model_info is LlmInfo with path/modelKey; the instance identifier is in the loaded handle. The next preparation rejected GGUF selection instead of MLX and created no pins; no models ran. The corrected full-pin variant first failed baseline resource admission. These sessions were not rewritten; a retry is created separately after a stable resource window. The new model phase uses an exact format/repository/revision selector and all 12 MLX registry bindings.

## Results

Attempts: {json.dumps(counts,ensure_ascii=False)}. The table contains primary SDK status, raw final content, and actual timing. Sampling affects latency, so sampled GGUF requests are not compared with an unsampled baseline as identical conditions.

| Deployment/case/repeat | Status | Primary stop / proof | Final / limit | Total / recovery, s |
| --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Not performed | — | — | — |'}

## Errors and limitations

{m['unavailable']['completion']} SDK userStopped is a measured API status, not an independent physical GPU-page counter. An OS stack sample proves an observed Metal call path during a controlled response; it does not count all offloaded layers. Runtime name/gpu ratio do not replace actual evidence. In particular, `stopGenerating() without a request_id … Taking no action` is negative evidence, not a cancellation pass.

## Hypothesis conclusion

{m['conclusion']} Source/API/model identity and cancellation conclusions are limited to the specific executed session. The offline review audit accepts only counted compute/dispatch frames from Call graph, excluding Binary Images, summaries, and wait-only frames. Original proof.json/samples/execution and pins were not rewritten; active-metal-proof.json and lifecycle-audit.json are separate derived results. Executed source is retained in run_lms.executed.py, with its original SHA-256 in controller-review-audit.json. Corrected run_lms.py requires a new session and fresh pins, including lms_evidence.py. Normal successful unloading now clears loaded; historical loaded=true with models_after=[] remains in the primary record and is explained by the audit. The old evidence inventory describes original bytes; controller-review-audit.json maps the modified controller path to its original snapshot. Earlier preparation failures and resource refusals are not declared hardware incompatibility. Full LAB33 admission retains the listed blockers; unknown metrics are not replaced with zeros.

## Answers to review questions

1. A common API does not establish a backend: version/package pins, loaded identity, and actual events/call paths are needed.
2. GPU ratio is configuration, not a count of executed layers. Model paths and registry hashes are checked separately.
3. HTTP disconnect, SDK cancel, recovery, unload, and physical GPU-page release are different observations.
4. Different GGUF/MLX quantization/template/defaults prevent isolating a frontend effect from overall latency.

## Submission bundle

Manifest/TSV/protocol/source registrations, SDK wheel hashes/schema, model/backend/registry pins, raw SDK/HTTP/runtime events/OS samples, resources, and cleanup are retained. There are no agent episodes; run_ids is empty. Submission checks completeness; reviewer decision **unverified**, and experiment pass is not assigned automatically.
''')
print(json.dumps(dict(report=str(directory.relative_to(root)),attempts=counts)))
