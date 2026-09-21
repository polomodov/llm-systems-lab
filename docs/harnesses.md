# Матрица обвязок

Для каждой из девяти обвязок подготовлена отдельная [лабораторная ЛР11–19](labs/README.md) с командами сборки, smoke, модельным эпизодом и независимой оценкой. Облачный учебный маршрут не требует локального provider bridge.

Состояние интеграции на **20 сентября 2026 года**. Все девять обвязок подключены к общей подготовке, Docker-запуску, записи трассы и независимой оценке. Установка и offline smoke проверяют инфраструктуру; успешность задач с реальным провайдером остаётся **unverified**, пока нет завершённых записей в `results/runs/`.

| Обвязка | Проверенный pin | Интерфейс | Провайдер / переменная `.env` | Выбор модели | Лимиты |
| --- | --- | --- | --- | --- | --- |
| [Claude Code](../experiments/claude-code/README.md) | 2.1.83 | CLI JSONL | Anthropic / `ANTHROPIC_API_KEY` | Явный ID | Ходы и USD через CLI |
| [OpenCode](../experiments/opencode/README.md) | 1.18.29 | CLI JSONL | Anthropic / `ANTHROPIC_API_KEY` | Явный ID | Steps advisory; USD observed |
| [Codex](../experiments/codex/README.md) | 0.155.1 | `codex exec --json` | OpenAI / `CODEX_API_KEY` | Явный ID | Внутренние ходы и USD недоступны |
| [Antigravity CLI](../experiments/antigravity-cli/README.md) | 1.2.7 | `agy` headless JSONL | Google / `GEMINI_API_KEY` | Явный ID через direct Gemini API | Внутренние ходы и USD недоступны |
| [Pi](../experiments/pi/README.md) | 0.73.1 | Native SDK `createAgentSession` | Anthropic или OpenAI / соответствующий API key | Явный ID | Предел ходов; USD observed |
| [mini-SWE-agent](../experiments/mini-swe-agent/README.md) | 2.4.6 | Native SDK `DefaultAgent` | Anthropic или OpenAI / соответствующий API key | Явный ID | Native step limit; USD observed |
| [OpenHands](../experiments/openhands/README.md) | SDK/tools 1.49.2 | Native SDK `Conversation` | Anthropic или OpenAI / соответствующий API key | Явный ID | Native iteration limit; USD observed |
| [Copilot CLI](../experiments/copilot-cli/README.md) | 1.0.86 | Headless CLI JSONL | Copilot / `COPILOT_GITHUB_TOKEN` | Явный поддерживаемый selector; underlying ID может быть неизвестен | USD и model-turn cap недоступны |
| [Amp](../experiments/amp/README.md) | 0.0.1789920039-gafe14b | CLI stream JSONL | Amp / `AMP_API_KEY` | `managed:low`, `managed:medium`, `managed:high`, `managed:ultra` | USD и model-turn cap недоступны |

## Что означает «проверенный pin»

Пин версии хранится в `experiments/<harness>/harness.json` и является единственным источником. `npm run check` сверяет его с `ARG`/`RUN test` в Dockerfile, с тегом `harness-lab/<id>:<pin>` в корневом README, со строкой этой таблицы и с README обвязки: расхождение в любом из мест — ошибка проверки, а не молчаливый дрейф. При запуске `run.mjs` сравнивает пин запечатанного профиля с версией, которую сообщает сам образ, и прерывает прогон до старта агента при несовпадении.

Класс доказательства по самому образу при этом разный, и таблица его не выравнивает:

- ID проверенного локального образа записан у всех девяти: `claude-code`, `opencode`, `amp`, `copilot-cli` — в README обвязки; `antigravity-cli`, `codex`, `pi`, `mini-swe-agent`, `openhands` — в NOTES.
- Машинный протокол offline smoke есть только у двух: `antigravity-cli` и `codex` (`experiments/<harness>/smoke/2026-09-20.json`). У остальных — текстовая заметка.
- Прогона с реальной моделью нет ни у одной обвязки.

21.09.2026 на машине оператора (Docker Engine 29.5.2, host darwin/arm64) version-команда каждого из девяти собранных образов вернула ровно закреплённый пин. Это наша проверка установки без ключей и без запросов к провайдеру, а не результат задачи.

Установка в образах по умолчанию идёт с `--ignore-scripts`. Три исключения задокументированы прямо в Dockerfile и проверены в собранных образах 21.09.2026: `opencode` (postinstall выбирает platform binary), `amp` (postinstall размещает native binary), `pi` (в дереве зависимостей `koffi` собирает native binding через install script).

