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
(directory/'report.md').write_text(f'''# LAB34 — фактические серверные слоты

Сессия `{m['session_id']}`, статус **{m['status']}**. {m['conclusion']}

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5, AC/mode 0. Qwen3.5-9B GGUF Q6_K, revision 3885219b6810b007914f3a7950a8d1b469d598a5, llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a / Metal tensor tile16. [Точные hashes и runtime](raw/deployment-reference.json). MLX не используется. Это HTTP нагрузка, не агентный episode; run_ids пуст.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и [source registration](raw/source-registration.json) закреплены commit до исполнения. Серверные слоты 1/2/4, общий контекст slots×8192 и фактический контекст 8192 на каждом слоте. Параметры: KV f16/f16, FA on, threads 8, batch 512, ubatch 256, reasoning auto; thinking={'false' if 'thinkingfalse' in m['planned_attempts'][0]['configuration_id'] else 'true'}, cache-ram 0, no-cache-prompt. HTTP output cap 512, temp 0, seed 1, top_p 1. Прогрев + три когорты на условие; 30 минут slots4 только после всех коротких проверок. Baseline free+spec ≥24 GiB, runtime ≥8 GiB, swap 0, pressure level 1, AC/mode 0. Порог не ослабляется после отказа.

## Ход выполнения

[Контроллер](raw/run_slots.py) проверяет артефакт и все bundled dylib до Popen, затем readiness/props/template/logs/фактические слоты. [Driver](raw/concurrency_driver.py) сохраняет каждый JSON запрос/ответ без retries. Cleanup затрагивает только собственные process groups. Отказ admission означает отсутствие загрузки модели, а не OOM. Будущие попытки not-run и первичная ошибка сохраняются.

## Результаты

Attempts: {json.dumps(counts)}. Latency — полный ответ, throughput — primary completion tokens / wall когорты. Наблюдаемые busy slots означают логический параллелизм сервера.

| Slots | Условие | Ответы / admission | p95, с | Throughput, tokens/s | Принято |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Не запускалось | — | — | — | — |'}

## Ошибки и ограничения

{m['unavailable'].get('completion','Все зарегистрированные попытки выполнены.')} Полный GPU budget, температура, энергия и TTFT неизвестны. Output cap 512 отличается от прежней очереди клиентов на одном слоте с cap 2048; прямое сравнение latency этих серий некорректно. Доказательства реальных слотов и logs обязательны независимо от CLI параметров.

## Вывод по гипотезе

{m['conclusion']} При отказе до модели данных о throughput нет. Успешная сдача отчёта не означает успешный эксперимент или универсальную поддержку оборудования.

## Ответы на контрольные вопросы

1. Client concurrency может образовать очередь на одном слоте; processing slots подтверждают логический параллелизм, но не одновременные GPU kernels.
2. Короткие когорты дают мало наблюдений для p95, это описательная оценка этих запросов, не устойчивый tail SLA.
3. Общий throughput считается как сумма primary completion tokens / сумма wall блоков; среднее отдельных tokens/s без весов ошибочно.
4. Для вывода о throttling нужны измеренные температура/питание/частоты и timeline нагрузки; этих collectors нет, снижение throughput само по себе недостаточно.

## Комплект сдачи

Manifest v2, protocol/source registration, pin reference, первичные admission/execution/ошибки и TSV сохранены. Все attempts перечислены. lab:check submission проверяет комплектность; reviewer decision **не проверено**.
''')
