# LAB05 — контекст и инструменты (gemma4-31b-it)

Сессия: `gemma4-31b-it-overnight`. Движок: llama.cpp b8407 (HIP).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `google/gemma-4-31B-it` (Q5_K_M) |
| Engine | llama.cpp b8407 |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`.

## Ход выполнения

| CTX | HTTP cases |
| --- | --- |
| 8192 | не запущено (bench exit 1) |

## Результаты

Числовых наблюдений нет: bench-заполнение не прошло.

## Ошибки и ограничения

llama.cpp b8407 не поддерживает архитектуру gemma4 (`unknown model architecture: 'gemma4'`),
см. `raw/context-8192-bench.log`. Поддержка gemma4 добавлена в llama.cpp после b8407.

## Вывод по гипотезе

Данных недостаточно на b8407. На llama.cpp b10000 (сессия `LAB05-gemma4-31b-it-b10000`)
пройдено 8/8 HTTP-кейсов во всех контекстах 8K/16K/32K.

## Ответы на контрольные вопросы

См. методичку ЛР05.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
