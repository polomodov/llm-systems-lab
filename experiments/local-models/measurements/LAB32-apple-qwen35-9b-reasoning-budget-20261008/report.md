# LAB32 — диагностика reasoning budget на 32K

Сессия `apple-qwen35-9b-reasoning-budget-20261008`, статус **completed**. Диагностический план завершён: budget128 прошёл long+short fixtures, budget512 не получил диагностического допуска. Исходная LAB32 остаётся blocked; полного32K protocol admission нет.

## Паспорт выполнения

Codex по запросу владельца, 08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5/25F71, arm64. Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5 SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Все закреплённые binaries/libs и GGUF повторно проверены, [preflight](raw/preflight-execution.json), [runtime](raw/runtime-manifest.json), [hardware](raw/fresh-hardware.json). Native Metal/tensor=true/offload33/33 подтверждены log.

Hard context32768 (props/slots), threads8, batch512/ubatch256, FAon, KVf16/f16, slots1, jinja/no-context-shift, reasoningauto/enable_thinking=true, temperature0/seed1/top_p1. Prefix cache отключён. Один resident server loopback8080 на всю диагностику, AC/powermode0. Server --reasoning-budget -1; request budgets отсутствует/128/512. Output cap2048, input28670 и prompt hash сохранены. Без agent harness, run_ids[].

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md)/[SHA](raw/protocol.sha256) и49attempts зарегистрированы до model start. Исходный [blocked отчёт](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md) не меняется. В каждом condition — warmup+3long, заранее заданный чередующийся порядокcontrol→128→512. Затем для128 и512 четыре shortcases×warmup+3. Semantic final failures допускаются в сравнительной диагностике, сохраняются failed; resource/transport failure прекращает опыт. Нет дополнительных seeds/retries/budgets по результату. Это авторская регистрация, не независимое удостоверение времени.

## Ход выполнения

Fresh preflight, offline synthetic allowlist, native server identity, apply-template/tokenize подтвердили тот же prompt SHA и28670tokens. Requests отличаются только thinking_budget_tokens, tokenizer/template/content/max_tokens2048 неизменны. Budget передаётся и в tool followup. Chat=LAB_READY, tool exactly1 lookup_lab_value(key=alpha)/nonemptyid/resultLAB_VALUE_42/finalLAB_VALUE_42; код модели не исполняется. Long final строгоLAB_SENTINEL_42. Saved JSON/SSE DONE/usage, assembled final/reasoning, log fragments и memory timeline. Сервер остановлен одним SIGINT verified child, nativeexit0.

## Результаты

Успешность включает warmup; median/min–max — r1–r3. Tool duration включает оба HTTP-вызова, outputtokens в таблице — первый вызов. Измеренные latency отказавшего control не подменены отсутствием данных; failed содержится в register и outcomes. TTFT content/reasoning — [TSV](measurements.tsv), JSON TTFT=null. [Полная сводка](raw/diagnostic-summary.json).

| Condition/case | Pass/all | Pass r1–r3 | Median total s | Min–max s | Output tokens r1–r3 |
| --- | ---: | ---: | ---: | ---: | --- |
| control-long | 0/4 | 0/3 | 71.173 | 70.709–76.818 | 2048,2048,2048 |
| budget128-long | 4/4 | 3/3 | 31.648 | 31.549–35.249 | 137,137,137 |
| budget512-long | 0/4 | 0/3 | 45.766 | 45.699–50.205 | 804,804,804 |
| budget128-chat | 4/4 | 3/3 | 2.431 | 2.429–2.438 | 132,132,132 |
| budget128-chat-stream | 4/4 | 3/3 | 2.394 | 2.345–2.413 | 132,132,132 |
| budget128-tool | 4/4 | 3/3 | 2.685 | 2.643–2.735 | 73,73,73 |
| budget128-tool-stream | 4/4 | 3/3 | 2.593 | 2.537–2.603 | 73,73,73 |
| budget512-chat | 4/4 | 3/3 | 4.289 | 4.271–4.307 | 242,242,242 |
| budget512-chat-stream | 4/4 | 3/3 | 4.288 | 4.269–4.296 | 242,242,242 |
| budget512-tool | 4/4 | 3/3 | 2.565 | 2.547–2.579 | 73,73,73 |
| budget512-tool-stream | 4/4 | 3/3 | 2.548 | 2.542–2.551 | 73,73,73 |

Для control все4long закончились length/output2048 без final. Для128 все4long — stop/output137, точныйLAB_SENTINEL_42. Для512 все4long — stop/output804; в content осталась часть reasoning, дополнительный </think> и sentinel в конце, поэтому exact final contract failed. Клиент не вырезает «последний правильный ответ». Все short chat/tool JSON/SSE случаи128/512 прошли. На long128/512 каждый log подтверждает activated с соответствующим budget, exhausted и forced sequence complete.

Native maxRSS **9.804GiB**, минимум vm_stat free pages **39.60GiB**, maxswap **0.000GiB**. Free pages не равны всей доступной памяти; RSS не складывается с пересекающимися Metal allocations. Cold startup отдельно в server-execution, не входит в request medians.

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
