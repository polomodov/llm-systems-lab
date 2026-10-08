# LAB32 — исходная no-thinking серия на M5 Max

Сессия: `apple-qwen35-9b-metal-20261007`. Статус: **blocked для исходного условия**. На 8K chat JSON/SSE прошли прогрев и три повтора; tool warmup вернул 10 без tool_calls и отклонён. Свежий no-thinking контроль повторил отказ, один auto-контроль прошёл. Двойной SIGINT вызвал abort при cleanup; один сигнал native child завершает сервер с exit0. Исходное условие не получило допуска к LAB08/нагрузке.

## Паспорт выполнения

Codex по запросу владельца, 07.10.2026. Apple M5 Max / 128 GiB / macOS 26.5 / arm64. llama.cpp b8407, commit `312cf03328496df9c56fe843952cf02a8964c59a` с сохранённым tensor tile16 patch. Local Qwen3.5-9B Q6_K @3885219… с SHA91898433… из LAB29; source/binary/weight hashes — в [runtime manifest](raw/runtime-manifest.json).

Threads8, batch512/ubatch256, KVf16/f16, FAon, slots1, jinja, no-context-shift, reasoning=off / enable_thinking=false, temperature0/seed1. Prefix cache отключён и сервером, и request.cache_prompt=false. Один сервер на loopback8080; actual n_ctx8192, offload33/33 и tensor=true проверены по props/slots/log. CPU/OS snapshot взят из предыдущей работы; актуальный GPU, memory/power наблюдаются в preflight и server logs. Harness не применяется, run_ids пусты.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), [SHA](raw/protocol.sha256), protocol_recorded_at в manifest сохранены до исполнения. Это авторская регистрация, без внешнего удостоверения времени. Все 8K/16K/32K попытки зарегистрированы; failures и пропуски сохранены. Portable probe извлечён из LAB05 без изменения parsing. Offline allowlist — отдельное упражнение с evidence_class=synthetic, не успешные вызовы модели. Основная серия требует прогрев и три повтора каждого случая; рост контекста допускается после успеха предыдущего этапа.

## Ход выполнения

Tool warmup JSON: HTTP200, prompt315/completion3, stop/content10 без tool_calls; lookup не исполнялся. Свежий no-thinking control снова вернул10/stop. Один fresh-auto JSON control выполнил lookup_lab_value с key alpha, непустым ID, связанным tool-result и final LAB_VALUE_42. Это одиночные диагностические случаи, не полный допуск auto.

Первоначальный SIGINT process group послал сигнал и time, и серверу; log показывает second interrupt/forced exit/GGML_ASSERT residency cleanup, nativeexit−6. Derived shutdown status ошибочно был completed только по guard_reason; исправлен наfailed и документирован. При сигнале только верифицированному native child cleanup завершилсяexit0 безassert. Fresh auto control сначала не запускался из-за TIME_WAIT ложного port guard; ошибка сохранена, SO_REUSEADDR correction и отдельный retry зарегистрированы до запуска.

Сохранены исходные request/response JSON/SSE, assembled messages, timing/usage/followup, полный long prompt/count, ресурсная телеметрия и native logs. Клиент не исполняет код модели: единственной разрешённой функции возвращает фиксированный LAB_VALUE_42. Диагностические controls учитываются отдельно от повторов основной серии. Серверы остановлены; агентские эпизоды не выполнялись.

## Результаты

Измеряемые r1–r3, без прогрева. Tool latency — сумма двух HTTP-вызовов; TTFT доступен только SSE и разделён на content/reasoning. Неизвестные значения остаются null.

| Case | Принятых повторов | Median total s | Min–max s |
| --- | ---: | ---: | --- |
| chat | 3 | 0.091 | 0.091–0.091 |
| chat-stream | 3 | 0.092 | 0.091–0.101 |

[TSV](measurements.tsv), [сводка](raw/phase-summary.json), manifest и raw содержат отдельные наблюдения и причины. Подготовлен long input на 4085 tokens; он не выполнялся и не засчитан. Короткий chat в пустом n_ctx8192 сам по себе не проверяет длинный контекст. **16K/32K не измерены.**

В основной серии действует отдельный sampler memory/power каждые 2s, free-page floor16GiB, swap0 и RSS ceiling24GiB. Process RSS/time сохранены в native server log; RSS и пересекающиеся Metal buffers не складываются. Короткие диагностические controls наблюдались до/после без отдельного sampler; это ограничение заранее записано.

## Ошибки и ограничения

Исходная серия не получила допуска к LAB08 или LAB34: tool contract failed. Одиночный auto-control не исправляет исходный результат. Другая thinking-конфигурация оформлена отдельной сессией.

Cancel сопоставляется по curl, активному слоту, server log и recovery без restart. Освобождение слота не является instruction-level GPU trace. В auto-серии сервер явно пишет cancel task; prefill продолжался некоторое время после отключения клиента, что видно в timeline. Отмена не объявляется мгновенной. Prefix cache выключен, reasoning меняет output count и время до final content; разные режимы не смешиваются.

В исходной серии SIGINT группе под macOS time доставил двойной сигнал, а checker ошибочно счёл shutdown успешным по отсутствию memory guard error. Ошибка derived status исправлена на failed с документированной причиной. Диагностика одним сигналом verified native child дала exit0. TIME_WAIT ложного port guard и отдельно зарегистрированный retry также сохранены. Для auto-серии исправления контроллера выполнены до запуска; model/shader bytes не менялись.

Energy/temperature, максимальный безопасный GPU budget и качество модели не измерены. Номинальная RAM128GiB и recommended working set не означают свободную GPU память. Отдельный эффект tensor API этой серией не исследуется.

## Вывод по гипотезе

Не поддержана для исходного no-thinking условия: short chat/SSE прошли, tool failed; long/воздействия и higher contexts не выполнялись по протоколу остановки.

Ready-for-review у blocked отчёта означает комплектность объяснения, не успешный эксперимент. In-progress отчёт проверяется в draft; сдача всей LAB32 пока невозможна. Ошибки исходного режима сохранены отдельно от новой серии.

## Ответы на контрольные вопросы

1. Non-streaming wall включает обработку входа и весь output; момент первого content неизвестен, поэтому TTFT=null.
2. Client CTX не выделяет cache. Здесь hard n_ctx установлен native server и подтверждён props/slots. MLX cap необходимо исследовать отдельно.
3. Client timeout закрывает соединение. Slot/log/recovery показывают реакцию сервера; перезапуск сервера не заменяет проверку отмены generation.
4. Prefix cache меняет prefill. Первый reasoning-токен может появиться значительно раньше final content; эти каналы измеряются отдельно.

## Комплект сдачи

Manifest v2, предварительные protocol/hash и полный register; fixtures/probe; binary/weight verification; JSON/SSE/token counts, logs/telemetry и failure/control evidence. Reviewer decision=null: независимой оценки нет. Оставшиеся попытки отмечены not-run с причиной остановки исходного условия.
