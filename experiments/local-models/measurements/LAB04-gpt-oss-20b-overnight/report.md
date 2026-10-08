# LAB04 — Vulkan против HIP/ROCm (gpt-oss-20b)

Сессия: `gpt-oss-20b-overnight`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `openai/gpt-oss-20b` |
| Engine | llama.cpp b8407 (312cf0332) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered).

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof | Vulkan 25 GPU / 0 CPU; HIP 25 / 0 |
| paired repeats | 3×2 |

## Результаты

- pp2048 median: Vulkan 1087.03, HIP 1219.45 t/s
- tg128@4096 median: Vulkan 75.30, HIP 63.68 t/s
- RSS: Vulkan 12026764 KiB, HIP 12190932 KiB

## Ошибки и ограничения

Сборки prebuilt разных toolchain.

## Вывод по гипотезе

gpt-oss-20b: offload GPU/CPU Vulkan 25/0, HIP 25/0. pp2048 median Vulkan 1087.03, HIP 1219.45 t/s. tg128@4096 median Vulkan 75.30, HIP 63.68 t/s. RSS Vulkan 12026764 KiB, HIP 12190932 KiB.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
