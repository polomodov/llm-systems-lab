# LAB05 — Контекст 8/16/32K, streaming и инструменты (Qwen3.5-9B, HIP)

Сессия: `qwen35-9b-hip-prebuilt`

Создано: 2026-10-07T10:20:00Z; бенды, server-сессии и HTTP-прогоны выполнены 2026-10-07T10:20 → 11:00 UTC.

Статус: **завершено для всех 3 контекстов на ROCm/HIP**. Один артефакт `Qwen3.5-9B-Q6_K.gguf` (7.46 GiB, hybrid-dense 9B) на HIP бэкенде llama.cpp b8407 (commit `312cf03328496df9c56fe843952cf02a8964c59a`) на стенде GTR Pro / Ryzen AI Max+ 395. Все три контекста прошли бенч + сервер + streaming/tool/long/overflow/cancel. **24/24** HTTP-кейсов вернули ожидаемые маркеры; 1/2 long-повторов на 16K исчерпал `max_tokens=4096` в режиме рассуждения (reasoning loop) и не дошёл до final answer (r2 прошёл).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-07 (10:20 → 11:00 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `unsloth/Qwen3.5-9B-GGUF@3885219b6810b007914f3a7950a8d1b469d598a5`; GGUF `Qwen3.5-9B-Q6_K.gguf` 7 458 301 152 B, SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59` (см. `LAB03-qwen35-9b`) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf0332`); ROCm/HIP бандл от ЛР04 qwen35-9b (GNU 13.3.0), binary SHA в `raw/binaries.sha256` |
| Context, KV/state dtype, slots, sampling, reasoning | 8K / 16K / 32K; KV `f16/f16`; flash-attn `1`; `-np 1`; jinja-шаблон модели (Qwen3.5, supports tools) |
| Harness | нет (LAB05 опрашивает модель через loopback `http://127.0.0.1:8080`) |
| Параметры sampling/reasoning | серверные defaults; reasoning извлекается в `message.reasoning_content` |
| Соседние отчёты | `LAB02-after-rocm` (паспорт), `LAB03-qwen35-9b` (артефакт), `qwen35-9b-smoke-amd-b8407` (smoke), `LAB04-qwen35-9b-prebuilt` (бэкенды) |
| Отличия от задания и причины | (a) Использован пребилд ROCm/HIP бандл b8407 (переиспользован), а не source-build — в машине нет cmake/HIP SDK. (b) Flash attention задан через `-fa 1` (на HIP эквивалентно `-fa on`; для единообразия с Vulkan-парой). (c) `http_probe.py` не отправляет `stream_options.include_usage=true` → `usage` для streaming `null`. |

## Гипотеза и протокол до запуска

**Гипотеза.** Тот же llama.cpp b8407 (commit 312cf03328496df9c56fe843952cf02a8964c59a), который прошёл smoke для Qwen3.5-9B на HIP, способен:

1. Рассмотреть три контекста (8K / 16K / 32K) с заполнением `depth = CTX − 128`, 3 повтора `tg128` на каждом.
2. Поднять OpenAI-совместимый HTTP-сервер на loopback с alias `lab-model` и шаблоном модели.
3. Поддержать chat (stream и non-stream), tool round-trip (stream и non-stream), long-context счёт count → `LAB_SENTINEL_42`, явный отказ при overflow и отмену долгого запроса.
4. Allowlist validator корректно различает разрешённый tool-call от отклонённого.

**Протокол до запуска.**

1. Сверка `weights.sha256` от ЛР03; захват binaries SHA от ЛР04 qwen35-9b.
2. Снимок `--help` server/bench, `--version`, `--list-devices`.
3. Шаги 2-8 из ЛР05 для каждого контекста (8K → 16K → 32K) с бендом `tg128@CTX-128` под `/usr/bin/time -v` и `vmstat -w 1`.
4. Подъём `llama-server` на loopback 8080 с `-ngl 999 -c $CTX -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1 --jinja --no-context-shift --alias lab-model`.
5. Health / props / models.
6. `http_probe.py` (verbatim) с фикстурами; 4 кейса × 2 повтора × 3 контекста.
7. Long-context через `/apply-template` + `/tokenize`, ×2.
8. Overflow (удвоение), cancel (1-сек timeout), recovery (короткий chat).
9. Offline allowlist (синтетика, без endpoint).

## Ход выполнения

