# LAB04 — Vulkan против HIP/ROCm (glm-47-flash)

Сессия: `glm-47-flash-overnight2`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `zai-org/GLM-4.7-Flash` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 48 GPU / 0 CPU; HIP 48 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 644.31, HIP 681.53 t/s
- tg128@4096 median: Vulkan 44.24, HIP 38.43 t/s
- RSS: Vulkan 31266060 KiB, HIP 31433744 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

glm-47-flash: offload GPU/CPU Vulkan 48/0, HIP 48/0. pp2048 median Vulkan 644.31, HIP 681.53 t/s. tg128@4096 median Vulkan 44.24, HIP 38.43 t/s. RSS Vulkan 31266060 KiB, HIP 31433744 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
