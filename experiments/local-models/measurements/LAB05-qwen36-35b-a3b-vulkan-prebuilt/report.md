# LAB05 — Контекст 8/16/32K, streaming и инструменты (Vulkan pairing)

Сессия: `qwen36-35b-a3b-vulkan-prebuilt`

Создано: 2026-10-07T09:19:25.260Z; бенды, server-сессии и HTTP-прогоны выполнены 2026-10-07T09:19 → 09:41 UTC.

Статус: **завершено для всех 3 контекстов на Vulkan/RADV**. Один артефакт `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` (24.64 GiB, hybrid-moe 35B/3B-active) на Vulkan бэкенде llama.cpp b8407 (commit `312cf03328496df9c56fe843952cf02a8964c59a`) на стенде GTR Pro / Ryzen AI Max+ 395. Все три контекста прошли бенч + сервер + streaming/tool/long/overflow/cancel. **24/24** HTTP-кейсов вернули ожидаемые маркеры (против 23/24 в HIP-сессии, где 32K tool-stream r1 исчерпал `max_tokens=2048` в рассуждении).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-07 (09:19 → 09:41 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` 26 456 194 016 B, SHA-256 `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932` (см. `LAB03-qwen36-35b-a3b`) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf03328496df9c56fe843952cf02a8964c59a`); Vulkan/RADV бандл от ЛР04 (llama-server SHA-256 `9f6bc8e8…`, llama-bench `7800ad09…`, см. `raw/binaries.sha256`) |
| Context, KV/state dtype, slots, sampling, reasoning | 8K / 16K / 32K; KV `f16/f16`; flash-attn `1` (см. примечание ниже); `-np 1`; jinja-шаблон модели (Unsloth-Qwen3.5-moe, supports tools, reasoning extracted в `reasoning_content`) |
| Harness | нет (LAB05 опрашивает модель через loopback `http://127.0.0.1:8080`) |
| Параметры sampling/reasoning | серверные defaults (top_k=20, top_p=0.95, temp=1.00 из GGUF metadata); chat_format `Content-only`, reasoning_format `none`; reasoning извлекается в `message.reasoning_content` |
| Соседние отчёты | `LAB02-after-rocm` (паспорт), `LAB03-qwen36-35b-a3b` (артефакт), `LAB04-qwen36-35b-a3b-prebuilt` (тот же runtime, Vulkan-ветвь), `LAB05-qwen36-35b-a3b-hip-prebuilt` (парная HIP-сессия) |
| Отличия от задания и причины | (a) Это Vulkan-pairing отложенной в HIP-сессии ветви: тот же протокол на Vulkan/RADV бандле из ЛР04, без пересборки. (b) Бандл llama.cpp переиспользован из ЛР04 (`raw/build-provenance.txt`). (c) Для flash attention на Vulkan использован `-fa 1`, а не `-fa on`: `-fa on` парсится как `false` на Vulkan b8407 (см. «Ошибки и ограничения»). (d) `http_probe.py` не отправляет `stream_options.include_usage=true` → `usage` для streaming приходит `null`; зафиксировано как отсутствие usage, без вычислений из длины. |

## Гипотеза и протокол до запуска

**Гипотеза.** Тот же llama.cpp b8407 (commit 312cf03328496df9c56fe843952cf02a8964c59a), который в ЛР04 показал на Vulkan/RADV измеримые темы (pp2048 675.98 t/s, tg128@4096 51.18 t/s, полный per-layer offload `Vulkan0`), способен:

1. Рассмотреть три контекста (8K / 16K / 32K) с заполнением `depth = CTX − 128`, 3 повтора `tg128` на каждом.
2. Поднять OpenAI-совместимый HTTP-сервер на loopback с alias `lab-model` и шаблоном модели.
3. Поддержать chat (stream и non-stream), tool round-trip (stream и non-stream), long-context счёт count → match `LAB_SENTINEL_42`, явный отказ при overflow и подтверждение, что cancel отменяет долгий запрос.
4. Allowlist validator корректно различает разрешённый tool-call от отклонённого.

