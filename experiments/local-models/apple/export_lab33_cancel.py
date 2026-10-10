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
 for path in sorted(folder.glob('backend-*/proof.json')):
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
(directory/'report.md').write_text(f'''# LAB33 — LM Studio: явная отмена и фактический backend

Сессия `{m['session_id']}`, статус **blocked**. {m['unavailable']['completion']}

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. Существующий центральный LM Studio 0.4.25+1 и selected runtimes llama.cpp/Metal 2.54.0, MLX/Metal 1.13.1. [Runtime](raw/runtime-manifest.json), [deployments](raw/deployments.json). GGUF Q6_K и MLX 4-bit — разные артефакты. SDK 1.5.0 установлен в отдельном venv; его wheels/dependencies закреплены hashes. Веса не скачивались, центральный app не переустанавливался.

Loader context 8192/parallel 1/gpu max — запрошенные настройки, не доказательство hard cap или всех 33 layers. SDK temperature 0/top_p 1/output cap 2048; seed, reasoning, KV и cache — defaults приложения с явными ограничениями. Точный source и pins для этой сессии находятся в её raw; отсутствие pinfile в неудачной preparation-сессии означает отсутствие модельной фазы, а не успешную проверку.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration закреплены commit до модели. Принимаются только собственные alias, один сервер 127.0.0.1:1234 и один loaded model. Admission — 120 с стабильно free+spec ≥16 GiB, pressure level 1, swap 0, AC/mode 0. Resource guard сохраняет минимум 8 GiB, RSS mapped backend ≤24 GiB, samples каждые 2 с/gap ≤15 с, bounded wall/request. Пороги не ослаблялись.

SDK chat/cancel/recovery и HTTP disconnect/recovery — отдельные условия, с прогревом и тремя повторами. SDK cancel после start и 1 с; iterator продолжается до primary stats, критерий userStopped и recovery. Final извлекается только по declared fragment reasoning_type, без trim/Markdown normalization. HTTP timeout и recovery не заменяют attributable request-id native stop. Физическое освобождение GPU страниц оценивается отдельно и остаётся unknown без collector.

## Ход выполнения

SDK schema/wheel verification → model/registry/backend pins → stable admission → controlled load → SDK/HTTP observations → собственный unload/server stop. Root PID и foreign models наблюдаются; чужие процессы не завершаются. [Контроллер](raw/run_lms.py), [клиент](raw/sdk_probe.py), [сводка](raw/runtime-summary.json).

Первый prototype сохранил SDK KeyError identifier после реального ответа LAB_READY. Result.model_info — LlmInfo с path/modelKey, instance identifier находится в loaded handle. Следующая preparation отказала при выборе GGUF вместо MLX и не создала pins; модели не запускались. Исправленный full-pin вариант сначала отказал на baseline resource admission. Эти сессии не переписаны; retry создаётся отдельно после стабильного resource window. Новая модельная фаза использует exact format/repository/revision selector и все 12 MLX registry bindings.

## Результаты

Attempts: {json.dumps(counts,ensure_ascii=False)}. В таблице — primary SDK status, raw final и фактическое время. Sample влияет на latency, поэтому sampled GGUF requests не сравниваются с unsampled baseline как одинаковые условия.

| Deployment/case/repeat | Статус | Primary stop / proof | Final / limit | Total / recovery, с |
| --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Не выполнялся | — | — | — |'}

## Ошибки и ограничения

{m['unavailable']['completion']} SDK userStopped — измеренный API status, не самостоятельный счётчик физических GPU страниц. OS stack sample доказывает наблюдаемый Metal call path во время контролируемого ответа; он не считает все offloaded layers. Runtime name/gpu ratio не заменяют фактическое доказательство. В частности, `stopGenerating() without a request_id … Taking no action` — отрицательное свидетельство, не pass отмены.

## Вывод по гипотезе

{m['conclusion']} Source/API/model identity и cancellation conclusions ограничены конкретной выполненной сессией. Прежние preparation failures и resource refusal не объявляются аппаратной несовместимостью. Полный LAB33 допуск сохраняет перечисленные blockers; unknown показатели не заменяются нулями.

## Ответы на контрольные вопросы

1. Общий API не удостоверяет backend: нужны version/package pins, loaded identity и фактические события/call path.
2. GPU ratio — конфигурация, не счётчик исполненных layers. Model path и registry hashes проверяются отдельно.
3. HTTP disconnect, SDK cancel, recovery, unload и освобождение физических GPU страниц — разные наблюдения.
4. Разные GGUF/MLX quantization/template/defaults исключают вывод об эффекте одного frontend по общей latency.

## Комплект сдачи

Manifest/TSV/protocol/source registrations, SDK wheel hashes/schema, model/backend/registry pins, raw SDK/HTTP/runtime events/OS samples, resources и cleanup сохранены. Агентных episodes нет, run_ids пуст. Submission проверяет комплектность; reviewer decision **не проверено**, experiment pass автоматически не назначается.
''')
print(json.dumps(dict(report=str(directory.relative_to(root)),attempts=counts)))
