# LAB04 — Сравнение llama.cpp Vulkan и HIP/ROCm (gpt-oss-120b)

Сессия: `gpt-oss-120b-prebuilt`

Создано: 2026-10-07T18:00:00Z (запись сессии); парные прогоны фактически выполнены 2026-10-08T07:15 → 07:19 UTC (по `test_time` bench-JSON).

Статус: **blocked (ретроспективная сессия)**. Протокол не был зарегистрирован до прогонов, поэтому по `docs/labs/report-validation.md` сессия не может быть `completed`; завершённый результат с preregistration перенесён в `gpt-oss-120b-prebuilt-prereg`. Данные ниже сохранены как есть.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; исполнение 2026-10-08 (07:15 → 07:19 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` |
| Модель/артефакт | `ggml-org/gpt-oss-120b-GGUF@238abdd290bb874b90a5da1b4549881b7d05c091`; `gpt-oss-120b-MXFP4.gguf` 63 387 346 208 B, SHA-256 `582bd40f6886200101f4c4ed9f25f3fe80cc14c86e9e2b37746cd8904a0c622d` |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf0332`); Vulkan/RADV (GNU 11.4) + ROCm/HIP (GNU 13.3), SHA в `raw/{vulkan,hip}-binaries.sha256` |
| Context, KV/state dtype, slots, sampling, reasoning | `pp2048` и `tg128 @ depth 4096`; KV `f16/f16`; flash-attn `1`; ngl 999; batch 512, ubatch 256, threads 8 |
| Harness/provider/version | неприменимо |
| Предыдущие отчёты / run IDs | `LAB03-gpt-oss-120b` (артефакт), `LAB02-after-rocm` (паспорт) |
| Отличия от задания и причины | Пребилды вместо source-build (нет cmake/HIP SDK). Flash attention задан `-fa 1` (на Vulkan b8407 `-fa on` парсится как `false`). |

## Гипотеза и протокол до запуска

**Гипотеза.** На gfx1151 (UMA ~102–122 GiB) один и тот же GGUF `gpt-oss-120b-MXFP4.gguf` может работать с полным GPU offload в обеих сборках llama.cpp b8407. При одинаковой нагрузке backend влияет на скорость prefill/decode и память; направление и величина эффекта неизвестны до измерений.

**Протокол до запуска.**

1. Сверка `weights.sha256`, snapshot версий/help/devices, binaries SHA.
2. Прогрев каждой ветви (`pp512 + tg128`), НЕ в статистике.
3. Три парных повтора (r1 vulkan→hip, r2 hip→vulkan, r3 vulkan→hip): `pp2048` и `tg128@4096`, каждый под `/usr/bin/time -v`.
4. `vmstat -w 1` в фоне.

## Ход выполнения

| Шаг | Действие | Результат | Ссылка |
| --- | --- | --- | --- |
| 1. Сверка GGUF | `sha256sum --check` | OK (`582bd40f…`) | `raw/verification-before.txt` |
| 2. Снимок бэкендов | `--version`, `--list-devices` | оба `8407 (312cf0332)`, gfx1151 | `raw/{vulkan,hip}-{version,devices}.txt` |
| 3. Warmup Vulkan/HIP | `-p 512 -n 128 -r 1 -fa 1` | exit 0, `flash_attn=true`, `n_gpu_layers=999` | `raw/{vulkan,hip}-warmup.*` |
| 4. Три парных повтора | чередование порядка | exit 0 | `raw/{vulkan,hip}-r{1,2,3}-{pp,tg}.*` |

## Результаты

### Сводная таблица по режимам

| Режим | Backend | r1 | r2 | r3 | median | min | max | HIP/Vulkan |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pp2048 | Vulkan | 389.30 | 392.40 | 385.39 | **389.30** | 385.39 | 392.40 | 1.065 |
| pp2048 | HIP/ROCm | 417.83 | 414.77 | 412.80 | **414.77** | 412.80 | 417.83 | — |
| tg128 @ 4096 | Vulkan | 51.59 | 51.61 | 51.20 | **51.59** | 51.20 | 51.61 | 0.831 |
| tg128 @ 4096 | HIP/ROCm | 42.88 | 42.90 | 42.60 | **42.88** | 42.60 | 42.90 | — |

**Разнонаправленный эффект**: HIP быстрее на prefill (+6.5%), Vulkan быстрее на decode (+20.3%). Это отличается от qwen36-35b-a3b и qwen35-9b, где Vulkan был быстрее на обоих режимах.

### Память и процесс

| Backend | Mode | Wall (s) | Max RSS (KiB) | Max RSS (GiB) |
| --- | --- | ---: | ---: | ---: |
| Vulkan | pp2048 | ~18.9 | 62 099 860 | 59.2 |
| Vulkan | tg128 d4096 | ~22.1 | 62 100 280 | 59.2 |
| HIP/ROCm | pp2048 | ~15.4 | 62 260 548 | 59.4 |
| HIP/ROCm | tg128 d4096 | ~19.3 | 62 264 636 | 59.4 |

