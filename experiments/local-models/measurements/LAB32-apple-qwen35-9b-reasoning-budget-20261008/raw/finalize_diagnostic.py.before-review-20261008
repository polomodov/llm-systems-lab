# -*- coding: utf-8 -*-
"""Export measured outcomes without turning diagnostic completion into admission."""
import csv
import hashlib
import json
import pathlib
import re
import statistics

LABELS=['control','budget128','budget512']
KINDS=['chat','chat-stream','tool','tool-stream','long']
REPEATS=['warmup','r1','r2','r3']


def classify_final(final,metrics,expected):
    return (metrics['http_status']==200 and metrics['finish_reason']=='stop'
            and final.get('content','').strip()==expected and not final.get('tool_calls'))


def summarize_group(records):
    measured=[record for record in records if record['repeat']!='warmup']
    values=[record['duration_seconds'] for record in measured]
    return dict(attempted=len(records),successful=sum(r['accepted'] for r in records),
        measured_repeats=len(measured),successful_measured_repeats=sum(r['accepted'] for r in measured),
        median_seconds=statistics.median(values) if values else None,
        min_seconds=min(values) if values else None,max_seconds=max(values) if values else None,
        measured_output_tokens=[r['completion_tokens'] for r in measured],
        finish_reasons=[r['finish_reason'] for r in measured],
        condition_pass=len(records)==4 and all(r['accepted'] for r in records))


