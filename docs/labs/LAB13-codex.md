# ЛР13. Codex CLI: автономный exec и проверка границ наблюдаемости

## Паспорт

| Поле | Значение |
| --- | --- |
| Обвязка | `codex`, CLI `@openai/codex@0.155.1`, режим `codex exec --json` |
| Предпосылка | [ЛР01](LAB01-reproducibility.md); Node.js ≥22, Git, Bash, Docker Engine; обычный пользователь координатора |
| Основной маршрут | OpenAI API, `CODEX_API_KEY` из `.env`; без local provider bridge |
| Минимальный объём | Parser/command tests, offline image smoke, один A2/T002 baseline с независимым judge |
| Расширения | Три повтора, `without-spec`, T001 frozen replay, T003-аудит конфигурации |
| Время | Ориентир 2–3 часа оператора плюс сборка/судейство; timeout отдельного исполнения 900 s |
| Готовность | CLI `0.155.1` прошёл offline установочную проверку 20.09.2026 на Linux/arm64; свои smoke и реальный эпизод — `not-run` до выполнения |

## Цель

Запустить независимого агента A2 через Codex CLI в контролируемом контейнере, получить внешнюю оценку исправления и объяснить разделение внутренних настроек CLI, внешней изоляции и итогового учёта. Проверить, почему пользовательский `turn` не является числом внутренних модельных ходов и почему правильный model argument не подтверждает ID ответа провайдера.

## Проверяемая гипотеза

Codex `0.155.1` с явным доступным OpenAI model ID, отключёнными внешними настройками и baseline prompt способен подготовить результат T002 для независимой проверки. Корректно завершённый JSONL сообщает usage, но не даёт достаточных оснований заполнить USD, внутренние ходы или observed model ID.

Зафиксируйте до запуска критерии успеха задачи и критерии корректности учёта отдельно. Ненулевые токены не доказывают содержательный успех, а неизвестная стоимость не означает бесплатное выполнение.

## Подготовка

Команды выполняются из корня лабораторного репозитория. `my-session` выберите один раз; для нового отчёта требуется новое имя. Все placeholders в угловых скобках далее заменяются до исполнения. После ненулевого exit code сохраните ошибку и остановите зависимые шаги: существующий старый образ или файл не доказывает успех текущей команды.

