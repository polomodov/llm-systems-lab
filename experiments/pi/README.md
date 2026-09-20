# Pi (pi-mono)

Учебный маршрут: [ЛР15 — Pi: исходный SDK-цикл, события и воспроизводимый T002](../../docs/labs/LAB15-pi.md). Работа содержит offline smoke, реальный эпизод, независимую оценку и задания по учёту native событий.

Статус: **SDK-адаптер реализован; сборка и offline-инициализация проверены 20.09.2026; реальные эпизоды unverified**. Закреплён `@mariozechner/pi-coding-agent@0.73.1`, Node.js 24.13.1. Используется исходный `createAgentSession`: системный prompt, инструменты и цикл Pi. `run.mjs` только настраивает сессию, передаёт prompt, сохраняет события и останавливает цикл на границе ходов. Компонент реестра — L011.

## Запуск

```bash
docker build -t harness-lab/pi:0.73.1 -f experiments/pi/Dockerfile experiments/pi
npm run new-run -- --harness pi --agent a2-janitor --task T002
RUN_ID='<ID из new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/pi:0.73.1 \
  --model '<точный ID модели>' --budget-mode observed
```

Для OpenAI задайте `prepare-run --provider openai`. Ключ выбранного провайдера читается только из `.env`: `ANTHROPIC_API_KEY` либо `OPENAI_API_KEY`. Общий координатор изолирует контейнер, сохраняет снимок и передаёт `/control/run.mjs`; локальный запуск SDK на машине оператора не нужен. Образ закрепляет основной пакет, итоговый image ID фиксирует разрешённые при сборке транзитивные зависимости. Используйте один образ на серию.

## Условия и учёт

- `budget-mode observed` обязателен: SDK не гарантирует жёсткий предел USD.
- Число ходов ограничено через native `agent.abort()` после `turn_end`, прежде чем начнётся следующий ход с моделью. Автоматические compaction и retry отключены, чтобы не добавлять вызовы вне этого счётчика. HTTP-повторы внутри провайдера не равны отдельным ходам.
- Модель выбирается по точному ID в каталоге SDK. У OpenAI каталог может содержать только имя семейства: для ID с суффиксом `YYYY-MM-DD` адаптер берёт transport/context/pricing metadata семейства, но отправляет **исходный точный snapshot ID**. Неизвестное семейство вызывает ошибку; перехода на другую модель нет. Цены семейства являются оценкой SDK, а не счётом провайдера.
- Трасса содержит исходные события SDK и один `lab_pi_result`. Суммируются только завершённые assistant `message_end`; дубли в `turn_end` не учитываются. Входные токены включают cache read/write. При оборванной трассе или неполном usage неизвестные итоги не заменяются нулями.
- Поле `model` в сообщениях Pi заполняется из переданной конфигурации, поэтому оно **не доказывает** фактический ID ответа провайдера: `observed_id=null`. Подагенты не добавлены; плагины пользователя с host не монтируются. Сравнение с иной конфигурацией compaction требует отдельной серии.

## Проверка без API

`node --test experiments/pi/adapter.test.mjs` проверяет аргументы, запрет USD cap, snapshot ID, полную/оборванную трассу. `run.mjs --help` импортирует SDK; `--smoke` создаёт настоящую сессию и проверяет native bash через `printf`, без `prompt()` и без обращения к модели:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/pi,dst=/control,readonly" \
  --entrypoint node harness-lab/pi:0.73.1 /control/run.mjs --smoke
```

`pi --version` в этой версии пишет в stderr. Поэтому координатор получает версию установленного пакета через `node -p`, как указано в `harness.json`. Offline-проверка выполнена также с `HTTP_PROXY`, `HTTPS_PROXY` и `NODE_USE_ENV_PROXY=1`; отдельный исполняемый cache mount не нужен.

Первичные источники, сверенные по тегу: [SDK](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/coding-agent/docs/sdk.md), [события JSON](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/coding-agent/docs/json.md), [подписка и abort](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/agent/src/agent.ts), [Anthropic model/usage mapping](https://github.com/badlogic/pi-mono/blob/v0.73.1/packages/ai/src/providers/anthropic.ts). После смены версии повторить сборку, offline smoke и проверку формата событий. Успешная задача проверяется только реальным зарегистрированным эпизодом и независимым вердиктом.
