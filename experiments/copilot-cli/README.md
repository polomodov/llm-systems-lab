# GitHub Copilot CLI: адаптер лаборатории

Практическое задание: [ЛР18 — Copilot CLI, model selector и AI credits](../../docs/labs/LAB18-copilot-cli.md). Включает smoke с native cache, полный T002 с внешним судейством и дополнительные серии.

Реализован локальный CLI-адаптер для общего цикла подготовки, контейнерного запуска, внешней оценки и сравнения. Проверенная версия — `@github/copilot@1.0.86`, дата сверки — **20.09.2026**. Реальных прогонов с моделью пока нет; облачный Copilot coding agent этим адаптером не запускается.

## Сборка и запуск

```bash
docker build --build-arg HARNESS_VERSION=1.0.86 -t harness-lab/copilot-cli:1.0.86 experiments/copilot-cli
docker run --rm --network none harness-lab/copilot-cli:1.0.86 copilot --help
npm run new-run -- --harness copilot-cli --harness-version 1.0.86 --provider copilot --model gpt-5.4 --agent a1-dossier --task T001
RUN_ID='<идентификатор из new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/copilot-cli:1.0.86 --model gpt-5.4 --budget-mode observed
npm run evaluation-template -- --run "$RUN_ID"
```

`gpt-5.4` — пример идентификатора в каталоге Copilot, доступность определяется подпиской. Выбранное имя записывается как запрос к сервису. Оно не доказывает точную версию весов и совпадение с моделью, доступной через прямой API другого провайдера. `auto` запрещён. [Выбор модели и неинтерактивный режим](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference).

Координатор читает только `COPILOT_GITHUB_TOKEN` из `.env`; файл не передаётся агенту. Нужен поддерживаемый GitHub токен с доступом к Copilot, например fine-grained PAT с разрешением Copilot Requests; classic PAT не поддерживается. [Аутентификация](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli).

## Условия эксперимента

Команда использует `--prompt`, JSONL, автоматическое разрешение инструментов внутри внешнего контейнера и `--no-ask-user`. Отключены автоматическое обновление, загрузка инструкций из репозитория, встроенный GitHub MCP, remote control и remote export. Спецификация поступает через общий prompt, поэтому вариант `without-spec` не возвращает её через локальные инструкции. Полный argv сохраняется в снимке адаптера. [Справочник CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).

CLI учитывает AI credits / premium requests, но эти числа нельзя записывать как USD. Жёсткий лимит USD не поддержан, `--budget-mode observed` обязателен. `--max-autopilot-continues` ограничивает продолжения autopilot и не является лимитом ходов модели; адаптер его не подменяет `turns`. Внешний таймаут действует независимо.

`harness.json` разрешает HTTPS CONNECT только к `github.com`, `api.github.com`, `api.githubcopilot.com` и трём плановым адресам `api.individual.githubcopilot.com`, `api.business.githubcopilot.com`, `api.enterprise.githubcopilot.com`. CLI поддерживает `HTTP_PROXY` / `HTTPS_PROXY` — проверено через `copilot help environment`. Адреса соответствуют [официальному списку сетевого доступа](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference) и [плановой маршрутизации GitHub](https://github.blog/changelog/2026-03-02-network-configuration-changes-for-copilot-coding-agent-now-in-effect/). Полнота списка для авторизованного CLI-эпизода **unverified**: при первом запуске проверяется трасса сети; wildcard автоматически не открывается. GHE.com и BYOK требуют отдельного профиля.

CLI распаковывает native addon в кеш. Поэтому профиль включает отдельный `exec` tmpfs `/tmp/harness-native` размером до 512 MiB, `TMPDIR` и `XDG_CACHE_HOME` указывают туда; основной `/tmp` остаётся `noexec`. Это требуется и для проверки версии. При offline `--version` на Linux arm64 кеш занял 161284 KiB (около 157,5 MiB); 128 MiB недостаточно. Проверены лимиты native tmpfs 256 и 512 MiB при `/tmp` 512 MiB и памяти контейнера 2 GiB; 512 MiB оставляет запас для старта. Максимум памяти cgroup в проверке с 256 MiB был около 381,6 MiB. Это измерение запуска CLI, не расход памяти реального эпизода. Скрытые проверки и файлы лаборатории по-прежнему отсутствуют в контейнере.

## Трасса и проверка

В исходном `app.js` установленного пакета `1.0.86` проверены JSONL formatter и фильтр: `assistant.usage` и `session.shutdown` исключены из stdout. Последнее сообщение имеет `type: result`, `sessionId`, числовой `exitCode` и статистику premium requests / времени. Парсер использует именно этот терминатор, а не одноимённую схему Claude. Наблюдаемый ID модели, token totals и USD остаются неизвестными. Полные пары `assistant.turn_start` / `assistant.turn_end` между `session.start` и `result` дают число ходов основного агента; дубликаты ID не считаются повторно. Схема самих событий описана в [официальном SDK](https://github.com/github/copilot-sdk/blob/main/nodejs/src/generated/session-events.ts).

```bash
node --test experiments/copilot-cli/adapter.test.mjs
```

На Docker Engine `29.5.2`, Linux arm64 проверены сборка, `--version`, справка, аргументы адаптера и отказ при отсутствии ключа без сети. Native cache проверен с `--read-only`, UID `1000`, `cap-drop ALL`, `no-new-privileges`. Образ: `sha256:17da822b2853ced41f6986f0f27f10c9e66dd64498bc1cb8be8f612cb5925474`. Это инфраструктурная проверка без API-запроса, а не результат задачи. Основания компонента — [L014 в реестре](../../docs/harness-ledger.md).
