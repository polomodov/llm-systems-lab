# LAB26 — протокол до запуска (ryzen-qwen35-9b)

## Deployment
- Модель qwen35-9b (Qwen3.5-9B Q6_K, unsloth@3885219b…, SHA-256 91898433…).
- Server: llama.cpp b8407 HIP/ROCm (312cf0332), gfx1151; `-ngl 999 -c 8192 -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on --jinja --reasoning off --no-cache-prompt --slots`, host 127.0.0.1:8080, alias qwen35-9b.
- Один слот; client concurrency 1/2/4 → очередь сервера (не увеличиваем slots).
- Reasoning off, чтобы финальный текст не обрезался бюджетом (load probe, не оценка качества). sampling — server defaults; prefix cache off.

## План и границы
- Прогрев: 2 запроса при concurrency 1.
- Серии: 1→2→4 по 12 запросов, timeout 120 s.
- Границы приемлемости: доля HTTP/protocol errors ≤ 0; swap не растёт; MemAvailable остаётся > 8 GiB.
- Один request (`raw/load-request.json`), max_tokens 512, stream false.

## Критерий остановки
OOM/потеря readiness/swap → ступень blocked, дальнейшие не запускать.
