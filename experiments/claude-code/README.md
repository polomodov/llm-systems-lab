# Claude Code: адаптер лаборатории

Пошаговое задание со своим отчётом, Docker smoke, реальным T002, аудитом usage и независимой оценкой: [ЛР11 — Claude Code](../../docs/labs/LAB11-claude-code.md).

Адаптер реализован; реальные результаты появятся только в `results/runs/`. Документация CLI сверена **20.09.2026**, совместимость каждого образа проверяется отдельно. Локальная версия на машине оператора не определяет версию прогона.

20.09.2026 выполнена инфраструктурная проверка на Docker Engine 29.5.2 / Linux arm64: образ собран, `claude --version` вернул `2.1.83 (Claude Code)`, справка CLI открылась с отключённой сетью. Установка с `--ignore-scripts` работает для этой версии. Это проверка установки, не эксперимент с моделью: ключи не передавались, запросы к провайдеру не выполнялись.

```bash
docker build --build-arg HARNESS_VERSION=2.1.83 -t harness-lab/claude-code:2.1.83 -f experiments/claude-code/Dockerfile experiments/claude-code
docker run --rm --network none harness-lab/claude-code:2.1.83 claude --version
docker run --rm --network none harness-lab/claude-code:2.1.83 claude --help
```

Идентификатор проверенного локального образа: `sha256:4d9080ac1909d7e8c49056f0f2ae881e13926c5fc37f398c463bcb42d6117761`. Повторная сборка может дать другой ID из-за базового образа и системных пакетов; для серии прогонов сохраняют один собранный образ.

## Запуск

Сначала соберите образ с закреплённой версией CLI по [корневой инструкции](../../README.md). Ключ провайдера берётся из `.env` оркестратором; сам файл не копируется в workspace. Выберите точный model ID, доступный через используемый API.

```bash
npm run new-run -- --harness claude-code --agent a1-dossier --task T001
RUN_ID='<идентификатор, напечатанный new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/claude-code:2.1.83 --model '<точный model ID>'
npm run judge-run -- --run "$RUN_ID" --evaluation '<JSON независимой оценки>'
npm run check
```

`judge-run` импортирует внешнюю оценку после исполнения. Успешное завершение CLI само по себе не означает `pass`. Оценщик работает вне агентного контейнера; критерии скрытой проверки нельзя добавлять в prompt.

## Что добавляет адаптер

`adapter.mjs` строит массив аргументов для запуска без shell: `claude -p`, явная модель, `--output-format stream-json --verbose`, лимиты `--max-turns` и `--max-budget-usd`. Права задаются через `--permission-mode dontAsk` и `/control/settings.json`, стандартные источники настроек отключены через `--setting-sources ''`. `DISABLE_AUTOUPDATER=1` отключает фоновое обновление. Источники: [CLI](https://code.claude.com/docs/en/cli-reference), [переменные окружения](https://code.claude.com/docs/en/env-vars).

`settings.example.json` — вход для подготовки контейнера. Файловую границу создаёт оркестратор: агент получает workspace, но не каталог репозитория со скрытыми проверками, метаданными результатов и файлом `.env`. Конфигурация инструментов работает внутри этой границы; скрытые проверки в контейнер не монтируются.

Прокси задаёт оркестратор через `HTTP_PROXY` / `HTTPS_PROXY`. Эти переменные поддерживаются CLI по [документации сети](https://code.claude.com/docs/en/network-config). Правила доступа к сети применяются отдельно от правил инструментов.

## Учёт результата

Парсер извлекает последний итоговый `result`; поддерживает JSONL, массив сообщений и единичный JSON. Источник формата — [официальный SDK parser](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/message_parser.py).

- `turns` — `num_turns`, `cost_usd` — `total_cost_usd`.
- `tokens_in` включает обычный вход, чтение и запись prompt cache. `tokens_out` берётся из output tokens. Если есть полная `modelUsage`, используется её сумма по моделям; `usage` повторно не прибавляется.
- Модель основного ответа проверяется по `assistant.message.model`; запрошенная модель и наблюдаемая модель — разные свидетельства. Отсутствие наблюдаемого ID не подтверждает выбор модели.
- Отсутствующие значения не заменяются нулями. Причины сохраняются в `metrics_unavailable`; обрыв без итогового сообщения даёт `trace_incomplete`.

Стоимость сообщает CLI. Она не является независимой сверкой биллинга. Полноту вспомогательных запросов и поведение лимитов конкретной версии следует подтвердить первым реальным прогоном. [Типы usage официального SDK](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py).

Проверка парсера без модели и API:

```bash
node --test experiments/claude-code/adapter.test.mjs
```

Обоснование компонентов и план их удаления фиксируются в [реестре](../../docs/harness-ledger.md), наблюдения — в `NOTES.md` с run ID.
