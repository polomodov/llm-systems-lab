"""Offline report export for the three registered native MLX LAB32 sessions."""
import datetime
import hashlib
import json
import pathlib
import sys

root=pathlib.Path(__file__).resolve().parents[3]
from artifacts import select_artifact,missing_artifact_pins
directory=(root/sys.argv[1]).resolve()
assert directory.parent==root/'experiments/local-models/measurements' and directory.name.startswith('LAB32-apple-mlx-')
raw=directory/'raw'
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
manifest=json.loads((directory/'manifest.json').read_text())
pins=json.loads((raw/'prestart-pins.json').read_text())
runtime=json.loads((raw/'runtime-manifest.json').read_text())
artifact=select_artifact(json.loads((raw/'artifact-manifest.json').read_text()),format='MLX/safetensors',repository='mlx-community/Qwen3.5-9B-MLX-4bit',revision=runtime['model_revision'])
missing=missing_artifact_pins(artifact,pins)
summary=[];measurements=[];table=[]
for ctx in (8192,16384,32768):
    folder=raw/f'ctx{ctx}'
    if not (folder/'execution.json').exists():continue
    execution=json.loads((folder/'execution.json').read_text())
    samples=[json.loads(line) for line in (folder/'memory.jsonl').read_text().splitlines()] if (folder/'memory.jsonl').exists() else []
    times=[datetime.datetime.fromisoformat(row['timestamp']).timestamp() for row in samples]
    device=json.loads((folder/'device-after.json').read_text()) if (folder/'device-after.json').exists() else None
    row=dict(input_budget_label=ctx,hard_context_cap=None,execution=execution,device=device,samples=len(samples),
        max_gap_seconds=max((b-a for a,b in zip(times,times[1:])),default=None),
        max_rss_gib=max((r['server_rss_bytes'] for r in samples),default=0)/2**30 if samples else None,
        min_free_spec_gib=min((r['free_speculative_bytes'] for r in samples),default=0)/2**30 if samples else None,
        max_swap_bytes=max((r['swap_used_bytes'] for r in samples),default=None),
        memory_unavailable_reason=None if samples else 'Native model not spawned; resource monitor did not start.')
    summary.append(row)
    for path in sorted(folder.glob('*.metrics.json')):
        metrics=json.loads(path.read_text());name=path.name.removesuffix('.metrics.json');base=name.removesuffix('.followup')
        case,repeat=base.rsplit('-',1)
        label=f'ctx{ctx}-'+('cancel-recovery' if case=='recovery' else case)+'-'+repeat
        attempt=next(a for a in manifest['planned_attempts'] if a['id']==label)
        evidence=str(path.relative_to(directory));usage=metrics.get('usage') or {}
        table.append(f'| {ctx} | {name} | {usage.get("prompt_tokens")} / {usage.get("completion_tokens")} | {metrics.get("ttft_content_s")} | {metrics.get("duration_s")} | {attempt["status"]} |')
        for metric,value,unit in [('http_total_seconds',metrics.get('duration_s'),'s'),('ttft_content_seconds',metrics.get('ttft_content_s'),'s'),('input_tokens',usage.get('prompt_tokens'),'tokens'),('output_tokens',usage.get('completion_tokens'),'tokens')]:
            measurements.append([f'ctx{ctx}-{name}-{metric}',attempt['configuration_id'],'qwen35-9b-mlx-4bit','mlx-lm-0.32.0','metal','',repeat if repeat!='warmup' else '',metric,str(value) if value is not None else '',unit,'measured' if value is not None else 'unavailable',evidence,'' if value is not None else 'Not reported; non-streaming TTFT and missing usage are not estimated.'])
save(raw/'runtime-summary.json',summary)
manifest['status']='blocked'
failed=[a for a in manifest['planned_attempts'] if a['status']=='failed']
failure=failed[0]['reason'] if failed else next((s['execution']['error'] or 'Native execution not accepted' for s in summary if not s['execution']['accepted']),None)
audit_path=raw/'model-pins-audit.json'
identity_gap=json.loads(audit_path.read_text()) if audit_path.exists() else None
if identity_gap and not identity_gap['model_identity_verified_at_execution']:
    failure=identity_gap['reason']
    manifest['unavailable']['model_identity_at_execution']=failure