| Шаг | Действие | Результат | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Сверка GGUF/бандлов | `sha256sum --check weights.sha256`, SHA binaries | OK (`91898433…`) | `raw/verification.txt`, `raw/binaries.sha256` |
| 2. Снимок help/version/devices | `--help`, `--version`, `--list-devices` | `8407 (312cf0332)`, GNU 13.3.0; `ROCm0 gfx1151` | `raw/server-help.txt`, `raw/hip-version.txt`, `raw/hip-devices.txt`, `raw/options-probed.txt` |
| 3. Фикстуры | `cp docs/labs/fixtures/*` + SHA + streaming variants | OK | `raw/fixtures.sha256`, `raw/*-request.json` |
| 4. `http_probe.py` verbatim | SHA `37182a66…` (совпал с ЛР05 qwen36) | OK | `raw/http_probe.py` |
| 5. Bench 8K | `-fa 1 -p 0 -n 128 -d 8064 -r 3` | exit 0, 25.93 t/s, RSS 7 603 172 KiB | `raw/context-8192-bench.*` |
| 6. Bench 16K | depth 16256 | exit 0, 23.80 t/s, RSS 7 602 572 KiB | `raw/context-16384-bench.*` |
| 7. Bench 32K | depth 32640 | exit 0, 20.36 t/s, RSS 7 604 108 KiB | `raw/context-32768-bench.*` |
| 8. Server 8K + HTTP 4×2 + long + overflow + cancel + recovery | полный цикл | 8/8 HTTP; long 2/2; overflow 400; cancel 28 | `raw/ctx8192-*`, `raw/server-8192.log` |
| 9. Server 16K + то же | полный цикл | 8/8 HTTP; long r1 `length`/empty, r2 OK | `raw/ctx16384-*`, `raw/server-16384.log` |
| 10. Server 32K + то же | полный цикл | 8/8 HTTP; long 2/2; overflow 400; cancel 28 | `raw/ctx32768-*`, `raw/server-32768.log` |
| 11. Offline allowlist | `--validate-tool-message` × 4 | 4/4 | `raw/offline-tool-*` |

## Результаты

### Сводка по контекстам

| CTX | Bench tg128 t/s | bench wall (s) | bench RSS (KiB) | HTTP 4×2 pass | Long |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8192 | 25.93 | 31.05 | 7 603 172 | 8/8 | 2/2 |
| 16384 | 23.80 | 61.31 | 7 602 572 | 8/8 | 1/2 (r1 `length`) |
| 32768 | 20.36 | 166.21 | 7 604 108 | 8/8 | 2/2 |

Bench `t/s` падает на 21.5% при увеличении контекста с 8K до 32K. RSS стабилен ~7.6 GiB. (Для сравнения: qwen36-35b-a3b MoE на HIP давал 43.39 / 39.26 / 33.56 t/s — decode быстрее из-за 3B активных параметров, но здесь 9B dense.)

### HTTP-кейсы (4 × 2 × 3 = 24 запроса, все успешны)

| CTX | Case | r1 finish | r1 dur (s) | r2 finish | r2 dur (s) | обе вернули expected |
| --- | --- | --- | ---: | --- | ---: | --- |
| 8192 | chat | stop | 12.15 | stop | 8.53 | ✓ |
| 8192 | chat-stream | stop | 7.90 | stop | 12.30 | ✓ |
| 8192 | tool | tool_calls | 3.34 | tool_calls | 3.00 | ✓ |
| 8192 | tool-stream | tool_calls | 2.99 | tool_calls | 2.62 | ✓ |
| 16384 | chat | stop | 7.51 | stop | 7.40 | ✓ |
| 16384 | chat-stream | stop | 14.67 | stop | 7.26 | ✓ |
| 16384 | tool | tool_calls | 3.12 | tool_calls | 2.99 | ✓ |
| 16384 | tool-stream | tool_calls | 2.92 | tool_calls | 2.99 | ✓ |
| 32768 | chat | stop | 7.38 | stop | 7.94 | ✓ |
| 32768 | chat-stream | stop | 8.01 | stop | 6.39 | ✓ |
| 32768 | tool | tool_calls | 3.49 | tool_calls | 3.11 | ✓ |
| 32768 | tool-stream | tool_calls | 2.93 | tool_calls | 2.96 | ✓ |

Tool round trip (stream и non-stream) работает на всех трёх контекстах.

### Long-context (count = prompt tokens ≤ CTX − 4096)

| CTX | Long fit | r1 finish | r1 dur (s) | TTFT content (s) | r2 finish | r2 TTFT content (s) | final |
| ---: | ---: | --- | ---: | ---: | --- | ---: | --- |
| 8192 | 4083 | stop | 19.55 | 19.29 | stop | 12.75 | `LAB_SENTINEL_42` ✓ |
| 16384 | 12287 | **length** | 198.88 | — (нет content) | stop | 11.01 | r1 ✗, r2 ✓ |
| 32768 | 28670 | stop | 149.52 | 149.19 | stop | 17.03 | `LAB_SENTINEL_42` ✓ |

16K long r1: модель ушла в длинный reasoning-цикл (198.9s, `finish_reason=length`, пустой `content`) и не сформировала final answer. r2 в той же конфигурации прошёл за 11.3s. Это стохастический reasoning-сбой dense-модели на long-контексте, не детерминированный отказ. Prefix cache виден на r2 (TTFT content 149.19s → 17.03s на 32K).

### Overflow / cancel / recovery

| CTX | Overflow input | HTTP status | Cancel exit | Recovery |
| ---: | ---: | ---: | ---: | --- |
| 8192 | 16305 | 400 | 28 | `LAB_READY` ✓ |
| 16384 | 24565 | 400 | 28 | `LAB_READY` ✓ |
| 32768 | 57331 | 400 | 28 | `LAB_READY` ✓ |

