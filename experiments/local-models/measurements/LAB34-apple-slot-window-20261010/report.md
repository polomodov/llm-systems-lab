# LAB34 — фактические серверные слоты

Сессия `apple-server-slots-20261010`, статус **blocked**. Actual server-slot campaign stopped: Admission changed during pin verification

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5, AC/mode 0. Qwen3.5-9B GGUF Q6_K, revision 3885219b6810b007914f3a7950a8d1b469d598a5, llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a / Metal tensor tile16. [Точные hashes и runtime](raw/deployment-reference.json). MLX не используется. Это HTTP нагрузка, не агентный episode; run_ids пуст.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и [source registration](raw/source-registration.json) закреплены commit до исполнения. Серверные слоты 1/2/4, общий контекст slots×8192 и фактический контекст 8192 на каждом слоте. Параметры: KV f16/f16, FA on, threads 8, batch 512, ubatch 256, reasoning auto/thinking true, cache-ram 0, no-cache-prompt. HTTP output cap 512, temp 0, seed 1, top_p 1. Прогрев + три когорты на условие; 30 минут slots4 только после всех коротких проверок. Baseline free+spec ≥24 GiB, runtime ≥8 GiB, swap 0, pressure level 1, AC/mode 0. Порог не ослабляется после отказа.

## Ход выполнения

[Контроллер](raw/run_slots.py) проверяет артефакт и все bundled dylib до Popen, затем readiness/props/template/logs/фактические слоты. [Driver](raw/concurrency_driver.py) сохраняет каждый JSON запрос/ответ без retries. Cleanup затрагивает только собственные process groups. Отказ admission означает отсутствие загрузки модели, а не OOM. Будущие попытки not-run и первичная ошибка сохраняются.

## Результаты

Attempts: {"completed": 0, "failed": 1, "not-run": 18}. Latency — полный ответ, throughput — primary completion tokens / wall когорты. Наблюдаемые busy slots означают логический параллелизм сервера.

| Slots | Условие | Ответы / admission | p95, с | Throughput, tokens/s | Принято |
| --- | --- | --- | --- | --- | --- |
| 1 | admission.json | free+spec 28.993 GiB | — | — | — |
| 1 | admission-after-pins.json | free+spec 22.199 GiB | — | — | — |

## Ошибки и ограничения

Admission changed during pin verification Полный GPU budget, температура, энергия и TTFT неизвестны. Output cap 512 отличается от прежней очереди клиентов на одном слоте с cap 2048; прямое сравнение latency этих серий некорректно. Доказательства реальных слотов и logs обязательны независимо от CLI параметров.

## Вывод по гипотезе

Actual server-slot campaign stopped: Admission changed during pin verification При отказе до модели данных о throughput нет. Успешная сдача отчёта не означает успешный эксперимент или универсальную поддержку оборудования.

## Ответы на контрольные вопросы

1. Concurrency клиентов и slots сервера проверяются отдельно: очередь на одном слоте не равна четырём processing slots.
2. Фиксированный контекст на слот требует общего context slots×8192 и проверки actual slots[*].n_ctx.
3. Стабильность требует primary ошибок/latency/usage и непрерывного resource collector, не только завершения клиента.
4. Cold start, прогрев и повторы разделены; 30 минут не запускаются после короткого отказа.
5. RSS и free+spec — разные показатели, физические GPU страницы и максимальный budget не выдумываются.

## Комплект сдачи

Manifest v2, protocol/source registration, pin reference, первичные admission/execution/ошибки и TSV сохранены. Все attempts перечислены. lab:check submission проверяет комплектность; reviewer decision **не проверено**.