Во всех случаях действует внешний timeout. Восемь обвязок требуют явного `--budget-mode observed`: отсутствие обязательного USD cap не скрывается. Это исследовательские попытки с отклонением от бюджета задачи; они не объединяются с политикой `hard`. Семантика native step/iteration у SDK может отличаться: сырые события сохраняются для интерпретации, счётчики разных видов не выдаются за одну универсальную метрику.

## Профили и воспроизводимость

Источник машинной конфигурации — `experiments/<harness>/harness.json`. В нём закреплены команда проверки версии, файлы конфигурации/runtime, провайдеры, имена credentials, точные сетевые домены, политика модели и доступные лимиты. `npm run harnesses` показывает их без чтения ключей.

Провайдер выбирается при `new-run --provider ...` либо `prepare-run --provider ...`; без явного выбора используется default profile. Он сохраняется в snapshot и run.json. Нельзя переключить провайдера на стадии run, сохранив старую сетевую политику. В контейнер передаются только имена credentials выбранного провайдера; содержимое `.env` целиком и настройки пользователя не монтируются.

SDK-адаптеры используют собственные циклы соответствующих проектов, а не общий самодельный агент. `harness.mode=sdk` отличает их от CLI. Версия библиотеки определяется внутри конкретного Docker image. Images собираются с pin; для серии сохраняют один image ID. Runtime-файлы и адаптер тоже входят в sealed inputs.

Copilot и Amp извлекают нативные модули при старте: у этих двух профилей есть `native_cache=true`. Координатор создаёт отдельный непривилегированный exec tmpfs `/tmp/harness-native` ёмкостью 512 MiB и задаёт `TMPDIR`/`XDG_CACHE_HOME`; весь корневой образ остаётся read-only. Это условие учтено в реестре и проверено offline под UID 1000. Другие профили не получают этот mount.

## Модель и измерения

Запрошенная модель, `model.provider`, `model.selection`, `model.lock` и наблюдаемая модель — отдельные поля. Amp задаёт managed selector и `lock=true`: это не обещание конкретной underlying модели. Такие серии не попадают в группы с явным model ID. Copilot selector также не считается подтверждением exact snapshot ответа. Отсутствующие наблюдения остаются `null` с причинами.

CLI/SDK по-разному учитывают cache, вспомогательные вызовы и стоимость. Парсеры берут только подтверждённые итоговые значения; отсутствующие поля не заменяются нулём. Ошибочный или оборванный terminal stream при exit 0 считается aborted. `awaiting_review` возникает после законченного исполнения, а `pass` — только после внешней оценки.

T003 готовит allowlist-снимок для каждой из девяти обвязок. Файлы `/control` отображаются в `.harness/control/`, рядом доступны исходный адаптер, профиль, runtime и общие границы координатора. Скрытые проверки и секреты в этот снимок не входят.

## Первичные источники и проверки

Для исследования открытых локальных моделей на Ryzen AI Max+ 395 / 128 GB / Linux подготовлена [отдельная кампания](local-models.md). Первые кандидаты на интеграцию — Pi, mini-SWE-agent, OpenCode и OpenHands. Это не готовый `local` provider: адаптация сетевого bridge, снимка настроек backend и условий сравнения ещё необходима. Возможность custom API в upstream не означает проверенную поддержку локального сервера текущим адаптером.

- Claude: [CLI reference](https://code.claude.com/docs/en/cli-reference), [официальные типы SDK](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py).
- OpenCode: [CLI v1](https://opencode.ai/docs/cli/), [network](https://opencode.ai/docs/network/). Команды v1 и v2 нельзя смешивать.
- Codex: [non-interactive mode](https://developers.openai.com/codex/noninteractive), [config reference](https://developers.openai.com/codex/config-reference).
- Antigravity: [install](https://antigravity.google/docs/cli/install/), [headless](https://antigravity.google/docs/cli/headless/). Проверен отдельный `agy`; предположения о переименовании Gemini CLI не нужны.
- Pi: [upstream coding agent](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).
- mini-SWE-agent: [upstream](https://github.com/SWE-agent/mini-swe-agent).
- OpenHands: [Software Agent SDK](https://github.com/OpenHands/software-agent-sdk).
- Copilot: [официальный CLI](https://github.com/github/copilot-cli).
- Amp: [manual](https://ampcode.com/manual).

Точные версии исходников, команды сборки, offline ограничения и наблюдения перечислены в README/NOTES соответствующего каталога. Проверки установки не создают фиктивных agent-run records. Для измерений нужны доступ выбранного аккаунта к API, реальный эпизод и внешний вердикт.
