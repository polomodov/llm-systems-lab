# -*- coding: utf-8 -*-
"""Finalize the registered 8K/16K/32K campaign; keep its 8K checkpoint."""
import csv, hashlib, json, pathlib, re, statistics
CONTEXTS = [8192, 16384, 32768]
def context_for_case(case,attempts):
    matches=[]
    for value in [case,attempts[case]['configuration_id']]:
        match=re.search(r'(?:^|-)ctx([0-9]+)(?:-|$)',value)
        if match:matches.append(int(match.group(1)))
    if not matches or any(value not in [8192,16384,32768] for value in matches) or len(set(matches))!=1:
        raise ValueError('Missing, unsupported or conflicting context for '+case)
    return matches[0]

def export_measurements(raw,root,attempts):
    records={};groups={}
    with (root/'measurements.tsv').open('w',newline='') as f:
        writer=csv.writer(f,delimiter='\t',lineterminator='\n')
        writer.writerow(['observation_id','configuration_id','model_id','engine','backend','context_tokens','repeat','metric','value','unit','status','evidence_path','unavailable_reason'])
        for path in sorted(raw.glob('*.metrics.json')):
            label=path.name.removesuffix('.metrics.json');case=label.removesuffix('.followup')
            if case not in attempts:continue
            data=json.loads(path.read_text());records[label]=data
            values=[('duration',data.get('duration_s'),'seconds'),('http_status',data.get('http_status'),'http-status'),
                ('ttft_content',data.get('ttft_content_s'),'seconds'),('ttft_reasoning',data.get('ttft_reasoning_s'),'seconds')]
            if data.get('usage'):
                values += [(key,data['usage'].get(key),'tokens') for key in ['prompt_tokens','completion_tokens']]
            for metric,value,unit in values:
                writer.writerow([label+'-'+metric,attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tensor','metal',context_for_case(case,attempts),
                    re.search(r'-r([123])$',case).group(1) if re.search(r'-r([123])$',case) else '',metric,value if value is not None else '',unit,
                    'measured' if value is not None else 'unavailable','raw/'+path.name,'' if value is not None else 'Not reported; JSON has no token timing or the corresponding channel did not occur.'])
        for case in attempts:
            if not re.fullmatch(r'ctx[0-9]+-(cancel|overflow)',case):continue
            path=raw/(case+'-execution.json')
            if not path.exists():continue
            data=json.loads(path.read_text())
            for metric,key,unit in [('slot_release_after_disconnect','release_after_client_s','seconds'),('http_status','status','http-status'),('error_wall','wall_seconds','seconds'),('curl_exit','exit_code','exit-code')]:
                if key in data:writer.writerow([case+'-'+metric,attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tensor','metal',context_for_case(case,attempts),'',metric,data[key],unit,'measured','raw/'+path.name,''])
    return records,groups

def finalize(root):
    raw = root / 'raw'
    manifest = json.loads((root/'manifest.json').read_text())
    attempts = {a['id']:a for a in manifest['planned_attempts']}
    failed = [a['id'] for a in attempts.values() if a['status']=='failed']
    if failed:
        for a in attempts.values():
            if a['status']=='planned':
                a.update(status='not-run', reason='Earlier admission failed; sequential campaign stopped.')
    completed = all(a['status']=='completed' for a in attempts.values())
    # Validate every admitted context against primary evidence before writing exports.
    details = {}
    for ctx in CONTEXTS:
        cases = [a for a in attempts.values() if a['id'].startswith(f'ctx{ctx}-')]
        if not cases or not all(a['status']=='completed' for a in cases):
            continue
        startup = json.loads((raw/f'ctx{ctx}-startup-execution.json').read_text())
        execution = json.loads((raw/f'ctx{ctx}-server-execution.json').read_text())
        count = json.loads((raw/f'ctx{ctx}-long-count.json').read_text())
        assert startup['accepted'] and startup['context']==ctx and startup['tensor_api']
        assert execution['returncode']==0 and execution['guard_reason'] is None
        assert ctx-4192 < count['input_tokens'] <= ctx-4096
        for kind in ['chat','chat-stream','tool','tool-stream','long']:
            for repeat in ['warmup','r1','r2','r3']:
                record = json.loads((raw/f'ctx{ctx}-{kind}-{repeat}-execution.json').read_text())
                assert record['accepted']
                if kind=='long':
                    assert record['metrics']['usage']['prompt_tokens']==count['input_tokens']
        cancel = json.loads((raw/f'ctx{ctx}-cancel-execution.json').read_text())
        overflow = json.loads((raw/f'ctx{ctx}-overflow-execution.json').read_text())
        assert cancel['accepted'] and cancel['exit_code']==28 and cancel['idle_after'] and cancel['server_cancellation_log']
        assert overflow['accepted'] and overflow['status']==400
        for effect in ['cancel','overflow']:
            assert json.loads((raw/f'ctx{ctx}-{effect}-recovery-execution.json').read_text())['accepted']
        timeline = [json.loads(line) for line in (raw/f'ctx{ctx}-memory.jsonl').read_text().splitlines()]
        details[str(ctx)] = dict(input_tokens=count['input_tokens'], input_budget=count['input_budget'],
            max_rss_bytes=execution['max_rss_bytes'], min_free_pages_bytes=min(r['free_pages_bytes'] for r in timeline),
            max_swap_used_bytes=max(r['swap_used_bytes'] for r in timeline),
            slot_release_after_disconnect_s=cancel['release_after_client_s'],
            overflow_input_tokens=json.loads((raw/f'ctx{ctx}-overflow-count.json').read_text())['input_tokens'],
            overflow_http_status=overflow['status'], started_at=execution['started_at'], ended_at=execution['ended_at'])
    if completed:
        assert set(details)==set(map(str,CONTEXTS)), 'Every context needs primary admission evidence'
    records, _ = export_measurements(raw,root,attempts)
    groups = {}
    for ctx in CONTEXTS:
        for kind in ['chat','chat-stream','tool','tool-stream','long']:
            values=[]
            for n in [1,2,3]:
                case=f'ctx{ctx}-{kind}-r{n}'
                if attempts[case]['status']=='completed':
                    primary=records[case];follow=records.get(case+'.followup')
                    values.append(primary['duration_s']+(follow['duration_s'] if follow else 0))
            if values:
                groups[f'ctx{ctx}-{kind}']=dict(context_tokens=ctx,case=kind,values=values,
                    median_seconds=statistics.median(values),min_seconds=min(values),max_seconds=max(values))
    status='completed' if completed else 'blocked' if failed else 'in-progress'
    conclusion = ('Все этапы 8K/16K/32K прошли protocol и resource admission; допуск ограничен проверенными fixtures и условиями.'
        if completed else 'Кампания не завершена; допуск только для полностью проверенных этапов: '+', '.join(details)+'. Отказы: '+', '.join(failed)+'.')
    summary=dict(conclusion=conclusion,condition='reasoning=auto / enable_thinking=true',
        contexts=CONTEXTS,admitted_contexts=list(map(int,details)),higher_contexts_measured=any(int(c)>8192 for c in details),
        case_statistics=groups,context_details=details,
        attempts={s:sum(a['status']==s for a in attempts.values()) for s in ['completed','failed','not-run','planned']})
    summary['failure_analysis'] = json.loads((raw/'ctx32768-failure-analysis.json').read_text()) if (raw/'ctx32768-failure-analysis.json').exists() else None
    (raw/'campaign-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    table='\n'.join(f"| {v['context_tokens']} | {v['case']} | {len(v['values'])} | {v['median_seconds']:.3f} | {v['min_seconds']:.3f}–{v['max_seconds']:.3f} |" for v in groups.values())
    resources='\n'.join(f"| {ctx} | {v['input_tokens']} / {v['input_budget']} | {v['max_rss_bytes']/2**30:.3f} | {v['min_free_pages_bytes']/2**30:.2f} | {v['max_swap_used_bytes']/2**30:.3f} | {v['slot_release_after_disconnect_s']:.3f} | {v['overflow_input_tokens']} / {v['overflow_http_status']} |" for ctx,v in details.items())
    failure_note = ('На 32K длинный warmup: input28670, HTTP200/SSE DONE, finish_reason=length, output2048, final content пуст. Sentinel присутствует в reasoning, поэтому потеря контекста не доказана; зарегистрированный final contract не выполнен. Long r1–r3, cancel/overflow/recovery на32K не запускались. Native shutdown exit0, swap0. [Разбор](raw/ctx32768-failure-analysis.json). Никаких retry или смены output cap/reasoning в исходной серии.' if 'ctx32768-long-warmup' in failed else '')
    report=f'''# LAB32 — контекст и инструменты на Apple M5 Max

Сессия: `{manifest['session_id']}`. Статус: **{status}**. {conclusion}

## Паспорт выполнения

Codex по запросу владельца, 07–08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5 build25F71, arm64. Нативный llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. [Runtime](raw/runtime-manifest.json), свежая [проверка продолжения](raw/continuation-preflight.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto/enable_thinking=true, temperature0/seed1/top_p1, prefix cache отключён сервером и request.cache_prompt=false. Один собственный server на loopback8080; hard caps8192/16384/32768 проверяются props/slots и log, offload33/33, tensor=true. Harness отсутствует; run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), его [hash](raw/protocol.sha256) и register сохранены до запуска. Прогрев и три повтора каждого chat/tool × JSON/SSE и long case; cancel/overflow с recovery на каждом контексте. Последовательный допуск8K→16K→32K. 8K измерен07.10, продолжение08.10 зарегистрировано [отдельно](raw/continuation-registration.json) без смены условий. Разница дней входит в условия сравнения, нет независимого удостоверения времени регистрации.

## Ход выполнения

На каждом контексте отдельный native server start/device/hard-cap verification. Final chat=LAB_READY; tool exactly1 lookup_lab_value(key=alpha), непустой call ID, связанный фиксированный resultLAB_VALUE_42, final=LAB_VALUE_42. Код модели не исполнялся. SSE требует DONE; usage и content/reasoning timings сохранены раздельно. Offline name/key/id allowlist — synthetic exercise, отдельно от модели.

Следующие проверки описывают протокол; принятые этапы: {', '.join(details) or 'нет'}. Long prompt построен серверными apply-template/tokenize с теми же thinking options, близок к input budgetCTX−4096, max_tokens2048; actual usage совпадает, final=LAB_SENTINEL_42. Cancel: curl timeout1s, exit28, активный slot наблюдается, DONE отсутствует, server cancel log, idle и recovery без restart. Overflow: точный input>hard cap, context-specific HTTP400 и recovery без restart. Успешность каждого воздействия определяется его attempt status и raw execution; при отказе следующие попытки не выполняются. Все первичные request/response, prompts/counts, timestamps, server logs и memory timeline сохранены. Серверы остановлены одним SIGINT верифицированному native child.

## Результаты

Медианы только r1–r3, прогрев отдельно. Tool round trip — сумма двух HTTP-вызовов. Cold startup не входит в latency, cache выключен. TTFT для JSON недоступен; SSE content и reasoning — в [TSV](measurements.tsv). [Сводка](raw/campaign-summary.json).

| Hard context | Case | Повторов | Median total s | Min–max s |
| ---: | --- | ---: | ---: | --- |
{table}

| Hard context | Long input / budget | Max RSS GiB | Min free pages GiB | Max swap GiB | Slot release after disconnect s | Overflow input / HTTP |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
{resources}

## Ошибки и ограничения

{failure_note}

Исходная thinking=false серия остаётся blocked в соседнем отчёте: модель не вызвала tool. Auto — самостоятельное условие, не исправление её результатов. Ошибка двойного SIGINT и TIME_WAIT port guard была исправлена до этой серии; новые модельные повторы не подменяли failures. Архив checkpoint8K сохранён в raw/checkpoint-8k-*; phase-summary.json и finalize_phase.py описывают только прежний этап, итог всей кампании — campaign-summary.json и finalize_campaign.py.

Swap0/free-page floor16GiB/RSS ceiling24GiB/AC powermode0 наблюдались каждые2s. RSS не складывается с пересекающимися Metal buffers. Отмена подтверждена slot/log/recovery, не instruction-level GPU trace; prefill может продолжаться после client disconnect. Energy/temperature и максимальный безопасный GPU budget не измерены. Результат относится к одной модели/квантизации/сборке/fixtures, не к общей надёжности tool use или качеству длинного контекста. MLX protocol — отдельная будущая сессия.

## Вывод по гипотезе

{conclusion} Для полностью принятых этапов допустим переход к LAB08/provider bridge и LAB34 для той же конфигурации и принятого контекста, с отдельными протоколами и проверками. Проверка loopback HTTP не реализует bridge и не является агентным эпизодом. Агентные попытки потребуют run.json. Не переносить GGUF память на MLX.

## Ответы на контрольные вопросы

1. JSON wall включает prefill и весь output, момент первого content неизвестен; TTFT=null.
2. Hard cap задаёт native server, проверяется props/slots; client CTX сам не выделяет cache. MLX cap требует отдельной проверки.
3. Client timeout закрывает socket; server logs/slot/recovery показывают последующую реакцию. Restart не заменяет recovery.
4. Prefix cache меняет prefill; первый reasoning token может предшествовать final content, поэтому каналы разделены.

## Комплект сдачи

Manifest v2, исходный protocol/hash и полный register, fixtures/probe, model/binary verification, JSON/SSE/token counts, logs/telemetry, offline validation, checkpoint и итоговый exporter. Reviewer decision=null: независимой научной оценки нет. lab:check проверяет комплектность, не истинность гипотезы.
'''
    (root/'report.md').write_text(report,encoding='utf-8')
    manifest.update(status=status,conclusion=conclusion,reviewer_decision=None)
    if completed:
        manifest['unavailable'].pop('completion',None)
    elif failed:
        manifest['unavailable']['completion']='Admission failed: '+', '.join(failed)+'; remaining attempts not-run.'
    manifest['unavailable']['gpu_budget_gib']='Fixed 8K/16K/32K fixtures do not establish maximum safe GPU memory budget.'
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name!='evidence-hashes.json'}
    (raw/'evidence-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    manifest['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    finalize(pathlib.Path(__file__).resolve().parent.parent)