def finalize(root):
    raw=root/'raw';manifest=json.loads((root/'manifest.json').read_text())
    attempts={a['id']:a for a in manifest['planned_attempts']}
    # A controller/transport/resource stop remains blocked, even with a passing output.
    unfinished=any(a['status']=='planned' for a in attempts.values())
    for a in attempts.values():
        if a['status']=='planned':a.update(status='not-run',reason='Diagnostic controller stopped; see driver-error.txt or prior failure.')
    fixtures=json.loads((raw/'fixtures-sha256.json').read_text())
    for name,digest in fixtures.items():assert hashlib.sha256((raw/name).read_bytes()).hexdigest()==digest
    baseline=json.loads((raw/'baseline-ctx32768-long-request.json').read_text())
    for label in LABELS:
        request=json.loads((raw/f'{label}-long-request.json').read_text())
        budget=request.pop('thinking_budget_tokens',None)
        assert request==baseline and budget==({'control':None,'budget128':128,'budget512':512}[label])
    startup=json.loads((raw/'ctx32768-startup-execution.json').read_text())
    assert startup['accepted'] and startup['context']==32768 and startup['tensor_api']
    verification=json.loads((raw/'prompt-verification.json').read_text())
    assert verification['accepted'] and verification['input_tokens']==28670
    groups={};observations=[];outcomes=[]
    for case,attempt in attempts.items():
        match=re.fullmatch(r'ctx32768-(control|budget128|budget512)-(chat|chat-stream|tool|tool-stream|long)-(warmup|r[123])',case)
        if not match or attempt['status']=='not-run':continue
        label,kind,repeat=match.groups();prefix=raw/case
        primary=json.loads(pathlib.Path(str(prefix)+'.metrics.json').read_text())
        final=json.loads(pathlib.Path(str(prefix)+'.final.json').read_text())
        execution=json.loads(pathlib.Path(str(prefix)+'-execution.json').read_text())
        expected='LAB_SENTINEL_42' if kind=='long' else 'LAB_VALUE_42' if kind.startswith('tool') else 'LAB_READY'
        follow_path=pathlib.Path(str(prefix)+'.followup.metrics.json')
        follow=json.loads(follow_path.read_text()) if follow_path.exists() else None
        accepted=classify_final(final,follow or primary,expected)
        assert execution['accepted']==accepted and (attempt['status']=='completed')==accepted
        if kind=='long':assert primary['usage']['prompt_tokens']==28670
        if '-stream' in kind or kind=='long':assert primary['stream_done'] and (follow is None or follow['stream_done'])
        if kind.startswith('tool'):
            assert primary['finish_reason']=='tool_calls' and follow
            follow_request=json.loads(pathlib.Path(str(prefix)+'.followup.request.json').read_text())
            assert follow_request['thinking_budget_tokens']==int(label.removeprefix('budget'))
        log=(raw/(case+'-server-fragment.txt')).read_text()
        forced='reasoning-budget: forced sequence complete, done' in log
        if kind=='long' and label!='control':
            budget=int(label.removeprefix('budget'))
            assert f'reasoning-budget: activated, budget={budget} tokens' in log and forced
        if label=='control':assert not forced
        duration=primary['duration_s']+(follow['duration_s'] if follow else 0)
        outcome=dict(case=case,condition=label,kind=kind,repeat=repeat,accepted=accepted,
            duration_seconds=duration,completion_tokens=primary['usage']['completion_tokens'],
            finish_reason=(follow or primary)['finish_reason'],final_content=final['content'],
            reasoning_characters=len(final.get('reasoning_content','')),forced_end_sequence_complete=forced)
        outcomes.append(outcome);groups.setdefault(f'{label}-{kind}',[]).append(outcome)
        for suffix,metrics in [('',primary),('.followup',follow)]:
            if metrics is None:continue
            metrics_path=f'raw/{case}{suffix}.metrics.json'
            values=[('duration',metrics['duration_s'],'seconds'),('http_status',metrics['http_status'],'http-status'),
                ('ttft_content',metrics.get('ttft_content_s'),'seconds'),('ttft_reasoning',metrics.get('ttft_reasoning_s'),'seconds'),
                ('prompt_tokens',metrics['usage']['prompt_tokens'],'tokens'),('completion_tokens',metrics['usage']['completion_tokens'],'tokens')]
            for metric,value,unit in values:
                observations.append([case+suffix+'-'+metric,attempt['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tensor','metal',32768,
                    repeat[1:] if repeat.startswith('r') else '',metric,value if value is not None else '',unit,
                    'measured' if value is not None else 'unavailable',metrics_path,'' if value is not None else 'Channel timing not reported for this response.'])
    statistics_by_case={key:summarize_group(values) for key,values in groups.items()}
    condition_admission={label:all(statistics_by_case.get(f'{label}-{kind}',{}).get('condition_pass',False) for kind in KINDS) for label in ['budget128','budget512']}
    execution=json.loads((raw/'ctx32768-server-execution.json').read_text())
    resources=[json.loads(line) for line in (raw/'ctx32768-memory.jsonl').read_text().splitlines()]
    resources_ok=execution['returncode']==0 and execution['guard_reason'] is None and all(
        row['swap_used_bytes']==0 and row['free_pages_bytes']>=16*2**30 and row['on_ac_power'] and row['ac_power_mode']==0
        and (row['observed_rss_bytes'] is None or row['observed_rss_bytes']<=24*2**30) for row in resources)
    status='completed' if not unfinished and resources_ok else 'blocked'
    condition_admission={key:value and resources_ok for key,value in condition_admission.items()}
    conclusion=('Диагностический план завершён: '+', '.join(f'{label} '+('прошёл long+short fixtures' if passed else 'не получил диагностического допуска') for label,passed in condition_admission.items())+'. Исходная LAB32 остаётся blocked; полного32K protocol admission нет.')
    summary=dict(status=status,conclusion=conclusion,context_tokens=32768,input_tokens=28670,output_cap=2048,server_reasoning_budget=-1,
        request_reasoning_budgets=[None,128,512],case_statistics=statistics_by_case,diagnostic_condition_admission=condition_admission,
        full_lab32_admission=False,outcomes=outcomes,attempts={s:sum(a['status']==s for a in attempts.values()) for s in ['completed','failed','not-run','planned']},
        resources=dict(accepted=resources_ok,max_rss_bytes=execution['max_rss_bytes'],min_free_pages_bytes=min(row['free_pages_bytes'] for row in resources),
            max_swap_used_bytes=max(row['swap_used_bytes'] for row in resources),started_at=execution['started_at'],ended_at=execution['ended_at'],native_exit_code=execution['returncode']))
    with (root/'measurements.tsv').open('w',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t',lineterminator='\n')
        writer.writerow('observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split())
        writer.writerows(observations)
    (raw/'diagnostic-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    table='\n'.join(f"| {key} | {v['successful']}/{v['attempted']} | {v['successful_measured_repeats']}/{v['measured_repeats']} | {v['median_seconds']:.3f} | {v['min_seconds']:.3f}–{v['max_seconds']:.3f} | {','.join(map(str,v['measured_output_tokens']))} |" for key,v in statistics_by_case.items())
    report=f'''# LAB32 — диагностика reasoning budget на 32K

Сессия `{manifest['session_id']}`, статус **{status}**. {conclusion}

## Паспорт выполнения

Codex по запросу владельца, 08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5/25F71, arm64. Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5 SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Все закреплённые binaries/libs и GGUF повторно проверены, [preflight](raw/preflight-execution.json), [runtime](raw/runtime-manifest.json), [hardware](raw/fresh-hardware.json). Native Metal/tensor=true/offload33/33 подтверждены log.

Hard context32768 (props/slots), threads8, batch512/ubatch256, FAon, KVf16/f16, slots1, jinja/no-context-shift, reasoningauto/enable_thinking=true, temperature0/seed1/top_p1. Prefix cache отключён. Один resident server loopback8080 на всю диагностику, AC/powermode0. Server --reasoning-budget -1; request budgets отсутствует/128/512. Output cap2048, input28670 и prompt hash сохранены. Без agent harness, run_ids[].

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md)/[SHA](raw/protocol.sha256) и49attempts зарегистрированы до model start. Исходный [blocked отчёт](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md) не меняется. В каждом condition — warmup+3long, заранее заданный чередующийся порядокcontrol→128→512. Затем для128 и512 четыре shortcases×warmup+3. Semantic final failures допускаются в сравнительной диагностике, сохраняются failed; resource/transport failure прекращает опыт. Нет дополнительных seeds/retries/budgets по результату. Это авторская регистрация, не независимое удостоверение времени.

## Ход выполнения

Fresh preflight, offline synthetic allowlist, native server identity, apply-template/tokenize подтвердили тот же prompt SHA и28670tokens. Requests отличаются только thinking_budget_tokens, tokenizer/template/content/max_tokens2048 неизменны. Budget передаётся и в tool followup. Chat=LAB_READY, tool exactly1 lookup_lab_value(key=alpha)/nonemptyid/resultLAB_VALUE_42/finalLAB_VALUE_42; код модели не исполняется. Long final строгоLAB_SENTINEL_42. Saved JSON/SSE DONE/usage, assembled final/reasoning, log fragments и memory timeline. Сервер остановлен одним SIGINT verified child, nativeexit{execution['returncode']}.

## Результаты

Успешность включает warmup; median/min–max — r1–r3. Tool duration включает оба HTTP-вызова, outputtokens в таблице — первый вызов. Измеренные latency отказавшего control не подменены отсутствием данных; failed содержится в register и outcomes. TTFT content/reasoning — [TSV](measurements.tsv), JSON TTFT=null. [Полная сводка](raw/diagnostic-summary.json).

| Condition/case | Pass/all | Pass r1–r3 | Median total s | Min–max s | Output tokens r1–r3 |
| --- | ---: | ---: | ---: | ---: | --- |
{table}

Для control все4long закончились length/output2048 без final. Для128 все4long — stop/output137, точныйLAB_SENTINEL_42. Для512 все4long — stop/output804; в content осталась часть reasoning, дополнительный </think> и sentinel в конце, поэтому exact final contract failed. Клиент не вырезает «последний правильный ответ». Все short chat/tool JSON/SSE случаи128/512 прошли. На long128/512 каждый log подтверждает activated с соответствующим budget, exhausted и forced sequence complete.

Native maxRSS **{execution['max_rss_bytes']/2**30:.3f}GiB**, минимум vm_stat free pages **{summary['resources']['min_free_pages_bytes']/2**30:.2f}GiB**, maxswap **{summary['resources']['max_swap_used_bytes']/2**30:.3f}GiB**. Free pages не равны всей доступной памяти; RSS не складывается с пересекающимися Metal allocations. Cold startup отдельно в server-execution, не входит в request medians.

## Ошибки и ограничения

8semantic failures (4control/4budget512) остаются failed; completed — завершение диагностического плана, не успешность всех условий. При512 ограничитель сработал, однако модель продолжила рассуждение после принудительного end tag: это вывод по final/rawSSE и sampler logs, не доказательство ошибки parser. Результат128 относится к одному prompt/model/deployment и детерминированной series, не гарантии качества модели или tool reliability на других inputs. Изменение budget меняет sampler/output trajectory. Порядок условии/один resident server/day не устраняют все временные факторы.

Cancel/overflow32K здесь не выполнялись; полная LAB32 и прежний auto-condition остаются blocked. Этот диагноз не является агентным run или полным допуском LAB34/bridge32K. Energy/temperature, maximalGPUbudget и MLX protocol неизвестны. No weights/shader/systemlimits/power changes, original evidence неизменна.

## Вывод по гипотезе

Поддержана для128 на зарегистрированных long+short fixtures, не поддержана для512 по exact final contract. Отсутствие final в control воспроизведено в четырёх запросах. Следующий полный8K→16K→32K протокол регистрируется отдельно с budget128 и проверками cancel/overflow/recovery; исходный отказ не заменяется.

Активация в **проверенном** HTTP deployment: server --reasoning-budget -1 (default), --reasoning auto, chat_template_kwargs.enable_thinking=true; в каждом /v1/chat/completions request и tool followup добавить `"thinking_budget_tokens":128`, max_tokens2048. Это расширение llama.cpp, не стандартное поле OpenAI. Server-level `--reasoning-budget 128` поддержан help/source, но отдельный процесс с ним здесь не измерялся. При server budget>=0 request override не применяется, как видно в source. README этого commit устарел (перечисляет−1/0), исполняемый help и source подтверждаютN>0. [Сохранённые excerpts/hashes](raw/reasoning-api-source.json), [help](raw/server-help.txt). Finite sampler принудительно вставляет end sequence и может дождаться завершения UTF-8; поэтому cap — ограничение reasoning, не всего output и не общий context cap.

## Ответы на контрольные вопросы

1. JSON wall не даёт TTFT; SSE фиксирует content/reasoning отдельно. В control content так и не появился.
2. Hard32768 задаётся server и проверен props/slots, client field не резервирует KV. Budget128 ограничивает reasoning sampler, а max_tokens2048 — весь output.
3. Client timeout и server cancellation различаются; cancel/overflow здесь не повторялись и не засчитаны.
4. Prefix cache выключен; forced end меняет output trajectory. Reasoning-only response200/DONE не удовлетворяет final contract, а marker в конце загрязнённогоcontent не делает его pass.

## Комплект сдачи

Manifestv2/register/protocol/hash, pinned source excerpts/API/help, requests+hashes, driver/probe/change patch, preflight/device/props/tokenization, JSON/SSE/followups/log fragments, resource timeline, TSV и diagnostic-summary. Все failures/unknowns сохранены с причинами, reviewer decision=null. lab:check оценивает комплектность, не научную истинность или полный LAB32 admission.
'''
    (root/'report.md').write_text(report,encoding='utf-8')
    manifest.update(status=status,conclusion=conclusion,reviewer_decision=None)
    if status=='blocked':manifest['unavailable']['completion']='Diagnostic controller/resource admission failed; remaining work not-run.'
    manifest['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
    (raw/'evidence-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name!='evidence-hashes.json'},indent=2)+'\n')
    manifest['evidence_files']=sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['status','attempts','diagnostic_condition_admission','resources']},ensure_ascii=False,indent=2))


if __name__=='__main__':finalize(pathlib.Path(__file__).resolve().parent.parent)
