# ЛР17. OpenHands SDK: Conversation, native tools и независимая оценка

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылка | Завершённая [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `openhands`, `mode=sdk`; `openhands-sdk==1.49.2`, `openhands-tools==1.49.2` |
| Среда | Python `3.12.12`, Node.js `24.13.1`; native terminal с tmux в общем Docker-контейнере |
| Минимум | Сборка, native offline smoke, анализ событий/метрик, одна реальная A2/T002 с независимым судьёй |
| Время | Ориентир 2–4 часа оператора плюс сборка/судья; agent execution ≤900 s |
| Условия | Cloud `anthropic` либо `openai`, exact model ID, baseline, USD observed |
| Расширения | Три заранее назначенных повтора, T001 replay, T003 и абляция spec |
| Начальное состояние | Эксперимент `not-run`; учебный manifest — `not-started` |

## Цель

Провести эпизод через исходные `Agent` и `Conversation.run()` OpenHands с native terminal/file editor и исследовать границу между итерацией Conversation, завершённым LLM response и внешним timeout. Получить проверенный результат задачи в общей лабораторной среде, сохранив собственный цикл SDK.

## Проверяемая гипотеза

Конфигурация OpenHands с native `TerminalTool`/`FileEditorTool` и общей спецификацией A2 позволяет выполнить T002 без browser, MCP, delegation или отдельного runtime server. Проверка — независимый `pass`/`fail`/`partial` по одной реальной попытке, сохранённые события инструментов и перечень дополнительных компонентов, если они понадобились. Это гипотеза о данном эпизоде, а не доказательство универсальной достаточности набора tools.

Требование к измерителю: `turns` отражает число завершённых LLM responses из полного `token_usages`; значение `max_iteration_per_run` и число вызовов инструментов не подменяют эту метрику. Configured model fields SDK не считаются наблюдаемой identity провайдера.

## Подготовка

Выполняйте команды из корня репозитория, под обычным пользователем с Node.js ≥22 и Docker Engine. Создайте отчёт до запуска:

```bash
npm run lab:new -- --lab LAB17 --session my-session
LAB_DIR='experiments/openhands/measurements/LAB17-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<точный доступный ID выбранного провайдера>'
IMAGE_TAG='harness-lab/openhands:1.49.2'
```

Для OpenAI поменяйте provider на `openai` до создания записи. Замените placeholder на точный доступный model ID, не `latest` и не плавающий alias. В `--model` не добавляйте provider prefix: адаптер сам передаёт SDK `anthropic/<ID>` или `openai/<ID>`. Корневой `.env` должен содержать нужный `ANTHROPIC_API_KEY` либо `OPENAI_API_KEY`; значения ключей не входят в команды и отчёт. `.env` не монтируется, но credential выбранного provider доступен процессам внутри agent container — это известная граница общей инфраструктуры.

Прочитайте [README OpenHands](../../experiments/openhands/README.md), [профиль](../../experiments/openhands/harness.json), [runtime](../../experiments/openhands/run.py), [адаптер](../../experiments/openhands/adapter.mjs), [метод](../method.md) и [общий порядок оценки](harness-workflow.md). Эта работа исследует **SDK 1.49.2**; legacy CLI/runtime image — другой deployment. Локальный provider для Ryzen пока требует реализации и приёмки [ЛР08](LAB08-local-bridge.md), облачный минимум уже использует существующий маршрут.

## Порядок выполнения

1. **Сохраните условия.** Зафиксируйте T002/A2, variant baseline, provider/model и версию рабочего дерева. Цель T002 — USD 2, но SDK-профиль использует `observed`, так как hard USD cap не реализован. Native `max_iteration_per_run=30` и внешний timeout 900 s записывайте раздельно; итерации не обещают ограничить HTTP retries провайдера.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/openhands/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Каждую следующую фазу начинайте после проверки exit code предыдущей. Эти adapter tests синтетические: реальных API вызовов и hidden checks в них нет.

2. **Соберите SDK-профиль и проверьте native terminal без модели.** Зафиксируйте оба image IDs; одинаковые теги после повторной сборки не гарантируют одинаковые транзитивные зависимости.

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/openhands/Dockerfile experiments/openhands > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/openhands,dst=/control,readonly" \
     --entrypoint python "$IMAGE_ID" /control/run.py --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint python "$IMAGE_ID" -c \
     "from importlib.metadata import version; print('sdk='+version('openhands-sdk')); print('tools='+version('openhands-tools'))" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Ожидаются обе версии `1.49.2`. Smoke создаёт Conversation, отправляет локальное user-событие для инициализации и вызывает native terminal с `printf sdk-ready`; `conversation.run()` и модель не вызываются. Он проверяет работу terminal и инициализацию tools с `/tmp noexec`. Отдельный executable cache и второй контейнер OpenHands не требуются данным профилем. В таблице сохраняйте реально полученный результат, не ожидаемый текст.

3. **Составьте схему исполнения.** По `run.py` отразите цепочку `LLM → Agent(native tools) → Conversation → send_message → run → callback/final metrics`. Покажите, где задаются workspace, iteration limit и `persistence_dir=None`. Workspace работает внутри общего контейнера; Docker socket, host home и скрытые проверки туда не передаются. События сохраняет координатор в host trace, временные tool caches остаются в `/tmp`.

   В отчёте перечислите явно подключённые `TerminalTool`/`FileEditorTool`; стандартные Finish/Think добавляет SDK. Browser, MCP, delegation и condenser в этот профиль не добавлены. Отметьте роль tmux и отличия этой среды от legacy OpenHands server. Не приписывайте адаптеру отсутствующие функции по одному названию продукта.

4. **Создайте новую запись T002 и запечатайте входы.** Перенесите фактически выданный run ID в отчёт:

   ```bash
   npm run new-run -- --harness openhands --harness-version 1.49.2 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Проверьте `prepared`, seed commit, выбранный profile/provider и network policy. После подготовки не изменяйте inputs, model/provider или task contract. Решающий агент не читает `tasks/*/check/`; оценивание происходит позже отдельной стороной. Любое изменение конфигурации означает новую подготовку с новым run ID.

5. **Запустите реальный Conversation и проверьте lifecycle.** На этом шаге начнутся API вызовы:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   Native `MaxIterationsReached` сохраняется как ограниченная остановка; он не означает успех исправления и не тождествен timeout. Нормальное завершение приводит к `awaiting_review`, провайдерная/инфраструктурная ошибка — к `aborted`. Не повторяйте `run` на той же записи и не меняйте `aborted` вручную на успешное состояние.

6. **Разберите события и metrics.** Сводка берёт только необходимые итоговые поля из сохранённой трассы:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/openhands-metrics-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const final = events.findLast(e => e?.type === 'lab_openhands_result');
   console.log(JSON.stringify({ native_events:events.filter(e => e?.type === 'openhands_event').length,
     stopReason:final?.stopReason ?? null, sessionId:final?.sessionId ?? null, error:final?.error ?? null,
     token_usages:final?.metrics?.token_usages ?? null, costs:final?.metrics?.costs ?? null,
     accumulated_cost:final?.metrics?.accumulated_cost ?? null }, null, 2));
   NODE
   ```

   Сопоставьте `openhands_event` с native вызовами terminal/file editor и финальным `lab_openhands_result`. Число завершённых response entries `token_usages.length` при полном успешном наборе задаёт reported turns; это не число tools и не лимит Conversation. Токены — суммы `prompt_tokens`/`completion_tokens`. Цена сообщается только при полном наборе положительных costs и корректном `accumulated_cost`; отсутствие цены не равно нулю. Если final содержит `error` или метрики неполны, суммарные usage остаются неизвестными с причиной.

   Запишите `model.observed_id=null`: SDK заполняет model fields из запроса, поэтому они не доказывают identity фактического ответа. `sessionId` связывает события Conversation, но не идентифицирует модель. В сравнении укажите долю подтверждённых model IDs отдельно, не выдавая request-only за наблюдаемую фиксацию модели.

7. **Получите независимую оценку.** Только для `awaiting_review` создайте чистый шаблон:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   По [общему workflow](harness-workflow.md) внешний оценщик выполняет T002 hidden-check и заполняет `result`, `evaluator`, `check_output`, сохраняя manifests/hashes. До этого решения не запускайте следующую команду. Ответ агента и состояние `finished` не являются независимым verdict.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

   `judge-run` проверяет связь оценки с неизменёнными артефактами, а содержательное решение принимает оценщик. Без него запись остаётся `awaiting_review`. Оценённый `fail`/`partial` допустим как результат лабораторной; ошибка запуска сама по себе не закрывает минимум.

8. **Сдайте анализ и расширьте серию при необходимости.** Запишите все run IDs в report/manifest и [NOTES](../../experiments/openhands/NOTES.md). Для исследования устойчивости заранее назначьте три новых повтора, сохранив модели, images и условия. T001 требует одного frozen source archive; T003 получает снимок именно OpenHands и анализируется как диагностика своих входов. `without-spec` сравнивайте парной серией по [ЛР10](LAB10-ablation.md), не удаляя Docker/gateway или native tool boundaries. Команды дополнительных задач есть в [общем workflow](harness-workflow.md). Добавление condenser/browser/delegation — отдельная изменённая конфигурация с записью в ledger, не продолжение исходного baseline под прежним названием.

## Таблицы результатов

| Проверка | План | Фактическое наблюдение | Evidence path |
| --- | --- | --- | --- |
| SDK/tools версии | 1.49.2 / 1.49.2 | — | — |
| Agent/gateway images | Immutable IDs | — | — |
| Offline Conversation/tools | Native terminal без `run()` | — | — |
| Iteration / time / USD | 30 / 900 s / observed | — | — |
| Identity | Exact request; observed отдельно | — | — |

| Слот | Run ID | Native stop reason | Completed responses | Tokens in / out | USD / источник | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Механизм | Что наблюдалось | Чем это отличается от reported turns | Evidence path |
| --- | --- | --- | --- |
| Conversation iteration limit | — | — | — |
| Terminal/file editor actions | — | — | — |
| `token_usages` | — | — | — |
| External timeout | — | — | — |

`not-run` здесь означает ещё не исполненный слот. Не переносите его в `run.json` вместо валидного lifecycle/verdict и не заполняйте измерения ожидаемыми числами.

## Что сдать

Report/manifest с заранее зафиксированной гипотезой и всеми run IDs, таблицы условий/метрик, build/version/adapter-test/smoke evidence, схему Conversation и разбор событий, полный архив минимум одной оценённой T002 и независимый verdict. Объясните request-only identity и все неизвестные usage/cost. Изменения дополнительных компонентов отражайте в NOTES/ledger; `.env` и ключи в комплект не включайте.

## Критерии завершения

- [ ] Зафиксированы обе версии SDK/tools, image IDs, точная модель/provider и все лимиты.
- [ ] Выполнены adapter tests и offline Conversation/native terminal smoke.
- [ ] Минимум одна реальная T002 завершена независимым `pass`/`fail`/`partial`; сохранены неуспешные начатые попытки.
- [ ] Iterations, tool actions и completed responses разведены; полнота usage и ограничения identity объяснены.
- [ ] Отчёт, evidence, NOTES и контрольные ответы готовы; `npm run check` проходит.

Если препятствие оставило только `aborted`/`awaiting_review`, зафиксируйте его в отчёте `blocked`. Учебный минимум остаётся незавершённым до новой оценённой попытки либо независимого судейства уже полученного результата.

## Контрольные вопросы

1. Почему эта работа исследует SDK-профиль, а не все способы запуска OpenHands?
2. Как соотносятся iteration limit, tool actions и `token_usages.length`?
3. Чем `MaxIterationsReached` отличается от timeout и содержательного `fail`?
4. Почему `Conversation.send_message` в offline smoke ещё не означает обращение к модели?
5. Что подтверждают `sessionId` и configured model fields, а чего они не подтверждают?
6. Почему добавление condenser или delegation создаёт новую конфигурацию для сравнения?

## Источники

Использованы закреплённые файлы проекта: [README OpenHands](../../experiments/openhands/README.md), [Dockerfile](../../experiments/openhands/Dockerfile), [harness.json](../../experiments/openhands/harness.json), [run.py](../../experiments/openhands/run.py), [adapter](../../experiments/openhands/adapter.mjs), [adapter tests](../../experiments/openhands/adapter.test.mjs), [метод](../method.md), [ledger L013](../harness-ledger.md), [общая инфраструктура](../../experiments/common/README.md). Доступность конкретного model ID и успешность эпизода до реального прогона — `unverified`; изменение версии требует отдельной повторной проверки.
