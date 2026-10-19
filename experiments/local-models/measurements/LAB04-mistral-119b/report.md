# ЛР04 — llama.cpp Vulkan и HIP/ROCm

Сессия: `mistral-119b`. Модель: `Mistral-Small-4-119B-2603` UD-Q4_K_M (3 шарда,
MoE 36 слоёв, 128 экспертов / 4 active). Стенд: Ryzen AI Max+ 395 / Radeon 8060S.

Статус: **завершено для Vulkan; HIP — blocked**. Один артефакт, один commit
llama.cpp b8407 (`312cf0332`), два backend-биндинга.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | open (agent); 2026-10-15 |
| Engine | llama.cpp b8407, commit `312cf03328496df9c56fe843952cf02a8964c59a` |
| Vulkan bundle | prebuilt `llama-b8407` (GNU 11.4) |
| HIP bundle | prebuilt `llama-b8407-ubuntu-24.04-rocm-7.2.1-…` (GNU 13.3) |
| Артефакт | `unsloth/Mistral-Small-4-119B-2603-GGUF` @ `bd93c721…`, 3 shard, 73 760 980 544 B, sha256 совпал (см. ЛР03) |
| GPU / backend | Vulkan0 RADV GFX1151; ROCm0 gfx1151 (HIP) |
| KV/FA | f16/f16, `-fa 1`, `-ngl 999`, `-b 512 -ub 256 -t 8` |
| Предыдущие | `LAB03-mistral-119b` |

## Гипотеза и протокол до запуска

Один и тот же GGUF работает с полным GPU offload в обеих сборках; backend может
влиять на скорость prefill/decode. Изменяемый фактор — backend. Константы: commit,
бинарь-семейство, веса, KV, FA, batch, потоки, глубина. Порядок — чередование;
число повторов — 3 на backend. Критерий остановки: OOM/GPU reset/устойчивая
подкачка. Правило: отсутствие ветви — blocker, а не доказательство преимущества.

## Ход выполнения

| Шаг | Действие | Результат | Evidence |
| --- | --- | --- | --- |
| 1 | Проверка SHA всех shards | 3/3 OK | `raw/verification-before.txt` |
| 2 | help/devices/version/binaries обоих бандлов | ок | `raw/*-bench-help.txt`, `raw/*-devices.txt`, `raw/*-binaries.sha256` |
| 3 | Vulkan warmup (`-fa 1`) | pp512 192.39 / tg128 33.15 t/s | `raw/vulkan-warmup.json` |
| 4 | HIP warmup (tiny `-p 64 -n 16`) | не завершился >19 мин, 88% CPU → **blocked** | `raw/hip-blocker.txt`, `raw/hip-loadtest.json` |
| 5 | Vulkan 3 повтора pp2048 и tg128@4096 | все exit=0 | `raw/vulkan-r[1-3]-*.json`, `-process.txt`, `-memory-*`, `-vmstat-*` |

## Результаты

| Backend | Commit / binary SHA | GPU / target | Слоёв на GPU / всего | Quant / KV / FA | Допуск |
| --- | --- | --- | --- | --- | --- |
| Vulkan | `312cf0332` / `raw/vulkan-binaries.sha256` | Vulkan0 RADV GFX1151 | 37/37 (запрошено 999, offload подтверждён скоростью и GTT≈74 GiB) | UD-Q4_K_M / f16,f16 / on | passed |
| HIP/ROCm | `312cf0332` / `raw/hip-binaries.sha256` | ROCm0 gfx1151 | 37/37 загружено (GTT≈74 GiB) | UD-Q4_K_M / f16,f16 / on | **blocked** |

| Backend | Повтор | pp2048, tokens/s | tg128 @ depth4096, tokens/s | Max RSS, KiB | Swap-out delta, pages | Статус / raw prefix |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Vulkan | 1 | 196.88 | 31.37 | 72 190 932 | 115 547 (pp) / 75 039 (tg) | ok / `raw/vulkan-r1-*` |
| Vulkan | 2 | 196.44 | 31.26 | 72 190 572 | 166 092 / 46 836 | ok / `raw/vulkan-r2-*` |
| Vulkan | 3 | 194.24 | 31.28 | 72 192 080 | 128 552 / 93 765 | ok / `raw/vulkan-r3-*` |
| HIP | — | — | — | 54 721 176 (при загрузке) | — | blocked, см. `raw/hip-blocker.txt` |

