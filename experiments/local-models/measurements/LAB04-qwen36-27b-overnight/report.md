# LAB04 — Vulkan против HIP/ROCm (qwen36-27b)

Сессия: `qwen36-27b-overnight`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Qwen/Qwen3.6-27B` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 65 GPU / 0 CPU; HIP 65 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 255.63, HIP 283.01 t/s
- tg128@4096 median: Vulkan 10.71, HIP 10.28 t/s
- RSS: Vulkan 19235348 KiB, HIP 19372688 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

qwen36-27b: offload GPU/CPU Vulkan 65/0, HIP 65/0. pp2048 median Vulkan 255.63, HIP 283.01 t/s. tg128@4096 median Vulkan 10.71, HIP 10.28 t/s. RSS Vulkan 19235348 KiB, HIP 19372688 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