if missing:
    failure='Required MLX model files absent from execution-time prestart pins; historical deployment identity unverified.'
    manifest['unavailable']['model_identity_at_execution']=failure
qualified=[]
for s in summary:
    ctx=s['input_budget_label']
    cases=[a for a in manifest['planned_attempts'] if a['id'].startswith(f'ctx{ctx}-') and not a['id'].endswith(('startup','overflow'))]
    if not missing and s['execution']['accepted'] and s['execution'].get('verified_before_popen') and len(cases)==24 and all(a['status']=='completed' for a in cases):qualified.append(ctx)
complete=qualified==[8192,16384,32768] and not failure
manifest['status']='completed' if complete else 'blocked'
if complete:manifest['unavailable'].pop('completion',None)
else:manifest['unavailable']['completion']=failure or 'Registered input-budget route not fully qualified.'
manifest['unavailable'].update(
    gpu_budget_gib='Maximum GPU allocation not measured; device recommendation is not an observed cap.',energy='No energy collector.',temperature='No verified thermal collector.',physical_gpu_release='GenerationContext.stop and generation routine exit observed; allocator cache/OS GPU release not independently instrumented.')
manifest['conclusion']='Native MLX input-budget qualification: '+('blocked by '+failure if failure else 'qualified budgets '+','.join(map(str,qualified))+'; hard cap/physical GPU release unavailable.')
save(raw/'model-identity-summary.json',dict(required_model_files=len(artifact['files']),missing_prestart_files=missing,qualified_input_budgets=qualified,scope='Prestart coverage and recorded verified_before_popen/accepted proofs; no post-hoc model hash confirmation'))
manifest['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file())
save(directory/'manifest.json',manifest)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(row)+'\n' for row in measurements))
cancel=[]
for path in sorted(raw.glob('ctx*/cancel-*.proof.json')):
    row=json.loads(path.read_text());cancel.append(f'| {path.parent.name}/{path.stem} | {row.get("client_exit")} | {row.get("release_observed_seconds")} | {bool(row.get("stop_requested"))} / {bool(row.get("generation_end"))} |')
