# -*- coding: utf-8 -*-
"""Checkpoint LAB32 honestly: failed no-thinking condition or admitted first stage."""
import csv,hashlib,json,pathlib,re,statistics,sys
raw=pathlib.Path(__file__).resolve().parent;root=raw.parent
manifest=json.loads((root/'manifest.json').read_text())
initial=sys.argv[1]=='initial'
# This entry point finalizes the first 8K checkpoint, not subsequent stages.
for path in list(raw.glob('ctx*.metrics.json'))+list(raw.glob('ctx*-execution.json')):
    match=re.match(r'ctx([0-9]+)-',path.name)
    if match and int(match.group(1))!=8192:
        raise ValueError('8K checkpoint cannot finalize higher-context evidence; extend the phase report before using this entry point')

if initial:
    for attempt in manifest['planned_attempts']:
        if attempt['status']=='planned':attempt.update(status='not-run',reason='Initial 8K tool contract failed; protocol stops the original condition and context growth. Diagnostic controls are separately registered.')
    manifest['status']='blocked'
    manifest['unavailable']['completion']='thinking=false condition failed tool warmup; long/cancel/overflow and16K/32K were not executed. Independent auto series does not repair this result.'
    conclusion='На 8K chat JSON/SSE прошли прогрев и три повтора; tool warmup вернул 10 без tool_calls и отклонён. Свежий no-thinking контроль повторил отказ, один auto-контроль прошёл. Двойной SIGINT вызвал abort при cleanup; один сигнал native child завершает сервер с exit0. Исходное условие не получило допуска к LAB08/нагрузке.'
else:
    failed=[a for a in manifest['planned_attempts'] if a['id'].startswith('ctx8192-') and a['status']=='failed']
    if failed:
        manifest['status']='blocked';manifest['unavailable']['completion']='8K phase has failures; no context growth admission.'
        for attempt in manifest['planned_attempts']:
            if attempt['status']=='planned':attempt.update(status='not-run',reason='8K phase failed; context growth stopped by protocol.')
        conclusion='reasoning-auto series started; 8K failures are retained, no16K/32K admission.'
    else:
        assert all(a['status']=='completed' for a in manifest['planned_attempts'] if a['id'].startswith('ctx8192-'))
        manifest['status']='in-progress'
        conclusion='Этап 8K с reasoning=auto прошёл: четыре protocol fixtures и длинный вход 4083 tokens имеют прогрев и три повтора; проверены отмена/освобождение слота/recovery и overflow/recovery. 16K/32K остаются планом, LAB32 целиком не завершена.'
manifest['conclusion']=conclusion;manifest['reviewer_decision']=None
manifest['unavailable'].update(temperature='Not measured.',energy='Not measured.',gpu_budget_gib='A fixed8K fixture does not establish maximum safe GPU memory budget.',
    agent_run='Native loopback protocol only; no agent harness/run.json.',mlx='Separate MLX session not started here.')
