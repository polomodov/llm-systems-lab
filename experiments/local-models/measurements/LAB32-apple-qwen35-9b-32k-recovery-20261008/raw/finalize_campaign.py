# -*- coding: utf-8 -*-
"""Finalize the scoped32K qualification; validate its fixed request budget128."""
import csv, hashlib, json, pathlib, re, statistics
CONTEXTS = [32768]
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
                if key in data:writer.writerow([case+'-'+metric,attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tensor','metal',context_for_case(case,attempts),'',metric,data[key] if data[key] is not None else '',unit,'measured' if data[key] is not None else 'unavailable','raw/'+path.name,'' if data[key] is not None else 'Slot release was not observed within the registered window.'])
    return records,groups


def verify_tool_round_trip(raw,case,request,primary):
    # Revalidate the saved call/result, not the controller's accepted flag.
    if request['stream']:
        message=json.loads((raw/(case+'.assembled.json')).read_text())
    else:
        response=json.loads((raw/(case+'.response.json')).read_text())
        assert len(response['choices'])==1
        choice=response['choices'][0]
        assert choice['finish_reason']==primary['finish_reason']=='tool_calls'
        message=choice['message']
    assert message['role']=='assistant'
    calls=message.get('tool_calls',[])
    assert len(calls)==1
    call=calls[0]
    assert call['type']=='function'
    assert call['function']['name']=='lookup_lab_value'
    assert json.loads(call['function']['arguments'])=={'key':'alpha'}
    assert isinstance(call.get('id'),str) and call['id'].strip()
    follow=json.loads((raw/(case+'.followup.request.json')).read_text())
    assert follow['messages']==request['messages']+[message,{
        'role':'tool','tool_call_id':call['id'],'content':'LAB_VALUE_42'}]


def verify_protocol(raw,case):
    request=json.loads((raw/(case+'.request.json')).read_text())
    final=json.loads((raw/(case+'.final.json')).read_text())
    primary=json.loads((raw/(case+'.metrics.json')).read_text())
    execution=json.loads((raw/(case+'-execution.json')).read_text())
    assert execution['metrics']==primary and primary['http_status']==200 and primary['usage']['prompt_tokens']>0
    follow=raw/(case+'.followup.metrics.json')
    metrics=json.loads(follow.read_text()) if follow.exists() else primary
    if '-tool-' in case or '-tool-stream-' in case:
        assert follow.exists() and primary['finish_reason']=='tool_calls'
        assert execution['followup_metrics']==metrics
        verify_tool_round_trip(raw,case,request,primary)
    else:
        assert not follow.exists()
    expected='LAB_SENTINEL_42' if '-long-' in case else 'LAB_VALUE_42' if '-tool' in case else 'LAB_READY'
    assert metrics['finish_reason']=='stop' and metrics['http_status']==200
    assert final.get('content','').strip()==expected and not final.get('tool_calls')
    if request['stream']:assert primary['stream_done'] and metrics['stream_done']


def verify_budget(raw,case):
    verify_protocol(raw,case)
    request=json.loads((raw/(case+'.request.json')).read_text())
    assert request['thinking_budget_tokens']==128
    assert request['chat_template_kwargs']['enable_thinking'] is True
    assert request['cache_prompt'] is False
    follow=raw/(case+'.followup.request.json')
    if follow.exists():assert json.loads(follow.read_text())['thinking_budget_tokens']==128
    log=(raw/(case+'-server-fragment.txt')).read_text()
    assert 'reasoning-budget: activated, budget=128 tokens' in log
    assert 'reasoning-budget: deactivated (natural end)' in log or 'reasoning-budget: forced sequence complete, done' in log


def verify_effects(raw,ctx,cancel,overflow,timeline):
    assert cancel['release_timeout_seconds']==60
    assert cancel['exit_code']==28 and not cancel['done_received']
    assert cancel['active_slot_observed'] and cancel['idle_after'] and cancel['server_cancellation_log']
    assert 0 <= cancel['release_after_client_s'] <= 60
    observed_release=cancel['observations'][-1]['elapsed_s']-cancel['client_exit_elapsed_s']
    assert abs(observed_release-cancel['release_after_client_s'])<1e-6
    # The cancellation is for the same task observed while the client was alive.
    active_ids={str(s['id_task']) for o in cancel['observations'] if o.get('client_alive')
                for s in o.get('slots',[]) if s.get('is_processing')}
    assert active_ids.intersection(cancel['canceled_task_ids'])
    assert any(not o.get('client_alive',True) and o.get('slots') and all(not s['is_processing'] for s in o['slots']) for o in cancel['observations'])
    for kind in ['cancel','overflow']:
        request=json.loads((raw/f'ctx{ctx}-{kind}-request.json').read_text())
        assert request['thinking_budget_tokens']==128 and request['chat_template_kwargs']['enable_thinking'] is True
        verify_budget(raw,f'ctx{ctx}-{kind}-recovery')
    assert overflow['status']==400 and re.search(r'context|exceed|too (?:large|long)',str(overflow['response']),re.I)
    assert json.loads((raw/f'ctx{ctx}-overflow-count.json').read_text())['input_tokens']>ctx
    assert all(r['swap_used_bytes']==0 and r['free_pages_bytes']>=16*2**30 and r['on_ac_power'] and r['ac_power_mode']==0
        and (r['observed_rss_bytes'] is None or r['observed_rss_bytes']<=24*2**30) for r in timeline)

def finalize(root):
    raw = root / 'raw'
    manifest = json.loads((root/'manifest.json').read_text())
    attempts = {a['id']:a for a in manifest['planned_attempts']}
    runtime=json.loads((raw/'runtime-manifest.json').read_text())
    assert runtime['thinking_budget_tokens']==128 and runtime['server_reasoning_budget']==-1 and runtime['cancel_release_timeout_seconds']==60
    fixture_hashes=json.loads((raw/'fixtures-sha256.json').read_text())
    assert all(hashlib.sha256((raw/name).read_bytes()).hexdigest()==digest for name,digest in fixture_hashes.items())
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
                verify_budget(raw,f'ctx{ctx}-{kind}-{repeat}')
                if kind=='long':
                    assert record['metrics']['usage']['prompt_tokens']==count['input_tokens']
        cancel = json.loads((raw/f'ctx{ctx}-cancel-execution.json').read_text())
        overflow = json.loads((raw/f'ctx{ctx}-overflow-execution.json').read_text())
        assert cancel['accepted'] and cancel['exit_code']==28 and cancel['idle_after'] and cancel['server_cancellation_log']
        assert overflow['accepted'] and overflow['status']==400
        for effect in ['cancel','overflow']:
            assert json.loads((raw/f'ctx{ctx}-{effect}-recovery-execution.json').read_text())['accepted']
        timeline = [json.loads(line) for line in (raw/f'ctx{ctx}-memory.jsonl').read_text().splitlines()]
        verify_effects(raw,ctx,cancel,overflow,timeline)
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
    conclusion = ('Самостоятельный контекст32K прошёл protocol и resource admission; допуск ограничен проверенными fixtures и условиями.'
        if completed else 'Кампания не завершена; допуск только для полностью проверенных этапов: '+', '.join(details)+'. Отказы: '+', '.join(failed)+'.')
    summary=dict(conclusion=conclusion,condition='reasoning=auto / enable_thinking=true / thinking_budget_tokens=128',thinking_budget_tokens=128,server_reasoning_budget=-1,cancel_release_timeout_seconds=60,
        contexts=CONTEXTS,full_lab32_admission=False,admission_scope="standalone32k",admitted_contexts=list(map(int,details)),higher_contexts_measured=any(int(c)>8192 for c in details),
        case_statistics=groups,context_details=details,
        attempts={s:sum(a['status']==s for a in attempts.values()) for s in ['completed','failed','not-run','planned']})
    summary['failure_analysis'] = json.loads((raw/'ctx32768-failure-analysis.json').read_text()) if (raw/'ctx32768-failure-analysis.json').exists() else None
    (raw/'campaign-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    table='\n'.join(f"| {v['context_tokens']} | {v['case']} | {len(v['values'])} | {v['median_seconds']:.3f} | {v['min_seconds']:.3f}–{v['max_seconds']:.3f} |" for v in groups.values())
    resources='\n'.join(f"| {ctx} | {v['input_tokens']} / {v['input_budget']} | {v['max_rss_bytes']/2**30:.3f} | {v['min_free_pages_bytes']/2**30:.2f} | {v['max_swap_used_bytes']/2**30:.3f} | {v['slot_release_after_disconnect_s']:.3f} | {v['overflow_input_tokens']} / {v['overflow_http_status']} |" for ctx,v in details.items())
    failure_note = ('Отказы сохранены: '+', '.join(failed)+'. Неисполненные попытки отмечены not-run; повторов для замены отказа нет.' if failed else 'Все зарегистрированные попытки прошли; предыдущие отказы сохранены в отдельных сессиях.')
    report=f'''# LAB32 — контекст и инструменты на Apple M5 Max

Сессия: `{manifest['session_id']}`. Статус: **{status}**. {conclusion}

## Паспорт выполнения

Codex по запросу владельца, 08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5 build25F71, arm64. Нативный llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. [Runtime](raw/runtime-manifest.json), свежая [проверка перед запуском](raw/preflight-execution.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto/enable_thinking=true, request thinking_budget_tokens=128 (включая followup, cancel/overflow/recovery), server --reasoning-budget -1, temperature0/seed1/top_p1, prefix cache отключён сервером и request.cache_prompt=false. Один собственный server на loopback8080; hard cap32768 проверяется props/slots и log, offload33/33, tensor=true. Harness отсутствует; run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), его [hash](raw/protocol.sha256) и register сохранены до запуска. Прогрев и три повтора каждого chat/tool × JSON/SSE и long case; cancel/overflow с recovery на каждом контексте. Это отдельная квалификация32K, опирающаяся на [диагностический допуск](raw/prior-diagnostic-reference.json) для тех же32K fixtures/budget128. Все28 попыток зарегистрированы до запуска; независимого удостоверения времени регистрации нет. Это один residentserver; последовательныймаршрут8K→16K→32K здесь не исполняется.

## Ход выполнения

На каждом контексте отдельный native server start/device/hard-cap verification. Final chat=LAB_READY; tool exactly1 lookup_lab_value(key=alpha), непустой call ID, связанный фиксированный resultLAB_VALUE_42, final=LAB_VALUE_42. Код модели не исполнялся. SSE требует DONE; usage и content/reasoning timings сохранены раздельно. Offline name/key/id allowlist — synthetic exercise, отдельно от модели.

Следующие проверки описывают протокол; принятые этапы: {', '.join(details) or 'нет'}. Long prompt построен серверными apply-template/tokenize с теми же thinking options, близок к input budgetCTX−4096, max_tokens2048; actual usage совпадает, final=LAB_SENTINEL_42. Cancel: curl timeout1s, exit28, активный slot наблюдается, DONE отсутствует, server cancel task ID совпадает с observed task, idle в пределах60s после client exit и recovery без restart. Время client exit фиксирует отдельный watcher независимо от /slots polling. Overflow: точный input>hard cap, context-specific HTTP400 и recovery без restart. Успешность каждого воздействия определяется его attempt status и raw execution; при отказе следующие попытки не выполняются. Все первичные request/response, prompts/counts, timestamps, server logs и memory timeline сохранены. Серверы остановлены одним SIGINT верифицированному native child.

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

Предыдущие [thinking=false](../LAB32-apple-qwen35-9b-metal-20261007/report.md) и [unrestricted-auto](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md) серии остаются blocked. [Диагностика128/512](../LAB32-apple-qwen35-9b-reasoning-budget-20261008/report.md) выделила128 как пригодный для exact final на одном длинном запросе; здесь заново проверены32K fixtures и воздействия. [Последовательная budget128 серия](../LAB32-apple-qwen35-9b-metal-budget128-20261008/report.md) остановлена на16K из-за лишнейточки в final; еёотказ не заменяется. full_lab32_admission=false, допуск ограничен отдельным32K deployment. Binary/shader/weights не менялись. Controller patch и sampler API source excerpts сохранены.

Окно ожидания отмены заранее увеличено с15 до60s: на32K prefill в диагностике занимал около26s. Фактическая задержка освобождения измеряется от client exit, не от завершения polling. Этот допуск не означает отмены за15s или мгновенного прекращения GPU работы; требования к чувствительному к задержке harness задаются отдельно. Сопоставление IDs/slot/log/recovery — operational evidence, без instruction-level GPU trace. Прежние измерения latency от наблюдения контроллером могут иметь другой polling lag.

Swap0/free-page floor16GiB/RSS ceiling24GiB/AC powermode0 наблюдались каждые2s. RSS не складывается с пересекающимися Metal buffers. Отмена подтверждена slot/log/recovery, не instruction-level GPU trace; prefill может продолжаться после client disconnect. Energy/temperature и максимальный безопасный GPU budget не измерены. Результат относится к одной модели/квантизации/сборке/fixtures, не к общей надёжности tool use или качеству длинного контекста. MLX protocol — отдельная будущая сессия.

## Вывод по гипотезе

{conclusion} Для этого отдельного32K deployment проверены fixtures/recovery при budget128; реальный harness должен дополнительно принять latency/операционныеусловия. ПолныймаршрутLAB32 не завершён. Для дальнейшейLAB08/provider bridge/LAB34, с отдельными протоколами и проверками. Проверка loopback HTTP не реализует bridge и не является агентным эпизодом. Агентные попытки потребуют run.json. Не переносить GGUF память на MLX.

## Ответы на контрольные вопросы

1. JSON wall включает prefill и весь output, момент первого content неизвестен; TTFT=null.
2. Hard cap задаёт native server, проверяется props/slots; client CTX сам не выделяет cache. MLX cap требует отдельной проверки.
3. Client timeout закрывает socket; server logs/slot/recovery показывают последующую реакцию. Restart не заменяет recovery.
4. Prefix cache меняет prefill; первый reasoning token может предшествовать final content, поэтому каналы разделены.

## Комплект сдачи

Manifest v2, исходный protocol/hash и полный register, fixtures/probe, model/binary verification, JSON/SSE/token counts, logs/telemetry, offline validation, sampler/source/controller patch и итоговый exporter. Reviewer decision=null: независимой научной оценки нет. lab:check проверяет комплектность, не истинность гипотезы.
'''
    (root/'report.md').write_text(report,encoding='utf-8')
    manifest.update(status=status,conclusion=conclusion,reviewer_decision=None)
    if completed:
        manifest['unavailable'].pop('completion',None)
    elif failed:
        manifest['unavailable']['completion']='Admission failed: '+', '.join(failed)+'; remaining attempts not-run.'
    manifest['unavailable']['gpu_budget_gib']='Scoped32K fixtures do not establish maximum safe GPU memory budget.'
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name!='evidence-hashes.json'}
    (raw/'evidence-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    manifest['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    finalize(pathlib.Path(__file__).resolve().parent.parent)
