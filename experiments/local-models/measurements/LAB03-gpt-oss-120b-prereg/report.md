# LAB03 — Артефакт gpt-oss-120b (preregistered, проверка SHA-256)

Сессия: `gpt-oss-120b-prereg`. Класс: `protocol`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | agent-harness-lab operator; 2026-10-08 |
| Машина, ОС, kernel | GTR Pro (GTRP112), Ubuntu 24.04.3, `7.0.0-34-generic` |
| Модель/артефакт | `openai/gpt-oss-120b`; GGUF `gpt-oss-120b-MXFP4.gguf` 63 387 346 208 B, SHA-256 `582bd40f…` |
| Репозиторий артефакта | `ggml-org/gpt-oss-120b-GGUF` @ `238abdd290bb874b90a5da1b4549881b7d05c091` |
| Quant / архитектура | MXFP4 / MoE (117B total, 5.1B active) |
| Планируемые контексты | 8192 / 16384 / 32768 (в LAB04/LAB05) |

## Гипотеза и протокол до запуска

Протокол: `raw/protocol.md`, зарегистрирован до проверки (`protocol_recorded_at` = 2026-10-08T15:06:20Z)
отдельным коммитом. Гипотеза: локальная копия совпадает с publisher по размеру и SHA-256.

## Ход выполнения

| Шаг | Действие | Результат |
| --- | --- | --- |
| 1 | Offline `fetch_artifact.py` (без `--download`) | все файлы `verified` |
| 2 | `sha256sum --check raw/weights.sha256` | OK, exit 0 |

## Результаты

- `file_bytes` = 63 387 346 208 B.
- `sha256_match_publisher` = true.
- `sha256sum_check_exit_code` = 0.

## Ошибки и ограничения

- MXFP4 — специальный 4-битный формат; поддержка на gfx1151 проверяется в LAB04/LAB05.
- Реального inference здесь нет — только целостность файла.

## Вывод по гипотезе

**Поддержана данными.** SHA-256 совпал с publisher при повторной offline-проверке.

## Ответы на контрольные вопросы

SHA-256 подтверждает битовую идентичность файла, но не работоспособность MXFP4 backend —
это проверяется в LAB04.

## Комплект сдачи

- [x] `manifest.json` (1 попытка, completed), `measurements.tsv` (4 наблюдения), `report.md`.
- [x] `raw/protocol.md`, `raw/artifact.json`, `raw/fetch_artifact.py`, `raw/verification.json`, `raw/verification.txt`, `raw/weights.sha256`.

Решение проверяющего: **не проверено**.