attempts={a['id']:a for a in manifest['planned_attempts']}
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
        for kind in ['chat','chat-stream','tool','tool-stream','long']:
            durations=[]
            for n in [1,2,3]:
                case=f'ctx8192-{kind}-r{n}';primary=records.get(case);follow=records.get(case+'.followup')
                if primary and attempts[case]['status']=='completed':durations.append(primary['duration_s']+(follow['duration_s'] if follow else 0))
            if durations:groups[kind]={'values':durations,'median_seconds':statistics.median(durations),'min_seconds':min(durations),'max_seconds':max(durations)}
        for case in attempts:
            if not re.fullmatch(r'ctx[0-9]+-(cancel|overflow)',case):continue
            path=raw/(case+'-execution.json')
            if not path.exists():continue
            data=json.loads(path.read_text())
            for metric,key,unit in [('slot_release_after_disconnect','release_after_client_s','seconds'),('http_status','status','http-status'),('error_wall','wall_seconds','seconds'),('curl_exit','exit_code','exit-code')]:
                if key in data:writer.writerow([case+'-'+metric,attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tensor','metal',context_for_case(case,attempts),'',metric,data[key],unit,'measured','raw/'+path.name,''])
    return records,groups

records,groups=export_measurements(raw,root,attempts)
summary={'conclusion':conclusion,'case_statistics':groups,'attempts':{status:sum(a['status']==status for a in attempts.values()) for status in ['completed','failed','not-run','planned']},
    'condition':'thinking=false' if initial else 'reasoning=auto / enable_thinking=true','context':8192,'higher_contexts_measured':False}
(raw/'phase-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
table='\n'.join(f"| {kind} | {len(values['values'])} | {values['median_seconds']:.3f} | {values['min_seconds']:.3f}–{values['max_seconds']:.3f} |" for kind,values in groups.items())
context_count=json.loads((raw/'ctx8192-long-count.json').read_text())['input_tokens'] if (raw/'ctx8192-long-count.json').exists() else None
details='''Tool warmup JSON: HTTP200, prompt315/completion3, stop/content10 без tool_calls; lookup не исполнялся. Свежий no-thinking control снова вернул10/stop. Один fresh-auto JSON control выполнил lookup_lab_value с key alpha, непустым ID, связанным tool-result и final LAB_VALUE_42. Это одиночные диагностические случаи, не полный допуск auto.

Первоначальный SIGINT process group послал сигнал и time, и серверу; log показывает second interrupt/forced exit/GGML_ASSERT residency cleanup, nativeexit−6. Derived shutdown status ошибочно был completed только по guard_reason; исправлен наfailed и документирован. При сигнале только верифицированному native child cleanup завершилсяexit0 безassert. Fresh auto control сначала не запускался из-за TIME_WAIT ложного port guard; ошибка сохранена, SO_REUSEADDR correction и отдельный retry зарегистрированы до запуска.'''
if not initial:
    cancel=json.loads((raw/'ctx8192-cancel-execution.json').read_text()) if (raw/'ctx8192-cancel-execution.json').exists() else {}
    over=json.loads((raw/'ctx8192-overflow-execution.json').read_text()) if (raw/'ctx8192-overflow-execution.json').exists() else {}
    details=f'''На 8K все четыре protocol fixtures имеют отдельный прогрев и три измеряемых повтора. Проверены reasoning/final, call IDs, arguments, связанный tool result и SSE DONE. Длинный вход: {context_count} токена при input budget4096; actual usage совпал с серверным tokenizer, final — LAB_SENTINEL_42.

Отмена: curl exit{cancel.get('exit_code')}, active slot observed={cancel.get('active_slot_observed')}, idle after={cancel.get('idle_after')}, освобождение слота после disconnect — {cancel.get('release_after_client_s'):.3f}s, DONE={cancel.get('done_received')}. Сопоставлены slot observations, server log и recovery без restart. Overflow: HTTP{over.get('status')} с context-specific error; точный input count — в raw/ctx8192-overflow-count.json, recovery — LAB_READY. Остановка одним SIGINT native child завершилась exit0. 16K/32K ещё не запускались.'''
report=f'''# LAB32 — {'исходная no-thinking серия' if initial else 'первый этап reasoning-auto'} на M5 Max

Сессия: `{manifest['session_id']}`. Статус: **{'blocked для исходного условия' if manifest['status']=='blocked' else 'in-progress: выполнен только этап 8K'}**. {conclusion}

## Паспорт выполнения

Codex по запросу владельца, 07.10.2026. Apple M5 Max / 128 GiB / macOS 26.5 / arm64. llama.cpp b8407, commit `312cf03328496df9c56fe843952cf02a8964c59a` с сохранённым tensor tile16 patch. Local Qwen3.5-9B Q6_K @3885219… с SHA91898433… из LAB29; source/binary/weight hashes — в [runtime manifest](raw/runtime-manifest.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, {'reasoning=off / enable_thinking=false' if initial else 'reasoning=auto / enable_thinking=true'}, temperature0/seed1. Prefix cache отключён и сервером, и request.cache_prompt=false. Один сервер на loopback8080; actual n_ctx8192, offload33/33 и tensor=true проверены по props/slots/log. CPU/OS snapshot взят из предыдущей работы; актуальный GPU, memory/power наблюдаются в preflight и server logs. Harness не применяется, run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), [SHA](raw/protocol.sha256), protocol_recorded_at в manifest сохранены до исполнения. Это авторская регистрация, без внешнего удостоверения времени. Все 8K/16K/32K попытки зарегистрированы; failures и пропуски сохранены. Portable probe извлечён из LAB05 без изменения parsing. Offline allowlist — отдельное упражнение с evidence_class=synthetic, не успешные вызовы модели. Основная серия требует прогрев и три повтора каждого случая; рост контекста допускается после успеха предыдущего этапа.

## Ход выполнения

{details}

Сохранены исходные request/response JSON/SSE, assembled messages, timing/usage/followup, полный long prompt/count, ресурсная телеметрия и native logs. Клиент не исполняет код модели: единственной разрешённой функции возвращает фиксированный LAB_VALUE_42. Диагностические controls учитываются отдельно от повторов основной серии. Серверы остановлены; агентские эпизоды не выполнялись.

## Результаты

Измеряемые r1–r3, без прогрева. Tool latency — сумма двух HTTP-вызовов; TTFT доступен только SSE и разделён на content/reasoning. Неизвестные значения остаются null.

| Case | Принятых повторов | Median total s | Min–max s |
| --- | ---: | ---: | --- |
{table}

[TSV](measurements.tsv), [сводка](raw/phase-summary.json), manifest и raw содержат отдельные наблюдения и причины. Подготовлен long input на {context_count} tokens; {'он не выполнялся и не засчитан' if initial else 'actual usage совпал с серверным tokenizer, sentinel проверен в каждом принятом повторе'}. Короткий chat в пустом n_ctx8192 сам по себе не проверяет длинный контекст. **16K/32K не измерены.**

В основной серии действует отдельный sampler memory/power каждые 2s, free-page floor16GiB, swap0 и RSS ceiling24GiB. Process RSS/time сохранены в native server log; RSS и пересекающиеся Metal buffers не складываются. Короткие диагностические controls наблюдались до/после без отдельного sampler; это ограничение заранее записано.

## Ошибки и ограничения

{'Исходная серия не получила допуска к LAB08 или LAB34: tool contract failed. Одиночный auto-control не исправляет исходный результат. Другая thinking-конфигурация оформлена отдельной сессией.' if initial else 'Это checkpoint, а не завершённая LAB32. Нужны последовательные этапы 16K/32K; MLX требует отдельной сессии. Проверка HTTP fixtures не реализует provider bridge и не является агентным прогоном.'}

Cancel сопоставляется по curl, активному слоту, server log и recovery без restart. Освобождение слота не является instruction-level GPU trace. В auto-серии сервер явно пишет cancel task; prefill продолжался некоторое время после отключения клиента, что видно в timeline. Отмена не объявляется мгновенной. Prefix cache выключен, reasoning меняет output count и время до final content; разные режимы не смешиваются.

В исходной серии SIGINT группе под macOS time доставил двойной сигнал, а checker ошибочно счёл shutdown успешным по отсутствию memory guard error. Ошибка derived status исправлена на failed с документированной причиной. Диагностика одним сигналом verified native child дала exit0. TIME_WAIT ложного port guard и отдельно зарегистрированный retry также сохранены. Для auto-серии исправления контроллера выполнены до запуска; model/shader bytes не менялись.

Energy/temperature, максимальный безопасный GPU budget и качество модели не измерены. Номинальная RAM128GiB и recommended working set не означают свободную GPU память. Отдельный эффект tensor API этой серией не исследуется.

## Вывод по гипотезе

{'Не поддержана для исходного no-thinking условия: short chat/SSE прошли, tool failed; long/воздействия и higher contexts не выполнялись по протоколу остановки.' if initial else 'Поддержана для выполненного этапа 8K; гипотеза всего маршрута8K/16K/32K ещё не проверена. Следующий этап — 16K в этой же auto-конфигурации после проверки checkpoint.'}

Ready-for-review у blocked отчёта означает комплектность объяснения, не успешный эксперимент. In-progress отчёт проверяется в draft; сдача всей LAB32 пока невозможна. Ошибки исходного режима сохранены отдельно от новой серии.

## Ответы на контрольные вопросы

1. Non-streaming wall включает обработку входа и весь output; момент первого content неизвестен, поэтому TTFT=null.
2. Client CTX не выделяет cache. Здесь hard n_ctx установлен native server и подтверждён props/slots. MLX cap необходимо исследовать отдельно.
3. Client timeout закрывает соединение. Slot/log/recovery показывают реакцию сервера; перезапуск сервера не заменяет проверку отмены generation.
4. Prefix cache меняет prefill. Первый reasoning-токен может появиться значительно раньше final content; эти каналы измеряются отдельно.

## Комплект сдачи

Manifest v2, предварительные protocol/hash и полный register; fixtures/probe; binary/weight verification; JSON/SSE/token counts, logs/telemetry и failure/control evidence. Reviewer decision=null: независимой оценки нет. {'Оставшиеся попытки отмечены not-run с причиной остановки исходного условия.' if initial else '16K/32K остались planned: работа начата, но не готова к submission.'}
'''
(root/'report.md').write_text(report,encoding='utf-8')
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name!='evidence-hashes.json'}
(raw/'evidence-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
manifest['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
(root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
