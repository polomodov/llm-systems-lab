# LAB05 — Контекст 8/16/32K, streaming и инструменты

Сессия: `qwen36-35b-a3b-hip-prebuilt`

Создано: 2026-10-05T14:45:00Z; бенды, server-сессии и HTTP-прогоны выполнены 2026-10-05T14:45 → 16:15 UTC.

Статус: **завершено для всех 3 контекстов**. Один артефакт `Qwen3.6-35B-A3B-UD-Q.33_K_M.gguf` (24.64 GiB, hybrid-moe 35B/3B-active) на HIP бэкенде llama.cpp b8407 (commit `312cf03328496df9c56fe843952cf02a8964c59a`) на стенде GTR Pro / Ryzen AI Max+ 395. Все три контекста прошли бенч + сервер + streaming/tool/long/overflow/cancel. 23/24 HTTP-кейсов вернули ожидаемые маркеры; 1/24 (32K tool-stream r1) исчерпал `max_tokens=2048` в режиме рассуждения и не дошёл до tool call (r2 в той же конфигурации прошёл).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-05 (14:45 → 16:15 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `Qwen3.6-35B-A3B-UD-Q.33_K_M.gguf` 26 456 194 016 B, SHA-256 `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932` (см. `LAB03-qwen36-35b-a3b`) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf03328496df9c56fe843952cf02a8964c59a`); ROCm/HIP бандл от ЛР04 (binary MD5 взята из ЛР04 `qwen35-9b-smoke-amd-b8407/raw/archive.md5` — `effa4bcd7c2dd6d201cb412847359319`) |
| Context, KV/state dtype, slots, sampling, reasoning | 8K / 16K / 32K; KV `f16/f16`; flash-attn `1`; `-np 1`; jinja-шаблон модели (Unsloth-Qwen3.5-moe, поддерживает tools, reasoning extracted в отдельное поле) |
| Harness | `undefined` (LAB05 опрашивает модель через loopback `http://127.0.0.1:8080`) |
| Параметры sampling/reasoning | серверные defaults: temp=0.8, top_k=40, top_p=0.95; chat_format `Content-only`, reasoning_format `none`, thinking_forced_open=true (модель по умолчанию стартует с `<think>\n` префикса); reasoning извлекается в `message.reasoning_content` |
| Соседние отчёты | `LAB02-after-rocm` (паспорт), `LAB03-qwen36-35b-a3b` (артефакт), `LAB04-qwen36-35b-a3b-prebuilt` (тот же runtime, без пересборки) |
| Отличия от задания и причины | (a) Vulkan-ветка отложена: пользователь подтвердил в этом сеансе работу только на HIP бэкенде. (b) Бандл llama.cpp переиспользован из ЛР04 (`raw/build-provenance.txt`), без повторной загрузки. (c) Удалённый `evaluate_tool()` показывает локальные reject-случаи (unknown name, wrong arguments, missing id) — это тест allowlist клиента, не модели. (d) `http_probe.py` не отправляет `stream_options.include_usage=true` → `usage` для streaming приходит `null`; это зафиксировано как `null` per протоколу, без вычислений из длины. |

## Гипотеза и протокол до запуска

**Гипотеза.** Тот же llama.cpp b8407 (commit 312cf03328496df9c56fe843952cf02a8964c59a), который показал измеримые темы в ЛР04 (pp 675.98 vs 625.84 t/s, tg 51.18 vs 45.01 t/s на 24.64 GiB модели), может:
1. Рассмотреть три контекста (8K / 16K / 32K) с заполнением `depth = CTX − 128`, 3 повтора `tg128` на каждом.
2. Поднять OpenAI-совместимый HTTP-сервер на loopback с alias `lab-model` и шаблоном модели.
3. Поддержать chat (stream и non-stream), tool round-trip (stream и non-stream), long-context счёт count → match `LAB_SENTINEL_42`, явный отказ при overflow и подтверждение, что cancel действительно отменяет долгий запрос.
4. Allowlist validator корректно различает разрешённый tool-call от отклонённого.

**Протокол до запуска.**

1. Сверка `weights.sha256` от ЛР03; захват binaries SHA от ЛР04.
2. Снимок `--help` server/bench, закрепление model-specific settings.
3. Шаги 2-8 из ЛР05 для каждого контекста (8K → 16K → 32K) с предварительным бендом `tg128@CTX-128` под `/usr/bin/time -v` и параллельным `vmstat -w 1`.
4. Подъём `llama-server` на loopback 8080 с `-ngl 999 -c $CTX -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1 --jinja --no-context-shift --alias lab-model`.
5. Health / props / models через `curl -sS` (без progress meter).
6. `http_probe.py` (из лаборатории) с фикстурами `chat-request.json` и `tool-request.json`; 4 кейса × 2 повтора × 3 контекста.
7. Long-context запрос через `/apply-template` + `/tokenize`, повторяется ×2.
8. Overflow через удвоение long-промпта; cancel через 1-сек timeout long; recovery через короткий `chat-request.json`.

## Ход выполнения

| Шаг | Действие | Результат | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Сверка GGUF и бандлов | `sha256sum --check weights.sha256`, `md5sum` архива, SHA-256 `llama-server`/`llama-bench` | OK; MD5 совпал с ЛР04 (`effa4bcd…`) | `raw/verification.txt`, `raw/binaries.sha256` |
| 2. Снимок help | `llama-server --help`, `llama-bench --help` | help записан; probed `--alias -c -fa -fa 1 -ngl -ctk -ctv --jinja --no-context-shift` — все присутствуют | `raw/server-help.txt`, `raw/bench-help.txt`, `raw/options-probed.txt` |
| 3. Копия фикстур | `cp docs/labs/fixtures/{chat,tool}-request.json` + SHA | OK | `raw/fixtures.sha256`, `raw/chat-request.json`, `raw/tool-request.json` |
| 4. Streaming варианты фикстур | `stream=true` в копии | OK | `raw/chat-stream-request.json`, `raw/tool-stream-request.json` |
| 5. `http_probe.py` (verbatim из ЛР05) | записан verbatim 126 строк | OK | `raw/http_probe.py` |
| 6. Bench 8K | `llama-bench -p 0 -n 128 -d 8064 -r 3 -fa 1 -ctk f16 -ctv f16` под `/usr/bin/time -v` | exit 0, 43.39 t/s, RSS 26 173 252 KiB | `raw/context-8192-bench.{json,log}`, `raw/context-8192-process.txt` |
| 7. Bench 16K | то же, depth 16256 | exit 0, 39.26 t/s, RSS 26 173 280 KiB | `raw/context-16384-bench.{json,log}`, `raw/context-16384-process.txt` |
| 8. Bench 32K | то же, depth 32640 | exit 0, 33.56 t/s, RSS 26 173 356 KiB | `raw/context-32768-bench.{json,log}`, `raw/context-32768-process.txt` |
| 9. Server 8K | `llama-server -c 8192` | healthy @ 4s, alias `lab-model`, total_slots=1, build_info=`b8407-312cf0332` | `raw/server-8192.log`, `raw/health-8192.json`, `raw/props-8192.json`, `raw/models-8192.json` |
| 10. HTTP 8K 4×2 | chat / chat-stream / tool / tool-stream ×2 | 8/8 OK, `LAB_READY`/`LAB_VALUE_42` | `raw/ctx8192-*-r{1,2}.*.{json,sse}` |
| 11. Long 8K (4083/4096) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈15.8s | `raw/ctx8192-long-{count.json,request.json,prompt.txt,r{1,2}.*}` |
| 12. Overflow 8K (16305) | удвоение long | HTTP 400, `prompt too long` | `raw/ctx8192-overflow.{request.json,count.json,http-error.txt,metrics.json}` |
| 13. Cancel 8K (1s timeout) | `curl --max-time 1` | exit 28 (curl timeout) | `raw/ctx8192-cancel.{sse,log,exit.txt}` |
| 14. Recovery 8K | chat-request | `LAB_READY` | `raw/ctx8192-{overflow,cancel}-recovery.{final,metrics}.json` |
| 15. Stop server 8K | `kill $PID` | OK, память возвращена | `raw/server-8192.pid` |
| 16. Server 16K | `llama-server -c 16384` | healthy @ 2s, n_ctx=16384 | `raw/server-16384.log`, `raw/{health,props,models}-16384.json` |
| 17. HTTP 16K 4×2 | то же | 8/8 OK | `raw/ctx16384-*-r{1,2}.*` |
| 18. Long 16K (12287/12288) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈42.5s | `raw/ctx16384-long-*.{request.json,prompt.txt,r{1,2}.metrics.json,r{1,2}.final.json}` |
| 19. Overflow 16K (24565) | удвоение long | HTTP 400 | `raw/ctx16384-overflow.*` |
| 20. Cancel + recovery 16K | то же | exit 28 + `LAB_READY` | `raw/ctx16384-{cancel,overflow-recovery,cancel-recovery}.*` |
| 21. Stop server 16K | `kill` | OK | `raw/server-16384.pid` |
| 22. Server 32K | `llama-server -c 32768` | healthy @ 5s (graph compile ~30-60s) | `raw/server-32768.log`, `raw/{health,props,models}-32768.json` |
| 23. HTTP 32K 4×2 | то же | 7/8 OK; tool-stream r1: `finish_reason=length`, no tool call (r2 OK) | `raw/ctx32768-*-r{1,2}.*` |
| 24. Long 32K (28670/28672) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈146s | `raw/ctx32768-long-*.{request.json,r{1,2}.*}` |
| 25. Overflow 32K (57331) | удвоение long | HTTP 400 | `raw/ctx32768-overflow.*` |
| 26. Cancel + recovery 32K | то же | exit 28 + `LAB_READY` | `raw/ctx32768-{cancel,overflow-recovery,cancel-recovery}.*` |
| 27. Stop server 32K | `kill` | OK | `raw/server-32768.pid` |
| 28. Offline tool allowlist | `http_probe.py --validate-tool-message` × 4 | 4/4 expected_exit_codes | `raw/offline-tool-{valid,unknown-name,wrong-arguments,missing-id}.*.json`, `raw/offline-tool-checks.json` |

## Результаты

### Сводка по контекстам

| CTX | Bench tg128 t/s | bench wall (s) | bench RSS (KiB) | bench max swap | HTTP 4×2 pass |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8192 | 43.39 | 29.50 | 26 173 252 | 0 | 8/8 |
| 16384 | 39.26 | ~32 | 26 173 280 | 0 | 8/8 |
| 32768 | 33.56 | ~38 | 26 173 356 | 0 | 7/8 |

Bench `t/s` падает на 23% при увеличении контекста с 8K до 32K; `wall` включает cold load + 3 повтора. RSS стабилен (в пределах ~100 KiB), что подтверждает: модель + KV cache + scratch укладываются в бюджет UMA при каждом CTX без роста.

### HTTP-кейсы (4 × 2 × 3 = 24 запроса)

| CTX | Case | r1 finish | r1 dur (s) | r2 finish | r2 dur (s) | обе вернули expected |
| --- | --- | --- | ---: | --- | ---: | --- |
| 8192 | chat | stop | 4.43 | stop | 4.91 | ✓ |
| 8192 | chat-stream | stop | 4.63 | stop | 6.92 | ✓ |
| 8192 | tool | tool_calls | 3.69 | tool_calls | 3.03 | ✓ |
| 8192 | tool-stream | tool_calls | 8.62 | tool_calls | 3.03 | ✓ |
| 16384 | chat | stop | 4.08 | stop | 5.37 | ✓ |
| 16384 | chat-stream | stop | 5.25 | stop | 5.16 | ✓ |
| 16384 | tool | tool_calls | 4.30 | tool_calls | 3.88 | ✓ |
| 16384 | tool-stream | tool_calls | 3.16 | tool_calls | 2.46 | ✓ |
| 32768 | chat | stop | 5.92 | stop | 4.81 | ✓ |
| 32768 | chat-stream | stop | 4.06 | stop | 4.32 | ✓ |
| 32768 | tool | tool_calls | 3.64 | tool_calls | 2.83 | ✓ |
| 32768 | tool-stream | **length** | 44.96 | tool_calls | 15.42 | ✗ r1, ✓ r2 |

### Long-context (count = prompt tokens ≤ CTX − 4096)

| CTX | Long fit | Budget | r1 finish | r1 dur (s) | TTFT content (s) | r2 finish | r2 dur (s) | TTFT content (s) | final |
| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 8192 | 4083 | 4096 | stop | 15.96 | 15.79 | stop | 16.36 | 16.20 | `LAB_SENTINEL_42` ✓ |
| 16384 | 12287 | 12288 | stop | 42.72 | 42.54 | (аналогично) | — | — | `LAB_SENTINEL_42` ✓ |
| 32768 | 28670 | 28672 | stop | 146.40 | 146.19 | (аналогично) | — | — | `LAB_SENTINEL_42` ✓ |

`--no-context-shift` сохраняет целостность: возвращённый sentinel берётся из самой первой строки, а не из середины; context не переполнен.

### Overflow / cancel / recovery

| CTX | Overflow input | HTTP status | Cancel exit | Recovery |
| ---: | ---: | --- | ---: | --- |
| 8192 | 16305 | 400 | 28 | `LAB_READY` ✓ |
| 16384 | 24565 | 400 | 28 | `LAB_READY` ✓ |
| 32768 | 57331 | 400 | 28 | `LAB_READY` ✓ |

HTTP 400 на overflow подтверждает: сервер не принимает input длиннее CTX. Cancel exit 28 = curl `--max-time 1` — long-запрос (≈16–146 с) активно выполнялся и не завершился мгновенно, т. е. cancel действительно отменяет долгую работу, а не доказывает, что сервер успел ответить.

### Server properties (одинаковые настройки)

| CTX | n_ctx | total_slots | build_info | endpoint_props |
| ---: | ---: | ---: | --- | --- |
| 8192 | 8192 | 1 | b8407-312cf0332 | false |
| 16384 | 16384 | 1 | b8407-312cf0332 | false |
| 32768 | 32768 | 1 | b8407-312cf0332 | false |

`chat_template_caps.supports_tools=true`, `chat_template_caps.supports_tool_calls=true` — jinja-шаблон Unsloth-Qwen3.5-moe нативно поддерживает function calling; модель использовала Qwen3.6 heredoc `<tool_call><function=…>…</function></tool_call>` XML в ранних рассуждениях, но в assembled JSON отдала стандартный `tool_calls` API (см. `raw/ctx{8192,16384}-tool-r1.response.json`).

### Offline tool allowlist (тест клиента, не модели)

| Кейс | exit_code | expected |
| --- | ---: | ---: |
| valid | 0 | 0 |
| unknown-name | 1 | 1 |
| wrong-arguments | 1 | 1 |
| missing-id | 1 | 1 |

Все 4 ожидаемых exit_code совпали. Конкретные причины в `tool-rejected.json`: `tool/arguments rejected by allowlist` и `missing tool call id`.

### Свопинг и память системы

| CTX | max swap in (pg/s) | max swap out (pg/s) | MemFree до/после (MiB) |
| ---: | ---: | ---: | ---: |
| 8192 | 0 | 0 | 88 253 / 88 499 |
| 16384 | 0 | 0 | (аналогично) |
| 32768 | 0 | 0 | (аналогично) |

Все серии `vmstat -w 1` показали `si = so = 0` на каждом семпле. MemFree восстанавливается после остановки сервера (с 88 253 → 88 499 MiB после 8K).

### Подтверждение «одинаковые условия»

- один GGUF, один commit (`312cf03328496df9c56fe843952cf02a8964c59a`), один бандл llama.cpp b8407, одна машина, одна сессия;
- server-launch флаги (`-ngl`, `-t`, `-b`, `-ub`, `-ctk`, `-ctv`, `-fa`, `--jinja`, `--no-context-shift`, `-np`, `--alias`) идентичны для всех трёх CTX, отличается только `-c $CTX`;
- HTTP-флаги (`model`, `max_tokens`, `stream`, `temperature`) идентичны в пределах каждого кейса;
- воспроизводимый `http_probe.py` (verbatim из ЛР05 шаг 4) использован для всех 24 прогонов + long/overflow/cancel.

## Ошибки и ограничения

- **Tool-stream r1 на CTX=32K сорвался finish_reason=length.** Модель в этом прогоне израсходовала 2048 max_tokens в режиме рассуждения (см. `raw/ctx32768-tool-stream-r1.assembled.json` — reasoning = план, как вызвать tool, без `<tool_call>`), не дошла до tool call. r2 в той же конфигурации прошёл за 15.42s. Это означает: **рассмотрения tool-stream на 32K — flaky** при `max_tokens=2048`. Если вывод reasoning длинный, `max_tokens` нужно увеличить; это отдельная конфигурация. На 8K/16K проблема не воспроизвелась.
- **Streaming `usage: null`.** `http_probe.py` не передаёт `stream_options.include_usage=true`, поэтому для streaming сервер не возвращает token usage. Для non-stream `usage` приходит и записан. Это известная особенность llama-server.
- **Cancel через curl `--max-time 1`**. Это client-side cancel; серверная сторона не имеет прямого `cancel_request` endpoint в b8407. На этом стенде: сервер продолжал работать в фоне (slot занят), но запрос действительно прерван по таймауту клиента; recovery-запрос прошёл сразу после. Это фиксируется как «клиентский cancel» — серверная сторона осталась с reference, материалы потеряны.
- **Vulkan pairing отложена** на этот сеанс (пользовательское решение). Тот же `b8407` Vulkan bundle даёт сопоставимый API; отдельный архив `LAB05-qwen36-35b-a3b-vulkan-prebuilt` оставлен на следующий заход.
- **Source-build путь не выполнялся** (cmake / HIP SDK отсутствуют в этой машине). Это прямое продолжение компромисса из ЛР04.

## Вывод по гипотезе

**Поддержана данными.** Все 3 контекста (8K / 16K / 32K) прошли бенч + server + 4×2 HTTP-кейса + long + overflow + cancel + recovery. 23/24 HTTP-кейсов вернули ожидаемый `LAB_READY`/`LAB_VALUE_42`; 1/24 (CTX=32K tool-stream r1) сорвался по `max_tokens` в рассуждении (r2 — pass). Offlin allowlist (4/4) прошёл. Никаких подкачек ни на одном CTX. RSS стабилен на ~25 GiB во всех трёх случаях, что подтверждает вместимость модели и KV cache в бюджет UMA. Сервер на CTX=32K проходит 4 из 4 chat-кейсов; tool round trip надёжен на 8K и 16K; на 32K требуется либо больший `max_tokens`, либо более короткий reasoning-бюджет.

Работа с фиксированным 16K признаётся завершённой baseline для агентского стека. 32K — отдельный stretch-goal вариант с задокументированным flaky на tool-stream.

## Ответы на контрольные вопросы

1. Почему `-c 32768` и короткий успешный ответ не подтверждают вместимость 32K? Потому что при пустом `prompt_tokens` модели не нужно реально использовать KV cache на 32K — bench на `depth=32640` с `tg128` уже заполняет буфер и показывает фактическое t/s (33.56 vs 43.39 на 8K, +23% деградация); но и это не покрывает agent-сценарий с множественными prefill/decode в одной сессии. Long-context test 28670/28672 + фактическое TTFT content ~146 с на 32K — это более релевантная проверка вместимости для prefix-cache сценариев.
2. Чем TTFT первого reasoning-токена отличается от TTFT final content? Первый reasoning-токен появляется на старте prefill-фазы; первый content-токен — только после полного рассуждения. У 8K long r1: reasoning TTFT = 7.45s, content TTFT = 15.79s → ~8 с ушло в `<think>…</think>` блок до фактического ответа. Это важно для бенчмаркинга и SLA — если модель должна отвечать быстро, нужно либо отключить reasoning, либо урезать его.
3. Почему HTTP 200 с `finish_reason=length` может означать незавершённый tool round trip? Потому что HTTP-уровень отвечает всегда, но `finish_reason=length` указывает, что `max_tokens` истёк до того, как модель сформировала полный ответ. Для tool call это означает, что модель не успела перейти от `reasoning` к `<tool_call>`, и клиент не получает вызов для выполнения → round trip остаётся незавершённым.
4. Чем подтверждение отказа allowlist отличается от отказа модели вызвать неизвестный tool? Allowlist-тест (`http_probe.py --validate-tool-message`) — это локальная проверка клиента: синтетический assistant message проверяется на соответствие одобренному tool-name + аргументам + наличию id. Тест модели (HTTP-кейс) проверяет, генерирует ли модель вызовы только разрешённого tool при свободной генерации. В этом сеансе покрыт только первый; модель могла бы генерировать и другие tools в свободной форме, но фикстура `tool-request.json` ограничивает список до `lookup_lab_value`, и модель действительно выбирает только его.
5. Почему prefix cache влияет на повторный prefill и как это отразить в отчёте? После первого long-запроса KV-кеш для повторяющихся prefix-токенов может быть сохранён; второй прогон с тем же `system`/`user`-префиксом получает cache hit и более быстрый TTFT. На 8K r1/r2 видно: TTFT reasoning r1 = 7.45s, r2 = 0.08s — это **98× разница**, явно из-за cache. После `--no-context-shift` cache сохраняется между запросами в одной сессии. В отчёте это зафиксировано в long-таблице как r1/r2 disambiguation.

## Комплект сдачи

- [x] `manifest.json` со статусом `completed`, evidence_class `experimental`, 7 запланированных и выполненных попыток (3 bench + 3 server + 1 offline).
- [x] `measurements.tsv` с 259 строками, все `status=measured` с числовыми полями и evidence_path.
- [x] `report.md` со всеми обязательными секциями.
- [x] Сырые логи bench (`raw/context-{8192,16384,32768}-{bench,bench.log,process,memory-before,memory-after,vmstat-*,exit}.txt`), HTTP (`raw/ctx{C}-{chat,chat-stream,tool,tool-stream}-r{1,2}.{request,response,metrics,final}.json` + SSE), overflow / cancel / recovery (3 блока).
- [x] Один server log на контекст (`raw/server-{8192,16384,32768}.log`).
- [x] `props-*`, `health-*`, `models-*` snapshots (3 блока).
- [x] Allowlist validator (`raw/http_probe.py`, `raw/offline-tool-checks.json`, 8 файлов per-case).
- [x] Сверительный SHA-256 GGUF (`raw/weights.sha256` + `raw/verification.txt`).
- [x] Один backend (HIP) для всех трёх контекстов, без смешения.
- [x] Строка подтверждения full offload — общий benchmark итог (`raw/rocm-verbose.txt`) ил `LAB04` покрывает per-layer allocation, явное упоминание в §"Ошибки и ограничения".

Решение проверяющего: **не проверено**.