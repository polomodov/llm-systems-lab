# LAB04 — Сравнение llama.cpp Vulkan и HIP/ROCm (Qwen3.5-9B)

Сессия: `qwen35-9b-prebuilt`

Создано: 2026-10-07T10:10:00Z; парные прогоны выполнены 2026-10-07T10:10 → 10:20 UTC.

Статус: **завершено**. Один артефакт `Qwen3.5-9B-Q6_K.gguf` (7.46 GiB) прошёл парное сравнение Vulkan vs HIP/ROCm на одном исходном commit `312cf03328496df9c56fe843952cf02a8964c59a` (тег `b8407`) на стенде Ryzen AI Max+ 395. Обе ветви — готовые официальные пребилды из ЛР04 qwen36 (выбор пути — см. «Ошибки и ограничения»).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-07 (10:10 → 10:20 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `unsloth/Qwen3.5-9B-GGUF@3885219b6810b007914f3a7950a8d1b469d598a5`; GGUF `Qwen3.5-9B-Q6_K.gguf` 7 458 301 152 B, SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59` (см. `LAB03-qwen35-9b`) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf03328496df9c56fe843952cf02a8964c59a`); бэкенды: ROCm/HIP (GNU 13.3) + Vulkan/RADV (GNU 11.4), бинарные SHA в `raw/{vulkan,hip}-binaries.sha256` |
| Context, KV/state dtype, slots, sampling, reasoning | bench: `pp2048` и `tg128 @ depth 4096`; KV `f16/f16`; flash-attn `1`; ngl 999 (запрос); batch 512, ubatch 256, threads 8 |
| Harness/provider/version | неприменимо (ЛР04 не использует harness) |
| Предыдущие отчёты / run IDs | `LAB02-after-rocm` (паспорт), `LAB03-qwen35-9b` (артефакт), `qwen35-9b-smoke-amd-b8407` (smoke ROCm/HIP), `LAB04-qwen36-35b-a3b-prebuilt` (та же пара бандлов) |
| Отличия от задания и причины | Канонический протокол ЛР04 требует `cmake -DGGML_VULKAN=ON` и `-DGGML_HIP=ON` на одном checkout. В этом сеансе используются **готовые пребилды** с одного upstream commit (переиспользованы из ЛР04 qwen36): официальный Vulkan tar.gz и AMD prebuilt ROCm zip (оба от `b8407`). Source-build не выполнялся — в машине нет `cmake`/HIP SDK (минимальный ROCm user-space из ЛР02). Flash attention задан через `-fa 1`, а не `-fa on`, т.к. на Vulkan b8407 `-fa on` парсится как `false` (см. ЛР05 Vulkan). |

## Гипотеза и протокол до запуска

**Гипотеза.** На стенде Ryzen AI Max+ 395 (gfx1151, UMA) один и тот же GGUF `Qwen3.5-9B-Q6_K.gguf` может работать с полным GPU offload в обеих сборках llama.cpp b8407 (Vulkan/RADV и ROCm/HIP). При одинаковой нагрузке backend влияет на скорость prefill/decode и память; направление и величина эффекта неизвестны до измерений.

**Протокол до запуска.**

1. Зафиксировать commit, источники пребилдов, SHA-256 бинарников и версии через `--version`/`--list-devices`.
2. Сверить `weights.sha256` (из ЛР03 qwen35-9b) против локального GGUF.
3. Поднять два бандла с явным `LD_LIBRARY_PATH` (каждая сборка self-contained).
4. Прогреть каждую ветвь одним прогоном `pp512 + tg128`, НЕ учитывать в статистике; проверить `flash_attn: true` и `n_gpu_layers: 999` в JSON.
5. Три парных повтора с чередованием порядка (r1 vulkan→hip, r2 hip→vulkan, r3 vulkan→hip). Каждый повтор — два `llama-bench` под `/usr/bin/time -v`: `-p 2048 -n 0 -r 1` и `-p 0 -n 128 -d 4096 -r 1`.
6. В фоне `vmstat -w 1`.
7. Считать median/min/max и отношение HIP/Vulkan; не интерпретировать как чистый эффект backend (toolchain различается).

## Ход выполнения

