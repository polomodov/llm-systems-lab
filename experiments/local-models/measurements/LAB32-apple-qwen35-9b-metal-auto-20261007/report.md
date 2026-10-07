# LAB32 — первый этап reasoning-auto на M5 Max

Сессия: `apple-qwen35-9b-metal-auto-20261007`. Статус: **in-progress: выполнен только этап 8K**. Этап 8K с reasoning=auto прошёл: четыре protocol fixtures и длинный вход 4083 tokens имеют прогрев и три повтора; проверены отмена/освобождение слота/recovery и overflow/recovery. 16K/32K остаются планом, LAB32 целиком не завершена.

## Паспорт выполнения

Codex по запросу владельца, 07.10.2026. Apple M5 Max / 128 GiB / macOS 26.5 / arm64. llama.cpp b8407, commit `312cf03328496df9c56fe843952cf02a8964c59a` с сохранённым tensor tile16 patch. Local Qwen3.5-9B Q6_K @3885219… с SHA91898433… из LAB29; source/binary/weight hashes — в [runtime manifest](raw/runtime-manifest.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=auto / enable_thinking=true, temperature0/seed1. Prefix cache отключён и сервером, и request.cache_prompt=false. Один сервер на loopback8080; actual n_ctx8192, offload33/33 и tensor=true проверены по props/slots/log. CPU/OS snapshot взят из предыдущей работы; актуальный GPU, memory/power наблюдаются в preflight и server logs. Harness не применяется, run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), [SHA](raw/protocol.sha256), protocol_recorded_at в manifest сохранены до исполнения. Это авторская регистрация, без внешнего удостоверения времени. Все 8K/16K/32K попытки зарегистрированы; failures и пропуски сохранены. Portable probe извлечён из LAB05 без изменения parsing. Offline allowlist — отдельное упражнение с evidence_class=synthetic, не успешные вызовы модели. Основная серия требует прогрев и три повтора каждого случая; рост контекста допускается после успеха предыдущего этапа.

## Ход выполнения

На 8K все четыре protocol fixtures имеют отдельный прогрев и три измеряемых повтора. Проверены reasoning/final, call IDs, arguments, связанный tool result и SSE DONE. Длинный вход: 4083 токена при input budget4096; actual usage совпал с серверным tokenizer, final — LAB_SENTINEL_42.

Отмена: curl exit28, active slot observed=True, idle after=True, освобождение слота после disconnect — 2.279s, DONE=False. Сопоставлены slot observations, server log и recovery без restart. Overflow: HTTP400 с context-specific error; точный input count — в raw/ctx8192-overflow-count.json, recovery — LAB_READY. Остановка одним SIGINT native child завершилась exit0. 16K/32K ещё не запускались.

Сохранены исходные request/response JSON/SSE, assembled messages, timing/usage/followup, полный long prompt/count, ресурсная телеметрия и native logs. Клиент не исполняет код модели: единственной разрешённой функции возвращает фиксированный LAB_VALUE_42. Диагностические controls учитываются отдельно от повторов основной серии. Серверы остановлены; агентские эпизоды не выполнялись.

## Результаты

Измеряемые r1–r3, без прогрева. Tool latency — сумма двух HTTP-вызовов; TTFT доступен только SSE и разделён на content/reasoning. Неизвестные значения остаются null.

| Case | Принятых повторов | Median total s | Min–max s |
| --- | ---: | ---: | --- |
| chat | 3 | 3.784 | 3.765–3.837 |
| chat-stream | 3 | 3.869 | 3.772–3.873 |
| tool | 3 | 2.298 | 2.281–2.312 |
| tool-stream | 3 | 2.315 | 2.307–2.316 |
| long | 3 | 18.108 | 18.045–18.901 |

[TSV](measurements.tsv), [сводка](raw/phase-summary.json), manifest и raw содержат отдельные наблюдения и причины. Подготовлен long input на 4083 tokens; actual usage совпал с серверным tokenizer, sentinel проверен в каждом принятом повторе. Короткий chat в пустом n_ctx8192 сам по себе не проверяет длинный контекст. **16K/32K не измерены.**

В основной серии действует отдельный sampler memory/power каждые 2s, free-page floor16GiB, swap0 и RSS ceiling24GiB. Process RSS/time сохранены в native server log; RSS и пересекающиеся Metal buffers не складываются. Короткие диагностические controls наблюдались до/после без отдельного sampler; это ограничение заранее записано.

## Ошибки и ограничения

Это checkpoint, а не завершённая LAB32. Нужны последовательные этапы 16K/32K; MLX требует отдельной сессии. Проверка HTTP fixtures не реализует provider bridge и не является агентным прогоном.

Cancel сопоставляется по curl, активному слоту, server log и recovery без restart. Освобождение слота не является instruction-level GPU trace. В auto-серии сервер явно пишет cancel task; prefill продолжался некоторое время после отключения клиента, что видно в timeline. Отмена не объявляется мгновенной. Prefix cache выключен, reasoning меняет output count и время до final content; разные режимы не смешиваются.

В исходной серии SIGINT группе под macOS time доставил двойной сигнал, а checker ошибочно счёл shutdown успешным по отсутствию memory guard error. Ошибка derived status исправлена на failed с документированной причиной. Диагностика одним сигналом verified native child дала exit0. TIME_WAIT ложного port guard и отдельно зарегистрированный retry также сохранены. Для auto-серии исправления контроллера выполнены до запуска; model/shader bytes не менялись.

Energy/temperature, максимальный безопасный GPU budget и качество модели не измерены. Номинальная RAM128GiB и recommended working set не означают свободную GPU память. Отдельный эффект tensor API этой серией не исследуется.

## Вывод по гипотезе

Поддержана для выполненного этапа 8K; гипотеза всего маршрута8K/16K/32K ещё не проверена. Следующий этап — 16K в этой же auto-конфигурации после проверки checkpoint.

Ready-for-review у blocked отчёта означает комплектность объяснения, не успешный эксперимент. In-progress отчёт проверяется в draft; сдача всей LAB32 пока невозможна. Ошибки исходного режима сохранены отдельно от новой серии.

## Ответы на контрольные вопросы

1. Non-streaming wall включает обработку входа и весь output; момент первого content неизвестен, поэтому TTFT=null.
2. Client CTX не выделяет cache. Здесь hard n_ctx установлен native server и подтверждён props/slots. MLX cap необходимо исследовать отдельно.
3. Client timeout закрывает соединение. Slot/log/recovery показывают реакцию сервера; перезапуск сервера не заменяет проверку отмены generation.
4. Prefix cache меняет prefill. Первый reasoning-токен может появиться значительно раньше final content; эти каналы измеряются отдельно.

## Комплект сдачи

Manifest v2, предварительные protocol/hash и полный register; fixtures/probe; binary/weight verification; JSON/SSE/token counts, logs/telemetry и failure/control evidence. Reviewer decision=null: независимой оценки нет. 16K/32K остались planned: работа начата, но не готова к submission.
