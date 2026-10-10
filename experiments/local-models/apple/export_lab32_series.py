"""Offline report export for the three registered native MLX LAB32 sessions."""
import datetime
import hashlib
import json
import pathlib
import sys

root=pathlib.Path(__file__).resolve().parents[3]
directory=(root/sys.argv[1]).resolve()
assert directory.parent==root/'experiments/local-models/measurements' and directory.name.startswith('LAB32-apple-mlx-')
raw=directory/'raw'
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
manifest=json.loads((directory/'manifest.json').read_text())
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
manifest['unavailable'].update(completion=failure or 'Hard context cap/overflow and independent physical GPU release unavailable; input-budget route only.',
    gpu_budget_gib='Maximum GPU allocation not measured; device recommendation is not an observed cap.',energy='No energy collector.',temperature='No verified thermal collector.',physical_gpu_release='GenerationContext.stop and generation routine exit observed; allocator cache/OS GPU release not independently instrumented.')
manifest['conclusion']='Native MLX input-budget qualification: '+('blocked by '+failure if failure else 'chat/tools/long/cancellation recovery completed at '+','.join(str(s['input_budget_label']) for s in summary)+'; hard cap unavailable.')
manifest['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file())
save(directory/'manifest.json',manifest)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(row)+'\n' for row in measurements))
cancel=[]
for path in sorted(raw.glob('ctx*/cancel-*.proof.json')):
    row=json.loads(path.read_text());cancel.append(f'| {path.parent.name}/{path.stem} | {row.get("client_exit")} | {row.get("release_observed_seconds")} | {bool(row.get("stop_requested"))} / {bool(row.get("generation_end"))} |')
counts={status:sum(a['status']==status for a in manifest['planned_attempts']) for status in ('completed','failed','not-run','planned')}
(directory/'report.md').write_text(f'''# LAB32 — MLX native input-budget qualification

Сессия `{manifest['session_id']}`, статус **blocked**. {manifest['conclusion']}

## Паспорт выполнения

Apple M5 Max /128GiB/macOS26.5/25F71, AC/mode0. MLX-LM0.32.0/MLX0.32.3/Python3.12.14; Qwen3.5-9B MLX4bit affine/group64 revision938d8919941c6e7efd3c7150eff7fe9d12afa631, отдельный VLM artifact в text-only inference. Исходнаяconversion revision неизвестна. [Artifact](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [267prestartpins](raw/prestart-pins.json), actual before/after loaded-images и device proofs вctx* directories. System frameworks закреплены macOSbuild, отдельноfilehashне заявлен.

Context hardcap **null**:8192/16384/32768 — labels input budgets, не KVreservation и не server caps. Один active server127.0.0.1:8081, seed1/temp0/top_p1/output2048/thinkingfalse/prefill2048/concurrency1. Prompt cache size0, full precision KV, без operator memory tuning. Observed entry wrapper не меняет оригинальные MLX-LM generation sources; его hash — часть конфигурации.

## Гипотеза и протокол до запуска

[Protocol](raw/protocol.md) и source-registration.json закреплены commit до каждого исполнения. Четыре chat/tool JSON/SSE fixtures, long и cancel/recovery: warmup+3 наbudget, новый owned server междуbudgets. Expected values exact LAB_READY/LAB_VALUE_42/LAB_SENTINEL_42, однаallowlisted lookup_lab_value/keyalpha/nonemptyid. Код модели не исполняется. Actualusage/tokenizer equality, DONE/finish, no-cacheusage, memoryguard2s/gap15s/free+spec8GiB/pressure1/ACmode0/swap0/RSS24GiB, wall900s/request240s. Послеотказаfuturebudgetnot-run.

## Ход выполнения

Source pins→CPUtokenization/shape/budget preparation→offlineallowlist→native server→shortprotocols→long→cancel/recovery→cleanup. [Controller](raw/run_series.py), [request hashes](raw/request-hashes.json), [offlineallowlist](raw/allowlist.json). Все rawrequests/responses/assembled/usage/errors сохранены; realagentepisodes не выполнялись, run_ids=[].

Три сессии разделены: исходная `apple-mlx-protocol-20261010` ошибочнопосчиталаlen(BatchEncoding)=2 и отправила113613actualtokens. Это protocol-invalid, не8Kопыт;контроллеротказалпослеusage mismatch иcleanup. `apple-mlx-tokenids-20261010` исправила flatIDs/count4085, но получила **LAB_SENTINEL_42** и отказалаexact-final. `apple-mlx-exact-final-20261010` отдельно запретилаMarkdown вlonginstruction и связала stop/end с одним nativeGenerationContext. Старые failures остаются неизменными; normalization не введена.

## Результаты

Attempts: {json.dumps(counts,ensure_ascii=False)}. Warmup не включается в median/p95; здесь приведены индивидуальные наблюдения. `context_tokens` вTSV пуст: hardcapнеизвестен. Runtime samples/RSS/allocator peaks/swap/exit/signal в [summary](raw/runtime-summary.json).

| Input-budget label | Case/repeat | Actualinput/output | TTFTcontent,s | Total,s | Attemptstatus |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table)}

| Cancel condition | Clientexit | End observed after clientexit,s | Stop/end observed |
| --- | --- | --- | --- |
{chr(10).join(cancel) or '| — | — | — | Not executed |'}

## Ошибки и ограничения

{manifest['unavailable']['completion']} Native generation cancellation требуетclientexit28/noDONE + samecontextobject/stopflagtrue/stop≤end и exactrecovery ≤60s в наблюдаемойv3конфигурации. Clienttimeout отдельно не доказывает GPUcancel. Getter allocator counters не измеряет физическоеосвобождениевсехGPUстраниц. Coldstartup/JIT отличается отwarmrequests. Первые две failedсессииcancelнеисполняли, ихmutablephaseeventsнеиспользуемкакcancelproof. Hardcap/overflowне имитируемOOM. Energy/thermal/maxGPUunknown с причинами.

## Вывод по гипотезе

{manifest['conclusion']} Результаты дают допуск только перечисленным input-budget protocols. Нельзя сравнивать label32K сllama.cpp hardcontext32K как одинаковуюKVreservation или переносить GGUFQ6_K size/performance наMLX4bit. НастоящийagentbridgeдляMLX остаётся отдельной инженерной задачей; эти HTTPзапросы неagentattempts.

## Ответы на контрольные вопросы

1. Non-streamingtotal включаетполнуюgeneration;TTFTиз него не извлекается, null.
2. ClientCTX и architecturemaxposition не задаютadmittedservercap. TokenIDs считаются явноreturn_dict=False и actualusage подтверждается отдельно.
3. Sockettimeout не прерываетGPUсам по себе: нужныnative stopflag/routineexit/queue recovery;physicalrelease требуетдругогоcollector.
4. Cache/reasoning меняютработуиTTFT: здесьthinkingfalse/cache0/seed1, usagecached0проверяется отдельно вновыхсериях;Gguf thinkingtrue — другойdeployment.

## Комплект сдачи

Manifest/TSV/protocol/sourcepins/loadedimages/device/modelidentity, requests/hashes, allHTTP/SSE/usage/finals, nativeevents/cancel/recovery, continuousresources/cleanup, offlineallowlist иsoftwarevalidation. Submissioncheck оцениваеткомплектностьblockedотчёта; reviewerdecision **не проверено**, experimentpassнеавтоматический.
''')
print(json.dumps(dict(report=str(directory.relative_to(root)),attempts=counts),ensure_ascii=False))
