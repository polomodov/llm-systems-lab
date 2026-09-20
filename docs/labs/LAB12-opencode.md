# ЛР12. OpenCode: слои конфигурации, steps и неизвестная стоимость

## Паспорт

| Поле | Значение |
| --- | --- |
| Обвязка | `opencode`, CLI v1 `opencode-ai@1.18.29` |
| Предпосылка | [ЛР01](LAB01-reproducibility.md), Node.js ≥22, Git, Bash, Docker Engine, непривилегированный пользователь координатора |
| Основной маршрут | Anthropic API, `ANTHROPIC_API_KEY` из `.env`; готовый cloud adapter, без локального bridge |
| Минимальный объём | Parser/config tests, сборка и offline CLI smoke, один реальный A2/T002 baseline с внешним judge |
| Расширения | Три повтора, `without-spec`, T001 с frozen archive, T003, проект проверенного session export |
| Время | Ориентир 2–3 часа оператора плюс сборка/оценка; timeout исполнения 900 s |
| Готовность | CLI `1.18.29` прошёл установочный smoke 20.09.2026 на Linux/arm64; реальный запуск и свои замеры — `not-run` до выполнения |

## Цель

Выполнить T002 через OpenCode build agent и проследить, как запечатанный файл permissions сочетается с runtime-конфигурацией основной и малой модели и ограничением `steps`. Установить, какие поля JSONL пригодны для вывода о завершении и какие не дают достоверного итогового usage.

## Проверяемая гипотеза

OpenCode `1.18.29` с фиксированным Anthropic model ID, build agent и разрешёнными инструментами способен подготовить оцениваемый результат T002. При этом поток `step_finish` сам по себе не доказывает полную стоимость и число модельных ходов сессии: недостаток наблюдаемости должен сохраниться в результате как неизвестность.

До запуска определите, что опровергает первую часть гипотезы, и какие наблюдения потребовались бы для устранения второй. Не приравнивайте отсутствие метрик к нулевым затратам или неуспеху содержательной задачи.

## Подготовка

Работайте из корня репозитория, в одной shell-сессии. `my-session` — выбранное имя отчёта; для повторной лабораторной используйте другое. Все значения в угловых скобках заменяются фактическими данными до запуска. При ненулевом exit code сохраните ошибку и не продолжайте зависимые шаги: старый image tag или файл не подтверждает успех текущей команды.

