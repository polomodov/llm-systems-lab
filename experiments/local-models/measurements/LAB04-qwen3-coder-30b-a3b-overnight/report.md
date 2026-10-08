# LAB04 — Vulkan против HIP/ROCm (qwen3-coder-30b-a3b)

Сессия: `qwen3-coder-30b-a3b-overnight`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Qwen/Qwen3-Coder-30B-A3B-Instruct` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 49 GPU / 0 CPU; HIP 49 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 761.10, HIP 458.88 t/s
- tg128@4096 median: Vulkan 66.85, HIP 41.55 t/s
- RSS: Vulkan 21361700 KiB, HIP 21526892 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

qwen3-coder-30b-a3b: offload GPU/CPU Vulkan 49/0, HIP 49/0. pp2048 median Vulkan 761.10, HIP 458.88 t/s. tg128@4096 median Vulkan 66.85, HIP 41.55 t/s. RSS Vulkan 21361700 KiB, HIP 21526892 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