| Режим | Vulkan median [min; max] | HIP | Ограничения вывода |
| --- | --- | --- | --- |
| pp2048 | 196.44 [194.24; 196.88] | blocked | только Vulkan; сравнение backend невозможно |
| tg128 @ depth4096 | 31.28 [31.26; 31.37] | blocked | то же |

Max RSS ≈ 72 191 000 KiB ≈ 68,9 GiB. `pswpout` растёт на всех повторах
(≈183–650 MiB): на этой UMA-машине вытеснение страниц присутствует, поэтому 32K
надо проверять отдельно (ЛР05). Значения снимались `/usr/bin/time -v` и
`/proc/vmstat` до/после; серия `vmstat` — `raw/vmstat-series.txt`.

## Ошибки и ограничения

- **HIP/ROCm ветвь blocked.** Prebuilt b8407 ROCm грузит 37/37 слоёв на ROCm0
  (GTT достигал ~74 GiB), но первый `llama-bench -p 64 -n 16` не завершился за
  >19 минут при 88% CPU. Это CPU-heavy путь/отсутствие оптимизированных kernels
  для архитектуры `mistral4` на gfx1151. Артефакт — `raw/hip-blocker.txt`,
  `raw/hip-loadtest.json` (незавершён), `raw/hip-loadtest.log`.
- `llama-bench` не печатает loader-строки, поэтому «слоёв на GPU» подтверждается
  скоростью (196 t/s pp у 119B исключает CPU) и ростом GTT, а не строкой
  `offloaded 37/37`. Логи загрузки слоёв будут в ЛР05 (`llama-server`).
- Prebuilt-путь (нет cmake/HIP SDK на машине) — сборка из исходников недоступна;
  toolchain Vulkan (GNU 11.4) и ROCm (GNU 13.3) различаются.
- Формат `-fa` в b8407 — `<0|1>`; применён `-fa 1` (в warmup `-fa on` дал FA
  off, поэтому warmup повторён с `-fa 1`).

## Вывод по гипотезе

**Данных недостаточно для сравнения backend.** Vulkan-ветвь полностью измерена:
pp2048 median 196.44 t/s, tg128@4096 median 31.28 t/s, RSS ≈ 68,9 GiB, с
умеренным swap-out. HIP-ветвь не дала ни одного завершённого замера за >19 минут
на минимальном прогоне, поэтому заявлять направление или величину эффекта backend
нельзя. Это инфраструктурный blocker конкретной связки (prebuilt ROCm b8407 +
mistral4 + gfx1151), а не преимущество Vulkan.

## Ответы на контрольные вопросы

1. **Почему разные commit не позволяют выделить эффект backend?** Меняются сразу
   kernels и версия движка; здесь commit один, но ветвь HIP не отработала.
2. **Почему tg128 при пустом контексте мало для агентной нагрузки?** Decode на
   пустом контексте не включает prefill длинного промпта; агентный шаг — это
   большой prefill плюс генерация.
3. **Что входит в process wall time и что исключено из t/s?** Wall включает
   загрузку модели и старт процесса; `llama-bench` t/s — только измеряемую фазу
   после прогрева.
4. **Как отличить успешный запуск от полного offload?** Нужны loader-логи/GTT и
   скорость; один exit 0 не доказывает residency.
5. **Что пересчитать при KV f16 → q8_0?** Память KV и, возможно, скорость; это
   новая конфигурация, а не исправление прежней.

## Комплект сдачи

- [x] Обе ветви зафиксированы (Vulkan измерен, HIP — воспроизводимый blocker).
- [x] Подтверждён Vulkan GFX1151 и одинаковые настройки.
- [x] Сохранены warmup и три повтора.
- [x] Записаны launch arguments; сравнение не вымышлено.