**Протокол до запуска.**

1. Сверка `weights.sha256` от ЛР03; захват binaries SHA от ЛР04 (Vulkan-ветвь).
2. Снимок `--help` server/bench, `--version`, `--list-devices`, закрепление model-specific settings.
3. Шаги 2-8 из ЛР05 для каждого контекста (8K → 16K → 32K) с предварительным бендом `tg128@CTX-128` под `/usr/bin/time -v` и параллельным `vmstat -w 1`.
4. Подъём `llama-server` на loopback 8080 с `-ngl 999 -c $CTX -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1 --jinja --no-context-shift --alias lab-model` (для Vulkan `-fa 1` включает flash attention; `-fa on` — нет).
5. Health / props / models через `curl`.
6. `http_probe.py` (verbatim из ЛР05) с фикстурами `chat-request.json` и `tool-request.json`; 4 кейса × 2 повтора × 3 контекста.
7. Long-context запрос через `/apply-template` + `/tokenize`, повторяется ×2.
8. Overflow через удвоение long-промпта; cancel через 1-сек timeout long; recovery через короткий `chat-request.json`.
9. Offline allowlist на синтетических ответах (без endpoint).

## Ход выполнения

| Шаг | Действие | Результат | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Сверка GGUF и бандлов | `sha256sum --check weights.sha256`, SHA-256 `llama-server`/`llama-bench` Vulkan | OK; SHA совпал с ЛР04 (`9f6bc8e8…`, `7800ad09…`) | `raw/verification.txt`, `raw/binaries.sha256` |
| 2. Снимок help/version/devices | `llama-server --help`, `--version`, `--list-devices` | help записан; version `8407 (312cf0332)`, GNU 11.4.0; `Found 1 Vulkan devices: AMD Radeon Graphics (RADV GFX1151)` | `raw/server-help.txt`, `raw/vulkan-version.txt`, `raw/vulkan-devices.txt`, `raw/options-probed.txt` |
| 3. Копия фикстур | `cp docs/labs/fixtures/{chat,tool}-request.json` + SHA | OK; SHA совпал с HIP-сессией | `raw/fixtures.sha256`, `raw/chat-request.json`, `raw/tool-request.json` |
| 4. Streaming варианты фикстур | `stream=true` в копии | OK | `raw/chat-stream-request.json`, `raw/tool-stream-request.json` |
| 5. `http_probe.py` (verbatim) | SHA совпал с HIP-сессией (`37182a66…`) | OK | `raw/http_probe.py` |
| 6. Bench 8K | `llama-bench -fa 1 -p 0 -n 128 -d 8064 -r 3` под `/usr/bin/time -v` | exit 0, 50.62 t/s, RSS 26 021 048 KiB | `raw/context-8192-bench.{json,log,process.txt}` |
| 7. Bench 16K | то же, depth 16256 | exit 0, 48.79 t/s, RSS 26 021 192 KiB | `raw/context-16384-bench.{json,log,process.txt}` |
| 8. Bench 32K | то же, depth 32640 | exit 0, 45.03 t/s, RSS 26 020 980 KiB | `raw/context-32768-bench.{json,log,process.txt}` |
| 9. Server 8K | `llama-server -c 8192 -fa 1` | healthy @ 5s, alias `lab-model`, n_ctx=8192, slots=1, `flash_attn=enabled`, device `Vulkan0` | `raw/server-8192.log`, `raw/{health,props,models}-8192.json` |
| 10. HTTP 8K 4×2 | chat / chat-stream / tool / tool-stream ×2 | 8/8 OK, `LAB_READY`/`LAB_VALUE_42` | `raw/ctx8192-*-r{1,2}.*.{json,sse}` |
| 11. Long 8K (4083/4096) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈11.7s | `raw/ctx8192-long-*` |
| 12. Overflow 8K (16305) | удвоение long | HTTP 400, `exceed_context_size_error` | `raw/ctx8192-overflow.*` |
| 13. Cancel 8K (1s timeout) | `curl --max-time 1` | exit 28 (curl timeout) | `raw/ctx8192-cancel.*` |
| 14. Recovery 8K | chat-request | `LAB_READY` | `raw/ctx8192-{overflow,cancel}-recovery.*` |
| 15. Stop server 8K | `kill $PID` | OK, память возвращена | `raw/server-8192.pid` |
| 16. Server 16K | `llama-server -c 16384 -fa 1` | healthy @ 6s, n_ctx=16384 | `raw/server-16384.log`, `raw/{health,props,models}-16384.json` |
| 17. HTTP 16K 4×2 | то же | 8/8 OK | `raw/ctx16384-*-r{1,2}.*` |
| 18. Long 16K (12287/12288) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈23.7s | `raw/ctx16384-long-*` |
| 19. Overflow 16K (24565) | удвоение long | HTTP 400 | `raw/ctx16384-overflow.*` |
| 20. Cancel + recovery 16K | то же | exit 28 + `LAB_READY` | `raw/ctx16384-{cancel,overflow-recovery,cancel-recovery}.*` |
| 21. Stop server 16K | `kill` | OK | `raw/server-16384.pid` |
| 22. Server 32K | `llama-server -c 32768 -fa 1` | healthy @ 6s, n_ctx=32768 | `raw/server-32768.log`, `raw/{health,props,models}-32768.json` |
| 23. HTTP 32K 4×2 | то же | **8/8 OK**, включая оба tool-stream повтора | `raw/ctx32768-*-r{1,2}.*` |
| 24. Long 32K (28670/28672) | генератор + 2 прогона | 2/2 OK, `LAB_SENTINEL_42`, TTFT content ≈53.0s | `raw/ctx32768-long-*` |
| 25. Overflow 32K (57331) | удвоение long | HTTP 400 | `raw/ctx32768-overflow.*` |
| 26. Cancel + recovery 32K | то же | exit 28 + `LAB_READY` | `raw/ctx32768-{cancel,overflow-recovery,cancel-recovery}.*` |
| 27. Stop server 32K | `kill` | OK | `raw/server-32768.pid` |
| 28. Offline tool allowlist | `http_probe.py --validate-tool-message` × 4 | 4/4 expected_exit_codes | `raw/offline-tool-*`, `raw/offline-tool-checks.json` |

