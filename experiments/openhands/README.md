# OpenHands

Учебный маршрут: [ЛР17 — OpenHands SDK: Conversation, native tools и независимая оценка](../../docs/labs/LAB17-openhands.md). Работа содержит offline smoke, реальный T002 и разбор различий между итерациями, действиями tools и завершёнными ответами модели.

Статус: **SDK-адаптер реализован; сборка и offline-инициализация проверены 20.09.2026; реальные эпизоды unverified**. Закреплены `openhands-sdk==1.49.2` и `openhands-tools==1.49.2`, Python 3.12.12 и Node.js 24.13.1. Это SDK-профиль OpenHands (`mode=sdk`), а не legacy CLI/runtime image. Компонент реестра — L013.

## Запуск

```bash
docker build -t harness-lab/openhands:1.49.2 \
  -f experiments/openhands/Dockerfile experiments/openhands
npm run new-run -- --harness openhands --agent a2-janitor --task T002
RUN_ID='<ID из new-run>'
npm run prepare-run -- --run "$RUN_ID" --provider anthropic
npm run run -- --run "$RUN_ID" --image harness-lab/openhands:1.49.2 \
  --model '<точный ID модели>' --budget-mode observed
```

OpenAI выбирается через `prepare-run --provider openai`. В LLM передаётся `anthropic/<ID>` либо `openai/<ID>`, ключ берётся из `.env` через профиль координатора. Ключи не записываются в аргументы, runtime config или SDK-трассу. Версия определяется через metadata установленного `openhands-sdk`. На серию сохраняйте один image ID; транзитивные версии устанавливаются при сборке.

## Условия и учёт

- `Agent` и `Conversation.run()` выполняют оригинальный цикл SDK. Подключены native `TerminalTool` и `FileEditorTool`; стандартные Finish/Think добавляются самим SDK. Контекст, системный prompt и события сохраняются исходными.
- `LocalWorkspace` работает **внутри** общего изолированного Docker-контейнера. Docker socket, host home, скрытые проверки и управляющий `run.json` туда не передаются. Пакетный tmux обеспечивает штатный terminal backend; дополнительный контейнер OpenHands не запускается.
- `max_iteration_per_run` ограничивает цикл SDK. Это предел итераций, не обещание ограничения HTTP retries. Native `MaxIterationsReached` сохраняется как причина ограниченного завершения. Внешний timeout ограничивает wall-clock.
- USD учитывается только в режиме `--budget-mode observed`; hard отклоняется до загрузки ключа. Стоимость из `llm.metrics` — оценка SDK. При отсутствии цены или итогового набора usage ноль не придумывается.
- Callback сохраняет native события в `openhands_event`; финальный `lab_openhands_result` содержит metrics, status и conversation ID. Токены суммируются по `token_usages`; `turns` — число завершённых LLM responses, а не число инструментов. При ошибке неполные usage totals остаются неизвестными.
- SDK заполняет model fields метрик из запроса, поэтому `observed_id=null`; такие поля не выдаются за подтверждённую модель ответа. Browser, MCP, delegation и condenser не добавлены. Persistence выключен: все события идут в host trace, временные tool caches остаются в `/tmp`.

## Проверка без API

`node --test experiments/openhands/adapter.test.mjs` проверяет запуск, провайдеров, ограничения и обработку неполных метрик. `run.py --help` импортирует SDK; `--smoke` создаёт `Conversation` и отправляет локальное user-событие для инициализации native tools, затем проверяет native terminal через `printf`, но **не вызывает `run()` или модель**:

```bash
docker run --rm --network none --read-only --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
  --mount "type=bind,src=$PWD/experiments/openhands,dst=/control,readonly" \
  --entrypoint python harness-lab/openhands:1.49.2 /control/run.py --smoke
```

Проверка прошла также с proxy env; SDK, terminal и file editor инициализируются с `/tmp noexec`, отдельный executable cache не нужен.

Первичные источники по тегу: [базовый SDK-пример](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/examples/01_standalone_sdk/01_hello_world.py), [метрики](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/examples/01_standalone_sdk/13_get_llm_metrics.py), [Conversation и предел итераций](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py), [формат TokenUsage](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-sdk/openhands/sdk/llm/utils/metrics.py), [native terminal](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.2/openhands-tools/openhands/tools/terminal/definition.py). После обновления версий необходимо повторить offline smoke и проверку метрик; успешность реального эпизода требует внешнего вердикта.
