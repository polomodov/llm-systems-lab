# OpenCode: адаптер лаборатории

Пошаговое задание по слоям конфигурации, реальному T002, неизвестным метрикам и независимой оценке: [ЛР12 — OpenCode](../../docs/labs/LAB12-opencode.md).

Адаптер поддерживает интерфейс CLI v1, сверенный **20.09.2026**. Документация продукта не подтверждает работу конкретного образа; реальный запуск и его версия должны попасть в запись прогона.

20.09.2026 выполнена инфраструктурная проверка на Docker Engine 29.5.2 / Linux arm64: образ собран, `opencode --version` вернул `1.18.29`, `opencode run --help` отработал с отключённой сетью. Пакет содержит `postinstall`; Dockerfile выполняет его внутри образа. Ключи не передавались, запросы к модели не выполнялись.

```bash
docker build --build-arg HARNESS_VERSION=1.18.29 -t harness-lab/opencode:1.18.29 -f experiments/opencode/Dockerfile experiments/opencode
docker run --rm --network none harness-lab/opencode:1.18.29 opencode --version
docker run --rm --network none harness-lab/opencode:1.18.29 opencode run --help
```

Идентификатор проверенного локального образа: `sha256:d94ef97e160c572b519c2bc03c8b8939a010326ed4907e9989167c0285bb8228`. Это проверка установки, не успешный агентный эпизод. Для серии повторов используют один образ; свежая сборка системных пакетов может изменить его ID.

## Запуск и ограничение бюджета

В адаптере пока нет подтверждённого жёсткого лимита стоимости OpenCode. Обычный запуск с политикой `hard` отклоняется до обращения к модели. Для исследовательского запуска нужно явно выбрать `--budget-mode observed`; это отклонение от обязательного бюджета задачи, которое нельзя смешивать с сопоставимыми прогонами `hard`.

Сборка образа с закреплённой версией описана в [корневой инструкции](../../README.md). Поддержан провайдер Anthropic с ключом из `.env`, переданным оркестратором.

```bash
npm run new-run -- --harness opencode --agent a1-dossier --task T001
RUN_ID='<идентификатор, напечатанный new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/opencode:1.18.29 --model '<точный model ID>' --budget-mode observed
npm run judge-run -- --run "$RUN_ID" --evaluation '<JSON независимой оценки>'
npm run check
```

`observed` не гарантирует итоговую стоимость: текущий адаптер честно помечает её недоступной. Тайм-аут и ограничение шагов не заменяют долларовый лимит. Пригодность артефакта оценивается отдельно, после исполнения.

## Команда и конфигурация

`adapter.mjs` вызывает `opencode run --model anthropic/<ID> --agent build --format json`; prompt передаётся одним аргументом без shell. Файл конфигурации задаётся через `OPENCODE_CONFIG=/control/opencode.json`, автообновление отключено через `OPENCODE_DISABLE_AUTOUPDATE=true`. [CLI v1](https://opencode.ai/docs/cli/).

В `OPENCODE_CONFIG_CONTENT` адаптер задаёт основной и малый model ID, а также `agent.build.steps`. Это runtime-слой поверх файла настроек. [Приоритет конфигурации](https://opencode.ai/docs/config/). По достижении `steps` OpenCode просит модель закончить текстовым ответом; это ограничение агентных действий, не эквивалент `max-turns` Claude Code. [Agent max steps](https://opencode.ai/docs/agents/#max-steps).

Права `read`, `edit`, `bash` и другие задаются `opencode.json`. Эта конфигурация регулирует инструменты внутри контейнера. Изоляцию скрытых проверок обеспечивает отсутствие каталога репозитория в его монтированиях. [Документация permissions](https://opencode.ai/docs/permissions/).

Сеть настраивает оркестратор. OpenCode поддерживает `HTTP_PROXY`, `HTTPS_PROXY`; локальный сервер нужно исключить через `NO_PROXY=localhost,127.0.0.1`. [Документация сети](https://opencode.ai/docs/network/).

## Трасса и неизвестные метрики

JSONL сохраняется целиком. Адаптер извлекает session ID и наблюдаемую причину остановки, но не выдаёт сумму `step_finish` за достоверный итог сессии. В потоке может отсутствовать конечное событие; полнота учёта вспомогательных запросов тоже не подтверждена. `turns`, стоимость и токены остаются неизвестными с объяснением в `metrics_unavailable`. [Код CLI](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/cli/cmd/run.ts), [описание пропуска события](https://github.com/anomalyco/opencode/issues/26855).

Следующий этап интеграции — проверенный экспорт из той же изолированной сессии, покрытие тестами конкретной версии и сверка модели, стоимости и usage. В CLI v1 команда — `opencode export <sessionID>`; не переносить сюда команду `opencode session export` из документации v2. Автоматический экспорт пока не реализован.

```bash
node --test experiments/opencode/adapter.test.mjs
```

Изменения компонентов фиксируются в [реестре](../../docs/harness-ledger.md), результаты — в `NOTES.md` с run ID. Сравнение условий выполняется общей командой `npm run compare -- --runs <run-id-1>,<run-id-2>`; исследовательские отклонения должны сохраняться в отчёте.
