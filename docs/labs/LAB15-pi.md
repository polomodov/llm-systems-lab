# ЛР15. Pi: исходный SDK-цикл, события и воспроизводимый T002

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылка | Завершённая [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `pi`, `mode=sdk`; `@mariozechner/pi-coding-agent@0.73.1`, Node.js `24.13.1` |
| Минимум | Сборка, offline smoke, разбор событий и одна реальная попытка A2/T002 с независимым судьёй |
| Время | Ориентир 2–4 часа оператора плюс сборка и ожидание судьи; agent execution ограничен 900 s |
| Режим | Облачный `anthropic` либо `openai`; точный доступный model ID; `baseline`, USD `observed` |
| Расширения | Три заранее назначенных повтора, T001 replay, T003, `without-spec` |
| Начальное состояние | Эксперимент `not-run`; созданный учебный manifest — `not-started` |

## Цель

Запустить исходную сессию Pi на общем эпизоде и показать по трассе, что адаптер сохраняет native цикл и не считает одно сообщение дважды. Получить независимую оценку результата, отделив качество исправления от успешного запуска SDK и полноты метрик.

## Проверяемая гипотеза

При зафиксированных модели, образе и входах стандартных инструментов Pi и общего agent spec достаточно для выполнения T002 без дополнительных расширений. Условия проверки: одна зарегистрированная попытка, независимый `pass`/`fail`/`partial`, перечень реально использованных инструментов и недоступных метрик. `fail` опровергает достаточность этой конфигурации в этой попытке; один `pass` не доказывает устойчивость результата.

Отдельно проверьте учёт: `message_end` даёт usage завершённого assistant message, а повтор того же сообщения в `turn_end` не должен увеличивать токены. Поле `model` в событиях Pi берётся из конфигурации и не подтверждает модель ответа провайдера.

## Подготовка

Работайте из корня репозитория под обычным пользователем с Node.js ≥22 и доступным Docker Engine. Команды ниже — задания для выполнения; опубликованная лабораторная не означает, что вы уже выполнили их. Создайте отчёт и запишите условия до модельного вызова:

```bash
npm run lab:new -- --lab LAB15 --session my-session
LAB_DIR='experiments/pi/measurements/LAB15-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<точный доступный ID выбранного провайдера>'
IMAGE_TAG='harness-lab/pi:0.73.1'
```

Замените `MODEL_ID` на snapshot, доступный вашему аккаунту; `latest` и семейство вместо точной модели не подходят. Для OpenAI измените `PROVIDER_ID` на `openai` **до** `new-run` и подготовки. В аргументе модели нет `anthropic/` или `openai/`: провайдера передают отдельно. Имена credentials в корневом `.env`: `ANTHROPIC_API_KEY` либо `OPENAI_API_KEY`. Не выводите значения и не копируйте `.env` в отчёт. Координатор передаёт только ключ выбранного профиля; он доступен процессам внутри agent container, что не равно полной изоляции секрета от bash агента.

Прочитайте [профиль](../../experiments/pi/harness.json), [адаптер](../../experiments/pi/adapter.mjs), [runtime](../../experiments/pi/run.mjs), [общий протокол](../method.md) и [порядок независимой оценки](harness-workflow.md). Локальное подключение к Ryzen — отдельное расширение после реализации и приёмки [ЛР08](LAB08-local-bridge.md) для Pi. Облачный минимум этой работы не зависит от bridge.

## Порядок выполнения

1. **Зафиксируйте конфигурацию.** Запишите Git revision, состояние дерева, версии Node/Docker, выбранные provider/model, цель USD 2 из T002, native предел 30 ходов и timeout 900 s. В `report.md` явно укажите: `observed` не останавливает траты на USD 2; это исследовательское отклонение от контрактного hard cap.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/pi/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Проверяйте exit code каждого шага до перехода к следующему. Тесты используют синтетические события, не API и не реальные hidden checks.

2. **Соберите и заморозьте образ, проверьте SDK без сети.** Сборка загружает зависимости; основной пакет закреплён, транзитивные версии фиксирует полученный image ID. Не пересобирайте образ между повторами серии. Общему gateway нужен отдельный образ Node.js:

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/pi/Dockerfile experiments/pi > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/pi,dst=/control,readonly" \
     --entrypoint node "$IMAGE_ID" /control/run.mjs --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint node "$IMAGE_ID" -p \
     "require('/opt/pi/node_modules/@mariozechner/pi-coding-agent/package.json').version" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Ожидаемый признак smoke: сессия и native bash инициализированы, `printf sdk-ready` исполнен; модель не вызвана. Версия должна быть `0.73.1`; `pi --version` в этой версии пишет в stderr, поэтому используем metadata пакета. Зафиксируйте фактический результат, не копируйте ожидаемый в таблицу наблюдений.

3. **Разберите границы native цикла.** В `run.mjs` найдите `createAgentSession`, `session.prompt`, обработчик `turn_end` и `agent.abort()`. Нарисуйте в отчёте последовательность «prompt → ответ → tools → turn_end → продолжение/abort». Отметьте отключённые automatic compaction и retry. Ограничение действует на границе хода Pi; HTTP retries транспорта не становятся универсальными agent turns. Пользовательские plugins и host home не подгружаются. Системный prompt и инструменты создаёт Pi, адаптер не реализует собственный агентный цикл.

4. **Создайте и подготовьте отдельный T002.** Сохраните выданный run ID в отчёте. Не используйте уже подготовленную учебную запись из ЛР01:

   ```bash
   npm run new-run -- --harness pi --harness-version 0.73.1 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Убедитесь, что запись имеет `prepared`, а `inputs/control/harness.json` содержит выбранный provider, неизменённый runtime и его разрешённые API domains. Проверьте manifest и seed commit по ЛР01. Не редактируйте запечатанные inputs и не открывайте `tasks/*/check/` при решении эпизода.

5. **Исполните native сессию и прочитайте результат координатора.** Только этот шаг обращается к модели:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   `awaiting_review` означает окончание исполнения, а не успех T002. При `aborted` сохраните причину; новая попытка требует нового ID. Если выбранного snapshot нет в каталоге Pi, OpenAI fallback может взять transport/context/pricing из известного семейства, сохраняя точный requested snapshot ID; неизвестное семейство даёт ошибку, а не замену модели. Доступность конкретного ID до реального прогона — `unverified`.

6. **Проверьте события и арифметику.** Считайте только host trace, сохранённую координатором. Сводка ниже выводит типы событий, не полный текст сообщений:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/pi-events-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const counts = {};
   for (const e of events) if (typeof e?.type === 'string') counts[e.type] = (counts[e.type] ?? 0) + 1;
   const messages = events.filter(e => e?.type === 'message_end' && e.message?.role === 'assistant');
   console.log(JSON.stringify({ counts, final:events.findLast(e => e?.type === 'lab_pi_result') ?? null,
     assistant_usage:messages.map(e => ({ stopReason:e.message.stopReason, usage:e.message.usage ?? null })) }, null, 2));
   NODE
   ```

   Сопоставьте native `turns`/`compactions` с `lab_pi_result`; входные токены — сумма `input + cacheRead + cacheWrite` завершённых assistant `message_end`, выходные — `output`. `turn_end` не прибавляет вторую копию usage. Стоимость — оценка SDK; при неполном usage/оборванной трассе сохраняйте `null` и причину. `model.observed_id=null` здесь корректен даже при наличии `message.model`: заполненное из запроса поле не является наблюдением ответа.

7. **Получите независимый вердикт.** Для `awaiting_review` сформируйте шаблон и передайте его оценщику вместе с неизменёнными артефактами и manifests, следуя [общему порядку](harness-workflow.md):

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Оценщик вне agent container выполняет T002 hidden-check, заполняет `result`, `evaluator`, `check_output`, сохраняя generated hashes. До его решения следующую команду не выполняйте. Отчёт агента и CLI exit 0 не заменяют проверку.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

8. **Оформите вывод и выберите расширение.** Добавьте run ID в manifest отчёта и наблюдения в [NOTES](../../experiments/pi/NOTES.md). Минимум не требует `pass`: содержательный `fail`/`partial` с независимой оценкой — завершённый эксперимент. `aborted` — материал для диагностики; чтобы закрыть минимум, устраните причину и получите новую оценённую попытку, сохранив старую. Для трёх повторов заранее назначьте три новых слота без отбора удачных. T001 выполняйте с одним frozen source archive, T003 — как аудит входов Pi, `without-spec` — как отдельную парную серию по [ЛР10](LAB10-ablation.md). Для T001/T003 builtin инструменты и системный prompt Pi остаются свойствами той же конфигурации. Порядок создания этих записей приведён в [общем workflow](harness-workflow.md).

## Таблицы результатов

До выполнения измерения остаются пустыми; `not-run` — состояние плана, не verdict зарегистрированной попытки.

| Проверка | План | Фактическое наблюдение | Evidence path |
| --- | --- | --- | --- |
| Пакет/image ID | Pi 0.73.1 / immutable ID | — | — |
| Native smoke | Session + bash без API | — | — |
| Identity | Exact request; observed отдельно | — | — |
| Usage | Только завершённые `message_end` | — | — |
| Ограничение | 30 native turns; 900 s; USD observed | — | — |

| Слот | Run ID | Requested / observed ID | Native turns | Tokens in / out | USD / источник | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Компонент Pi | Зачем нужен | Событие/код, подтверждающие роль | Измерение или ограничение |
| --- | --- | --- | --- |
| Исходный session/tools | — | — | — |
| Abort на `turn_end` | — | — | — |
| Compaction/retry disabled | — | — | — |

## Что сдать

`report.md`, заполненный учебный manifest, таблицы с evidence paths, build/version/smoke/test logs, разбор событий Pi, ссылку на целый `results/runs/<run-id>/` и независимую оценку. Сдавайте inputs/trace/artifacts вместе с `run.json`; одного скриншота final answer недостаточно. В отчёте укажите, какие метрики неизвестны и почему, границу USD и вывод о достаточности исходной конфигурации. Секреты и `.env` не входят в комплект.

## Критерии завершения

- [ ] Закреплены версия, image IDs, provider, exact model, вариант, native лимит, USD policy и timeout.
- [ ] Offline tests/smoke пройдены либо диагностированы; подготовка не раскрывает hidden checks.
- [ ] Есть минимум одна реальная T002-попытка `completed` с независимым `pass`/`fail`/`partial`; остальные начатые попытки сохранены.
- [ ] Продемонстрирован учёт `message_end` без повторного счёта `turn_end`, объяснено `observed_id=null`.
- [ ] Отчёт, raw evidence, ответы и NOTES согласованы; `npm run check` проходит.

Если модель/судья недоступны, сдайте отчёт `blocked` с выполненными шагами и причиной. Это честный промежуточный результат, но не завершённый минимум лабораторной.

## Контрольные вопросы

1. Почему `message_end` и `turn_end` не означают два оплаченных ответа?
2. Что ограничивает `agent.abort()` и какие вызовы нельзя назвать одинаковыми turns разных обвязок?
3. Почему поле `model` в сообщении Pi недостаточно для `observed_id`?
4. Как отключённая compaction влияет на интерпретацию длинной серии?
5. Почему одинаковый package version не заменяет immutable image ID?
6. Чем independent `fail` отличается от `aborted` и успешного offline smoke?

## Источники

Версии и команды этой работы взяты из закреплённых файлов репозитория: [README Pi](../../experiments/pi/README.md), [Dockerfile](../../experiments/pi/Dockerfile), [harness.json](../../experiments/pi/harness.json), [runtime](../../experiments/pi/run.mjs), [adapter tests](../../experiments/pi/adapter.test.mjs), [метод](../method.md), [ledger L011](../harness-ledger.md), [общая инфраструктура](../../experiments/common/README.md). Работа не заявляет совместимость с другими версиями SDK; после изменения версии нужны новая конфигурация, smoke и проверка событий.
