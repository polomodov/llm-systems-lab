# LAB04 — Vulkan против HIP/ROCm (gemma4-31b-it)

Сессия: `gemma4-31b-it-overnight`. Движок: llama.cpp b8407.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `google/gemma-4-31B-it` (Q5_K_M) |
| Engine | llama.cpp b8407 |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`.

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| offload-proof Vulkan | ошибка загрузки |
| offload-proof HIP | ошибка загрузки |

## Результаты

Числовых наблюдений нет.

## Ошибки и ограничения

Обе ветви b8407 завершились `error loading model architecture: unknown model architecture: 'gemma4'`
(`raw/vulkan-offload-proof.log`, `raw/hip-offload-proof.log`). Закреплённый b8407 опубликован 2026-03-18,
а поддержка gemma4 появилась в llama.cpp в апреле 2026.

## Вывод по гипотезе

Данных недостаточно на b8407: архитектура не поддержана. Повторено на llama.cpp b10000
(сессия `LAB04-gemma4-31b-it-b10000`), где обе ветви полностью выгружают модель на GPU.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
