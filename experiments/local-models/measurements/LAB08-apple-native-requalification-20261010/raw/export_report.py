"""Offline export from primary evidence; never judges the task or changes a run."""
import datetime
import hashlib
import json
import pathlib
import statistics
raw=pathlib.Path(__file__).resolve().parent
root=raw.parents[4]
report=raw.parent
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
manifest=json.loads((report/'manifest.json').read_text())
run_summaries=[]
for rid in manifest['run_ids']:
    directory=root/'results/runs'/rid
    run=json.loads((directory/'run.json').read_text())
    records=[json.loads(f.read_text()) for f in (directory/'trace/inference').glob('*record.json')]
    accepted=[r for r in records if r['accepted']]
    samples=[json.loads(l) for l in (directory/'trace/local-native/native-memory.jsonl').read_text().splitlines()]
    stamps=[datetime.datetime.fromisoformat(r['timestamp']).timestamp() for r in samples]
    summary=dict(run_id=rid,status=run['status'],stop_reason=run['loop']['stop_reason'],wall_seconds=run['loop']['wall_clock_s'],
        turns=run['loop']['turns'],exit_code=run['execution']['exit_code'],accepted_responses=len(accepted),jobs=len(records),
        partial_tokens_in=sum(r['usage']['input'] for r in accepted if r['usage']),partial_tokens_out=sum(r['usage']['output'] for r in accepted if r['usage']),
        samples=len(samples),max_gap_seconds=max(b-a for a,b in zip(stamps,stamps[1:])),max_rss_gib=max(r['server_rss_bytes'] for r in samples)/2**30,
        max_swap_bytes=max(r['swap_used_bytes'] for r in samples),shutdown=json.loads((directory/'trace/local-native/shutdown-process.json').read_text()))
    run_summaries.append(summary)
    # Primary snapshot inventory excludes ignored task workspace and the inventory itself.
    files={str(f.relative_to(directory)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest())
        for base in ['inputs','trace'] for f in (directory/base).rglob('*') if f.is_file()}
    files['run.json']=dict(bytes=(directory/'run.json').stat().st_size,sha256=hashlib.sha256((directory/'run.json').read_bytes()).hexdigest())
    save(directory/'primary-sha256.json',dict(scope='run.json + sealed inputs + primary trace; workspace excluded',files=files))
    attempt=next(a for a in manifest['planned_attempts'] if a['run_id']==rid)
    if run['status']=='aborted':attempt.update(status='failed',reason='Actual pilot aborted: '+str(run['loop']['stop_reason'])+'; see primary trace.',evidence_files=['raw/primary-summary.json'])
    elif run['status']=='awaiting_review':attempt.update(status='planned',reason='Execution finished; independent hidden-check pending, not completed.',evidence_files=['raw/primary-summary.json'])
    else:raise RuntimeError('Export expects actual stopped evidence')
save(raw/'primary-summary.json',run_summaries)
qualifications=[]
for label,folder in [('native-short',raw),('native-short16',raw/'ctx16'),('native-short16-retry',raw/'ctx16-retry')]:
    if not (folder/'qualification.json').exists():continue
    q=json.loads((folder/'qualification.json').read_text());qualifications.append((label,q))
    next(a for a in manifest['planned_attempts'] if a['id']==label).update(status='completed' if q['accepted'] else 'failed',reason=None if q['accepted'] else q['error'] or 'qualification rejected',evidence_files=[str((folder/'qualification.json').relative_to(report))])
