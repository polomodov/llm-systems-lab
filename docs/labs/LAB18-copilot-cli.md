# ЛР18. Copilot CLI: автономный эпизод, selector модели и AI credits

## Паспорт

| Поле | Значение |
| --- | --- |
| Предварительная работа | [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `copilot-cli`, пакет `@github/copilot` **1.0.86** |
| Основной маршрут | Облачный provider `copilot`; локальный bridge не требуется |
| Агент и задача | `a2-janitor` / T002 |
| Минимум | Offline smoke с native cache и один реальный T002 с независимой оценкой |
| Расширение | Три новых T002, T001 replay, T003, абляция спецификации |
| Время | Ориентир 2–4 часа без задержек сервиса; не измеренный результат |
| Начальный статус | `not-run`; эта работа содержит задания, а не отчёт о выполнении |

## Цель

Запустить локальный Copilot CLI через общий координатор и получить независимо оценённый результат. Отделить выбранный Copilot selector от подтверждённого model snapshot, а premium requests / AI credits — от стоимости в USD. Проверить, не мешает ли собственному циклу CLI контейнерная граница и ограниченный native cache.

## Проверяемая гипотеза

CLI 1.0.86 с явным доступным selector выполнит T002 без интерактивных вопросов и завершит JSONL потоком `result`. Полные пары событий ходов дадут наблюдаемое число ходов основного агента, но текущий формат не обеспечит token totals, USD и фактический model ID. Независимый verdict проверит качество задачи отдельно от терминального `exitCode=0`.

## Подготовка

Нужны Node.js ≥22, Bash, Git, Docker и аккаунт с доступом к Copilot CLI. Это **локальное исполнение CLI с облачным сервисом**, а не GitHub Copilot coding agent. Координатор запускается обычным пользователем из корня репозитория. На Linux x64 повторите smoke самостоятельно: сохранённые инфраструктурные измерения относились к Linux arm64.

Прочитайте [README](../../experiments/copilot-cli/README.md), [профиль](../../experiments/copilot-cli/harness.json), [протокол](../method.md), `agents/a2-janitor/spec.md` и открытый [контракт T002](../../tasks/T002-repo-janitor/task.md). Скрытые `tasks/*/check/` не читаются решающим агентом, контракты не редактируются.

Выполняйте блоки последовательно в Bash, разбирая ошибку до продолжения:

```bash
npm run lab:new -- --lab LAB18 --session my-session
LAB_DIR='experiments/copilot-cli/measurements/LAB18-my-session'
HARNESS_VERSION='1.0.86'
IMAGE_REF='harness-lab/copilot-cli:1.0.86'
PROVIDER_ID='copilot'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

В `.env` требуется **`COPILOT_GITHUB_TOKEN`**, поддерживаемый токен с доступом Copilot; в исследовании закреплённой версии указан fine-grained PAT с разрешением Copilot Requests, classic PAT не поддерживается. Значение не выводите и не копируйте в отчёт; не монтируйте `.env` в контейнер. До API-вызова запишите выбранную конфигурацию, лимиты T002, `timeout=900 s`, `budget-mode=observed`, одну основную попытку и независимого оценщика. Тип подписки запишите без идентификаторов и секретов аккаунта.

## Порядок выполнения

1. **Соберите образ и сохраните его identity.** Используйте закреплённый npm package 1.0.86. Сборка требует сети для пакетов, но не ключа и не вызова модели; существующий проверенный образ можно использовать без пересборки.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/copilot-cli \
     > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Проверьте native cache без сети и credentials.** CLI распаковывает native addon; `noexec /tmp` без отдельного exec tmpfs мешает даже `--version`. Сохраните основной `/tmp` как `noexec`, выделите отдельный `/tmp/harness-native` 512 MiB и направьте туда `TMPDIR`/`XDG_CACHE_HOME`. Это настройка существующего профиля, а не разрешение исполнять файлы лаборатории.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --tmpfs /tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777 \
       --env HOME=/tmp --env TMPDIR=/tmp/harness-native \
       --env XDG_CACHE_HOME=/tmp/harness-native --env COPILOT_HOME=/tmp/copilot \
       --env COPILOT_AUTO_UPDATE=false --env CI=true --workdir /tmp \
       "$IMAGE_ID" copilot "$FLAG" \
       > "$LAB_DIR/raw/copilot-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/copilot-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/copilot-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/copilot-cli/adapter.test.mjs \
     > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Проверьте оба файла и коды завершения: версия должна быть 1.0.86, справка должна завершиться успешно. После `break` smoke считается незавершённым; API-этап не начинается. Старое измерение cache ≈157,5 MiB для arm64 из README не переносите в свой отчёт как собственное. 512 MiB — максимальная ёмкость tmpfs, а не заранее выделенная или измеренная память эпизода.

3. **Разберите контракт адаптера.** По [адаптеру](../../experiments/copilot-cli/adapter.mjs) и тестам найдите `--no-ask-user`, `--no-custom-instructions`, `--disable-builtin-mcps`, `--no-remote-export`, отключение обновления и передачу prompt одним argv. Объясните, почему `--allow-all` допустим только вместе с внешней границей. Не добавляйте к текущему заданию GitHub MCP, BYOK, GHE.com или remote execution: это новые условия и профили.

4. **Выберите явный selector и подготовьте новый T002.** Пример `gpt-5.4` присутствует в тестах и README закреплённого адаптера. Используйте его только если он доступен в вашем Copilot аккаунте, иначе до `new-run` замените другим поддерживаемым явным selector и запишите источник выбора. `auto`, `default`, `latest` запрещены. Название Copilot selector не доказывает тот же snapshot, что прямой API другого провайдера.

   ```bash
   MODEL_ID='gpt-5.4'
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Сохраните выданный ID в учебном manifest и следующей переменной:

   ```bash
   RUN_ID='<ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   До исполнения убедитесь, что запись `prepared`. Профиль разрешает только `github.com`, `api.github.com`, `api.githubcopilot.com`, `api.individual.githubcopilot.com`, `api.business.githubcopilot.com`, `api.enterprise.githubcopilot.com`. Полнота списка для вашего авторизованного CLI остаётся проверяемой гипотезой, а не основанием открыть wildcard.

5. **Выполните реальный эпизод.** Это первый этап, использующий модель и credentials.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   `observed` означает, что USD cap задачи не обеспечен. `--max-autopilot-continues` не используется как подмена лимита модельных ходов; принудительный предел — внешний timeout. При ошибке авторизации или denied egress сохраните причину. Изменение профиля требует новой подготовки и нового run ID; не расширяйте сеть в запечатанной попытке. Не передавайте токен в аргументы команд диагностики.

6. **Проверьте trace и неизвестные показатели.** Сохраните сводку record:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   Найдите в raw JSONL `session.start`, пары `assistant.turn_start` / `assistant.turn_end` и терминатор `type: result` с числовым `exitCode`. При полном наборе пар основной агент получает измеряемые turns, повторные ID не суммируются. `assistant.usage` и `session.shutdown` фильтруются stdout formatter этой версии; текущий парсер оставляет token totals и observed model неизвестными. Premium requests/AI credits нельзя переводить в USD без отдельного обоснованного измерения; в run record USD остаётся `null` с причиной. Наличие `result` и успешного exit code ещё не проверяет решение T002.

7. **Завершите независимое судейство.** Для `awaiting_review` создайте шаблон; при `aborted` сохраните ошибку и при необходимости создайте новую попытку. Незавершённую/прерванную запись нельзя превратить в успех редактированием record.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Независимый оценщик по [общей процедуре](harness-workflow.md) выполняет T002 hidden-check вне agent container и заполняет `result`, `evaluator`, `check_output` с версией проверки и наблюдениями; `human_notes` необязателен. `result` принимает `pass`, `fail`, `partial`; generated hashes остаются неизменными. Пока независимой оценки нет, запись остаётся `awaiting_review`.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   Минимум лабораторной — реальный `completed` с любым содержательно обоснованным verdict. Внесите фактические ID, наблюдаемость, egress и ограничения selector в `experiments/copilot-cli/NOTES.md`. Новый компонент требует ledger row; отсутствие token totals не разрешает придумывать измерение.

8. **Расширьте исследование по заранее заданному плану.** Для тройки создайте три новых T002 через шаги 4–7. Первый основной эпизод остаётся pilot; сохраняются версия, image IDs, selector, provider, task inputs, timeout и observed budget. Анализируйте все начатые исходы:

   ```bash
   SERIES_RUN_IDS='<три новых run ID через запятую без пробелов>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   Для T001 используйте единый архив зарегистрированного discovery run. Если его нет, выполните отдельный live discovery по [workflow](harness-workflow.md); архив должен содержать HTTP bodies/status, а не только URL.

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl discovery run>'
   AS_OF_DATE='<общая дата YYYY-MM-DD>'
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<новый T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Исполнение — шаг 5, оценка — шаг 7, но метод T001 — `rubric` с предусмотренным проверяющим скриптом. Для T003 подготовьте отдельный аудит:

   ```bash
   npm run new-run -- --harness copilot-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<новый T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Выполните шаг 5 и внешнюю `rubric` оценку. Разные harness дают разные входные конфигурации T003. Для абляции создайте новый T002 как в шаге 4 и подготовьте `--variant without-spec`, затем исполните и оцените. Проверьте, что спецификация не возвращается через custom instructions; Docker и gateway остаются. Эффект исследуйте тремя baseline и тремя without-spec по [ЛР10](LAB10-ablation.md).

## Таблицы результатов

| Run ID | Task / variant | CLI version / image ID | Copilot selector | Статус | Внешний verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Показатель | Значение | Единица | Измерение или причина `null` | Evidence |
| --- | --- | --- | --- | --- |
| Ходы основного агента | — | turns | — | — |
| Токены вход/выход | — | tokens | — | — |
| Premium requests / AI credits | — | Как обозначено сервисом | — | — |
| Стоимость прогона | — | USD | — | — |
| Время | — | s | — | — |
| Наблюдаемый model ID | — | ID | — | — |

| Проверка | Условие до запуска | Наблюдение | Evidence / ограничение |
| --- | --- | --- | --- |
| Native cache smoke | Отдельный exec tmpfs 512 MiB, сеть отключена | — | — |
| Turn pairs | Полные уникальные пары основного агента | — | — |
| Egress | Только домены закреплённого profile | — | — |
| T002 | Независимая содержательная оценка | — | — |

## Что сдать

- Учебные manifest/report LAB18 с предварительным протоколом, таблицами и контрольными ответами.
- Версию, архитектуру, image IDs, offline help/version/tests и параметры native tmpfs; без токена и `.env`.
- Ссылки на все созданные run records, immutable inputs/trace/artifacts, T002 `trace/change.patch` и внешние оценки.
- Compare JSON на точных IDs, NOTES и при необходимости ledger additions; отдельное объяснение selector identity и границы AI credits/USD.

## Критерии завершения

- [ ] 1.0.86 подтверждена offline; native cache работает при сохранённом noexec основном `/tmp`.
- [ ] Есть хотя бы один реальный T002 `completed` с независимым verdict; ошибки и aborted не скрыты.
- [ ] Зафиксированы явный selector, provider, immutable images, observed budget и timeout 900 s.
- [ ] Selector не объявлен точным model snapshot, AI credits не подменены USD, отсутствующие токены не заменены нулями.
- [ ] Turns имеют evidence полных пар либо остаются неизвестными с причиной.
- [ ] `npm run check` проходит; offline smoke и реальный результат не смешаны; дополнительные серии имеют собственные IDs.

## Контрольные вопросы

1. Чем локальный Copilot CLI отличается от Copilot coding agent в облаке?
2. Почему тот же строковый selector в Copilot и другом API не гарантирует одинаковые веса?
3. Почему общий `/tmp` остаётся noexec, хотя нужен исполняемый native cache?
4. Какие события нужны для достоверного числа ходов? Что делать с незакрытой парой?
5. Почему premium requests не являются стоимостью конкретной попытки в USD?
6. Что нужно проверить до расширения egress после сетевого отказа и почему требуется новая запись?

## Источники

- [README](../../experiments/copilot-cli/README.md), [NOTES](../../experiments/copilot-cli/NOTES.md), [профиль](../../experiments/copilot-cli/harness.json), [Dockerfile](../../experiments/copilot-cli/Dockerfile), [адаптер](../../experiments/copilot-cli/adapter.mjs), [тесты](../../experiments/copilot-cli/adapter.test.mjs).
- [Протокол](../method.md), [workflow оценки](harness-workflow.md), [реестр L014](../harness-ledger.md), [ЛР09](LAB09-agent-campaign.md), [ЛР10](LAB10-ablation.md).
- Первичные источники, на которые опирается снимок репозитория от 20.09.2026: [программный CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference), [аутентификация](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), [сетевой allowlist](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference). Выполнение задания проверяет закреплённую версию 1.0.86, а не текущий `latest`.
