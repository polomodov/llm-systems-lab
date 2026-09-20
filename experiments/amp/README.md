# Amp: адаптер лаборатории

Практическое задание: [ЛР19 — Amp, managed mode и независимая оценка](../../docs/labs/LAB19-amp.md). Включает smoke с native cache, полный T002 с внешним судейством и дополнительные серии.

Реализован локальный CLI-адаптер с явно обозначенной управляемой маршрутизацией моделей. Проверенная версия — `@ampcode/cli@0.0.1789920039-gafe14b`, дата — **20.09.2026**. Реальных эпизодов с моделью пока нет.

## Сборка и запуск

```bash
docker build --build-arg HARNESS_VERSION=0.0.1789920039-gafe14b -t harness-lab/amp:0.0.1789920039-gafe14b experiments/amp
docker run --rm --network none harness-lab/amp:0.0.1789920039-gafe14b amp --help
npm run new-run -- --harness amp --harness-version 0.0.1789920039-gafe14b --provider amp --model managed:medium --agent a1-dossier --task T001
RUN_ID='<идентификатор из new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/amp:0.0.1789920039-gafe14b --model managed:medium --budget-mode observed
npm run evaluation-template -- --run "$RUN_ID"
```

Координатор читает `AMP_API_KEY` из `.env`. Используется access token из настроек Amp, а не краткоживущий session token интерактивного входа. Без ключа сам CLI начинает login flow даже в execute mode; координатор обязан остановить такой запуск до контейнера. [Execute mode и авторизация](https://ampcode.com/docs/cli/execute-mode).

Профиль принимает только `managed:low`, `managed:medium`, `managed:high`, `managed:ultra`. Эти значения проверены по `--help` закреплённой версии. Координатор передаёт адаптеру имя режима без префикса, CLI получает `--mode` и `--executor local`. Модели, системные инструкции, инструменты и подагенты зависят от маршрутизации Amp. Нельзя записывать имя режима как наблюдаемый model ID или считать такой эпизод сравнением одной фиксированной модели через разные обвязки. [Режимы Amp](https://ampcode.com/docs/the-dial), [модели и подагенты](https://ampcode.com/docs/models-and-subagents).

## Условия эксперимента

`settings.json` загружается из `/control/amp-settings.json`: разрешает команды внутри внешней контейнерной границы, отключает обновления, remote thread creation и внешние каталоги навыков. Отдельные флаги отключают IDE-контекст, уведомления и удалённый терминал, выставляют private visibility. Настройки workspace и сервиса могут влиять на Amp; их фактический состав и полнота отключения подключённых аккаунту plugins/MCP **unverified** до первого эпизода. [Конфигурация](https://ampcode.com/docs/cli/settings), [схема настроек](https://ampcode.com/cli-settings.schema.json).

`amp.proxy=http://egress:8080` направляет запросы сервиса через общий шлюз. `AMP_URL` закреплён на `https://ampcode.com/`, разрешён ровно домен `ampcode.com`; оба параметра подтверждены справкой установленного CLI. Полнота сетевого списка для авторизованного локального эпизода **unverified**. Новые адреса добавляются после проверки первичного источника и сетевой трассы, а не через wildcard. Установка использует npm registry; загрузка пакетов выполняется при сборке образа, отдельно от сети эпизода.

Пакет требует `postinstall`, который размещает native binary из пакета той же версии. Bun извлекает native addon во временный каталог: с `noexec /tmp` даже `--version` завершается ошибкой загрузки. Профиль `native_cache` включает только отдельный `exec` tmpfs `/tmp/harness-native` размером до 512 MiB и задаёт `TMPDIR` / `XDG_CACHE_HOME`; основной `/tmp` остаётся `noexec`. При offline `--version` кеш занял 2672 KiB (около 2,6 MiB), максимум памяти cgroup — около 153,8 MiB. Проверены `/tmp` 512 MiB, native tmpfs 512 MiB и память контейнера 2 GiB. Это измерение старта CLI, не памяти реального эпизода; tmpfs расходует память по мере заполнения. Это не открывает агенту данные лаборатории.

Жёсткие ограничения USD и числа ходов у этого адаптера отсутствуют, поэтому требуется `--budget-mode observed`. Таймаут обеспечивает координатор. Управляемая маршрутизация и наблюдаемый бюджет должны учитываться при группировке сравнений.

## Трасса и проверка

Парсер разбирает [официальную stream-json схему](https://ampcode.com/docs/cli/streaming-json). Итоговый `result.num_turns` даёт ходы; `result.usage`, если возвращён, даёт токены. Вход учитывается только при наличии полного набора input/cache buckets; assistant usage не прибавляется повторно. Документированный пример результата не содержит usage, поэтому неизвестные метрики допустимы и сопровождаются причиной. Схема не подтверждает фактические ID маршрутизируемых моделей и стоимость в USD — эти поля остаются неизвестными. Ошибки `error_max_turns` / `error_during_execution` и обрыв различаются.

```bash
node --test experiments/amp/adapter.test.mjs
```

На Docker Engine `29.5.2`, Linux arm64 проверены сборка, `--version`, справка и распознавание аргументов адаптера без сети и ключей. Версия проходит с read-only root, UID `1000`, `cap-drop ALL`, `no-new-privileges` и отдельным native tmpfs. Образ: `sha256:31b165957d2ed53eb0fee4474e7dedb347b31aa3acc146a103c0aad5b3c8be49`. Вызов модели не выполнялся; эти проверки не являются экспериментальным run. Основания компонента — [L015 в реестре](../../docs/harness-ledger.md).
