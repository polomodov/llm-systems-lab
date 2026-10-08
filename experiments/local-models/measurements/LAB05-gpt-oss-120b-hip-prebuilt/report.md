# LAB05 — Контекст 8/16/32K, streaming и инструменты (gpt-oss-120b, HIP)

Сессия: `gpt-oss-120b-hip-prebuilt`

Создано: 2026-10-07T18:20:00Z; бенды, server-сессии и HTTP-прогоны выполнены 2026-10-07T18:20 → 19:00 UTC.

Статус: **завершено для всех 3 контекстов на ROCm/HIP**. Один артефакт `gpt-oss-120b-MXFP4.gguf` (59 GiB, MoE 117B total / 5.1B active) на HIP бэкенде llama.cpp b8407 (commit `312cf03328496df9c56fe843952cf02a8964c59a`). Все три контекста прошли бенч + сервер + streaming/tool/long/overflow/cancel. **24/24** HTTP-кейсов вернули ожидаемые маркеры; long-context прошёл на всех контекстах (6/6).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-07 (18:20 → 19:00 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` |
| Модель/артефакт | `ggml-org/gpt-oss-120b-GGUF@238abdd290bb874b90a5da1b4549881b7d05c091`; `gpt-oss-120b-MXFP4.gguf` 63 387 346 208 B, SHA-256 `582bd40f6886200101f4c4ed9f25f3fe80cc14c86e9e2b37746cd8904a0c622d` |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf0332`); ROCm/HIP бандл (GNU 13.3.0), SHA в `raw/binaries.sha256` |
| Context, KV/state dtype, slots, sampling, reasoning | 8K / 16K / 32K; KV `f16/f16`; flash-attn `1`; `-np 1`; jinja-шаблон gpt-oss (supports tools) |
| Harness | нет (loopback `http://127.0.0.1:8080`) |
| Соседние отчёты | `LAB03-gpt-oss-120b` (артефакт), `LAB04-gpt-oss-120b-prebuilt` (бэкенды) |
| Отличия от задания | Пребилд вместо source-build; `-fa 1` для flash attention; streaming usage `null`. |

## Гипотеза и протокол до запуска

**Гипотеза.** Тот же llama.cpp b8407 (commit `312cf0332`), который в ЛР04 загрузил gpt-oss-120b с полным offload на обоих бэкендах, на HIP способен: (a) пройти три llama-bench заполнения на CTX=8K/16K/32K, (b) обслуживать chat + tool + streaming на loopback, (c) явно отказывать при overflow и отменять долгий запрос, (d) пройти tool round trip по open fixtures.

**Протокол.** Как в ЛР05 qwen35-9b: сверка SHA, bench `tg128@CTX-128` ×3 под `/usr/bin/time -v` + `vmstat`, сервер на 8080, `http_probe.py` (4 кейса ×2 ×3), long `/apply-template`+`/tokenize` ×2, overflow/cancel/recovery, offline allowlist.

## Ход выполнения

| Шаг | Действие | Результат | Ссылка |
| --- | --- | --- | --- |
| 1. Сверка GGUF | `sha256sum --check` | OK (`582bd40f…`) | `raw/verification.txt` |
| 2. Снимок help/version/devices | `--help`, `--version`, `--list-devices` | `8407 (312cf0332)`, ROCm0 gfx1151 | `raw/{server-help,hip-version,hip-devices}.txt` |
| 3. Bench 8K/16K/32K | `-fa 1 -p 0 -n 128 -d CTX-128 -r 3` | 36.32 / 27.36 / 14.61 t/s | `raw/context-{8192,16384,32768}-bench.*` |
| 4. Server 8K + полный цикл | HTTP 4×2 + long + overflow + cancel + recovery | 8/8; long 2/2 | `raw/ctx8192-*` |
| 5. Server 16K + полный цикл | то же | 8/8; long 2/2 | `raw/ctx16384-*` |
| 6. Server 32K + полный цикл | то же | 8/8; long 2/2 | `raw/ctx32768-*` |
| 7. Offline allowlist | `--validate-tool-message` ×4 | 4/4 | `raw/offline-tool-*` |

## Результаты

### Сводка по контекстам

| CTX | Bench tg128 t/s | bench wall (s) | bench RSS (KiB) | HTTP 4×2 pass | Long |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8192 | 36.32 | 37.24 | 62 264 932 | 8/8 | 2/2 |
| 16384 | 27.36 | 68.91 | 62 267 056 | 8/8 | 2/2 |
| 32768 | 14.61 | 164.77 | 62 267 416 | 8/8 | 2/2 |

Bench `t/s` падает на 60% от 8K к 32K (36.32 → 14.61) — заметно сильнее, чем у qwen36-35b-a3b (23%) и qwen35-9b (21%). RSS стабилен ~62.3 GiB.

### HTTP-кейсы (4 × 2 × 3 = 24 запроса, все успешны)

| CTX | chat r1/r2 | chat-stream r1/r2 | tool r1/r2 | tool-stream r1/r2 |
| --- | --- | --- | --- | --- |
| 8192 | stop / stop | stop / stop | tool_calls / tool_calls | tool_calls / tool_calls |
| 16384 | stop / stop | stop / stop | tool_calls / tool_calls | tool_calls / tool_calls |
| 32768 | stop / stop | stop / stop | tool_calls / tool_calls | tool_calls / tool_calls |

