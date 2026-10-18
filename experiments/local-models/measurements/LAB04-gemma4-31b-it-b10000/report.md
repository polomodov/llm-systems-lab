# LAB04 — Vulkan против HIP/ROCm (gemma4-31b-it)

Сессия: `gemma4-31b-it-b10000`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `google/gemma-4-31B-it` |
| Engine | llama.cpp b10000 (ROCm 7.2 / Vulkan) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 61 GPU / 0 CPU; HIP 61 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 201.75, HIP 180.07 t/s
- tg128@4096 median: Vulkan 9.13, HIP 8.52 t/s
- RSS: Vulkan 21365804 KiB, HIP 21537860 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

gemma4-31b-it: offload GPU/CPU Vulkan 61/0, HIP 61/0. pp2048 median Vulkan 201.75, HIP 180.07 t/s. tg128@4096 median Vulkan 9.13, HIP 8.52 t/s. RSS Vulkan 21365804 KiB, HIP 21537860 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
