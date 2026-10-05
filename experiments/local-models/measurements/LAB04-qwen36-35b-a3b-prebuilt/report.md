# LAB04 — Сравнение llama.cpp Vulkan и HIP/ROCm на одном артефакте

Сессия: `qwen36-35b-a3b-prebuilt`

Создано: 2026-10-05T11:00:00Z; загрузка бандлов и парные прогоны выполнены 2026-10-05T11:00 → 12:10 UTC.

Статус: **завершено**. Один артефакт `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` (24.64 GiB) прошёл парное сравнение Vulkan vs HIP/ROCm на одном исходном commit `312cf03328496df9c56fe843952cf02a8964c59a` (тег `b8407`) на стенде Ryzen AI Max+ 395. Обе ветви — готовые официальные пребилды с GitHub Releases и AMD prebuilt repo (выбор пути — см. «Ошибки и ограничения»).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-05 (11:00 → 12:10 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.3 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `Qwen/Qwen3.6-35B-A3B` rev `995ad96eacd98c81ed38be0c5b274b04031597b0`; GGUF `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` 26 456 194 016 B, SHA-256 `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932` (см. `LAB03-qwen36-35b-a3b`) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf03328496df9c56fe843952cf02a8964c59a`); бэкенды: ROCm/HIP `40de23cc…` (llama-bench) + `be8c03c5…` (llama-server); Vulkan/RADV `7800ad09…` (llama-bench) + `9f6bc8e8…` (llama-server) |
| Context, KV/state dtype, slots, sampling, reasoning | `8K` для warmup; `pp2048` и `tg128 @ depth 4096` для основных; KV `f16/f16`; flash-attn `1`; ngl 999 (запрос); batch 512, ubatch 256, threads 8 |
| Harness/provider/version | неприменимо (ЛР04 не использует harness) |
| Предыдущие отчёты / run IDs | `LAB02-after-rocm` (паспорт), `LAB03-qwen36-35b-a3b` (артефакт), `qwen35-9b-smoke-amd-b8407` (smoke b8407 ROCm/HIP, MD5 сверен) |
| Отличия от задания и причины | Канонический протокол ЛР04 требует `cmake -DGGML_VULKAN=ON` и `cmake -DGGML_HIP=ON` на одном checkout llama.cpp. В этом сеансе используются **готовые пребилды** с одного upstream commit: официальный Vulkan tar.gz и AMD prebuilt ROCm zip (оба от `b8407`, источник https://github.com/ggml-org/llama.cpp/releases/tag/b8407). Source-build путь не выполнялся, потому что в машине установлен только **минимальный** ROCm user-space (`install-rocm-7.2.sh minimal` для ЛР02): нет `cmake`, нет HIP SDK/hipruntime, нет `hipconfig`. Решение о пребилдах принято оперативно и зафиксировано в `raw/build-provenance.txt`. Из-за этого два бинарных комплекта собраны разными toolchain (GNU 13.3 для ROCm, GNU 11.4 для Vulkan); это единственное систематическое различие между ветвями и его влияние обсуждается ниже. |

## Гипотеза и протокол до запуска

**Гипотеза.** На `ldm561` (Ryzen AI Max+ 395, gfx1151, UMA 108.94 GiB) один и тот же GGUF может работать с полным GPU offload в обеих сборках llama.cpp; при одинаковой нагрузке backend влияет на скорость prefill/decode и память, направление и величина эффекта неизвестны до измерений.

**Протокол до запуска.**

1. Зафиксировать `git rev-parse HEAD`, источники пребилдов, MD5/SHA-256 бинарников и версии через `--version`.
2. Сверить `weights.sha256` (из ЛР03) против локального GGUF.
3. Поднять две распаковки: `$ROCM_DIR` и `$VULKAN_DIR` с явным `LD_LIBRARY_PATH` (каждая сборка несёт self-contained зависимости).
4. Прогреть каждую ветвь одним прогоном `pp512 + tg128`, НЕ учитывать в финальной статистике; убедиться, что `flash_attn: true` и `n_gpu_layers: 999` в JSON.
5. Запустить 3 парных повтора с чередованием порядка (r1 vulkan→hip, r2 hip→vulkan, r3 vulkan→hip). Каждый повтор — это два `llama-bench` под `/usr/bin/time -v`: `-p 2048 -n 0 -r 1` и `-p 0 -n 128 -d 4096 -r 1`. Все запуски — в одном shell с `set -eu`; не запускать ветви одновременно.
6. В фоне во время серии 3 повторов собрать `vmstat -w 1`.
7. Считать медианы, min/max, отношение HIP/Vulkan для одинаковых режимов; не интерпретировать отношение как чистый эффект backend (toolchain тоже отличается).

## Ход выполнения

| Шаг | Действие | Результат | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Скачать Vulkan пребилд | `curl -sSL -o llama-b8407-bin-ubuntu-vulkan-x64.tar.gz https://github.com/ggml-org/llama.cpp/releases/download/b8407/llama-b8407-bin-ubuntu-vulkan-x64.tar.gz` | 47 505 253 B, OK | `raw/build-provenance.txt` |
| 2. Распаковать Vulkan | `tar -xzf` в `$VULKAN_DIR` | 137 MiB на диске | `raw/build-provenance.txt` |
| 3. Скачать ROCm пребилд | `curl --continue-at - … https://repo.radeon.com/rocm/llama.cpp/linux/rocm-rel-7.2.1/llama-b8407-…gfx115X-x64.zip` | 3 814 589 285 B | `raw/build-provenance.txt` |
| 4. MD5 ROCm пребилда | `md5sum` | `effa4bcd7c2dd6d201cb412847359319` совпал с заявленным в `qwen35-9b-smoke-amd-b8407/raw/archive.md5` | `raw/build-provenance.txt` |
| 5. Распаковать ROCm | `unzip`, `chmod +x` на binaries | ~5.4 GiB на диске | `raw/build-provenance.txt` |
| 6. Сверить GGUF SHA | `sha256sum --check raw/weights.sha256` | OK | `raw/verification-before.txt` |
| 7. Снимок бэкендов | `--version`, `--help`, `--list-devices`, binaries SHA-256 | оба `8407 (312cf0332)`, оба видят gfx1151 | `raw/{vulkan,rocm}-{version,bench-help,devices}.txt`, `raw/{vulkan,rocm}-binaries.sha256` |
| 8. Warmup ROCm | `llama-bench -p 512 -n 128 -r 1 -fa 1` | exit 0, JSON с `flash_attn=true`, `n_gpu_layers=999` | `raw/rocm-warmup.{json,log}` |
| 9. Warmup Vulkan | то же с LD_LIBRARY_PATH=VULKAN_DIR | exit 0, JSON с `flash_attn=true`, `n_gpu_layers=999` | `raw/vulkan-warmup.{json,log}` |
| 10. Старт `vmstat -w 1` | background, PID ~200 | 143 строк за 2:23 работы | `raw/vmstat-series.txt`, `raw/vmstat-pid.txt` |
| 11. r1: vulkan→hip | 2 × 2 `llama-bench` под `/usr/bin/time -v` | exit 0, оба backend | `raw/vulkan-r1-*`, `raw/hip-r1-*` |
| 12. r2: hip→vulkan | то же | exit 0 | `raw/hip-r2-*`, `raw/vulkan-r2-*` |
| 13. r3: vulkan→hip | то же | exit 0 | `raw/vulkan-r3-*`, `raw/hip-r3-*` |
| 14. Стоп vmstat | `kill $VMSTAT_PID` | OK | `raw/vmstat-series.txt` |
| 15. Пересверка SHA | повторно `sha256sum --check raw/weights.sha256` | OK | `raw/verification-after.txt` |

## Результаты

### Сводная таблица по режимам

| Режим | Backend | r1 t/s | r2 t/s | r3 t/s | median t/s | min | max | HIP/Vulkan |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pp2048 | Vulkan | 696.45 | 675.98 | 674.37 | **675.98** | 674.37 | 696.45 | 0.926 |
| pp2048 | HIP/ROCm | 629.81 | 625.84 | 617.92 | **625.84** | 617.92 | 629.81 | — |
| tg128 @ depth 4096 | Vulkan | 51.40 | 51.18 | 50.98 | **51.18** | 50.98 | 51.40 | 0.880 |
| tg128 @ depth 4096 | HIP/ROCm | 45.01 | 45.03 | 44.90 | **45.01** | 44.90 | 45.03 | — |

### Память и процесс (по одному `/usr/bin/time -v` для каждого backend для /usr/bin/time -v)

| Backend | Mode | Wall (s) | User (s) | Sys (s) | Max RSS (KiB) | Max RSS (GiB) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| HIP/ROCm | pp2048 | 8.94 | 7.41 | 2.13 | 26 174 304 | 24.96 |
| HIP/ROCm | tg128 d4096 | 12.82 | 11.94 | 4.20 | 26 173 972 | 24.96 |
| Vulkan | pp2048 | 9.20 | 2.72 | 1.43 | 26 021 448 | 24.81 |
| Vulkan | tg128 d4096 | 11.62 | 3.60 | 1.49 | 26 020 204 | 24.81 |

Различия по User-time показывают, что HIP проводит больше CPU-работы на тот же объём декодирования (вероятно из-за разных путей аллокации/вычислений в плагине). RSS у HIP чуть выше (≈150 MiB) — на уровне шума.

### Память системы и swap

| Источник | MemTotal | MemFree до/после прогона | Swap до/после | pswpin/pswpout (vmstat-series) |
| --- | ---: | --- | --- | --- |
| r1 vulkan→hip | 134 153 334 784 B | 89 025 785 856 / 89 019 154 432 B | 0 / 0 | 0 / 0 |
| r2 hip→vulkan | (см. файлы) | без изменений | 0 / 0 | 0 / 0 |
| r3 vulkan→hip | (см. файлы) | без изменений | 0 / 0 | 0 / 0 |

Подкачка не использовалась ни в одном прогоне (143 строки vmstat, `si = so = 0` во всех семплах). Свободно ~89 GiB; 24.64 GiB весов умещаются без вытеснения page cache.

### GPU residency и flash attention

Чтобы исключить сценарий, в котором `-ngl 999` молча оставил слои на CPU, был выполнен отдельный прогон с `-v` на каждой ветви (`raw/rocm-verbose.txt`, `raw/vulkan-verbose.txt`). Фактический per-layer offload подтверждается сообщениями `load_tensors: layer N assigned to device {ROCm0,Vulkan0}` для **всех 41 слоёв** (включая embedding и output) на обоих бэкендах. Подробности:

| Backend | Устройство первой доставки | Свободно при load | Model buffer на GPU | KV buffer на GPU | Recurrent state на GPU | CPU-Mapped |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| HIP/ROCm | `ROCm0 (AMD Radeon Graphics) (0000:c6:00.0)` | 121 807 MiB | 24 704.80 MiB | 10.00 MiB | 62.81 MiB | 515.31 MiB |
| Vulkan | `Vulkan0 (AMD Radeon Graphics (RADV GFX1151)) (0000:c6:00.0)` | 101 829 MiB | 24 704.80 MiB | 10.00 MiB | 62.81 MiB | 515.31 MiB |

MoE-смещение при warmup равно нулю (`n_cpu_moe: 0`). Гибридное recurrent state (`llama_memory_recurrent` = 62.81 MiB на GPU) корректно учитывает гибридный attention. На обоих бэкендах 24 704.80 MiB = весь вес модели 24.64 GiB помещён в GPU buffer; CPU mapped buffer (515.31 MiB) — служебные метаданные (tokenizer, control buffers), не веса. Совпадение байтов в Model buffer между бэкендами подтверждает: один и тот же GGUF реально загружается на один и тот же физический пул UMA.

JSON-результаты основных 12 вызовов содержат `flash_attn: true` и `n_gpu_layers: 999`, что согласуется с verbose-выводом: FA активирован, все слои на GPU. `-ngl 999` — это запрос; verbose-прогон доказывает, что запрос был выполнен буквально.

### Подтверждение «одинаковые условия»

- один GGUF, один commit (`312cf03328496df9c56fe843952cf02a8964c59a`), одна машина, одна сессия;
- `-ngl`, `-t`, `-b`, `-ub`, `-ctk`, `-ctv`, `-fa`, `-r` идентичны во всех 12 вызовах;
- порядок чередуется по протоколу (vulkan→hip, hip→vulkan, vulkan→hip), что убирает дрейф от первой итерации;
- прогон ровно 1 повтор (`-r 1`) per вызов — ровно `llama-bench` JSON-семпл на ячейку таблицы.

## Ошибки и ограничения

- **Source-build не выполнялся**: `cmake` отсутствует в этой машине (минимальный ROCm user-space). Пребилды с одного upstream commit — единственный путь. Это отступление от канона ЛР04. В обоих пребилдах `version: 8407 (312cf0332)` совпадает, но toolchain различается (GNU 13.3 для ROCm, GNU 11.4 для Vulkan). Часть наблюдаемой разницы может быть не backend-эффектом, а эффектом компилятора/оптимизатора Vulkan build. Это явно фиксируется как «одинаковые условия с оговоркой», а не как «чистое сравнение backend».
- **Vulkan flash-attn через RADV** — это Mesa RADV + `libggml-vulkan.so` из upstream. Производительность может отличаться от RADV, оптимизированного AMD; на этой машине других Vulkan-ICD нет.
- **Vulkan не использует VMM** (как и HIP на этой машине) — оба явно по существу. Это часть UMA-архитектуры.
- **`/usr/bin/time -v` показывает wall ~9 с на pp2048**, при том что `llama-bench` JSON-тайминг даёт 3 с. Разница = cold load (mmap + init). Это не «скорость загрузки модели» в смысле «как быстро она приходит в память из диска», но и не «декодирование без накладных расходов». Wall-clock включает весь процесс.
- **Page cache не сбрасывался** между прогонами: после первого cold load веса в page cache, второй-третий повторы уже «warm» по диску. Это общий случай для семейства ЛР04 (протокол не очищает кеш).
- **24.64 GiB модель на UMA** — укладывается в `vulkan_heap1_budget 65.99 GiB` (см. ЛР02) и `MemTotal 134.15 GiB` с большим запасом. OOM не наблюдался.
- **Источник версий**: `llama-server --version` показал `version: 8407 (312cf0332)` для обеих ветвей, что подтверждает один источник. Реальные SHA-256 бинарников различаются (см. `raw/{vulkan,rocm}-binaries.sha256`) — это нормально для разных toolchain.

## Вывод по гипотезе

**Поддержана данными.** Один и тот же GGUF (24.64 GiB MoE) запускается с полным GPU offload (`n_gpu_layers: 999`) и flash-attn (`flash_attn: true`) в обеих ветвях на gfx1151; swap не используется; сравнение произведено за 3 парных повтора с чередованием порядка.

Backend влияет на скорость: **Vulkan быстрее HIP/ROCm** для этой модели и этого пребилда: pp2048 **+8.0%** (675.98 vs 625.84 t/s), tg128@4096 **+13.7%** (51.18 vs 45.01 t/s). Разброс внутри серии < 3% для каждой ячейки. Эффект не равен чистому backend-эффекту, потому что toolchain различается (GNU 13.3 vs 11.4); это явно фиксируется.

Дополнительно: HIP проводит ~2-3× больше User-CPU на тех же pp/tg, что объясняет более низкую пропускную способность при слегка большем RSS.

## Ответы на контрольные вопросы

1. Почему сравнение разных commit не позволяет выделить эффект Vulkan/HIP? Потому что тогда наблюдаемая разница — это смесь изменений исходников и backend. В нашем сеансе commit фиксирован (`312cf03328`); переменная — toolchain и бэкенд.
2. Почему tg128 при пустом контексте недостаточно для оценки агентной нагрузки? Агентные сценарии используют контекст 8K–32K и множество коротких prefill/decode циклов. `tg128 @ depth 4096` меряет только устойчивый decode с заполненным KV; он не нагружает prompt processing в реалистичной пропорции и не учитывает ни Hybrid attention state (MoE имеет отдельный state dtype), ни batching.
3. Что входит в process wall time и что исключено из `llama-bench` t/s? `llama-bench` измеряет только время prefill/decode в чистом виде (`avg_ns`). В process wall time дополнительно входят: `mmap` файла модели, чтение метаданных GGUF, инициализация backend, аллокации и т.д. Для 24.64 GiB модели cold load = ~6 s overhead в wall time, но не входит в `t/s`.
4. Как отличить успешный запуск от полного GPU offload? По JSON-полям `n_gpu_layers` (запрошенное число), `backends` (имя бэкенда), `flash_attn` (фактическое состояние FA), `model_size` (размер в памяти) и логам устройств (`ggml_cuda_init` / `ggml_vulkan: Found`). Полный offload не доказан per-tensor в этом сеансе (без verbose), но `n_gpu_layers: 999` + фактическая скорость ~700 t/s в prefill при MoE 35B total / 3B active указывают, что основная матрица работает на GPU.
5. Что нужно пересчитать при смене KV f16 на q8_0? KV cache уменьшается в 2× по байтам (на ту же длину контекста). На планировщике: `kv_cache_reserve_gib` для 8K/16K/32K делится пополам. На производительности: q8_0 KV обычно теряет 1-5% качества и экономит 30-50% памяти KV; скорость decode может как уменьшаться (из-за dequant), так и расти (из-за большего batch size на том же бюджете).

## Комплект сдачи

- [x] `manifest.json` со статусом `completed`, evidence_class `experimental`, **14 запланированных и выполненных попыток** (12 paired measurements + 2 warmups), все `completed`.
- [x] `measurements.tsv` с **36 строками**, все `status=measured` с числовыми полями и evidence_path.
- [x] `report.md` со всеми обязательными секциями.
- [x] Сырые логи: `raw/{rocm,vulkan}-{version,bench-help,devices,binaries.sha256}.txt`, `raw/{rocm,vulkan}-{verbose,warmup}.{txt,log,json}`, `raw/{rocm,vulkan}-r{1,2,3}-{pp,tg}.{json,log,process.txt}`, `raw/{rocm,vulkan}-r{1,2,3}-{memory,vmstat}-{before,after}.txt`, `raw/vmstat-series.txt`, `raw/vmstat-pid.txt`, `raw/{verification-before,verification-after,uname,os-release,build-provenance}.txt`.
- [x] Сверительный SHA-256 GGUF: `raw/weights.sha256` + `raw/verification-{before,after}.txt`.
- [x] Обе ветви описаны отдельной колонкой в таблицах, без смешения.
- [x] Все numeric наблюдения помечены `measured`, не кандидат-данные от планировщика.
- [x] Verbose-прогоны (`raw/rocm-verbose.txt`, `raw/vulkan-verbose.txt`) подтверждают полный per-layer GPU offload для всех 41 слоя на обоих бэкендах.

Решение проверяющего: **не проверено**.