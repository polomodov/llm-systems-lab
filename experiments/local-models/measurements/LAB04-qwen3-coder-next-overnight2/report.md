# LAB04 — Vulkan против HIP/ROCm (qwen3-coder-next)

Сессия: `qwen3-coder-next-overnight2`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Qwen/Qwen3-Coder-Next` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 49 GPU / 0 CPU; HIP 49 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 428.95, HIP 420.41 t/s
- tg128@4096 median: Vulkan 46.86, HIP 40.96 t/s
- RSS: Vulkan 55523976 KiB, HIP 55650792 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

qwen3-coder-next: offload GPU/CPU Vulkan 49/0, HIP 49/0. pp2048 median Vulkan 428.95, HIP 420.41 t/s. tg128@4096 median Vulkan 46.86, HIP 40.96 t/s. RSS Vulkan 55523976 KiB, HIP 55650792 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