```bash
npm run lab:new -- --lab LAB13 --session my-session
LAB_DIR='experiments/codex/measurements/LAB13-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Прочитайте [A2](../../agents/a2-janitor/spec.md), [открытый T002](../../tasks/T002-repo-janitor/task.md), [профиль](../../experiments/codex/harness.json), [адаптер](../../experiments/codex/adapter.mjs), [общую инфраструктуру](../../experiments/common/README.md) и [порядок независимой оценки](harness-workflow.md). Не открывайте `tasks/*/check/`, не меняйте task contracts. До запуска определите внешнего оценщика и метод `hidden-check`.

Подготовьте в `.env` именно `CODEX_API_KEY`. Переменная `OPENAI_API_KEY` используется другими harness и не подменяет credential этого профиля. Если `.env` ещё нет, создайте его по `.env.example`; существующий файл не перезаписывайте. Не выводите ключ в терминал/отчёт и не выполняйте `source .env`: его разбирает координатор. Домашние `auth.json`, settings и сессии не монтируются; доступ в приложении Codex на хосте не подтверждает API-доступ внутри лабораторного контейнера.

Выберите точный доступный model ID для OpenAI API и запишите способ подтверждения доступности. `latest`, `auto`, `default` не подходят. В профиле нет каталога доступных аккаунту моделей: корректная строка в CLI не доказывает доступ или observed identity. Provider в этом adapter — только `openai`, API-domain — `api.openai.com`.

## Порядок выполнения

1. **Проверьте adapter без API.**

   ```bash
   node --test experiments/codex/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Зафиксируйте exit code. Объясните пять сценариев тестов: буквальный prompt как один argv; отказ от неподдержанного provider/USD/turn cap; `input_tokens` уже включает cached input; malformed/failed trace не выдаёт полный usage; явный нулевой usage допустим. Эти fixtures не являются эпизодами T002.

2. **Соберите и зафиксируйте CLI.** Сеть нужна для сборки и proxy image, но version/help запускаются без сети и ключей. Не обновляйте пакет во время серии.

   ```bash
   docker build --build-arg HARNESS_VERSION=0.155.1 \
     -t harness-lab/codex:0.155.1 \
     -f experiments/codex/Dockerfile experiments/codex \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/codex:0.155.1)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" codex --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" codex exec --help > "$LAB_DIR/raw/exec-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Проверьте `0.155.1`, architecture, image ID и proxy ID. Исторический [smoke](../../experiments/codex/smoke/2026-09-20.json) — ориентир для структуры evidence, не результат на вашей машине. Свежая сборка может получить другой ID из-за base image/системных пакетов; заморозьте один образ для всех повторов.

3. **Разберите фактическую команду Codex.** По адаптеру и сохранённой справке заполните таблицу настройки/границы. Зафиксированы `exec --json`, явный model, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--skip-git-repo-check`, `approval_policy="never"`, `web_search="disabled"`, `agents.enabled=false`. Наличие флага и его передача подтверждаются исходниками/smoke; поведение при реальном эпизоде фиксируется отдельно.

   Встроенный sandbox запущен в `danger-full-access`. В этой лаборатории файловые/процессные/сетевые границы задаются внешним Docker-контейнером и gateway; отсутствие internal sandbox не даёт агенту rootfs хоста. Не запускайте сформированную команду adapter напрямую на host workspace. Пользовательские credentials/config/rules не наследуются, спецификацию A2 передаёт prompt координатора.

   Native turn cap и USD cap не поддержаны текущим adapter. Runner передаёт `turns=null`, `budget=null` при `observed`; timeout 900 остаётся принудительным. Один `turn.completed` может включать внутренний инструментальный цикл, поэтому считать его одним модельным ходом нельзя.

4. **Зарегистрируйте новый T002.** Запишите в manifest отчёта модель, baseline, image IDs, `observed`, timeout 900 и выбранного судью. Бюджет T002 до 30 ходов или $2 в этом маршруте не обеспечивается native CLI; отклонение фиксируется заранее.

   ```bash
   MODEL_ID='<точный доступный OpenAI model ID>'
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a2-janitor --task T002 --provider openai --model "$MODEL_ID"
   RUN_ID='<ID, напечатанный new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai
   ```

   Добавьте выданный ID в отчёт. Проверьте `inputs/manifest.json`: provider openai, harness codex, baseline, seed commit и разрешённые входы. `.env` и hidden checks не входят в снимок. После prepare не редактируйте sealed files или workspace вручную.

5. **Выполните облачный эпизод.** Он расходует средства выбранного API-аккаунта; USD не ограничен этим adapter.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider openai --timeout 900 --budget-mode observed
   ```

   Проверьте `run.json`, `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch`, `artifacts/report.md`. Если состояние `aborted`, запишите причину; retry получает новый ID. Если `awaiting_review`, переходите к внешней оценке. Наличие токенов, exit 0 или текста «готово» не заменяет verdict.

6. **Проверьте usage и завершённость потока.** Найдите `thread.started`, `turn.started`, terminal event и `turn.completed.usage`. Сопоставьте `input_tokens`/`output_tokens` с `loop.tokens_in`/`loop.tokens_out`. `cached_input_tokens` — часть input, не дополнительный слагаемый. Если последняя часть JSONL оборвана или завершение ошибочно, parser не должен объявлять usage полным.

   Отдельно объясните `loop.turns=null`, `loop.cost_usd=null` и `model.observed_id=null`. `thread_id` идентифицирует CLI-сессию, не underlying модель. Запрошенный model фиксируется, но потоком не подтверждается ID provider response. Сохраните причины в `metrics_unavailable`, не заполняйте поля вручную из предположений или стоимости другого run.

7. **Проведите независимое судейство.** Только для `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Внешний оценщик применяет hidden-check T002 по [процедуре](harness-workflow.md), заполняет `result`, `evaluator`, `check_output`, при необходимости notes; сгенерированные hashes не изменяются. Результаты агента остаются неизменными. Затем:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `completed` может иметь `pass`, `fail` или `partial`: все три — результаты измерения. Judge не создаёт содержательный вердикт автоматически и не переводит aborted в completed. Без внешнего оценщика работа остаётся `awaiting_review` и не удовлетворяет минимуму.

8. **Расширение: три повтора и абляция prompt.** До серии назначьте три baseline и три without-spec, сохранив provider/model/image/proxy/timeout и входы. Чередуйте варианты, создавая для каждого новый run из шага 4. Для without-spec используйте вместо baseline prepare:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider openai
   ```

   Выполните шаги 5–7 для каждой назначенной попытки. Минимальный T002 служит pilot и допуском в ЛР09; сравнительные baseline/without-spec тройки всегда состоят из новых попыток. Не заменяйте aborted успешными retry. Сравните все ID:

   ```bash
   SERIES_RUN_IDS='<все назначенные run IDs через запятую>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   Покажите исходы, время и полноту токенов; стоимость и внутренние ходы остаются неизвестными. `--ignore-rules` действует в обоих вариантах; without-spec убирает текст A2 из prompt координатора, а не отменяет внешнюю Docker-границу. Подробнее — [ЛР10](LAB10-ablation.md).

9. **Расширение: источники и аудит.** Создайте discovery T001 отдельно:

   ```bash
   AS_OF_DATE='<общая дата YYYY-MM-DD>'
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a1-dossier --task T001 --provider openai --model "$MODEL_ID"
   RUN_ID='<новый ID discovery>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai --as-of "$AS_OF_DATE"
   ```

   Выполните шаги 5–7 с методом `rubric`; для T001 оценщик применяет и предусмотренную проверку источников. Встроенный web search Codex остаётся отключённым; доступ к разрешённым источникам идёт через инструменты и gateway лаборатории. Сохраните `trace/sources.jsonl` с URL, телами и статусами. Создайте новый T001 той же командой `new-run`, присвойте новый ID и подготовьте replay:

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl discovery run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Выполните шаги 5–7; все controlled T001 используют один архив и дату, discovery учитывается отдельно. Для T003:

   ```bash
   npm run new-run -- --harness codex --harness-version 0.155.1 \
     --agent a3-ledger-auditor --task T003 --provider openai --model "$MODEL_ID"
   RUN_ID='<новый ID T003>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider openai
   ```

   Получите `ledger.md`, `ablation-plan.md` и внешнюю rubric-оценку через шаги 5–7. Отличайте фактическую команду adapter от более широких возможностей Codex. Конфигурационные входы T003 различаются между harness и требуют отдельной интерпретации.

10. **Сделайте вывод о deployment.** В `experiments/codex/NOTES.md` запишите ID, условия, успехи/ошибки и неизвестные показатели. Установочный smoke, parser tests и реальная задача — разные свидетельства. Для нового компонента нужен ledger row; существующий adapter указан как L009 в [реестре](../harness-ledger.md). Не включайте восстановление пользовательских правил или других возможностей в baseline задним числом.

## Таблицы результатов

| Настройка | Фактическое значение/argv | Уровень: CLI или Docker/gateway | Evidence | Ограничение |
| --- | --- | --- | --- | --- |
| Model, rules/config, sandbox, approvals, web, agents, timeout | Заполнить | Заполнить | Исходник + свой smoke/run | Заполнить |

| Слот до запуска | Task/variant | Run ID | Status/verdict | Terminal event | Wall-clock, s |
| --- | --- | --- | --- | --- | --- |
| Заполнить | T002/baseline | После new-run | После run/judge | Из trace | Из record |

| Показатель | Значение или `null` | Определение | Evidence | Причина отсутствия |
| --- | --- | --- | --- | --- |
| Input/cache/output, turns, USD, model identity | После запуска | Без двойного cache | Поле record/событие | Заполнить |

| Расширение | ID всех назначенных попыток | Исходы | Изменённое условие | Ограничение вывода |
| --- | --- | --- | --- | --- |
| Тройки/without-spec/replay/T003 | При выполнении | Все исходы | Заполнить | Заполнить |

## Что сдать

- Manifest и отчёт с гипотезой до запуска, таблицами, всеми run IDs и ответами на вопросы.
- Parser tests, build/version/help evidence, immutable image/proxy IDs и архитектуру.
- Минимум один реальный независимо оценённый T002: patch, report, raw trace и evaluation с неизменными manifests; предыдущие ошибки не скрываются.
- Объяснение внешней границы и неизвестных USD/turns/model identity, запись в NOTES; результаты расширений только при выполнении.

## Критерии завершения

- [ ] CLI `0.155.1` и immutable IDs проверены в своей среде, parser tests проходят.
- [ ] Объяснены взаимодействие `danger-full-access` с внешним контейнером и отключение user rules/config.
- [ ] Один T002 имеет `completed` и независимый `pass`, `fail` или `partial`; aborted/awaiting_review не названы завершённым минимумом.
- [ ] Основной запуск использовал `observed`, timeout 900; отсутствие native USD/turn cap явно указано.
- [ ] Cache не прибавлен повторно, `turn.completed` не объявлен числом внутренних ходов, requested ID отделён от observed.
- [ ] Все попытки сохранены, нет секретов/hidden checks/ручной коррекции результата; `npm run check` проходит.

## Контрольные вопросы

1. Почему `CODEX_API_KEY` нельзя заменить переменной другого OpenAI adapter без изменения профиля?
2. Почему `danger-full-access` внутри этого эксперимента не означает полный доступ к хосту?
3. Чем отличается `turn.completed` от полного количества модельных ходов?
4. Как двойной учёт cached input исказил бы сравнение?
5. Почему `thread_id` и requested model недостаточны для observed model ID?
6. Какие ограничения остаются при `observed`, а какие отсутствуют?
7. Что именно удаляет without-spec при уже отключённых пользовательских rules?
8. Как T001 получает источники при отключённом встроенном web search?

## Источники

- [README Codex](../../experiments/codex/README.md), [профиль](../../experiments/codex/harness.json), [адаптер](../../experiments/codex/adapter.mjs), [тесты](../../experiments/codex/adapter.test.mjs), [Dockerfile](../../experiments/codex/Dockerfile), [исторический offline smoke](../../experiments/codex/smoke/2026-09-20.json).
- [Протокол](../method.md), [внешняя инфраструктура](../../experiments/common/README.md), [независимый judge](harness-workflow.md), [ЛР10](LAB10-ablation.md).
- Команды взяты из закреплённого adapter `0.155.1`, а не из возможностей текущей версии приложения Codex; доступность выбранной API-модели подтверждается при выполнении лабораторной.