counts={status:sum(a['status']==status for a in manifest['planned_attempts']) for status in ('completed','failed','not-run','planned')}
(directory/'report.md').write_text(f'''# LAB32 — native MLX: protocols and input budgets

Session `{manifest['session_id']}`, status **{manifest['status']}**. {manifest['conclusion']}

{'**Execution-time MLX model identity unverified.** See raw/model-pins-audit.json; functional cases do not admit a specific artifact.' if identity_gap and not identity_gap['model_identity_verified_at_execution'] else ''}

## Run profile

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC / mode 0. MLX-LM 0.32.0, MLX 0.32.3, Python 3.12.14. Qwen3.5-9B MLX 4-bit affine / group64, revision `938d8919941c6e7efd3c7150eff7fe9d12afa631`. This is a separate VLM artifact used for text inference; the original conversion commit is unknown. [Artifact](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [{len(pins["files"])} pinned files](raw/prestart-pins.json), [model identity](raw/model-identity-summary.json). Actual loaded native images and device proofs are saved in ctx* directories. System frameworks are pinned by macOS version; individual file hashes are not claimed.

Hard context cap: **null**. Values 8192/16384/32768 denote input budgets, not KV reservations or server limits. One server at `127.0.0.1:8081`; seed 1, temperature 0, top_p 1, output cap 2048, thinking false, prefill step 2048, concurrency 1. Prompt cache size 0, unquantized KV, no operator changes to memory limits. The observation wrapper preserves original MLX-LM algorithms; its hash is a series condition.

## Hypothesis and protocol before execution

[Protocol](raw/protocol.md) and source-registration.json are committed before each series. Each condition has warmup and three repeats of four chat/tool JSON/SSE cases, long input, and cancellation with recovery. Exact expected values: LAB_READY, LAB_VALUE_42, LAB_SENTINEL_42; one lookup_lab_value with key alpha and a nonempty ID. Model-generated code is not executed.

Actual usage, token count, DONE, and finish reason are checked. Resource guard: samples every 2 s, maximum gap 15 s, minimum free+spec 8 GiB, pressure level 1, AC/mode 0, swap 0, maximum RSS 24 GiB. Wall limit: 900 s per condition and 240 s per request. Later budgets are not run after a rejection. New series additionally require cached_tokens=0.

## Execution log

Pins → tokenizer preparation without weights → offline allowlist → native server → short protocols → long → cancel/recovery → cleanup. [Controller](raw/run_series.py), [request hashes](raw/request-hashes.json), [allowlist](raw/allowlist.json). All original requests, responses, assembled messages, usage, and errors are retained. There are no agent attempts here; run_ids is empty.

Sessions are separate. `apple-mlx-protocol-20261010` incorrectly counted len(BatchEncoding)=2 and sent 113613 tokens: a protocol violation, not an 8K experiment. The controller rejected the usage mismatch and stopped the server. `apple-mlx-tokenids-20261010` correctly counted 4085 tokens but received Markdown in final content. `apple-mlx-exact-final-20261010` separately forbade Markdown and tied stop/end to one GenerationContext; all 24 cases at 8K passed, then 16K port preflight failed. `apple-mlx-budget-resume-20261010` checked SO_REUSEADDR and continued at 16K; its 12282-token long input finished, but the resource guard rejected free+spec 7.425 GiB. Earlier errors were not rewritten, and final-content normalization was not introduced. Separate `apple-mlx-identity-repeat-20261010` selected the correct MLX artifact and included all 12 files before Popen; its results are evaluated separately.

## Results

Attempts: {json.dumps(counts,ensure_ascii=False)}. Warmup is listed separately in the table. The TSV context_tokens column is empty because the hard cap is unknown. RSS, allocator peaks, swap, gaps, and cleanup are in the [summary](raw/runtime-summary.json).

| Input budget | Case / repeat | Actual input / output | TTFT content, s | Total, s | Attempt status |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table)}

| Cancellation condition | Client exit | Generation end observed after client exit, s | Stop / end observed |
| --- | --- | --- | --- |
{chr(10).join(cancel) or '| — | — | — | Not performed |'}

## Errors and limitations

{manifest['unavailable'].get('completion','Protocols for the tested input budgets are complete; hard cap and physical GPU release remain unverified.')} Native cancellation in v3 requires client exit 28 without DONE, the same context object, stop flag true, stop before generation end, and exact recovery within 60 s. A client timeout alone does not prove GPU cancellation. Allocator counters do not measure release of all physical GPU pages. Cold startup/JIT differs from warmed requests. The first two failed sessions did not execute cancellation; their mutable phase events are not used as cancellation evidence.

Hard cap and overflow are unverified; no OOM was induced to simulate them. Maximum GPU budget, energy, and temperature are unknown. Resource-guard rejection at pressure level 1 and swap 0 does not establish hardware incompatibility: observed conditions failed the preregistered reserve.

## Hypothesis conclusion

{manifest['conclusion']} Fully qualified budgets for this session: {qualified}. This accounts for every model pin before Popen and all 24 cases per condition; functional data from older sessions does not replace those requirements. Do not compare an input-budget label with llama.cpp hard context as an identical KV reservation, or transfer GGUF Q6_K estimates to MLX 4-bit. An MLX provider bridge requires a separate implementation; these requests are not agent attempts.

## Answers to review questions

1. Non-streaming total includes all generation: TTFT cannot be extracted from it and remains null.
2. Client CTX and architecture max_position_embeddings do not establish a verified server cap. IDs are counted with return_dict=False and checked separately against actual usage.
3. Socket timeout needs confirmation of the native stop flag, routine completion, and recovery; physical memory release needs a different collector.
4. Cache and reasoning change work and latency. Here, thinking is false and cache size is 0; GGUF with thinking true is another deployment.

## Submission bundle

Manifest, TSV, protocol, source pins, loaded images, device/model identity, requests and hashes, HTTP/SSE/usage/finals, native events, cancellation/recovery, resources and cleanup, offline allowlist, and software validation are retained. Submission checks the blocked report’s completeness. Reviewer decision: **unverified**; experiment pass is not assigned automatically.
''')
print(json.dumps(dict(report=str(directory.relative_to(root)),attempts=counts),ensure_ascii=False))