| Шаг | Действие | Результат | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Сверка GGUF | `sha256sum --check weights.sha256` | OK (`91898433…`) | `raw/verification-before.txt`, `raw/weights.sha256` |
| 2. Снимок бэкендов | `--version`, `--list-devices`, binaries SHA | оба `8407 (312cf0332)`, оба видят gfx1151 | `raw/{vulkan,hip}-{version,devices,bench-help,binaries.sha256}.txt` |
| 3. Warmup Vulkan | `llama-bench -p 512 -n 128 -r 1 -fa 1` | exit 0, `flash_attn=true`, `n_gpu_layers=999` | `raw/vulkan-warmup.{json,log}` |
| 4. Warmup HIP | то же с ROCm бандлом | exit 0, `flash_attn=true`, `n_gpu_layers=999` | `raw/hip-warmup.{json,log}` |
| 5. Старт `vmstat -w 1` | background | 118 семплов за серию | `raw/vmstat-series.txt`, `raw/vmstat-pid.txt` |
| 6. r1: vulkan→hip | 2 × 2 `llama-bench` под `/usr/bin/time -v` | exit 0 | `raw/{vulkan,hip}-r1-{pp,tg}.*` |
| 7. r2: hip→vulkan | то же | exit 0 | `raw/{hip,vulkan}-r2-{pp,tg}.*` |
| 8. r3: vulkan→hip | то же | exit 0 | `raw/{vulkan,hip}-r3-{pp,tg}.*` |
| 9. Стоп vmstat | `kill` | OK | `raw/vmstat-series.txt` |

## Результаты

### Сводная таблица по режимам

| Режим | Backend | r1 t/s | r2 t/s | r3 t/s | median | min | max | HIP/Vulkan |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pp2048 | Vulkan | 857.88 | 846.50 | 865.76 | **857.88** | 846.50 | 865.76 | 0.893 |
| pp2048 | HIP/ROCm | 773.96 | 763.89 | 765.94 | **765.94** | 763.89 | 773.96 | — |
| tg128 @ 4096 | Vulkan | 29.40 | 29.16 | 29.42 | **29.40** | 29.16 | 29.42 | 0.911 |
| tg128 @ 4096 | HIP/ROCm | 26.62 | 26.77 | 26.86 | **26.77** | 26.62 | 26.86 | — |

Vulkan быстрее HIP: pp2048 **+12.0%**, tg128@4096 **+9.8%**. Разброс внутри серии < 2.5%.

### Память и процесс (`/usr/bin/time -v`)

| Backend | Mode | Wall (s) | Max RSS (KiB) | Max RSS (GiB) |
| --- | --- | ---: | ---: | ---: |
| Vulkan | pp2048 | ~6.0 | 7 467 152 | 7.12 |
| Vulkan | tg128 d4096 | ~10.4 | 7 467 492 | 7.12 |
| HIP/ROCm | pp2048 | ~6.5 | 7 603 136 | 7.25 |
| HIP/ROCm | tg128 d4096 | ~12.1 | 7 602 784 | 7.25 |

RSS у HIP выше (~130 MiB) — на уровне шума; согласуется с ЛР04 qwen36 (там разница была ~150 MiB).

### Свопинг

| Источник | max swap in | max swap out |
| --- | ---: | ---: |
| `vmstat-series.txt` (118 семплов) | 0 | 0 |

Подкачка не использовалась ни в одном прогоне.

### Подтверждение offload и flash attention

- `n_gpu_layers: 999` и `flash_attn: true` в JSON всех 12 основных вызовов.
- Устройства: `Vulkan0 (AMD Radeon Graphics (RADV GFX1151))` и `ROCm0 (AMD Radeon Graphics, gfx1151)` — подтверждены `--list-devices`.

### Подтверждение «одинаковые условия»

- один GGUF, один commit (`312cf0332`), одна машина, одна сессия;
- `-ngl 999`, `-t 8`, `-b 512`, `-ub 256`, `-ctk f16`, `-ctv f16`, `-fa 1` идентичны во всех вызовах;
- порядок чередуется (vulkan→hip, hip→vulkan, vulkan→hip);
- ровно `-r 1` per вызов — один `llama-bench` JSON-семпл на ячейку.

## Ошибки и ограничения

