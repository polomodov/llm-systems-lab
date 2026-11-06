# Pi (pi-mono)

Учебный маршрут: [ЛР15 — Pi: исходный SDK-цикл, события и воспроизводимый T002](../../docs/labs/LAB15-pi.md). Работа содержит offline smoke, реальный эпизод, независимую оценку и задания по учёту native событий.

Статус: **SDK-адаптер реализован; сборка и offline-инициализация проверены 20.09.2026; Pi/local/T002 имеет два независимо оценённых fail и один pass на Ryzen (12–15.10.2026); cloud-эпизоды unverified**. Закреплён `@mariozechner/pi-coding-agent@0.73.1`, Node.js 24.13.1. Используется исходный `createAgentSession`: системный prompt, инструменты и цикл Pi. `run.mjs` только настраивает сессию, передаёт prompt, сохраняет события и останавливает цикл на границе ходов. Компонент реестра — L011.

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

## Local provider bridge — первая реализация LAB08

Для Pi добавлен provider `local` / GGUF / controlled native llama.cpp Metal на macOS и ROCm на Linux. [LAB15 Ryzen](measurements/LAB15-local-ryzen/report.md) содержит оценённые T002; сводный отчёт blocked по предрегистрации повторов. Ниже сохранён пример Apple deployment, чей pilot ожидает независимой оценки. Это отдельная инженерная ветка; прежние cloud providers не меняются. Сначала нужен полный deployment manifest v1, прошедшие LAB32 условия и проверка текущих файлов. Пример исходного manifest: [LAB08 deployment](https://github.com/polomodov/agent-harnesses-exps/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/raw/deployment.json). Абсолютные пути относятся к этому стенду; подставлять другой endpoint или alias после prepare нельзя.

```sh
npm run new-run -- --harness pi --agent a2-janitor --task T002 --provider local --model lab-model
RUN_ID='<реальный ID новой записи>'
npm run prepare-run -- --run "$RUN_ID" --provider local \
  --local-deployment experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/raw/deployment.json
npm run run -- --run "$RUN_ID" --provider local --model lab-model \
  --image harness-lab/pi:0.73.1 --proxy-image node:24.13.1-bookworm-slim \
  --budget-mode observed --timeout 900
```

Runner запускает собственный native server на loopback Mac после проверки weights/executables/всех bundled dylib hashes и завершает только его. Применяются ресурсный и AC guard. Запечатанный supervisor проверяет PID/props/template/context и файлы до/после каждого HTTP-запроса. Изменённый manifest или runtime identity вызывает отказ; cloud fallback отсутствует. Подключение к произвольному уже работающему серверу пока не поддерживается.

Agent container имеет только internal Docker network, 2 GiB RAM и прежние mounts/permissions. Доверенный broker имеет вторую Docker bridge network для публикации host control port только на loopback; он не пересылает CONNECT и не создаёт upstream sockets. Host-worker инициирует reverse control connection с одноразовой capability и пересылает только POST `/v1/chat/completions` на закреплённый endpoint. GET `/health` доступен агенту; `/props`, `/slots`, `/models`, LAN/cloud и control API без capability запрещены. T001/T003 через local provider пока не допущены; публичный source gateway/replay сохранён для cloud.

Pi использует свой `createAgentSession` и native tools. SDK API — `openai-completions`, provider — `local`; это протокол совместимости, без обращения к OpenAI. Публичный dummy marker `harness-local-dummy` нужен ModelRegistry и не передаётся upstream; `.env` не требуется. Настоящий server auth в этом варианте не поддерживается. SDK требует числовые цены, поэтому их нулевые placeholders не считаются стоимостью: `run.json` содержит cost=null с причиной. Tokens берутся из первичного HTTP usage; при его отсутствии SDK zeros отвергаются.

Первый bridge буферизует SSE до finish/DONE; события tool calls сохранены, но поток не отражает реальный TTFT. Request limit 1 MiB, response 4 MiB, один запрос одновременно, upstream deadline 300 s, автоматические retries/compaction отключены. Отмена client connection закрывает собственный upstream request. `awaiting_review` не является pass; независимую оценку импортируют существующим judge-run.

Проверки: `npm test`, `npm run test:docker`, `npm run test:local-docker` (требует обоих pinned images), `npm run check`. Результаты, исходные отказы и статус pilot — в [LAB08 отчёте](https://github.com/polomodov/agent-harnesses-exps/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-provider-bridge-20261009/report.md). Компоненты L024/L025 имеют статус «предложена»; вклад в качество и перенос на другие adapters/platforms не установлены.

После первого настоящего pilot добавлены wall-clock deadline check и отказ при разрыве resource timeline >15 s/движении часов назад. Software/Docker regressions прошли; новая [Apple-квалификация](https://github.com/polomodov/agent-harnesses-exps/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-apple-native-requalification-20261010/report.md) выполнена, её 16K pilot остаётся awaiting_review. [Ryzen-продолжение](https://github.com/polomodov/agent-harnesses-exps/blob/a12e9f430f8b4bd19f1d316811a63b7caca9e4cc/experiments/local-models/measurements/LAB08-ryzen-linux-bridge/report.md) имеет оценённые fail/pass; это другие условия. Guards действуют при возобновлении host и не обещают остановку во время полной его приостановки. Две реальные aborted попытки сохранены в LAB08.