## Результаты

### Сводка по контекстам (Vulkan vs HIP)

| CTX | Bench tg128 t/s (Vulkan) | Bench tg128 t/s (HIP) | Δ Vulkan/HIP | bench wall (s) | bench RSS (KiB) | swap | HTTP 4×2 pass |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8192 | 50.62 | 43.39 | +16.6% | 24.26 | 26 021 048 | 0 | 8/8 |
| 16384 | 48.79 | 39.26 | +24.3% | 36.35 | 26 021 192 | 0 | 8/8 |
| 32768 | 45.03 | 33.56 | +34.2% | 66.80 | 26 020 980 | 0 | 8/8 |

Bench `t/s` падает на 11% при увеличении контекста с 8K до 32K на Vulkan (против 23% на HIP). RSS стабилен (в пределах ~200 KiB), что подтверждает: модель + KV cache + scratch укладываются в бюджет UMA при каждом CTX без роста. Vulkan-бандл потребляет ~150 MiB меньше RSS, чем HIP (~24.81 GiB vs ~24.96 GiB) — на уровне шума, но стабильно.

### HTTP-кейсы (4 × 2 × 3 = 24 запроса, все успешны)

| CTX | Case | r1 finish | r1 dur (s) | r2 finish | r2 dur (s) | обе вернули expected |
| --- | --- | --- | ---: | --- | ---: | --- |
| 8192 | chat | stop | 4.23 | stop | 5.46 | ✓ |
| 8192 | chat-stream | stop | 5.35 | stop | 6.29 | ✓ |
| 8192 | tool | tool_calls | 3.70 | tool_calls | 2.87 | ✓ |
| 8192 | tool-stream | tool_calls | 2.42 | tool_calls | 2.13 | ✓ |
| 16384 | chat | stop | 4.02 | stop | 5.17 | ✓ |
| 16384 | chat-stream | stop | 4.11 | stop | 3.89 | ✓ |
| 16384 | tool | tool_calls | 3.09 | tool_calls | 2.10 | ✓ |
| 16384 | tool-stream | tool_calls | 4.00 | tool_calls | 3.01 | ✓ |
| 32768 | chat | stop | 4.48 | stop | 4.12 | ✓ |
| 32768 | chat-stream | stop | 3.84 | stop | 4.07 | ✓ |
| 32768 | tool | tool_calls | 3.17 | tool_calls | 1.84 | ✓ |
| 32768 | tool-stream | tool_calls | 2.35 | tool_calls | 2.48 | ✓ |

