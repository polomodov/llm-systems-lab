# LAB32 — контекст и инструменты на Apple M5 Max

Сессия: `apple-qwen35-9b-32k-recovery-20261008`. Статус: **completed**. Самостоятельный контекст32K прошёл protocol и resource admission; допуск ограничен проверенными fixtures и условиями.

## Паспорт выполнения

Codex по запросу владельца, 08.10.2026. Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5 build25F71, arm64. Нативный llama.cpp b8407 commit312cf03328496df9c56fe843952cf02a8964c59a с tensor tile16 patch из LAB30. Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. [Runtime](raw/runtime-manifest.json), свежая [проверка перед запуском](raw/preflight-execution.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto/enable_thinking=true, request thinking_budget_tokens=128 (включая followup, cancel/overflow/recovery), server --reasoning-budget -1, temperature0/seed1/top_p1, prefix cache отключён сервером и request.cache_prompt=false. Один собственный server на loopback8080; hard cap32768 проверяется props/slots и log, offload33/33, tensor=true. Harness отсутствует; run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), его [hash](raw/protocol.sha256) и register сохранены до запуска. Прогрев и три повтора каждого chat/tool × JSON/SSE и long case; cancel/overflow с recovery на каждом контексте. Это отдельная квалификация32K, опирающаяся на [диагностический допуск](raw/prior-diagnostic-reference.json) для тех же32K fixtures/budget128. Все28 попыток зарегистрированы до запуска; независимого удостоверения времени регистрации нет. Это один residentserver; последовательныймаршрут8K→16K→32K здесь не исполняется.

## Ход выполнения

На каждом контексте отдельный native server start/device/hard-cap verification. Final chat=LAB_READY; tool exactly1 lookup_lab_value(key=alpha), непустой call ID, связанный фиксированный resultLAB_VALUE_42, final=LAB_VALUE_42. Код модели не исполнялся. SSE требует DONE; usage и content/reasoning timings сохранены раздельно. Offline name/key/id allowlist — synthetic exercise, отдельно от модели.

Следующие проверки описывают протокол; принятые этапы: 32768. Long prompt построен серверными apply-template/tokenize с теми же thinking options, близок к input budgetCTX−4096, max_tokens2048; actual usage совпадает, final=LAB_SENTINEL_42. Cancel: curl timeout1s, exit28, активный slot наблюдается, DONE отсутствует, server cancel task ID совпадает с observed task, idle в пределах60s после client exit и recovery без restart. Время client exit фиксирует отдельный watcher независимо от /slots polling. Overflow: точный input>hard cap, context-specific HTTP400 и recovery без restart. Успешность каждого воздействия определяется его attempt status и raw execution; при отказе следующие попытки не выполняются. Все первичные request/response, prompts/counts, timestamps, server logs и memory timeline сохранены. Серверы остановлены одним SIGINT верифицированному native child.

## Результаты

Медианы только r1–r3, прогрев отдельно. Tool round trip — сумма двух HTTP-вызовов. Cold startup не входит в latency, cache выключен. TTFT для JSON недоступен; SSE content и reasoning — в [TSV](measurements.tsv). [Сводка](raw/campaign-summary.json).

| Hard context | Case | Повторов | Median total s | Min–max s |
| ---: | --- | ---: | ---: | --- |
| 32768 | chat | 3 | 2.101 | 2.095–2.112 |
| 32768 | chat-stream | 3 | 2.118 | 2.112–2.129 |
| 32768 | tool | 3 | 2.322 | 2.303–2.323 |
| 32768 | tool-stream | 3 | 2.335 | 2.328–2.388 |
| 32768 | long | 3 | 29.639 | 28.953–30.514 |

| Hard context | Long input / budget | Max RSS GiB | Min free pages GiB | Max swap GiB | Slot release after disconnect s | Overflow input / HTTP |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 32768 | 28670 / 28672 | 9.866 | 43.09 | 0.000 | 27.154 | 57331 / 400 |

## Ошибки и ограничения

Все зарегистрированные попытки прошли; предыдущие отказы сохранены в отдельных сессиях.

Предыдущие [thinking=false](../LAB32-apple-qwen35-9b-metal-20261007/report.md) и [unrestricted-auto](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md) серии остаются blocked. [Диагностика128/512](../LAB32-apple-qwen35-9b-reasoning-budget-20261008/report.md) выделила128 как пригодный для exact final на одном длинном запросе; здесь заново проверены32K fixtures и воздействия. [Последовательная budget128 серия](../LAB32-apple-qwen35-9b-metal-budget128-20261008/report.md) остановлена на16K из-за лишнейточки в final; еёотказ не заменяется. full_lab32_admission=false, допуск ограничен отдельным32K deployment. Binary/shader/weights не менялись. Controller patch и sampler API source excerpts сохранены.

Окно ожидания отмены заранее увеличено с15 до60s: на32K prefill в диагностике занимал около26s. Фактическая задержка освобождения измеряется от client exit, не от завершения polling. Этот допуск не означает отмены за15s или мгновенного прекращения GPU работы; требования к чувствительному к задержке harness задаются отдельно. Сопоставление IDs/slot/log/recovery — operational evidence, без instruction-level GPU trace. Прежние измерения latency от наблюдения контроллером могут иметь другой polling lag.

Swap0/free-page floor16GiB/RSS ceiling24GiB/AC powermode0 наблюдались каждые2s. RSS не складывается с пересекающимися Metal buffers. Отмена подтверждена slot/log/recovery, не instruction-level GPU trace; prefill может продолжаться после client disconnect. Energy/temperature и максимальный безопасный GPU budget не измерены. Результат относится к одной модели/квантизации/сборке/fixtures, не к общей надёжности tool use или качеству длинного контекста. MLX protocol — отдельная будущая сессия.

## Вывод по гипотезе

Самостоятельный контекст32K прошёл protocol и resource admission; допуск ограничен проверенными fixtures и условиями. Для этого отдельного32K deployment проверены fixtures/recovery при budget128; реальный harness должен дополнительно принять latency/операционныеусловия. ПолныймаршрутLAB32 не завершён. Для дальнейшейLAB08/provider bridge/LAB34, с отдельными протоколами и проверками. Проверка loopback HTTP не реализует bridge и не является агентным эпизодом. Агентные попытки потребуют run.json. Не переносить GGUF память на MLX.

## Ответы на контрольные вопросы

1. JSON wall включает prefill и весь output, момент первого content неизвестен; TTFT=null.
2. Hard cap задаёт native server, проверяется props/slots; client CTX сам не выделяет cache. MLX cap требует отдельной проверки.
3. Client timeout закрывает socket; server logs/slot/recovery показывают последующую реакцию. Restart не заменяет recovery.
4. Prefix cache меняет prefill; первый reasoning token может предшествовать final content, поэтому каналы разделены.

## Комплект сдачи

Manifest v2, исходный protocol/hash и полный register, fixtures/probe, model/binary verification, JSON/SSE/token counts, logs/telemetry, offline validation, sampler/source/controller patch и итоговый exporter. Reviewer decision=null: независимой научной оценки нет. lab:check проверяет комплектность, не истинность гипотезы.