```bash
npm run lab:new -- --lab LAB12 --session my-session
LAB_DIR='experiments/opencode/measurements/LAB12-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Прочитайте [A2](../../agents/a2-janitor/spec.md), [открытый T002](../../tasks/T002-repo-janitor/task.md), [профиль](../../experiments/opencode/harness.json), [opencode.json](../../experiments/opencode/opencode.json), [адаптер](../../experiments/opencode/adapter.mjs) и [процедуру независимой оценки](harness-workflow.md). Каталоги `tasks/*/check/` не открывайте; task contracts не редактируйте. Внешний судья и метод `hidden-check` определяются заранее.

В `.env` нужен только `ANTHROPIC_API_KEY` выбранного профиля. Если `.env` отсутствует, создайте его по `.env.example`; если существует, отредактируйте без перезаписи других данных. Не сохраняйте значение в отчёте/команде. Оркестратор читает `.env` сам: не выполняйте `source .env` и не монтируйте домашние credentials. Процессы внутри агентного контейнера получают выбранный ключ; граница этого механизма описана в [common README](../../experiments/common/README.md).

Выберите точный доступный Anthropic API model ID. Профиль не содержит списка моделей и не доказывает доступ аккаунта; зафиксируйте способ его подтверждения без секретов. В этой работе используется только provider `anthropic`, разрешённый API-host — `api.anthropic.com`. Наличие других провайдеров в upstream OpenCode не означает их поддержку текущим адаптером.

## Порядок выполнения

1. **Проверьте parser и сборку команды без API.**

   ```bash
   node --test experiments/opencode/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Зафиксируйте exit code. Объясните, почему событие с `cost: 0` и token counts в синтетическом `step_finish` оставляет итоговые поля неизвестными; почему `error` важнее предыдущего finish; почему запрос обязательного USD budget отклоняется. Никакой реальный `run.json` для этих fixtures не создаётся.

2. **Соберите фиксированную версию, проверьте CLI без сети.** OpenCode Dockerfile выполняет package postinstall внутри образа; не переносите инструкцию `--ignore-scripts` из другого harness. Сборка и загрузка proxy image требуют сети, smoke не получает credentials.

   ```bash
   docker build --build-arg HARNESS_VERSION=1.18.29 \
     -t harness-lab/opencode:1.18.29 \
     -f experiments/opencode/Dockerfile experiments/opencode \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/opencode:1.18.29)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" opencode --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" opencode run --help > "$LAB_DIR/raw/run-help.txt"
   docker run --rm --network none "$IMAGE_REF" opencode export --help > "$LAB_DIR/raw/export-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Проверьте `1.18.29`, architecture и immutable IDs. Сохранённая справка должна соответствовать CLI v1: команда экспорта здесь `opencode export`, а не непроверенная команда из другой версии. Сам export из реальной сессии пока не встроен в runner.

3. **Разберите два слоя конфигурации.** Заполните таблицу по текущим файлам, не меняя их. `OPENCODE_CONFIG` указывает на `/control/opencode.json`, который задаёт default deny и разрешает `read`, `edit`, `glob`, `grep`, `list`, `bash`. `OPENCODE_CONFIG_CONTENT` дополнительно задаёт `model`, `small_model` и `agent.build.model` одному `anthropic/<ID>`, а `agent.build.steps` получает предел из задачи. `OPENCODE_DISABLE_AUTOUPDATE=true` выключает auto-update.

   Сформулируйте назначение каждого слоя: какая возможность определяется файлом permissions, какая — адаптером, а какая — Docker/gateway. `steps` просит OpenCode завершить цикл и не является гарантированным количеством полных модельных запросов или USD cap.

4. **Создайте и подготовьте минимальный T002.** В отчёте заранее закрепите baseline, модель, image IDs, `observed`, timeout 900. Contract T002 задаёт до 30 ходов или $2; здесь USD не ограничивается, а native steps не равно универсальному счётчику ходов. Это явно исследовательское отклонение.

   ```bash
   MODEL_ID='<точный доступный Anthropic model ID>'
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a2-janitor --task T002 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<ID, напечатанный new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Внесите ID в manifest отчёта, проверьте harness/provider/variant/seed commit в `inputs/manifest.json`. Снимок не должен содержать `.env` и скрытые проверки. После prepare входы не редактируют; изменение конфигурации означает новый run.

5. **Исполните реальную попытку.** Команда использует выбранный платный API; подтверждённого жёсткого USD cap у этого adapter нет.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   Проверьте состояние и причину остановки в `run.json`. Сохраните ссылки на `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch`, `artifacts/report.md`. `awaiting_review` не равен pass. При `aborted` не исправляйте результаты и не перезапускайте тот же ID; добавьте диагноз, а retry оформите новой попыткой.

6. **Составьте карту наблюдаемости OpenCode.** В raw JSONL найдите session ID, `step_finish` и ошибки; укажите точные события, на которых основана причина остановки. Проверьте, что `run.json` содержит `null` с причинами для turns/cost/input/output, а `model.observed_id` остаётся неизвестным. `--model` и runtime config подтверждают запрос модели, но parser не подтверждает модель provider response.

   Не суммируйте `step_finish` в итоговые поля run вручную. Успех этой части — объяснённые ограничения, а не заполнение всех ячеек числами. Если данные нужны для будущего улучшения, опишите проверяемый экспорт из той же сессии с полным учётом основных и вспомогательных запросов. Сессия внутри контейнера не сохраняется автоматически как доступная host CLI session.

7. **Получите внешнюю оценку.** Только из `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Внешний оценщик применяет T002 hidden-check по [общей процедуре](harness-workflow.md), заполняет `result`, `evaluator`, `check_output` и при необходимости notes, не меняя хеши и результаты агента. После этого:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `pass`, `fail` и `partial` одинаково допустимы как честно завершённое измерение. `aborted` не импортируется через judge, а без внешнего оценщика работа остаётся незавершённой. Все предыдущие неудачные попытки сохраняются в списке `run_ids`.

8. **Расширение: повторы и удаление спецификации.** Заранее назначьте три baseline и три `without-spec`, одинаковые модель, образы, timeout, входы и судью; чередуйте варианты. На каждый слот выполните `new-run` из шага 4 с новым ID; для without-spec вместо baseline prepare:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider anthropic
   ```

   Это подготовка новой записи. Выполните шаги 5–7 для всех назначенных слотов. Минимальный T002 служит pilot и допуском в ЛР09; сравнительные baseline/without-spec тройки всегда состоят из новых попыток. Сохраните все начатые ошибки, затем сравните точные ID:

   ```bash
   SERIES_RUN_IDS='<все назначенные run IDs через запятую>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   Покажите исходы, `pass@3`/`pass^3` и измеренное время; сравнение стоимости недоступно при текущем parser. `without-spec` не удаляет Docker, permissions и gateway. Подробная интерпретация и реестр — [ЛР10](LAB10-ablation.md).

9. **Расширение: T001 discovery/replay и T003.** Создайте отдельный live T001:

   ```bash
   AS_OF_DATE='<общая дата YYYY-MM-DD>'
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a1-dossier --task T001 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<новый ID discovery>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic --as-of "$AS_OF_DATE"
   ```

   Выполните шаги 5–7 с методом `rubric`; T001 также использует предусмотренную проверку источников. Архив `trace/sources.jsonl` должен содержать тела, статусы и URL. Создайте новый T001 через ту же `new-run`, присвойте новый ID и подготовьте replay:

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl discovery run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Выполните шаги 5–7; controlled series использует один архив и дату, discovery отмечается отдельно. Для аудита OpenCode:

   ```bash
   npm run new-run -- --harness opencode --harness-version 1.18.29 \
     --agent a3-ledger-auditor --task T003 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<новый ID T003>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   После исполнения получите rubric-оценку `ledger.md` и `ablation-plan.md`. T003 получает собственную копию конфигурации OpenCode; входы других harness будут отличаться.

10. **Сформулируйте результат и следующую проверку.** В `experiments/opencode/NOTES.md` запишите реальные ID, проблемы и необходимые изменения. Наличие `null` само по себе не требует нового компонента. Если предлагаете session export, опишите тест его полноты, безопасный путь сохранения из той же сессии и новый ledger component; пока он не реализован и не проверен, метрики остаются неизвестными. Исходный adapter относится к L008 в [реестре](../harness-ledger.md).

## Таблицы результатов

| Слой/параметр | Источник | Фактическое значение | Что гарантирует | Что не проверено |
| --- | --- | --- | --- | --- |
| permissions / model / small_model / steps / timeout | Файл или launch | Заполнить | По коду и наблюдению | Заполнить |

| Слот | Task/variant | Run ID | Status/verdict | Stop event | Wall-clock, s | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Назначить до запуска | T002/baseline | После new-run | После run/judge | Raw event | Из record | Путь |

| Показатель | Значение или `null` | Основание | Причина отсутствия | Требуемое подтверждение |
| --- | --- | --- | --- | --- |
| Model identity / turns / cost / tokens | После запуска | Поле record + trace | Сохранить точную причину | Не подменять предположением |

| Расширение | ID всех слотов | Изменённый фактор | Исходы | Ограничение вывода |
| --- | --- | --- | --- | --- |
| Тройки/without-spec/replay/T003 | При выполнении | Заполнить | Все попытки | Заполнить |

## Что сдать

- Manifest и отчёт с гипотезой до запуска, всеми run IDs и заполненными таблицами.
- Parser tests, build/version/help evidence, image/proxy IDs и архитектуру своей среды.
- Один реальный T002 до `completed`, исходные трассы, patch, report и независимую оценку с неизменными hashes; ошибки отдельно.
- Карту config layers и observability, ответы на контрольные вопросы, NOTES; optional series и план session export только при выборе расширения.

## Критерии завершения

- [ ] На своей машине подтверждены CLI `1.18.29`, parser tests и image IDs.
- [ ] Определено различие file config, runtime config и внешней изоляции.
- [ ] Реальный T002 независимо оценён; verdict не выведен из exit 0.
- [ ] Использованы `observed` и timeout 900, ограничение `steps` описано как advisory.
- [ ] Неизвестные usage/model identity сохранены, `step_finish` не выдан за полный session accounting.
- [ ] Все попытки сохранены, секретов и скрытых проверок в отчёте нет, `npm run check` проходит.

## Контрольные вопросы

1. Зачем адаптер одновременно задаёт `model`, `small_model` и `agent.build.model`?
2. Чем OpenCode `steps` отличается от Claude `max-turns` и внешнего timeout?
3. Почему `cost: 0` в одном событии не делает стоимость сессии нулевой?
4. Что потребовалось бы доказать для безопасного включения session export в учёт метрик?
5. Почему запуск с `hard` отклоняется и почему `observed` всё ещё может расходовать больше $2?
6. Подтверждает ли requested model ID фактическую модель provider response?
7. Какая граница сохраняет hidden checks недоступными при разрешённом `bash`?

## Источники

- [README OpenCode](../../experiments/opencode/README.md), [профиль](../../experiments/opencode/harness.json), [конфигурация](../../experiments/opencode/opencode.json), [адаптер](../../experiments/opencode/adapter.mjs), [тесты](../../experiments/opencode/adapter.test.mjs), [Dockerfile](../../experiments/opencode/Dockerfile).
- [Протокол](../method.md), [общая инфраструктура](../../experiments/common/README.md), [независимый judge](harness-workflow.md), [ЛР10](LAB10-ablation.md).
- Работа описывает закреплённый CLI v1 `1.18.29`; команды другой версии и возможности upstream не считаются реализованными в этом adapter без отдельной проверки.
