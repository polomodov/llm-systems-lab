# LAB04 — Vulkan против HIP/ROCm (qwen35-35b-a3b)

Сессия: `qwen35-35b-a3b-overnight`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Qwen/Qwen3.5-35B-A3B` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 41 GPU / 0 CPU; HIP 41 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 712.77, HIP 660.48 t/s
- tg128@4096 median: Vulkan 51.83, HIP 45.18 t/s
- RSS: Vulkan 25817240 KiB, HIP 25953468 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

qwen35-35b-a3b: offload GPU/CPU Vulkan 41/0, HIP 41/0. pp2048 median Vulkan 712.77, HIP 660.48 t/s. tg128@4096 median Vulkan 51.83, HIP 45.18 t/s. RSS Vulkan 25817240 KiB, HIP 25953468 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
