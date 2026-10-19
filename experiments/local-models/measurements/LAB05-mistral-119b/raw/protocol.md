# LAB05 — протокол context/tools (session mistral-119b)

Backend: Vulkan (HIP blocked в ЛР04). Модель: mistral-small-4-119b UD-Q4_K_M.

> **Ретроспективный протокол.** Записан 2026-10-15T13:31:23Z, после фактического
> выполнения (raw/progress.txt: 8K bench 13:02:59Z–13:04:30Z, последняя запись
> 32K в 13:25:13Z). Содержимое отражает то, что реально выполнялось в сессии
> (порядок, fill-probe, long/overflow/cancel, стоп-критерии), но фиксация
> случилась постфактум. Это **не** pre-registration в строгом смысле; см.
> `unavailable.protocol_recorded_at` в manifest.json.

План до запусков:

- Контексты 8192/16384/32768 проверяются последовательно, по одному серверу за раз.
- Константы: prebuilt llama.cpp b8407, `-ngl 999 -t 8 -b 512 -ub 256 -ctk f16
  -ctv f16 -fa 1 --jinja --no-context-shift -np 1`, server defaults, alias lab-model.
- Для каждого контекста: (1) fill-probe `llama-bench -p 0 -n 128 -d (CTX-128) -r 3`;
  (2) `llama-server`; (3) health/props/models; (4) chat/chat-stream/tool/tool-stream
  ×2; (5) offline allowlist; (6) long-вход через `/apply-template`+`/tokenize` ×2;
  (7) overflow + recovery; (8) cancel + recovery.
- Длинный вход ≤ CTX−4096, чтобы остался output reserve.
- Стоп-критерий: OOM, GPU reset, устойчивая подкачка, тихое обрезание. Более
  длинный контекст не запускается автоматически после неудачи предыдущего.
- Отмена считается проверенной только если запрос реально не завершился за 1 с.
- Первый (cold) и повторный (warm/prefix-cache) запросы помечаются отдельно.
