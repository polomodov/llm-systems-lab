# ЛР19. Amp: managed mode, собственный цикл агента и независимая оценка

## Паспорт

| Поле | Значение |
| --- | --- |
| Предварительная работа | [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `amp`, пакет `@ampcode/cli` **0.0.1789920039-gafe14b** |
| Основной маршрут | Облачный provider `amp`, selector `managed:medium`; локальный bridge не требуется |
| Агент и задача | `a2-janitor` / T002 |
| Минимум | Offline smoke с native cache и один реальный T002 с независимой оценкой |
| Расширение | Три новых T002, другие managed modes, T001 replay, T003, абляция |
| Время | Ориентир 2–4 часа, не измеренная продолжительность |
| Начальный статус | `not-run`: описана процедура будущего выполнения |

## Цель

Провести автономную задачу через Amp, сохранив его управляемый выбор моделей, инструментов и подагентов. Получить внешний verdict, исследовать доступную телеметрию и сформулировать вывод о данном deployment без выдуманного фиксированного model ID.

## Проверяемая гипотеза

Закреплённый Amp с `managed:medium` и `--executor local` выполнит T002 внутри контейнерной границы и вернёт итоговый stream-json result для внешней оценки. Успех либо неуспех можно установить независимо от неизвестной underlying модели; выводы о различии собственно harness при одной фиксированной модели из такого прогона получить нельзя. Токены измеримы только при наличии полного итогового usage.

## Подготовка

Нужны Node.js ≥22, Bash, Git, Docker и доступный аккаунт Amp. Координатор запускается обычным пользователем из корня репозитория. `--executor local` означает место исполнения инструментов; он **не означает локальный LLM** и не использует ROCm/Vulkan вашего Ryzen. Проверку Linux x64 выполните самостоятельно: существующий smoke был выполнен на Linux arm64.

Прочитайте [README Amp](../../experiments/amp/README.md), [settings](../../experiments/amp/settings.json), [профиль](../../experiments/amp/harness.json), [протокол](../method.md), `agents/a2-janitor/spec.md` и открытый [контракт T002](../../tasks/T002-repo-janitor/task.md). Решающий агент не читает `tasks/*/check/`; task contracts остаются неизменными.

Выполняйте блоки последовательно в Bash и остановитесь для разбора любой ошибки до следующего этапа:

```bash
npm run lab:new -- --lab LAB19 --session my-session
LAB_DIR='experiments/amp/measurements/LAB19-my-session'
HARNESS_VERSION='0.0.1789920039-gafe14b'
IMAGE_REF='harness-lab/amp:0.0.1789920039-gafe14b'
PROVIDER_ID='amp'
MODEL_ID='managed:medium'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

В `.env` нужен **`AMP_API_KEY`** — access token из настроек Amp, не краткоживущий session token интерактивного login. Не выводите значение и не переносите `.env` в отчёт или container mount. До запуска модели сохраните лимиты T002, `timeout=900 s`, `budget-mode=observed`, одну основную попытку, выбранный managed mode и независимого оценщика. Укажите применимые настройки workspace/account без их секретов: полнота отключения подключённых сервису plugins/MCP до первого эпизода остаётся `unverified`.

## Порядок выполнения

1. **Соберите закреплённый образ.** Amp требует обычного npm `postinstall` для native binary той же версии; не заменяйте Dockerfile установкой с `--ignore-scripts`. Сборка загружает пакеты, но не вызывает модель. При наличии образа разрешается использовать его без повторной сборки, сохранив ID.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/amp > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Проверьте CLI без сети, ключа и вызова execute.** Bun извлекает native addon во временный каталог. Отдельный exec tmpfs необходим даже для `--version`; основной `/tmp` остаётся noexec.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --tmpfs /tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777 \
       --env HOME=/tmp --env TMPDIR=/tmp/harness-native \
       --env XDG_CACHE_HOME=/tmp/harness-native --workdir /tmp \
       "$IMAGE_ID" amp "$FLAG" \
       > "$LAB_DIR/raw/amp-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/amp-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/amp-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/amp/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Проверьте оба файла и коды завершения: версия должна содержать закреплённый ID, а справка — режимы `low`, `medium`, `high`, `ultra`, local executor и stream-json. После `break` smoke незавершён. Отсутствие ключа в execute mode вызывает login flow; в этой работе не запускайте его как offline проверку. Координатор отдельно проверяет наличие credentials до реального контейнера. Старое измерение native cache ≈2,6 MiB из README не является измерением на вашей машине или расходом памяти агента.

3. **Проверьте managed policy и конфигурацию.** Профиль принимает только `managed:low`, `managed:medium`, `managed:high`, `managed:ultra`. Префикс сохраняется в record, а CLI получает `--mode medium` и `--executor local`. Режимы `smart`/`rush` к этой версии не относятся. `model.selection=managed` и `model.lock=true` фиксируют выбор режима, а не веса модели.

   В [settings](../../experiments/amp/settings.json) найдите proxy, отключение обновления, remote thread creation и внешних каталогов skills. В [адаптере](../../experiments/amp/adapter.mjs) найдите private visibility, отключение IDE context и remote control terminal. Объясните, какие account-side настройки этим ещё не доказаны. `AMP_URL` закреплён на `https://ampcode.com/`, профиль разрешает ровно `ampcode.com`; полнота allowlist для авторизованного эпизода требует проверки реальной трассы.

4. **Подготовьте новый T002.** Не подставляйте в Amp точный ID сторонней модели: текущий адаптер его не выбирает.

   ```bash
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Сохраните фактический ID в manifest отчёта и переменную:

   ```bash
   RUN_ID='<ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Убедитесь в состоянии `prepared`. Prompt/spec, settings, адаптер и provider profile запечатаны. Конфигурацию нельзя менять внутри уже подготовленной попытки. Агент видит workspace задачи, а не исходную лабораторию и hidden-check.

5. **Выполните реальный эпизод.** Здесь начинается обращение к сервису с подготовленным ключом:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   Жёсткий USD cap и native turn limit в этом адаптере отсутствуют. `observed` — исследовательское отклонение от USD-ограничения контракта; внешний timeout принудителен. Сохраните любые ошибки сервиса/egress; не добавляйте wildcard и не меняйте settings в запечатанной попытке. Новые настройки, другой mode или исправление профиля требуют нового run ID.

6. **Разберите aggregate и unknown metrics.** Сохраните безопасную сводку record:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   В raw trace найдите итоговый `type: result`, его `subtype`, `is_error`, `num_turns`, при наличии `usage`. Адаптер принимает input tokens только при полном наборе `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, а output — при корректном `output_tokens`. Usage отдельных assistant events повторно не складывается с итогом. Отсутствующие поля остаются `null` с причинами. USD и underlying model ID текущая схема не подтверждает; managed mode не копируют в `observed_id`. Проверьте отдельно ошибки `error_max_turns`, `error_during_execution` и обрыв потока.

7. **Получите внешний verdict.** Нормальная передача оценщику начинается из `awaiting_review`. `aborted` остаётся ошибочной попыткой; retry всегда создаёт новую запись. Если оценщик пока недоступен, не помечайте лабораторную выполненной.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Оценщик по [workflow](harness-workflow.md) проверяет T002 скрытым check вне agent container, не изменяя результаты. Он заполняет `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` с версией проверки и наблюдениями, при необходимости `human_notes`; generated hashes остаются неизменными. `judge-run` импортирует его решение и проверяет целостность, а не решает задачу за судью.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   В отчёт включите `completed` с любым обоснованным verdict, все предыдущие ошибки, ограничения model identity и метрик. Обновите `experiments/amp/NOTES.md` реальными run IDs. Новые компоненты получают ledger row в том же изменении; успех одной попытки не подтверждает полезность компонента без сравнения до/после.

8. **Проведите выбранное расширение.** Основной эпизод остаётся pilot. Для тройки создайте три новых T002 через шаги 4–7 при неизменных mode, images, task inputs, provider, timeout и budget policy. Все начатые исходы входят в анализ.

   ```bash
   SERIES_RUN_IDS='<три новых run ID через запятую без пробелов>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   Для исследования режима заранее выберите, например, `managed:low` или `managed:high` и выполните ещё одну отдельную тройку с новым `MODEL_ID`; не меняйте mode внутри записей. Это сравнение режимов управляемого сервиса, включая возможные изменения моделей и инструментов, а не изолированный эффект одной модели или harness.

   T001 использует единый archive зарегистрированного discovery run с телами/статусами HTTP и общей датой. Если архива ещё нет, выполните отдельный live discovery по [workflow](harness-workflow.md); не включайте его в controlled replay серию.

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl discovery run>'
   AS_OF_DATE='<общая дата YYYY-MM-DD>'
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<новый T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Исполнение — шаг 5, оценка — шаг 7 с методом T001 `rubric` и предусмотренным проверяющим скриптом. Для T003 отдельно подготовьте аудит:

   ```bash
   npm run new-run -- --harness amp --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<новый T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Повторите исполнение и внешнюю `rubric` оценку. T003 для разных harness получает разные конфигурации; единого причинного рейтинга обвязок из этих результатов не следует. Для абляции создайте новый T002 как в шаге 4, подготовьте `--variant without-spec` и повторите шаги 5–7. Полный объём — три baseline и три without-spec по [ЛР10](LAB10-ablation.md); сервисные инструкции Amp остаются частью managed deployment, а границы Docker/gateway сохраняются.

## Таблицы результатов

| Run ID | Task / variant | CLI version / image ID | Managed selector | Статус | Внешний verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Поле | Значение | Единица | Измерение или причина `null` | Evidence |
| --- | --- | --- | --- | --- |
| Ходы итогового result | — | turns | — | — |
| Input + cache buckets | — | tokens | — | — |
| Output tokens | — | tokens | — | — |
| Стоимость | — | USD | — | — |
| Время | — | s | — | — |
| Underlying model ID | — | ID | — | — |

| Условие | Что фиксируется до запуска | Что подтверждено после | Ограничение / evidence |
| --- | --- | --- | --- |
| Managed policy | Явный поддерживаемый mode | — | — |
| Native cache | Exec tmpfs 512 MiB, общий /tmp noexec | — | — |
| Account/workspace settings | Применимый состав без секретов | — | — |
| API egress | ampcode.com через gateway | — | — |

## Что сдать

- Manifest/report LAB19 с гипотезой, условиями, таблицами и контрольными ответами.
- Build/help/version/unit evidence, архитектуру и immutable image IDs; отдельно параметры native cache.
- Все реальные run records, inputs/trace/artifacts, T002 `trace/change.patch`, независимые оценки и compare JSON на точных IDs.
- NOTES, ledger additions при изменении компонентов и объяснение, какие выводы позволяет managed routing. Секреты и `.env` не включаются.

## Критерии завершения

- [ ] Закреплённая версия и допустимые modes подтверждены offline без login flow; unit-тесты проходят.
- [ ] Есть хотя бы один реальный T002 `completed` с независимым verdict; остальные попытки не скрыты.
- [ ] Зафиксированы `managed:<mode>`, provider amp, immutable images, timeout 900 s и observed budget.
- [ ] `model.lock` не истолкован как закрепление underlying весов, `--executor local` — как локальный inference.
- [ ] Usage учитывается только при достаточной evidence, без двойного суммирования; USD и неизвестные model IDs не выдуманы.
- [ ] NOTES отражает реальные наблюдения, `npm run check` проходит; расширения и незавершённые этапы явно отмечены.

## Контрольные вопросы

1. Что именно фиксирует `model.lock=true` для Amp и чем это отличается от model snapshot?
2. Почему `--executor local` не означает выполнение модели на Ryzen?
3. Какие cache buckets нужны для input totals и почему нельзя добавить assistant usage к result?
4. Почему отсутствие `AMP_API_KEY` проверяет координатор до execute mode?
5. Какие переменные меняются вместе с managed mode и как это ограничивает сравнение?
6. Что можно заключить о полезности спецификации после её абляции, если серверные инструкции Amp неизвестны?

## Источники

- [README](../../experiments/amp/README.md), [NOTES](../../experiments/amp/NOTES.md), [профиль](../../experiments/amp/harness.json), [settings](../../experiments/amp/settings.json), [Dockerfile](../../experiments/amp/Dockerfile), [адаптер](../../experiments/amp/adapter.mjs), [тесты](../../experiments/amp/adapter.test.mjs).
- [Протокол](../method.md), [workflow](harness-workflow.md), [реестр L015](../harness-ledger.md), [ЛР09](LAB09-agent-campaign.md), [ЛР10](LAB10-ablation.md).
- Первичные ссылки из исследования репозитория от 20.09.2026: [execute mode](https://ampcode.com/docs/cli/execute-mode), [modes](https://ampcode.com/docs/the-dial), [models and subagents](https://ampcode.com/docs/models-and-subagents), [stream-json](https://ampcode.com/docs/cli/streaming-json), [settings](https://ampcode.com/docs/cli/settings). Работа привязана к закреплённой версии пакета, а не к обновляющемуся сервисному описанию.
