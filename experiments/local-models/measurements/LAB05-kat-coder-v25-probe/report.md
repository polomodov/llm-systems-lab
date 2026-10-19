# LAB05 — контекст и инструменты (kat-coder-v25)

Сессия: `kat-coder-v25-probe`.

Статус: **blocked** (см. `unavailable.completion` в `manifest.json`).
Probe-кампания проверяла только короткий серверный протокол chat/chat-stream/tool/tool-stream
на 8K/16K/32K; полная матрица ЛР05 (long, overflow, cancellation, recovery, offline allowlist)
не выполнялась.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `Kwaipilot/KAT-Coder-V2.5-Dev` |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`.

## Ход выполнения

| CTX | HTTP cases | Замечания |
| --- | --- | --- |
| 8192 | 8/8 | все маркеры LAB_VALUE_42 |
| 16384 | 8/8 | все маркеры LAB_VALUE_42 |
| 32768 | 7/8 | tool-stream-r1 final=`42`, не `LAB_VALUE_42` (raw/ctx32768-tool-stream-r1.final.json) |

## Результаты

См. `measurements.tsv`. Матрица замеров покрывает только `bench` + `chat`/`chat-stream`/`tool`/`tool-stream`
× 2 повтора на 3 контекста. Long, overflow, cancel, recovery и offline allowlist — не выполнялись
(unavailable.* в `manifest.json`).

## Ошибки и ограничения

- **32K tool-stream-r1 не прошёл.** `raw/ctx32768-tool-stream-r1.final.json` содержит
  `content="42"` вместо обязательного маркера `LAB_VALUE_42` (`docs/labs/LAB05-context-tools.md:22-24`).
  `tool-stream-r2` той же сессии вернул `LAB_VALUE_42`. Счёт `8/8` для 32K завышен;
  корректное значение `7/8`.
- **Probe-кампания, не полный замер ЛР05.** Цикл overnight запускал только bench + 4 HTTP-кейса
  × 2 повтора; long/overflow/cancel/recovery/offline-allowlist в этой сессии не зафиксированы.
  Поведение модели в этих кейсах остаётся `unverified`.
- Автоматическая кампания: model-specific sampling/reasoning могут отличаться.

## Вывод по гипотезе

ctx8192: 8/8; ctx16384: 8/8; ctx32768: 7/8 (tool-stream-r1 не вернул маркер).
Полная матрица ЛР05 не выполнялась — статус blocked.

## Ответы на контрольные вопросы

См. методичку ЛР05.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, raw evidence.
- [ ] Полная матрица ЛР05 (long, overflow, cancel, recovery, offline allowlist) — не выполнялась.
- [x] 32K счёт исправлен на 7/8.
