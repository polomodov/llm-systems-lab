# LAB34 — продолжение нагрузки на Mac

Сессия `apple-load-resume-20261009`, 09.10.2026 08:19:32–08:30:21 UTC. Статус **blocked**.

## Паспорт выполнения

M5 Max, 128 GiB, macOS 26.5, arm64. Qwen3.5-9B Q6_K GGUF, pinned revision/hash и patched llama.cpp b8407/tile16 закреплены в [runtime manifest](raw/runtime-manifest.json) и [build reference](raw/build-reference.json). Новый native PID 76804; лог подтверждает Metal/M5, offload 33/33 и tensor capability. Context 8192, один GPU-слот, client concurrency 1/2/4, KV f16/f16, output cap 2048, seed 1, temperature 0; no-cache-prompt, reasoning auto и enable_thinking=true. [Точное тело запроса](raw/load-request.json). Агентный harness не запускался, run_ids=[].

## Гипотеза и протокол до запуска

Новый resident deployment завершит оставшиеся короткие клетки и ≥1800 секунд sustained в прежних границах. [Протокол](raw/protocol.md), source hashes и план десяти попыток закреплены до старта в commit `1484f47`. Четыре успешных блока 08.10 скопированы с проверкой hashes как историческая evidence; они не являются новыми запросами. Старый неудачный r2-c4 и неизвестный источник SIGKILL остаются в [предыдущем отчёте](../LAB34-apple-load-complete-20261008/report.md).

## Ход выполнения

| Шаг | Результат | Доказательство |
| --- | --- | --- |
| prior-evidence-audit | completed, offline exercise; hashes копий совпали | [Audit](raw/prior-evidence-audit-execution.json) |
| startup | completed; AC/mode 0, чужих моделей нет, pinned binary/model hashes совпали | [Startup](raw/startup-execution.json), [process](raw/startup-process.json), [server](raw/server.txt) |
| warmup | completed, 2/2 | [Первичные ответы и summary](raw/warmup/summary.json) |
| r2-c4 retry | failed, 11/12; последний ответ timeout | [Block](raw/r2-c4/summary.json), [execution](raw/r2-c4-execution.json) |
| r2-c1, r3-c4/c1/c2, sustained | not-run после guard | [Остановка](raw/campaign-error.json) |
| shutdown | failed по допуску кампании; native exit 0, один SIGINT, guard сохраняется | [Shutdown](raw/shutdown-execution.json) |

## Результаты

| Новая серия | Успех / всего | Median / p95 / max успешных latency, s | Wall, s | Requests/s | Completion tokens/s |
| --- | --- | --- | --- | --- | --- |
| warmup c1 | 2/2 | 33.090 / 33.778 / 33.778 | 66.182 | 0.030220 | 61.890 |
| r2-c4 retry | 11/12 | 139.514 / 143.418 / 143.418 | 578.133 | 0.019027 | 38.967 |
| остальные короткие клетки / sustained | not-run | — | — | — | — |

302 наблюдения TSV включают первичные метрики новых запросов и исторических копий; последние имеют `prior-short/` в metric/evidence path. Копии не прибавляются к новым запросам. Для двух сессий 08.10 и 09.10: предыдущая — 62 запроса/2 ошибки; новая — 14/1; вместе 76/3. Это счёт именно этих двух сессий, без более ранней `apple-direct-load-20261008`.

223 macOS samples: минимальный free+speculative 29.845 GiB; pressure free минимум 88%, pressure level всегда 1, swap максимум 0, native RSS максимум 7.584 GiB. Все 13 успешных новых ответов имеют finish_reason=length и 2048 completion tokens; качество текста/выполнение примерно 300 слов не оценивалось. Throughput не является decode-only speed.

## Ошибки и ограничения

В 08:27:10.846 UTC [guard](raw/guard-trigger.json) зафиксировал Battery Power/19%, AC=false при mode 0. Память при этом была в границах: free+speculative 31.585 GiB, normal pressure, swap 0. Причина guard в этой сессии установлена по переключению питания; это не доказательство причины старого SIGKILL.

Guard отправил один SIGINT в 08:27:10.876 UTC. Последний HTTP-запрос дождался deadline 300 секунд; shutdown затем зафиксировал native exit 0. Двойного SIGINT и teardown assertion здесь нет. Timeline прекращается после guard; непрерывная telemetry оставшегося HTTP ожидания отсутствует, после cleanup сохранён отдельный sample с восстановленным AC. Длинная серия не начиналась, selection отсутствует. TTFT, энергия, температура и максимальный GPU budget неизвестны с причинами.

## Вывод по гипотезе

**Данных недостаточно:** пять коротких клеток и 30 минут не завершены. Отказ c4 вызван потерей зарегистрированного условия питания; он сохраняется и не объявляется успешным блоком. Штатное завершение native процесса подтверждает корректность cleanup для наблюдавшейся остановки, но не даёт допуска полной LAB34.

## Ответы на контрольные вопросы

1. Client concurrency не равна GPU parallelism: четыре клиента стоят в очереди к одному server slot.
2. p95 на 12 запросах близок к максимуму и имеет слабую статистическую точность; в failed блоке latency успешных ответов не описывает timeout.
3. Общий throughput — сумма успешных tokens / полный wall interval; среднее block rates игнорирует разные длительности и ожидание ошибки.
4. Для throttling нужны проверенные thermal/power measurements, привязанные ко времени. Одной задержки или смены power source недостаточно.

## Комплект сдачи

Manifest v2 перечисляет 3 completed, 2 failed, 5 not-run. Сохранены native log, все requests/responses, usage/latency, macOS timeline, остановка и cleanup; [summary](raw/summary.json), [SHA-256 inventory](raw/evidence-sha256.json), TSV и offline exporter. Агентных попыток нет. Структурная проверка submission означает комплектность, а не pass аппаратного допуска. Решение проверяющего: **не проверено**.
