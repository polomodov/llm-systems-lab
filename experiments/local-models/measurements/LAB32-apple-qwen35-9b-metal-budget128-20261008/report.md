# LAB32 — контекст и инструменты на Apple M5 Max

Сессия: `apple-qwen35-9b-metal-budget128-20261008`. Статус: **blocked**. Кампания не завершена; допуск только для полностью проверенных этапов: 8192. Отказы: ctx16384-long-warmup.

## Паспорт выполнения

Codex по запросу владельца, 08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5 build25F71, arm64. Нативный llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. [Runtime](raw/runtime-manifest.json), свежая [проверка перед запуском](raw/preflight-execution.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto/enable_thinking=true, request thinking_budget_tokens=128 (включая followup, cancel/overflow/recovery), server --reasoning-budget -1, temperature0/seed1/top_p1, prefix cache отключён сервером и request.cache_prompt=false. Один собственный server на loopback8080; hard caps8192/16384/32768 проверяются props/slots и log, offload33/33, tensor=true. Harness отсутствует; run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), его [hash](raw/protocol.sha256) и register сохранены до запуска. Прогрев и три повтора каждого chat/tool × JSON/SSE и long case; cancel/overflow с recovery на каждом контексте. Последовательный допуск8K→16K→32K. Это независимая серия с фиксированным request budget128 после диагностики. Все 80 попыток зарегистрированы до запуска; независимого удостоверения времени регистрации нет. Контексты перезапускаются последовательно после успешного предыдущего допуска.

## Ход выполнения

На каждом контексте отдельный native server start/device/hard-cap verification. Final chat=LAB_READY; tool exactly1 lookup_lab_value(key=alpha), непустой call ID, связанный фиксированный resultLAB_VALUE_42, final=LAB_VALUE_42. Код модели не исполнялся. SSE требует DONE; usage и content/reasoning timings сохранены раздельно. Offline name/key/id allowlist — synthetic exercise, отдельно от модели.

Следующие проверки описывают протокол; принятые этапы: 8192. Long prompt построен серверными apply-template/tokenize с теми же thinking options, близок к input budgetCTX−4096, max_tokens2048; actual usage совпадает, final=LAB_SENTINEL_42. Cancel: curl timeout1s, exit28, активный slot наблюдается, DONE отсутствует, server cancel task ID совпадает с observed task, idle в пределах60s после client exit и recovery без restart. Время client exit фиксирует отдельный watcher независимо от /slots polling. Overflow: точный input>hard cap, context-specific HTTP400 и recovery без restart. Успешность каждого воздействия определяется его attempt status и raw execution; при отказе следующие попытки не выполняются. Все первичные request/response, prompts/counts, timestamps, server logs и memory timeline сохранены. Серверы остановлены одним SIGINT верифицированному native child.

## Результаты

Медианы только r1–r3, прогрев отдельно. Tool round trip — сумма двух HTTP-вызовов. Cold startup не входит в latency, cache выключен. TTFT для JSON недоступен; SSE content и reasoning — в [TSV](measurements.tsv). [Сводка](raw/campaign-summary.json).

| Hard context | Case | Повторов | Median total s | Min–max s |
| ---: | --- | ---: | ---: | --- |
| 8192 | chat | 3 | 2.121 | 2.111–2.124 |
| 8192 | chat-stream | 3 | 2.175 | 2.174–2.200 |
| 8192 | tool | 3 | 2.407 | 2.395–2.413 |
| 8192 | tool-stream | 3 | 2.418 | 2.394–2.433 |
| 8192 | long | 3 | 5.366 | 5.348–5.411 |
| 16384 | chat | 3 | 2.108 | 2.098–2.132 |
| 16384 | chat-stream | 3 | 2.107 | 2.103–2.126 |
| 16384 | tool | 3 | 2.308 | 2.296–2.318 |
| 16384 | tool-stream | 3 | 2.332 | 2.327–2.345 |

| Hard context | Long input / budget | Max RSS GiB | Min free pages GiB | Max swap GiB | Slot release after disconnect s | Overflow input / HTTP |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8192 | 4083 / 4096 | 7.977 | 45.64 | 0.000 | 2.352 | 16305 / 400 |

## Ошибки и ограничения

Отказы сохранены: ctx16384-long-warmup. Неисполненные попытки отмечены not-run; повторов для замены отказа нет. На16K long warmup вернул `LAB_SENTINEL_42.` с лишней точкой вместо точного LAB_SENTINEL_42. Input12287, output138, HTTP200/SSE DONE, finish_reason=stop; budget128 сработал по sampler log. Это exact-final failure, а не установленная потеря контекста или OOM. Long r1–r3, воздействия16K и весь32K в этой серии не запускались.

Предыдущие [thinking=false](../LAB32-apple-qwen35-9b-metal-20261007/report.md) и [unrestricted-auto](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md) серии остаются blocked. [Диагностика128/512](../LAB32-apple-qwen35-9b-reasoning-budget-20261008/report.md) выделила128 как пригодный для exact final на одном длинном запросе; здесь заново проверены все контексты и воздействия. Binary/shader/weights не менялись. Controller patch и sampler API source excerpts сохранены.

Окно ожидания отмены заранее увеличено с15 до60s: на32K prefill в диагностике занимал около26s. Фактическая задержка освобождения измеряется от client exit, не от завершения polling. Этот допуск не означает отмены за15s или мгновенного прекращения GPU работы; требования к чувствительному к задержке harness задаются отдельно. Сопоставление IDs/slot/log/recovery — operational evidence, без instruction-level GPU trace. Прежние измерения latency от наблюдения контроллером могут иметь другой polling lag.

Swap0/free-page floor16GiB/RSS ceiling24GiB/AC powermode0 наблюдались каждые2s. RSS не складывается с пересекающимися Metal buffers. Отмена подтверждена slot/log/recovery, не instruction-level GPU trace; prefill может продолжаться после client disconnect. Energy/temperature и максимальный безопасный GPU budget не измерены. Результат относится к одной модели/квантизации/сборке/fixtures, не к общей надёжности tool use или качеству длинного контекста. MLX protocol — отдельная будущая сессия.

## Вывод по гипотезе

Кампания не завершена; допуск только для полностью проверенных этапов: 8192. Отказы: ctx16384-long-warmup. Для полностью принятых этапов допустим переход к LAB08/provider bridge и LAB34 для той же конфигурации и принятого контекста, с отдельными протоколами и проверками. Проверка loopback HTTP не реализует bridge и не является агентным эпизодом. Агентные попытки потребуют run.json. Не переносить GGUF память на MLX.

## Ответы на контрольные вопросы

1. JSON wall включает prefill и весь output, момент первого content неизвестен; TTFT=null.
2. Hard cap задаёт native server, проверяется props/slots; client CTX сам не выделяет cache. MLX cap требует отдельной проверки.
3. Client timeout закрывает socket; server logs/slot/recovery показывают последующую реакцию. Restart не заменяет recovery.
4. Prefix cache меняет prefill; первый reasoning token может предшествовать final content, поэтому каналы разделены.

## Комплект сдачи

Manifest v2, исходный protocol/hash и полный register, fixtures/probe, model/binary verification, JSON/SSE/token counts, logs/telemetry, offline validation, sampler/source/controller patch и итоговый exporter. Reviewer decision=null: независимой научной оценки нет. lab:check проверяет комплектность, не истинность гипотезы.