В отличие от HIP-сессии, где 32K tool-stream r1 сорвался по `finish_reason=length` (модель израсходовала `max_tokens=2048` в рассуждении и не дошла до tool call), на Vulkan оба повтора tool-stream на 32K прошли. Reasoning на Vulkan в этих прогонах оказался короче и не исчерпал output-бюджет.

### Long-context (count = prompt tokens ≤ CTX − 4096)

| CTX | Long fit | Budget | r1 finish | r1 dur (s) | TTFT content (s) | TTFT reasoning (s) | r2 TTFT content (s) | final |
| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| 8192 | 4083 | 4096 | stop | 11.83 | 11.69 | 5.76 | 6.68 | `LAB_SENTINEL_42` ✓ |
| 16384 | 12287 | 12288 | stop | 23.86 | 23.72 | 18.27 | 6.99 | `LAB_SENTINEL_42` ✓ |
| 32768 | 28670 | 28672 | stop | 53.13 | 52.98 | 46.64 | 5.76 | `LAB_SENTINEL_42` ✓ |

`--no-context-shift` сохраняет целостность: sentinel берётся из первой строки, контекст не переполнен. Long prefill на Vulkan заметно быстрее HIP: 32K TTFT content 52.98s против ~146s (HIP) — ≈2.8×. Prefix cache виден на r2 (ttft_reasoning падает с 46.64s до 0.10s на 32K).

### Overflow / cancel / recovery

| CTX | Overflow input | HTTP status | Cancel exit | Recovery |
| ---: | ---: | ---: | ---: | --- |
| 8192 | 16305 | 400 | 28 | `LAB_READY` ✓ |
| 16384 | 24565 | 400 | 28 | `LAB_READY` ✓ |
| 32768 | 57331 | 400 | 28 | `LAB_READY` ✓ |

HTTP 400 на overflow подтверждает: сервер не принимает input длиннее CTX (`request (N tokens) exceeds the available context size`), тихого обрезания нет. Cancel exit 28 = curl `--max-time 1` — long-запрос активно выполнялся и не завершился мгновенно.

### Server properties (одинаковые настройки)

| CTX | n_ctx | total_slots | build_info | alias |
| ---: | ---: | ---: | --- | --- |
| 8192 | 8192 | 1 | b8407-312cf0332 | lab-model |
| 16384 | 16384 | 1 | b8407-312cf0332 | lab-model |
| 32768 | 32768 | 1 | b8407-312cf0332 | lab-model |

`chat_template_caps.supports_tools=true`, `chat_template_caps.supports_tool_calls=true` — jinja-шаблон Unsloth-Qwen3.5-moe нативно поддерживает function calling; assembled JSON отдаёт стандартный `tool_calls` API, reasoning извлекается в `reasoning_content`.

### Offline tool allowlist (тест клиента, не модели)

| Кейс | exit_code | expected |
| --- | ---: | ---: |
| valid | 0 | 0 |
| unknown-name | 1 | 1 |
| wrong-arguments | 1 | 1 |
| missing-id | 1 | 1 |

Все 4 ожидаемых exit_code совпали. Конкретные причины в `tool-rejected.json`: `tool/arguments rejected by allowlist` и `missing tool call id`.