HTTP 400 на overflow — явный отказ, тихого обрезания нет. Cancel exit 28 = curl `--max-time 1`.

### Server properties (одинаковые настройки)

| CTX | n_ctx | total_slots | supports_tools | device |
| ---: | ---: | ---: | --- | --- |
| 8192 | 8192 | 1 | true | ROCm0 gfx1151 |
| 16384 | 16384 | 1 | true | ROCm0 gfx1151 |
| 32768 | 32768 | 1 | true | ROCm0 gfx1151 |

### Offline tool allowlist

| Кейс | exit_code | expected |
| --- | ---: | ---: |
| valid | 0 | 0 |
| unknown-name | 1 | 1 |
| wrong-arguments | 1 | 1 |
| missing-id | 1 | 1 |

4/4 совпадение.

### Свопинг

Все `vmstat -w 1` серии: `si = so = 0`. Подкачка не использовалась.

### Подтверждение «одинаковые условия»

- один GGUF, один commit (`312cf0332`), один HIP-бандл, одна машина, одна сессия;
- server-launch флаги идентичны, отличается только `-c $CTX`;
- воспроизводимый `http_probe.py` (SHA `37182a66…`) для всех 24 прогонов;
- flash attention включён во всех контекстах (`-fa 1`).

## Ошибки и ограничения

- **16K long r1: reasoning loop.** Модель израсходовала `max_tokens=4096` в рассуждении (198.9s, `finish_reason=length`, пустой `content`) и не дошла до final answer. r2 прошёл. Аналогичный стохастический сбой наблюдался на HIP qwen36 (32K tool-stream r1). При длинном reasoning на dense-модели `max_tokens=2048` (fixtures) или `4096` (long) может не хватить; это отдельная конфигурация с большим output-бюджетом.
- **Streaming `usage: null`.** Не передан `stream_options.include_usage`; для non-stream `usage` записан.
- **Cancel через curl `--max-time 1`** — client-side cancel (серверного `cancel_request` в b8407 нет).
- **Пребилд вместо source-build** — см. ЛР04 qwen35-9b (toolchain GNU 13.3.0).
- **Vulkan-пара для qwen35-9b не выполнялась в этом архиве** — ЛР04 показал Vulkan быстрее HIP (+12%/+9.8%); при необходимости Vulkan-серия ЛР05 делается отдельным архивом.

## Вывод по гипотезе

**Поддержана данными.** Все 3 контекста (8K / 16K / 32K) прошли бенч + server + 4×2 HTTP-кейса + overflow + cancel + recovery на ROCm/HIP для Qwen3.5-9B. **24/24** HTTP-кейсов вернули `LAB_READY`/`LAB_VALUE_42`; offline allowlist 4/4; swap отсутствует; RSS стабилен ~7.6 GiB.

Long-context в целом работает (5/6 повторов вернули `LAB_SENTINEL_42`); 16K long r1 сорвался по `finish_reason=length` из-за reasoning-цикла (r2 прошёл). Это flaky, а не детерминированный отказ. Работа с фиксированным 16K признаётся baseline; 32K пройден без отклонений.

## Ответы на контрольные вопросы

1. **Почему `-c 32768` и короткий успешный ответ не подтверждают вместимость 32K?** Пустой `prompt_tokens` не использует KV cache на 32K. Bench `depth=32640` (20.36 t/s) и long 28670/28672 (TTFT content ≈149s) реально заполняют контекст.
2. **Чем TTFT первого reasoning-токена отличается от TTFT final content?** Reasoning-токен появляется на старте prefill; content — после полного рассуждения. На 32K long r1: reasoning TTFT = 116.58s, content TTFT = 149.19s → ~33s в `<think>`. Для 16K long r1 reasoning-фаза вообще не завершилась до `max_tokens`.
3. **Почему HTTP 200 с `finish_reason=length` может означать незавершённый tool round trip?** HTTP отвечает всегда, но `length` означает, что output-бюджет истёк до завершения генерации (здесь — до final answer в long r1). Для tool-call это означало бы неполученный вызов.
4. **Чем подтверждение отказа allowlist отличается от отказа модели вызвать неизвестный tool?** Allowlist-тест — проверка клиента на синтетическом message; тест модели — генерирует ли модель только разрешённый tool. Здесь покрыт первый; фикстура ограничивает список до `lookup_lab_value`.
5. **Почему prefix cache влияет на повторный prefill?** После первого long-запроса KV-кеш для повторяющегося префикса сохраняется; r2 получает cache hit. 32K: TTFT content 149.19s → 17.03s. r1/r2 разведены в таблице.

## Комплект сдачи

- [x] `manifest.json` (completed, experimental, 7 попыток), `measurements.tsv` (262 строки), `report.md`.
- [x] Bench/HTTP/long/overflow/cancel/recovery raw evidence на 3 контекста.
- [x] `server-*.log`, `props/health/models-*.json`, allowlist, `weights.sha256` + verification.
- [x] Один backend (ROCm/HIP) без смешения; full offload (`n_gpu_layers=999`, device ROCm0).

Решение проверяющего: **не проверено**.