manifest.update(status='blocked',conclusion='Короткие native qualifications завершены; T002 attempts сохранены отдельно. Полный агентный допуск требует independently judged pilot.',reviewer_decision=None)
manifest['unavailable'].update(completion='Нет независимо оценённого успешного T002 pilot.',energy='Энергия не измерялась.',temperature='Нет подтверждённого thermal collector.',gpu_budget_gib='Максимальный GPU budget не измерен.',ttft='Bridge buffers SSE; no TTFT measurement.')
manifest['evidence_files']=sorted(str(f.relative_to(report)) for f in raw.rglob('*') if f.is_file() and f.name!='evidence-sha256.json')
save(report/'manifest.json',manifest)
rows=[]
for label,q in qualifications:
    context=8192 if label=='native-short' else 16384
    folder=raw if context==8192 else raw/'ctx16-retry' if label.endswith('retry') else raw/'ctx16'
    configuration=next(a['configuration_id'] for a in manifest['planned_attempts'] if a['id']==label)
    for request in q['requests']:
        rows.append([f'{label}-r{request["repeat"]}',configuration, 'qwen35-9b-q6','llama-cpp','metal',str(context),str(request['repeat']) if request['repeat'] else '','http_total',str(request['wall_seconds']),'s','measured',str((folder/'qualification.json').relative_to(report)),''])
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split()
(report/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(row)+'\n' for row in rows))
table='\n'.join(f'| `{s["run_id"]}` | {s["status"]}/{s["stop_reason"]} | {s["accepted_responses"]}/{s["jobs"]} | {s["wall_seconds"]} | {s["max_gap_seconds"]:.3f} | {s["max_rss_gib"]:.3f} |' for s in run_summaries)
(report/'report.md').write_text(f'''# LAB08 — новая native квалификация и Pi T002

Статус **blocked**: короткая аппаратная квалификация и настоящие pilot attempts сохранены. Независимого pass задачи нет.

## Паспорт выполнения

Apple M5 Max / 128GiB / macOS26.5/25F71, AC/mode0; pinned llama.cpp312cf033 + tile16 / Metal, Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5. [Deployment8K](raw/deployment.json), [deployment16K](raw/ctx16/deployment.json). Pi0.73.1/native SDK в isolated Docker. Context8192→16384, output2048, slot1/KVf16, temp0/seed1/top_p1/thinkingtrue, no prefix cache. USD budget observed; policy и images находятся в run.json. Source registration ae1b9e2 и083bdcf; поправка16K d1e6cf8.

## Гипотеза и протокол до запуска

[Protocol](raw/protocol.md) до исполнения; [поправка после overflow8K](raw/context-amendment.md) до новой квалификации16K. Warmup+3 exact SSE chat, verify25pins до Popen и после запросов,20s idle, cleanup0/одинSIGINT. Resource samples2s, stale>15s/clock backwards, wall180s. Затем новый sealed T002 pilot с timeout900s. Synthetic negative guard tests остаются отдельным software evidence; suspend/clock на машине не имитировали. Full host suspension не допускает исполнения guard до resume.

## Ход выполнения

Короткая8K серия → настоящий T0028K → сохранённый отказ8265>8192 → отдельная16K qualification и новыйrun. Предыдущие два aborted из LAB08-apple-provider-bridge-20261009 остаются неизменными. Команды и bodies сохранены в raw и primary run traces. Ни одного hidden-check не читали/не выполняли агентом.

## Результаты

8K:4/4 exact LAB_READY,30samples/maxgap2.016s/RSSpeak7.422GiB/swap0, total63.514s включая startup/verify/idle/cleanup. Первая16K qualification дала4/4HTTP, но **не допущена**: free+spec7.785GiB<8GiB. [Исходный результат](raw/ctx16/qualification.json), [первая unsafe строка](raw/ctx16/native/native-memory.jsonl). Последующая ps ошибка затёрла первичныйguard; новый supervisor сохраняет первую причину и прекращает polling. [Поправка](raw/first-guard-amendment.md) и новый retry имеют отдельную регистрацию. Три повтора отделены отwarmup, coldstartup не считается latency запроса.

| Run | Итог | Accepted/jobs | Agent wall,s | Max gap,s | Peak RSS,GiB |
| --- | --- | --- | --- | --- | --- |
{table}

[Primary summary](raw/primary-summary.json) содержит partial usage, samples и cleanup. Partial tokens не выданы за полный итог interrupted request. Cost/energy/temperature/maxGPU остаютсяnull с причиной. Primary inputs/trace inventories доступны в каждом run; native pre-Popen hashes включают все23enginepaths/21dylibpaths, GGUF и passport.

## Ошибки и ограничения

8K pilot22-й запрос: HTTP400 `exceed_context_size_error`,8265prompttokens>8192. 21ответ принят, nativeexit0/одинSIGINT,146samples/maxgap2.161s/swap0. Это другой отказ, не повтор прежнего telemetry gap. Менять задним числом context или aborted нельзя. Новый16K — отдельная конфигурация с новымfingerprint и run ID. Ни CLIexit0, ни tool transport не заменяют независимую оценку задачи. При awaiting_review отчёт остаётся draft, пока judge pending; aborted не judge-ятся как pass. Идентичность/runtime safeguards проверены, вклад bridge в качество не установлен.

## Вывод по гипотезе

Native короткая8K квалификация поддержала непрерывность telemetry в наблюдавшемся интервале. T0028K выявил ограничение длины, bridge сохранил ошибку и cleanup. По16K выводы только из нового run/qualification. Полный LAB08 допуск требует independently judged successful pilot; агентную LAB09 кампанию не расширять до этого. Независимая MLX HTTP LAB32 может идти дальше.

## Ответы на контрольные вопросы

1. LAN allowlist не ограничивает модельный endpoint; internal broker принимает только fixed chat API, target выбирает trusted worker.
2. Alias не удостоверяет weights; manifest hashes, PID, command, props/template удостоверяют deployment.
3. GPU model вне2GiB container: это граница agent harness; отдельный native guard контролирует Mac.
4. Backend/context/build/OS входят в fingerprint;16K не объединяется с8K.
5. Mock подтверждает transport, настоящий T002 требует own run и independent verdict.
6. SDKprice0 не измеряет energy/железо;costnull. Отсутствующее usage canceled/rejected запроса тожеnull.

## Комплект сдачи

Manifest/TSV/protocol/amendment, deploymentpins, rawHTTP/usage/serverlogs, continuous samples/cleanup, sealed inputs/trace и tests сохранены. Software/lab integrity проверка сохраняется отдельно в raw. Reviewer decision: **не проверено**. Полнота blocked отчёта не означает passT002.
''')
save(raw/'evidence-sha256.json',{str(f.relative_to(report)):hashlib.sha256(f.read_bytes()).hexdigest() for f in raw.rglob('*') if f.is_file() and f.name!='evidence-sha256.json'})
print(json.dumps(run_summaries,indent=2))