### Свопинг и память системы

| CTX | max swap in (pg/s) | max swap out (pg/s) |
| ---: | ---: | ---: |
| 8192 | 0 | 0 |
| 16384 | 0 | 0 |
| 32768 | 0 | 0 |

Все серии `vmstat -w 1` показали `si = so = 0` на каждом семпле.

### Подтверждение «одинаковые условия»

- один GGUF, один commit (`312cf03328496df9c56fe843952cf02a8964c59a`), один бандл llama.cpp b8407 (Vulkan/RADV), одна машина, одна сессия;
- server-launch флаги идентичны для всех трёх CTX, отличается только `-c $CTX`;
- HTTP-флаги (`model`, `max_tokens`, `stream`, `temperature`) идентичны в пределах каждого кейса;
- воспроизводимый `http_probe.py` (verbatim, SHA `37182a66…`) использован для всех 24 прогонов + long/overflow/cancel;
- flash attention включён во всех трёх контекстах через `-fa 1`.

## Ошибки и ограничения

- **`-fa on` не включает flash attention на Vulkan b8407.** Проверено контрольным прогоном: `-fa on` → `flash_attn: False`, `-fa 1` → `flash_attn: True`. Это различие CLI-парсинга (Vulkan-бэкенд), а не backend-возможности. Для сопоставимости с HIP (где flash_attn был включён) использован `-fa 1`. Зафиксировано в `raw/model-settings.txt` и здесь.
- **Streaming `usage: null`.** `http_probe.py` не передаёт `stream_options.include_usage=true`, поэтому для streaming сервер не возвращает token usage. Для non-stream `usage` приходит и записан. В `measurements.tsv` для streaming записан `usage_tokens_present=0`; значение никогда не выводится из длины текста.
- **Cancel через curl `--max-time 1`** — client-side cancel; серверной стороны нет прямого `cancel_request` endpoint в b8407. Сервер продолжал работать, запрос прерван по таймауту клиента; recovery-запрос прошёл сразу. Это «клиентский cancel».
- **Первый inference-запрос сервера.** Bench и сервер — разные процессы; модель загружается сервером заново. Первый HTTP-запрос на Vulkan не показал большой задержки pipeline-компиляции (chat-r1 8192 ≈4.2s), но первый long-запрос r1 содержит cold prefill (не пустой OS page cache). Первый и повторный запросы обозначены r1/r2 отдельно.
- **Vulkan flash-attn через RADV** — это Mesa RADV + `libggml-vulkan.so` upstream. Производительность long-prefill может зависеть от конкретного RADV; на этой машине других Vulkan-ICD нет.
- **Source-build путь не выполнялся** (cmake / HIP SDK отсутствуют). Прямое продолжение компромисса из ЛР04; бандл переиспользован.
- **Flaky tool-stream 32K (HIP) не воспроизвёлся на Vulkan.** На HIP 32K tool-stream r1 исчерпал `max_tokens=2048` в рассуждении. На Vulkan оба повтора прошли. Это наблюдение не доказывает, что Vulkan «лучше» — reasoning-длина стохастична; зафиксировано как отсутствие воспроизведения, а не как исправление.

## Вывод по гипотезе

**Поддержана данными.** Все 3 контекста (8K / 16K / 32K) прошли бенч + server + 4×2 HTTP-кейса + long + overflow + cancel + recovery на Vulkan/RADV. **24/24** HTTP-кейсов вернули ожидаемый `LAB_READY`/`LAB_VALUE_42` (против 23/24 в HIP). Offline allowlist 4/4. Никаких подкачек ни на одном CTX. RSS стабилен ~24.81 GiB. Flash attention включён (через `-fa 1`).

Backend-различие измерено и согласуется с ЛР04: Vulkan быстрее HIP на этой машине — bench tg128 +16.6% / +24.3% / +34.2% (8K/16K/32K), long-prefill 32K ≈2.8× быстрее (52.98s vs ~146s). Эффект не равен чистому backend-эффекту, потому что toolchain отличается (GNU 11.4 для Vulkan vs GNU 13.3 для ROCm), как зафиксировано в ЛР04.

