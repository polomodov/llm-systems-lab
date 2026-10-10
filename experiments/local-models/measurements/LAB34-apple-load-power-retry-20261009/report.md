# LAB34 — короткая матрица и прерванная длительная серия

Сессия `apple-load-power-retry-20261009`; native 08:35:19–09:19:12 UTC. Статус **blocked**.

## Паспорт выполнения

M5 Max / 128 GiB / macOS 26.5, native GGUF Qwen3.5-9B Q6_K, patched llama.cpp b8407/tile16/Metal. [Runtime и hashes](raw/runtime-manifest.json), [build](raw/build-reference.json), [native log](raw/server.txt). Context 8192, один GPU-слот, KV f16/f16, no-cache-prompt, temperature 0/seed 1, output cap 2048, reasoning auto/enable_thinking=true. Агентных попыток нет, run_ids=[].

## Гипотеза и протокол до запуска

Пять оставшихся коротких клеток и ≥1800 секунд sustained завершатся после восстановления AC. [Протокол](raw/protocol.md) и [двухминутный admission](raw/preflight-stable-power.jsonl) закреплены до старта в commit b21b1f7. Четыре клетки 08.10 — исторические primary copies с hashes; обе предыдущие неудачные r2-c4 остаются в исходных отчётах. Девять успешных клеток матрицы происходят из двух сессий/двух дней; история остановок включает три процесса.

## Ход выполнения

Audit, startup, warmup и пять коротких блоков completed. Выбор c1 записан до sustained: минимальная concurrency в пределах 95% максимальной median requests/s. Sustained и shutdown failed по native exit -9. [Attempt register](manifest.json), [selection](raw/sustained-selection.json), [series](raw/sustained/series.json), [shutdown](raw/shutdown-execution.json).

## Результаты

| Новая короткая клетка | Успех / всего | Median / p95 latency, s | Completion tokens/s |
| --- | --- | --- | --- |
| r2-c4 | 12/12 | 145.616 / 146.056 | 56.684 |
| r2-c1 | 12/12 | 36.207 / 36.603 | 56.525 |
| r3-c4 | 12/12 | 145.440 / 146.122 | 56.199 |
| r3-c1 | 12/12 | 37.585 / 39.383 | 54.403 |
| r3-c2 | 12/12 | 78.124 / 80.844 | 52.489 |

Warmup 2/2. Для матрицы есть по три успешных блока c1/c2/c4; median requests/s: 0.027279 / 0.026974 / 0.027441. Throughput c4 выше c1 примерно на 0.59%, c2 ниже примерно на 1.12%; при одном слоте рост concurrency в основном увеличивает очередь. Это сравнение двух дней/процессов, а не доказанная эквивалентность runtimes.

Sustained c1: 337.251 секунды из 1800, 8/12 успешных ответов, четыре ошибки соединения. Whole-interval throughput 48.581 completion tokens/s; median успешной latency 38.175 s, p95 38.946 s. Ошибки включены в wall time и знаменатель requests, успешные latency не описывают отказ.

За эту сессию 74 запроса / 4 ошибки; вместе с двумя предыдущими учитываемыми сессиями — 150 / 7. Исторические copies не прибавлены повторно. Более ранняя apple-direct-load-20261008 находится вне этой суммы. В TSV только новые наблюдения; исторические блоки отдельно в summary/raw. [Индивидуальные ответы длинной серии](raw/sustained/block-0001/summary.json) сохранены даже при пустом blocks в первичном series.json.

## Ошибки и ограничения

Native завершился с -9; guard=null, controller interrupts=[]. Источник SIGKILL неизвестен. Не приписываем его команде владельца, Codex cleanup или OOM. Первичный series.json содержит blocks=[], поскольку controller проверил завершение сервера до возврата результата блока; offline exporter обнаруживает реальный failed block по primary summary, не меняя series.json.

После явного «Стоп» controller/client/server/caffeinate уже отсутствовали; проверка не отправила сигналов, [user-stop](raw/user-stop.json). Новое «Продолжи лабу» разрешает отдельное продолжение. Прерванные 337 секунд не складываются с новой длительной серией. TTFT, энергия, температура и максимальный GPU budget неизвестны; latency/throughput не доказывают качество текста или thermal throttling.

## Вывод по гипотезе

**Данных недостаточно для полного допуска:** короткая матрица выполнена, 30 минут — нет. Два старых failed r2-c4 и четыре ошибки sustained сохраняются. Длительную серию требуется повторить в новом resident process со свежим прогревом.

## Ответы на контрольные вопросы

1. Client concurrency — очередь к одному GPU-слоту, не число одновременно работающих GPU sequences.
2. p95 на 12 наблюдениях почти максимум и плохо оценивает хвост распределения; failures учитываются отдельно.
3. Общий throughput требует суммы tokens / полного wall time, а не среднего block rates.
4. Для throttling нужны проверенные thermal/power measurements, сопоставленные с timeline; самой деградации скорости недостаточно.

## Комплект сдачи

Manifest v2, protocol, primary responses/usage/latency, native log, macOS timeline, source hashes, failed series и cleanup сохранены. Offline exporter/summary/TSV включают failed sustained block и не повторяют historical counts. Submission проверяет комплектность; аппаратный pass не назначен, решение проверяющего **не проверено**.
