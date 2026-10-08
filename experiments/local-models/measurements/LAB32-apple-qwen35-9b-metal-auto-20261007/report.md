# LAB32 — контекст и инструменты на Apple M5 Max

Сессия: `apple-qwen35-9b-metal-auto-20261007`. Статус: **blocked**. Кампания не завершена; допуск только для полностью проверенных этапов: 8192, 16384. Отказы: ctx32768-long-warmup.

## Паспорт выполнения

Codex по запросу владельца, 07–08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5 build25F71, arm64. Нативный llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. [Runtime](raw/runtime-manifest.json), свежая [проверка продолжения](raw/continuation-preflight.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto/enable_thinking=true, temperature0/seed1/top_p1, prefix cache отключён сервером и request.cache_prompt=false. Один собственный server на loopback8080; hard caps8192/16384/32768 проверяются props/slots и log, offload33/33, tensor=true. Harness отсутствует; run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), его [hash](raw/protocol.sha256) и register сохранены до запуска. Прогрев и три повтора каждого chat/tool × JSON/SSE и long case; cancel/overflow с recovery на каждом контексте. Последовательный допуск8K→16K→32K. 8K измерен07.10, продолжение08.10 зарегистрировано [отдельно](raw/continuation-registration.json) без смены условий. Разница дней входит в условия сравнения, нет независимого удостоверения времени регистрации.

## Ход выполнения

На каждом контексте отдельный native server start/device/hard-cap verification. Final chat=LAB_READY; tool exactly1 lookup_lab_value(key=alpha), непустой call ID, связанный фиксированный resultLAB_VALUE_42, final=LAB_VALUE_42. Код модели не исполнялся. SSE требует DONE; usage и content/reasoning timings сохранены раздельно. Offline name/key/id allowlist — synthetic exercise, отдельно от модели.

Следующие проверки описывают протокол; принятые этапы: 8192, 16384. Long prompt построен серверными apply-template/tokenize с теми же thinking options, близок к input budgetCTX−4096, max_tokens2048; actual usage совпадает, final=LAB_SENTINEL_42. Cancel: curl timeout1s, exit28, активный slot наблюдается, DONE отсутствует, server cancel log, idle и recovery без restart. Overflow: точный input>hard cap, context-specific HTTP400 и recovery без restart. Успешность каждого воздействия определяется его attempt status и raw execution; при отказе следующие попытки не выполняются. Все первичные request/response, prompts/counts, timestamps, server logs и memory timeline сохранены. Серверы остановлены одним SIGINT верифицированному native child.

## Результаты

Медианы только r1–r3, прогрев отдельно. Tool round trip — сумма двух HTTP-вызовов. Cold startup не входит в latency, cache выключен. TTFT для JSON недоступен; SSE content и reasoning — в [TSV](measurements.tsv). [Сводка](raw/campaign-summary.json).

| Hard context | Case | Повторов | Median total s | Min–max s |
| ---: | --- | ---: | ---: | --- |
| 8192 | chat | 3 | 3.784 | 3.765–3.837 |
| 8192 | chat-stream | 3 | 3.869 | 3.772–3.873 |
| 8192 | tool | 3 | 2.298 | 2.281–2.312 |
| 8192 | tool-stream | 3 | 2.315 | 2.307–2.316 |
| 8192 | long | 3 | 18.108 | 18.045–18.901 |
| 16384 | chat | 3 | 3.848 | 3.833–3.875 |
| 16384 | chat-stream | 3 | 4.009 | 3.950–4.009 |
| 16384 | tool | 3 | 2.378 | 2.376–2.384 |
| 16384 | tool-stream | 3 | 2.403 | 2.397–2.414 |
| 16384 | long | 3 | 29.205 | 27.956–29.853 |
| 32768 | chat | 3 | 4.081 | 4.060–4.219 |
| 32768 | chat-stream | 3 | 4.101 | 4.076–4.110 |
| 32768 | tool | 3 | 2.405 | 2.391–2.405 |
| 32768 | tool-stream | 3 | 2.412 | 2.404–2.417 |

| Hard context | Long input / budget | Max RSS GiB | Min free pages GiB | Max swap GiB | Slot release after disconnect s | Overflow input / HTTP |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8192 | 4083 / 4096 | 7.982 | 39.33 | 0.000 | 2.279 | 16305 / 400 |
| 16384 | 12287 / 12288 | 8.612 | 58.52 | 0.000 | 9.238 | 24565 / 400 |

## Ошибки и ограничения

На 32K длинный warmup: input28670, HTTP200/SSE DONE, finish_reason=length, output2048, final content пуст. Sentinel присутствует в reasoning, поэтому потеря контекста не доказана; зарегистрированный final contract не выполнен. Long r1–r3, cancel/overflow/recovery на32K не запускались. Native shutdown exit0, swap0. [Разбор](raw/ctx32768-failure-analysis.json). Никаких retry или смены output cap/reasoning в исходной серии.

Исходная thinking=false серия остаётся blocked в соседнем отчёте: модель не вызвала tool. Auto — самостоятельное условие, не исправление её результатов. Ошибка двойного SIGINT и TIME_WAIT port guard была исправлена до этой серии; новые модельные повторы не подменяли failures. Архив checkpoint8K сохранён в raw/checkpoint-8k-*; phase-summary.json и finalize_phase.py описывают только прежний этап, итог всей кампании — campaign-summary.json и finalize_campaign.py.

Swap0/free-page floor16GiB/RSS ceiling24GiB/AC powermode0 наблюдались каждые2s. RSS не складывается с пересекающимися Metal buffers. Отмена подтверждена slot/log/recovery, не instruction-level GPU trace; prefill может продолжаться после client disconnect. Energy/temperature и максимальный безопасный GPU budget не измерены. Результат относится к одной модели/квантизации/сборке/fixtures, не к общей надёжности tool use или качеству длинного контекста. MLX protocol — отдельная будущая сессия.

## Вывод по гипотезе

Кампания не завершена; допуск только для полностью проверенных этапов: 8192, 16384. Отказы: ctx32768-long-warmup. Для полностью принятых этапов допустим переход к LAB08/provider bridge и LAB34 для той же конфигурации и принятого контекста, с отдельными протоколами и проверками. Проверка loopback HTTP не реализует bridge и не является агентным эпизодом. Агентные попытки потребуют run.json. Не переносить GGUF память на MLX.

## Ответы на контрольные вопросы

1. JSON wall включает prefill и весь output, момент первого content неизвестен; TTFT=null.
2. Hard cap задаёт native server, проверяется props/slots; client CTX сам не выделяет cache. MLX cap требует отдельной проверки.
3. Client timeout закрывает socket; server logs/slot/recovery показывают последующую реакцию. Restart не заменяет recovery.
4. Prefix cache меняет prefill; первый reasoning token может предшествовать final content, поэтому каналы разделены.

## Комплект сдачи

Manifest v2, исходный protocol/hash и полный register, fixtures/probe, model/binary verification, JSON/SSE/token counts, logs/telemetry, offline validation, checkpoint и итоговый exporter. Reviewer decision=null: независимой научной оценки нет. lab:check проверяет комплектность, не истинность гипотезы.