Работа с фиксированным 16K признаётся завершённой baseline для агентского стека; 32K — отдельный stretch-goal, на Vulkan пройден без наблюдавшихся на HIP отклонений.

## Ответы на контрольные вопросы

1. **Почему `-c 32768` и короткий успешный ответ не подтверждают вместимость 32K?** Потому что при пустом `prompt_tokens` модели не нужно реально использовать KV cache на 32K. Bench на `depth=32640` с `tg128` заполняет буфер и показывает фактическое t/s (45.03 на 32K vs 50.62 на 8K, −11%). Long-context 28670/28672 + фактическое TTFT content ≈53s на 32K — более релевантная проверка вместимости.

2. **Чем TTFT первого reasoning-токена отличается от TTFT final content?** Первый reasoning-токен появляется на старте prefill; первый content-токен — только после полного рассуждения. На 8K long r1: reasoning TTFT = 5.76s, content TTFT = 11.69s → ~6s ушло в `<think>…</think>` до ответа. Для SLA это критично: если нужен быстрый ответ, reasoning надо урезать или отключить.

3. **Почему HTTP 200 с `finish_reason=length` может означать незавершённый tool round trip?** HTTP-уровень отвечает всегда, но `finish_reason=length` указывает, что `max_tokens` истёк до того, как модель сформировала полный ответ (или перешла от reasoning к `<tool_call>`). В HIP-сессии это дало незавершённый tool round trip на 32K tool-stream r1. На Vulkan в этой сессии не воспроизвелось (24/24).

4. **Чем подтверждение отказа allowlist отличается от отказа модели вызвать неизвестный tool?** Allowlist-тест (`--validate-tool-message`) — локальная проверка клиента: синтетический assistant message проверяется на имя/аргументы/id. Тест модели (HTTP-кейс) проверяет, генерирует ли модель вызовы только разрешённого tool. Здесь покрыт первый; фикстура `tool-request.json` ограничивает список до `lookup_lab_value`, и модель выбирает только его.

5. **Почему prefix cache влияет на повторный prefill и как это отразить в отчёте?** После первого long-запроса KV-кеш для повторяющихся prefix-токенов сохраняется; второй прогон получает cache hit и более быстрый TTFT. На 32K r1/r2: ttft_reasoning 46.64s → 0.10s (≈460×), явно из-за cache. В long-таблице r1/r2 разведены отдельно.

## Комплект сдачи

- [x] `manifest.json` со статусом `completed`, evidence_class `experimental`, 7 запланированных и выполненных попыток (3 bench + 3 server + 1 offline).
- [x] `measurements.tsv` с 263 строками, все `status=measured` с числовыми полями и evidence_path.
- [x] `report.md` со всеми обязательными секциями.
- [x] Сырые логи bench (`raw/context-{8192,16384,32768}-{bench,bench.log,process,memory-before,memory-after,vmstat-*,exit}.txt`), HTTP (`raw/ctx{C}-{chat,chat-stream,tool,tool-stream}-r{1,2}.{request,response,metrics,final}.json` + SSE), overflow / cancel / recovery (3 блока).
- [x] Один server log на контекст (`raw/server-{8192,16384,32768}.log`).
- [x] `props-*`, `health-*`, `models-*` snapshots (3 блока).
- [x] Allowlist validator (`raw/http_probe.py`, `raw/offline-tool-checks.json`, 8 файлов per-case).
- [x] Сверительный SHA-256 GGUF (`raw/weights.sha256` + `raw/verification.txt`).
- [x] Один backend (Vulkan/RADV) для всех трёх контекстов, без смешения с HIP.
- [x] Подтверждение full offload — device `Vulkan0 (AMD Radeon Graphics (RADV GFX1151))` в server log, `n_gpu_layers=999` и `flash_attn=true` в bench JSON.

Решение проверяющего: **не проверено**.
