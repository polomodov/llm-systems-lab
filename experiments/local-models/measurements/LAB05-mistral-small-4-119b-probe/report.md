# LAB05 — Контекст и инструменты (mistral-small-4-119b)

Сессия: `mistral-small-4-119b-probe`. Статус: **blocked**.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | opencode probe pipeline; 2026-10-12 |
| Модель | `mistralai/Mistral-Small-4-119B-2603`, UD-Q4_K_M (68.69 GiB) |
| Артефакт | `unsloth/Mistral-Small-4-119B-2603-GGUF@bd93c721…` (LAB03 verified) |
| Engine | llama.cpp b8407 (312cf0332) Vulkan/HIP; стенд Ryzen AI Max+ 395 / gfx1151 |
| Готовность | not started |

## Гипотеза и протокол до запуска

Протокол не создавался: работа не начиналась (см. `unavailable.protocol_before_run`).

## Ход выполнения

Не запущено. Причина — незавершённая LAB04 (HIP-ветвь зависла на загрузке модели),
к 8K/16K/32K и HTTP-протоколу не переходили.

## Результаты

Наблюдений нет (см. `unavailable.measurements` и `raw/dependency.md`).

## Ошибки и ограничения

Зависимость от LAB04-mistral не выполнена. Повтор возможен отдельно на Vulkan.

## Вывод по гипотезе

Данных недостаточно: LAB05 не выполнялся.

## Ответы на контрольные вопросы

- Контекст 8/16/32K и tool/stream round-trip не измерялись, поэтому о поведении модели сказать нечего.

## Комплект сдачи

- [x] manifest.json (blocked), measurements.tsv, report.md, raw/dependency.md.
- [ ] Наблюдения — не выполнены.