Все 24 вернули `LAB_READY` / `LAB_VALUE_42`. Короткие запросы быстрые (~1–2 s). Tool round trip (stream и non-stream) работает на всех контекстах.

### Long-context (count = prompt tokens ≤ CTX − 4096)

| CTX | Long fit | r1 finish | r1 TTFT content (s) | r2 finish | r2 TTFT content (s) | final |
| ---: | ---: | --- | ---: | --- | ---: | --- |
| 8192 | 4093 | stop | 12.7 | stop | 3.0 | `LAB_SENTINEL_42` ✓ |
| 16384 | 12283 | stop | 36.4 | stop | 2.5 | `LAB_SENTINEL_42` ✓ |
| 32768 | 28669 | stop | 108.8 | stop | 5.7 | `LAB_SENTINEL_42` ✓ |

Все 6 long-повторов вернули `LAB_SENTINEL_42`; `--no-context-shift` сохраняет целостность (sentinel из первой строки). Prefix cache виден на r2 (108.8 → 5.7 s на 32K).

### Overflow / cancel / recovery

| CTX | Overflow input | HTTP status | Cancel exit | Recovery |
| ---: | ---: | ---: | ---: | --- |
| 8192 | 16171 | 400 | 28 | `LAB_READY` ✓ |
| 16384 | 24499 | 400 | 28 | `LAB_READY` ✓ |
| 32768 | 57271 | 400 | 28 | `LAB_READY` ✓ |

### Свопинг

| CTX | max swap in (pages) | max swap out (pages) |
| ---: | ---: | ---: |
| 8192 | 4 868 | 11 472 |
| 16384 | 7 932 | 7 520 |
| 32768 | 320 752 | 458 048 |

На 32K появляется значительная подкачка (~1.8 GiB swap-out) — 59 GiB модель + KV cache 32K приближаются к лимиту UMA. Это согласуется с ЛР04, где swap был ненулевым уже на bench.

### Server properties

| CTX | n_ctx | total_slots | supports_tools | device |
| ---: | ---: | ---: | --- | --- |
| 8192 | 8192 | 1 | true | ROCm0 gfx1151 |
| 16384 | 16384 | 1 | true | ROCm0 gfx1151 |
| 32768 | 32768 | 1 | true | ROCm0 gfx1151 |

### Offline tool allowlist

4/4: valid принят (exit 0), unknown-name / wrong-arguments / missing-id отклонены (exit 1).

## Ошибки и ограничения

- **Подкачка на 32K** (~1.8 GiB swap-out): 59 GiB модель близка к лимиту UMA. Для 32K агентной нагрузки стоит рассмотреть KV quant (q8_0) или меньший контекст.
- **Падение decode на 60%** от 8K к 32K — сильнее, чем у Qwen; связано с MoE + большой KV на заполненном контексте.
- **Streaming `usage: null`** (не передан `stream_options.include_usage`).
- **Cancel через `--max-time 1`** — client-side cancel.
- **Пребилд вместо source-build** (нет cmake/HIP SDK); toolchain GNU 13.3.
- **MXFP4** — специальный 4-битный формат; численные характеристики могут отличаться от BF16 (не оценивается здесь).

## Вывод по гипотезе

**Поддержана данными.** gpt-oss-120b MXFP4 MoE проходит полный протокол ЛР05 на ROCm/HIP: 24/24 HTTP-кейсов, long 6/6 (`LAB_SENTINEL_42` на 4093/12283/28669 токенов), overflow HTTP 400, cancel exit 28, recovery `LAB_READY`, offline allowlist 4/4. Tools работают (native tool template). RSS стабилен ~62.3 GiB; на 32K появляется значительная подкачка (~1.8 GiB), что ограничивает 32K-нагрузку.

## Ответы на контрольные вопросы

1. **Почему `-c 32768` и короткий ответ не подтверждают вместимость 32K?** Пустой prompt не использует KV cache на 32K. Bench `depth=32640` (14.61 t/s) и long 28669/28672 (TTFT 108.8 s) реально заполняют контекст — но уже с подкачкой.
2. **Чем TTFT reasoning-токена отличается от TTFT content?** Reasoning появляется на старте prefill, content — после рассуждения. У gpt-oss-120b reasoning короткий (см. long r1/r2).
3. **Почему HTTP 200 с `finish_reason=length` означает незавершённый tool round trip?** `length` = output-бюджет истёк до завершения генерации; здесь такого не было (все stop/tool_calls).
4. **Чем подтверждение отказа allowlist отличается от отказа модели?** Allowlist-тест — проверка клиента на синтетическом message; здесь модель генерирует только разрешённый tool.
5. **Почему prefix cache влияет на повторный prefill?** KV-кеш префикса сохраняется; r2 получает cache hit (32K long: 108.8 → 5.7 s).

## Комплект сдачи

- [x] `manifest.json` (7 попыток), `measurements.tsv` (263 строки), `report.md`.
- [x] Bench/HTTP/long/overflow/cancel/recovery raw evidence на 3 контекста.
- [x] `server-*.log`, `props/health/models-*.json`, allowlist, `weights.sha256` + verification.
- [x] Один backend (ROCm/HIP), full offload (`n_gpu_layers=999`).

Решение проверяющего: **не проверено**.