RSS ~59.2–59.4 GiB — модель 59 GiB + scratch. HIP ~160 MiB больше RSS.

### Свопинг

Объём подкачки — из дельт `/proc/vmstat` `pswpout` (страницы × 4096 B) по каждому повтору; `vmstat si/so` — это скорость (KiB/s), а не счётчик.

| Backend | pswpout Δ по r1/r2/r3, страниц | Сумма, страниц | Сумма, GiB |
| --- | ---: | ---: | ---: |
| Vulkan | 180 919 / 31 655 / 61 096 | 273 670 | 1.04 |
| HIP/ROCm | 23 218 / 18 043 / 15 330 | 56 591 | 0.22 |

В отличие от qwen36-35b-a3b и qwen35-9b, где swap = 0, для 59 GiB модели появилась **небольшая, но ненулевая** подкачка, сильнее на Vulkan (≈1.04 GiB против ≈0.22 GiB). Это признак приближения к лимиту UMA: большая модель + page cache + OS близки к доступной памяти.

### Подтверждение offload и flash attention

`n_gpu_layers: 999` в JSON — это запрошенное значение, а не фактическая раскладка. Прямое подтверждение снято в preregistered-сессии `gpt-oss-120b-prebuilt-prereg` (`llama-bench -v`): `load_tensors: layer … assigned to device (Vulkan|ROCm)`, **37 слоёв на GPU, 0 на CPU** в обеих ветвях. `flash_attn: true` присутствует в JSON всех 12 вызовов; устройства `Vulkan0 (RADV GFX1151)` / `ROCm0 (gfx1151)`.

### Подтверждение «одинаковые условия»

Один GGUF, один commit, одна машина, одна сессия; идентичные флаги (`-ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1`); порядок чередуется; ровно `-r 1` per вызов.

## Ошибки и ограничения

- **Source-build не выполнялся** (нет cmake/HIP SDK). Toolchain различается (GNU 13.3 HIP / 11.4 Vulkan) — эффект не чистый backend.
- **MXFP4** — специальный 4-битный формат; поддержка на gfx1151 работает в b8407 (обе ветви загружаются), но численные характеристики могут отличаться от BF16.
- **Ненулевой swap** — см. таблицу свопинга; это ограничение вместимости UMA для 59 GiB модели, а не backend-эффект.
- **Vulkan flash-attn через RADV** — Mesa RADV + `libggml-vulkan.so`.
- **Page cache не сбрасывался** — повторы warm по диску.

## Вывод по гипотезе

**Поддержана данными.** Один GGUF (59 GiB) работает с полным offload и flash-attn в обеих ветвях. Backend-эффект **разнонаправлен**: HIP +6.5% на pp2048, Vulkan +20.3% на tg128@4096. Это не противоречит гипотезе (эффект существует), но направление зависит от режима — в отличие от Qwen-моделей, где Vulkan был быстрее везде. Появилась небольшая подкачка (pswpout ≈1.04 GiB Vulkan / ≈0.22 GiB HIP), отсутствовавшая у меньших моделей. Сессия помечена `blocked` как ретроспективная; preregistered-результат — в `gpt-oss-120b-prebuilt-prereg`.

## Ответы на контрольные вопросы

1. **Почему сравнение разных commit не выделяет эффект Vulkan/HIP?** Смешиваются изменения исходников и backend. Здесь commit фиксирован.
2. **Почему tg128 при пустом контексте недостаточно для агентной нагрузки?** Агентные сценарии — 8K–32K контекст, множество prefill/decode; `tg128@4096` меряет только устойчивый decode.
3. **Что входит в process wall time?** `mmap` 59 GiB модели, метаданные, инициализация backend, аллокации (cold load ≈8–10 s overhead), плюс сам bench.
4. **Как отличить успешный запуск от полного offload?** Успешный запуск доказывается exit code, полный offload — только явной раскладкой: в preregistered-сессии `llama-bench -v` показал 37/37 слоёв на GPU и 0 на CPU. `n_gpu_layers=999` — это запрос, а не доказательство.
5. **Что пересчитать при KV f16 → q8_0?** KV cache ~2× меньше по байтам; для 59 GiB модели это заметная экономия UMA и может снизить подкачку.

## Комплект сдачи

- [x] `manifest.json` (14 попыток), `measurements.tsv` (36 строк), `report.md`.
- [x] Raw: `{vulkan,hip}-{version,devices,bench-help,binaries.sha256}`, `{vulkan,hip}-{warmup,r{1,2,3}-pp,r{1,2,3}-tg}.*`, process metrics, memory/vmstat, `vmstat-series.txt`.
- [x] `weights.sha256` + `verification-before.txt`.

Решение проверяющего: **не проверено**.
