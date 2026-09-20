# mini-SWE-agent

Учебный маршрут: [ЛР16 — mini-SWE-agent: минимальный native цикл и цена наблюдаемости](../../docs/labs/LAB16-mini-swe-agent.md). Работа содержит offline smoke, реальный T002, независимую оценку и исследование `mini.yaml`, step limits и полноты trajectory.

Статус: **SDK-адаптер реализован; сборка и offline-инициализация проверены 20.09.2026; реальные эпизоды unverified**. Закреплён `mini-swe-agent==2.4.6`, Python 3.12.12 и Node.js 24.13.1 для общего entrypoint. Используются оригинальные `DefaultAgent`, `LitellmModel`, `LocalEnvironment` и встроенный `mini.yaml` с native bash tool calling. Компонент реестра — L012.

## Запуск

```bash
docker build -t harness-lab/mini-swe-agent:2.4.6 \
  -f experiments/mini-swe-agent/Dockerfile experiments/mini-swe-agent
npm run new-run -- --harness mini-swe-agent --agent a2-janitor --task T002
RUN_ID='<ID из new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/mini-swe-agent:2.4.6 \
  --model '<точный ID модели>' --budget-mode observed
```

OpenAI выбирается через `prepare-run --provider openai`; адаптер передаёт LiteLLM `openai/<ID>` либо `anthropic/<ID>`. Ключ берётся из `.env` по выбранному профилю: `OPENAI_API_KEY` или `ANTHROPIC_API_KEY`. Provider prefix добавляется адаптером; в `--model` достаточно точного ID. Используйте один собранный image ID на серию: pin основного пакета не является lock-файлом всех зависимостей.

## Условия и учёт

- Исходный `DefaultAgent.run()` выполняет весь цикл. Подкласс переопределяет только `add_messages` для JSONL-трассы; логика выполнения инструментов, завершения и исправления format errors остаётся upstream.
- `step_limit` — native предел `n_calls`. Встроенный `cost_limit` проверяется **после** траты и может быть превышен, поэтому адаптер отклоняет hard USD и требует `--budget-mode observed`. В этом режиме `cost_limit=0`; внешний wall-clock timeout остаётся действующим.
- `mini.yaml` содержит workflow исправления репозитория. Это свойство данной обвязки, применяемое и к T001/T003; оно зафиксировано версией пакета, а не скрытой заменой общего agent spec. Конфигурация включается в итоговую траекторию.
- Отдельные `mini_message` сохраняют исходные сообщения, `lab_mini_result.trajectory` — полный результат `serialize()`. `turns` берётся из `model_stats.api_calls`, включая неудавшиеся попытки. Итоги токенов/стоимости сообщаются лишь при наличии response usage для каждого такого вызова. Стоимость — оценка LiteLLM; неизвестная цена даёт ошибку upstream вместо выдуманного нуля.
- `response.model` позволяет фиксировать наблюдаемый ID и обнаруживать несколько моделей. `LITELLM_LOCAL_MODEL_COST_MAP=True` использует таблицу установленного пакета без сетевого обновления цен. CLI onboarding и домашние credentials оператора не используются.

## Проверка без API

`node --test experiments/mini-swe-agent/adapter.test.mjs` проверяет выбор провайдера, лимиты, полную и оборванную трассы. `run.py --help` импортирует SDK; `--smoke` создаёт native agent/model/environment и исполняет безвредный `printf` через `LocalEnvironment`, не вызывая модель:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/mini-swe-agent,dst=/control,readonly" \
  --entrypoint python harness-lab/mini-swe-agent:2.4.6 /control/run.py --smoke
```

Offline smoke прошёл также с proxy env; `/tmp` не требует разрешения исполнять файлы. Версия определяется через metadata установленного Python-пакета.

Первичные источники по тегу: [DefaultAgent и step/cost limits](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/agents/default.py), [LiteLLM: raw response, usage и cost](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/models/litellm_model.py), [mini.yaml](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/config/mini.yaml), [LocalEnvironment](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/environments/local.py). Доступность конкретного model ID и результат эпизода проверяются отдельным зарегистрированным прогоном.