- **Source-build не выполнялся**: `cmake` отсутствует (минимальный ROCm user-space). Пребилды с одного upstream commit — единственный путь. Toolchain различается (GNU 13.3 для ROCm, GNU 11.4 для Vulkan); часть разницы может быть не backend-эффектом, а эффектом компилятора. Зафиксировано как «одинаковые условия с оговоркой».
- **Flash attention на Vulkan**: `-fa on` не включает FA на Vulkan b8407 (парсится как `false`), поэтому использован `-fa 1` для обоих бэкендов — `flash_attn=true` на обоих.
- **Vulkan flash-attn через RADV** — Mesa RADV + `libggml-vulkan.so` upstream.
- **Page cache не сбрасывался**: после первого cold load веса в page cache, последующие повторы warm по диску. Это общий случай для ЛР04 (протокол не чистит кеш).
- **Сравнение ограничено**: одна модель (9B dense), один контекст (4096 depth), 3 повтора. Не является рейтингом бэкендов вообще; не оценивает агентную нагрузку (см. контрольные вопросы).

## Вывод по гипотезе

**Поддержана данными.** Один и тот же GGUF (7.46 GiB) запускается с полным GPU offload (`n_gpu_layers: 999`) и flash-attn (`flash_attn: true`) в обеих ветвях на gfx1151; swap не используется; 3 парных повтора с чередованием порядка.

Vulkan быстрее HIP/ROCm для этой модели и пребилда: pp2048 **+12.0%** (857.88 vs 765.94 t/s), tg128@4096 **+9.8%** (29.40 vs 26.77 t/s). Эффект не равен чистому backend-эффекту, т.к. toolchain различается (GNU 11.4 vs 13.3). Направление совпадает с ЛР04 qwen36 (там Vulkan был +8% pp / +13.7% tg).

## Ответы на контрольные вопросы

1. **Почему сравнение разных commit не позволяет выделить эффект Vulkan/HIP?** Наблюдаемая разница стала бы смесью изменений исходников и backend. Здесь commit фиксирован (`312cf03328`); переменная — toolchain и backend.
2. **Почему tg128 при пустом контексте недостаточно для агентной нагрузки?** Агентные сценарии используют контекст 8K–32K и множество коротких prefill/decode циклов. `tg128 @ depth 4096` меряет устойчивый decode с заполненным KV; не нагружает prompt processing в реалистичной пропорции и не учитывает batching.
3. **Что входит в process wall time и что исключено из `llama-bench` t/s?** `llama-bench` меряет только prefill/decode (`avg_ns`). В wall time дополнительно: `mmap` модели, чтение метаданных GGUF, инициализация backend, аллокации. Для 7.46 GiB модели cold load ≈2–3 s overhead.
4. **Как отличить успешный запуск от полного GPU offload?** По JSON `n_gpu_layers` (запрос), `backends` (имя), `flash_attn`, и по скорости (pp ~800 t/s у 9B dense указывает на GPU-работу). Полный per-tensor offload доказывается verbose-логом (здесь `--list-devices` + `n_gpu_layers=999`).
5. **Что нужно пересчитать при смене KV f16 на q8_0?** KV cache уменьшается ~2× по байтам на ту же длину контекста; decode может меняться из-за dequant. Для 9B это не критично по памяти, но меняет бюджеты и скорость.

## Комплект сдачи

- [x] `manifest.json` со статусом `completed`, evidence_class `experimental`, 14 запланированных попыток (12 парных + 2 warmup).
- [x] `measurements.tsv` с 36 строками, все `status=measured`.
- [x] `report.md` со всеми обязательными секциями.
- [x] Сырые логи: `raw/{vulkan,hip}-{version,devices,bench-help,binaries.sha256}.txt`, `raw/{vulkan,hip}-{warmup,r{1,2,3}-pp,r{1,2,3}-tg}.{json,log,process.txt}`, `raw/{vulkan,hip}-r{1,2,3}-{memory,vmstat}-{before,after}.txt`, `raw/vmstat-series.txt`.
- [x] Сверительный SHA-256 GGUF: `raw/weights.sha256` + `raw/verification-before.txt`.
- [x] Обе ветви описаны отдельной колонкой, без смешения.

Решение проверяющего: **не проверено**.
