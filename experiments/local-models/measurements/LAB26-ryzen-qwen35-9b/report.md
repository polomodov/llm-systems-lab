# LAB26 — Параллельная нагрузка (Ryzen, qwen35-9b)

Сессия: `ryzen-qwen35-9b`. Статус: **completed**.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | Qwen3.5-9B Q6_K, unsloth@3885219b…, SHA-256 91898433… |
| Server | llama.cpp b8407 HIP/ROCm (312cf0332), gfx1151; `-ngl 999 -c 8192 -np 1 -t 8 -b 512 -ub 256 -fa on --jinja --reasoning off --no-cache-prompt --slots` |
| Endpoint | http://127.0.0.1:8080/v1/chat/completions, alias qwen35-9b |
| Request | raw/load-request.json, max_tokens 512, stream false; один слот, prefix cache off |
| Стенд | Ryzen AI Max+ 395 / 128 GB; power profile balanced |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`. Порог: 4/4 verdict… (см. LAB20) — здесь: 0 HTTP/protocol errors, swap не растёт, MemAvailable > 8 GiB.

## Ход выполнения

Прогрев 2 запроса (c=1), затем серии 1→2→4 по 12 запросов, timeout 120 s, одна за другой.

## Результаты

| Повтор / concurrency | Success/total | Errors | Median latency, s | p95, s | Req/s | Completion tok/s |
| --- | --- | --- | --- | --- | --- | --- |
| warmup / 1 | 2/2 | 0 | 16.49 | 16.54 | 0.0606 | 27.31 |
| r1 / 1 | 12/12 | 0 | 18.27 | 18.71 | 0.0558 | 27.47 |
| r1 / 2 | 12/12 | 0 | 36.24 | 37.42 | 0.0550 | 27.45 |
| r1 / 4 | 12/12 | 0 | 71.35 | 73.57 | 0.0555 | 27.45 |

| Повтор / concurrency | Min sampled MemAvailable, B | pswpin Δ / pswpout Δ, pages | Raw directory |
| --- | --- | --- | --- |
| r1 / 1 | 119 131 967 488 | +827 / 0 | raw/r1-c1 |
| r1 / 2 | 117 546 446 848 | 0 / 0 | raw/r1-c2 |
| r1 / 4 | 116 069 101 568 | +6 / 0 | raw/r1-c4 |

Отношение req/s (c2/c1, c4/c1) ≈ 0.99 / 1.00; отношение median latency ≈ 1.98 / 3.90.

## Ошибки и ограничения

- **Нет роста throughput**: один server slot очередит запросы, поэтому c2/c4 только
  увеличивают задержку (~линейно), а не параллелизм GPU. Увеличение slots — отдельная серия.
- **Ненулевой pswpin в r1-c1 и r1-c4.** Code review отметил, что прежний «не зафиксирован
  рост» неверен: raw/r1-c1/system-memory.jsonl показывает +827 pswpin_pages
  (8 836 581 → 8 837 408) при 0 pswpout_pages; raw/r1-c4 — +6 pswpin
  (8 837 408 → 8 837 414). c2 — 0/0. Все три серии выполнялись в одном
  bash-цикле, поэтому дельта r1-c2 (0/0) наследует счётчик r1-c1; +6 в r1-c4
  приходится на ~80 с между r1-c1 и r1-c4. pswpout_pages неизменна за весь прогон
  (8 959 232), то есть ничего не вытеснялось. Трафик swap-in совпадает с
  background-IO UMA-машины (см. `journalctl --since '...'`), не с самой серией;
  отметка «swap не растёт» относится к swap-out (page reclaim), а не к page-in.
- `ttft_seconds=null` (non-streaming драйвер), p95 при 12 наблюдениях ≈ max.
- Reasoning off (чтобы финальный текст не обрезался бюджетом) — это load probe, не оценка
  качества. Prefix cache off; запросы идентичны, cache-эффекты не исследовались.
- Энергия не измерялась (нет прибора).
- server process/GPU peak telemetry не собиралась драйвером (null).

## Вывод по гипотезе

**Не поддержана**: client concurrency 1→4 не повысила throughput на этом deployment —
сервер с одним слотом ставит запросы в очередь. Полезный параллелизм требует увеличения
server slots (иной фактор, вне этой серии).

## Ответы на контрольные вопросы

1. Client concurrency ≠ GPU batch ≠ число server slots.
2. Рост req/s с очередью ухудшает пользовательскую задержку — здесь именно рост latency.
3. Короткие отказы и отсутствующий usage искажают throughput; здесь ошибок/неизвестного usage нет.
4. При 12 запросах p95 ≈ max — информации мало.
5. Non-streaming драйвер не даёт TTFT/decode-only.
6. Prefix cache и thermal state влияют на переносимость.
7. Wh/request и tokens/s не отвечают о стоимости успешной агентной задачи.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, все raw-директории driver, server log/props.
- [x] driver offline tests прошли; `npm run check` проходит.
- [x] swap-counter таблица: pswpin/pswpout Δ в страницах для каждой серии (см. «Ошибки и ограничения»).
