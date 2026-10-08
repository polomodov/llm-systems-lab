# LAB05 — контекст и инструменты (qwen3-coder-30b-a3b)

Сессия: `qwen3-coder-30b-a3b-overnight`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Qwen/Qwen3-Coder-30B-A3B-Instruct` |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`.

## Ход выполнения

| CTX | HTTP cases |
| --- | --- |
| 8192 | 4/8 |
| 16384 | 4/8 |
| 32768 | 4/8 |

## Результаты

См. `measurements.tsv`.

## Ошибки и ограничения

Автоматическая кампания: model-specific sampling/reasoning могут отличаться.

## Вывод по гипотезе

ctx8192: 4/8; ctx16384: 4/8; ctx32768: 4/8.

## Ответы на контрольные вопросы

См. методичку ЛР05.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
