# LAB04 — Vulkan против HIP/ROCm (kat-coder-v25)

Сессия: `kat-coder-v25-probe`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Kwaipilot/KAT-Coder-V2.5-Dev` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 41 GPU / 0 CPU; HIP 41 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 714.93, HIP 676.14 t/s
- tg128@4096 median: Vulkan 55.98, HIP 48.60 t/s
- RSS: Vulkan 24614940 KiB, HIP 24761988 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

kat-coder-v25: offload GPU/CPU Vulkan 41/0, HIP 41/0. pp2048 median Vulkan 714.93, HIP 676.14 t/s. tg128@4096 median Vulkan 55.98, HIP 48.60 t/s. RSS Vulkan 24614940 KiB, HIP 24761988 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
