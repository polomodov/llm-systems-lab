# ЛР14. Antigravity CLI: Gemini API, автономный эпизод и границы наблюдаемости

## Паспорт

| Поле | Значение |
| --- | --- |
| Предварительная работа | [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `antigravity-cli`, официальный `agy` **1.2.7** |
| Основной маршрут | Облачный `google` / Gemini API; локальный bridge не требуется |
| Агент и задача | `a2-janitor` / T002 |
| Минимум | Offline smoke и один реальный T002 с независимой оценкой |
| Расширение | Три новых T002, T001 replay, T003, абляция спецификации |
| Время | Ориентир 2–4 часа без очередей провайдера; не результат измерения |
| Начальный статус | `not-run`: команды являются заданием, результаты ещё нужно получить |

## Цель

Провести T002 через собственный цикл `agy`, сохранить воспроизводимые входы и внешний verdict. Проверить, какие сведения действительно доступны из Antigravity stream-json, и не подменить идентификатор модели ответа настройкой CLI.

## Проверяемая гипотеза

Закреплённый Antigravity CLI с явным Gemini API model ID выполнит автономный T002 через разрешённый gateway и вернёт пригодный для независимой оценки результат. При этом итоговый `result` позволит получить output tokens, но текущий адаптер не подтвердит USD, внутренние модельные ходы, input/cache и фактический ID модели ответа. Успех задачи и полнота телеметрии проверяются раздельно.

## Подготовка

Нужны Node.js ≥22, Bash, Git, Docker и доступ к Gemini API. Координатор запускайте обычным пользователем из корня лаборатории. Для отдельной Linux x64 машины проведите собственный smoke: сохранённая в репозитории проверка 20.09.2026 относилась к Linux arm64. ROCm/Vulkan здесь не участвуют: модель обслуживается провайдером.

Прочитайте [README адаптера](../../experiments/antigravity-cli/README.md), [профиль](../../experiments/antigravity-cli/harness.json), [протокол](../method.md), спецификацию `agents/a2-janitor/spec.md` и открытый [контракт T002](../../tasks/T002-repo-janitor/task.md). Не читайте `tasks/*/check/`, не изменяйте контракт задачи и запечатанные входы.

Выполняйте блоки последовательно в Bash; после ошибки разберите её до следующего шага. Создание отчёта не создаёт экспериментальный run:

```bash
npm run lab:new -- --lab LAB14 --session my-session
LAB_DIR='experiments/antigravity-cli/measurements/LAB14-my-session'
HARNESS_VERSION='1.2.7'
IMAGE_REF='harness-lab/antigravity-cli:1.2.7'
PROVIDER_ID='google'
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
git status --short > "$LAB_DIR/raw/working-tree.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

До API-вызова запишите гипотезу, лимиты из T002, timeout **900 s**, `budget-mode=observed`, одну основную попытку и имя независимого оценщика в отчёт. В `.env` требуется только имя **`GEMINI_API_KEY`** из выбранного профиля; значение не печатайте, не копируйте в отчёт и не передавайте через `docker --env-file`. Координатор читает `.env` сам. `settings.json` задаёт `modelProvider: gemini`; это Antigravity CLI, а не пакет Gemini CLI и не интерактивная подписка Antigravity.

## Порядок выполнения

1. **Соберите закреплённый образ и gateway.** Сборка загружает системные пакеты и официальный архив, но не вызывает модель. Если эти образы уже существуют, можно использовать их, сохранив ID. Установщик проверяет SHA-512 по локальному manifest версии 1.2.7; не подменяйте его установкой `latest`.

   ```bash
   docker build --build-arg HARNESS_VERSION="$HARNESS_VERSION" \
     -t "$IMAGE_REF" experiments/antigravity-cli \
     > "$LAB_DIR/raw/build.log" 2>&1
   docker pull node:24.13.1-bookworm-slim
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker image inspect node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-image.json"
   IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
   PROXY_IMAGE_ID="$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)"
   ```

2. **Проверьте CLI без API и ключей.** Сохраните вывод версии и справки, затем проверьте синтетические тесты адаптера. Здесь нет mount репозитория или `.env` и нет сетевого доступа. `--version` должен показать 1.2.7; несовпадение означает остановку до эпизода.

   ```bash
   for FLAG in --version --help; do
     if docker run --rm --network none --read-only \
       --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
       --memory 2g --pids-limit 256 \
       --tmpfs /tmp:rw,nosuid,noexec,size=512m,mode=1777 \
       --env HOME=/tmp --workdir /tmp \
       "$IMAGE_ID" agy "$FLAG" \
       > "$LAB_DIR/raw/agy-${FLAG#--}.txt" 2>&1; then
       printf '%s\n' 0 > "$LAB_DIR/raw/agy-${FLAG#--}.exit"
     else
       SMOKE_STATUS=$?
       printf '%s\n' "$SMOKE_STATUS" > "$LAB_DIR/raw/agy-${FLAG#--}.exit"
       break
     fi
   done
   node --test experiments/antigravity-cli/adapter.test.mjs \
     > "$LAB_DIR/raw/adapter-tests.tap" 2>&1
   ```

   Проверьте коды завершения каждого smoke и содержание файлов; отсутствие второго файла после `break` означает незавершённый smoke. В тестах найдите случаи финального aggregate, повторного `step_update`, неполной трассы и неподдерживаемого USD cap. Объясните, почему `num_turns` Antigravity не переносится в `loop.turns`: здесь это пользовательские запросы, а не внутренние обращения модели.

3. **Зафиксируйте модель и создайте T002.** Выберите явный доступный ID в своём Gemini API аккаунте до создания записи. `google/gemini-2.5-pro` используется в синтетическом тесте адаптера; это не подтверждение доступности в вашем аккаунте. В примере ниже замените placeholder. Профиль допускает префикс `google/`, адаптер передаёт CLI ID без него. Не используйте `auto`, `latest` или `default`.

   ```bash
   MODEL_ID='<явный доступный ID модели Gemini API>'
   npm run new-run -- --harness antigravity-cli \
     --harness-version "$HARNESS_VERSION" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --agent a2-janitor --task T002
   ```

   Перенесите выданный ID в manifest отчёта и переменную. Далее используется только эта новая запись:

   ```bash
   RUN_ID='<ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Убедитесь, что запись стала `prepared`. Снимок фиксирует `settings.json`, runtime wrapper и явный `google` profile. Runtime создаёт временный HOME и переносит туда настройку Gemini API; файлы авторизации хоста не подключаются. Разрешённый API-домен профиля — `generativelanguage.googleapis.com`.

4. **Выполните одну реальную попытку.** Эту команду запускают после подготовки ключа и согласования протокола оценки; это первый этап работы, который обращается к модели.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" \
     --proxy-image "$PROXY_IMAGE_ID" --provider "$PROVIDER_ID" \
     --model "$MODEL_ID" --timeout 900 --budget-mode observed
   ```

   `observed` не обеспечивает USD cap из контракта. У `agy` также нет подтверждённого ограничения внутренних ходов; принудительный предел обеспечивает внешний timeout. Адаптер использует `--output-format stream-json`, отключает slash-разворачивание, явно передаёт `--print-timeout 0` и пропускает интерактивные разрешения внутри Docker. Пропуск разрешений сам по себе не является изоляцией.

5. **Проверьте состояние и происхождение метрик.** Сохраните сводку, которая не включает credentials:

   ```bash
   node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/summary-$RUN_ID.json"
   import { readFileSync } from 'node:fs';
   const run = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ run_id: run.run_id, status: run.status, harness: run.harness,
     model: run.model, loop: run.loop, metrics_unavailable: run.metrics_unavailable,
     verdict: run.verdict }, null, 2));
   NODE
   ```

   Установите по record и raw trace, был ли финальный `event: result`, какой `result.status` получен и есть ли корректный `usage.output_tokens`. Не суммируйте накопительный итог со `step_update`. `init.model` — настройка; текущий `observed_id=null` не заменяют её значением. `tokens_in`, USD и модельные ходы сохраняются неизвестными с причинами. Если сеть/авторизация не прошла, сохраните отказ; не расширяйте allowlist wildcard и не меняйте профиль после `prepare`. Исправление создаёт новую конфигурацию и новый run.

6. **Получите независимую оценку.** Только `awaiting_review` допускает следующую последовательность. `aborted` сохраняется со своей причиной; без завершённой реальной попытки минимальная работа остаётся незавершённой. Exit 0 не является `pass`.

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" \
       > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Передайте неизменные результаты внешнему оценщику по [процедуре судейства](harness-workflow.md). Для T002 он выполняет скрытую проверку вне контейнера агента, заполняет `result` (`pass`, `fail` или `partial`), `evaluator`, `check_output` с версией проверки и наблюдениями, при необходимости `human_notes`. Сгенерированные hashes не меняются. Решающий задачу агент не получает скрытую проверку. Пока оценщика нет, сохраняется `awaiting_review`.

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/compare.json"
   npm run check
   ```

   После импорта содержательной оценки ожидается `completed`; отрицательный verdict также является пригодным результатом лабораторной. `judge-run` проверяет целостность, но не выносит содержательное решение самостоятельно. Внесите реальные run IDs и наблюдения в `experiments/antigravity-cli/NOTES.md`; при добавлении компонента требуется строка ledger в том же изменении.

7. **Выполните выбранное расширение.** Основной эпизод считайте pilot. Для серии создайте **три новых** T002 через шаги 3–6, заранее назначив порядок; сохраните один image ID/model/provider/timeout/budget policy. Не заменяйте начатые неудачи успешным повтором.

   ```bash
   SERIES_RUN_IDS='<три новых run ID через запятую без пробелов>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-series.json"
   ```

   Для T001 создайте новую запись и подготовьте её с одним архивом discovery run, содержащим тела/статусы страниц, и общей датой. Если архива нет, сначала проведите отдельный live discovery по [общей процедуре](harness-workflow.md); не включайте его в controlled replay серию.

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl зарегистрированного discovery run>'
   AS_OF_DATE='<общая дата YYYY-MM-DD>'
   npm run new-run -- --harness antigravity-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a1-dossier --task T001
   RUN_ID='<новый T001 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" \
     --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Исполнение — шаг 4, оценка — шаг 6, но T001 использует `rubric` и предусмотренный проверяющий скрипт. Для T003 отдельно выполните:

   ```bash
   npm run new-run -- --harness antigravity-cli --harness-version "$HARNESS_VERSION" \
     --provider "$PROVIDER_ID" --model "$MODEL_ID" --agent a3-ledger-auditor --task T003
   RUN_ID='<новый T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
   ```

   Повторите исполнение и внешнюю оценку методом `rubric`. T003 содержит конфигурацию выбранной обвязки, поэтому его результаты между harness не имеют одинаковых входов. Для абляции повторите создание T002 из шага 3 с новым ID и подготовьте `--variant without-spec`; затем выполните шаги 4–6. Полная проверка эффекта — три baseline и три without-spec по [ЛР10](LAB10-ablation.md); Docker, gateway и hidden-check остаются неизменными.

## Таблицы результатов

Заполните условия до вызова API, результаты — после наблюдения. Прочерк означает пустое поле, а не ноль.

| Run ID | Вариант/задача | CLI version / image ID | Requested model / provider | Статус | Независимый verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

| Показатель | Значение | Единица | Наблюдение или причина `null` | Источник в trace/record |
| --- | --- | --- | --- | --- |
| Выходные токены | — | tokens | — | — |
| Входные/cache токены | — | tokens | — | — |
| Внутренние ходы | — | turns | — | — |
| Стоимость | — | USD | — | — |
| Время | — | s | — | — |
| Модель ответа | — | ID | — | — |

| Проверка | Ожидание, заданное до запуска | Фактическое наблюдение | Evidence / ограничение |
| --- | --- | --- | --- |
| Offline version/help | 1.2.7, без сети и ключа | — | — |
| Итоговый stream-json | Последний корректный result | — | — |
| Автономный T002 | Результат для внешней оценки | — | — |

## Что сдать

- Manifest и отчёт LAB14 с гипотезой, заранее заданными условиями, заполненными таблицами и ответами на вопросы.
- Build/version/help/test evidence, image IDs и сведения об архитектуре; это отдельные инфраструктурные результаты.
- Реальный `results/runs/<run-id>/run.json`, архив inputs/trace/artifacts и независимую оценку; для T002 — также ссылку на `trace/change.patch`.
- Compare JSON на явно выбранных IDs, NOTES и ledger update при изменении компонентов. Не включайте `.env` или значения ключей.

## Критерии завершения

- [ ] Версия и архитектура подтверждены собственным offline smoke, unit-тесты прошли.
- [ ] Хотя бы один реальный T002 прошёл полный lifecycle до `completed` с независимым verdict; все остальные попытки также перечислены.
- [ ] Google API profile, requested model, immutable images, timeout 900 s и observed budget сохранены.
- [ ] Неизвестные input/cache, модельные ходы, USD и observed model не заменены выдуманными значениями.
- [ ] Двойной учёт aggregate исключён, границы контейнера сохранены, `npm run check` проходит.
- [ ] В отчёте различаются smoke, выполнение CLI и содержательный успех задачи; расширения обозначены выполненными только при наличии evidence.

## Контрольные вопросы

1. Чем Antigravity CLI с `modelProvider: gemini` отличается от Gemini CLI и подписочного входа?
2. Почему `init.model` не подтверждает underlying модель ответа?
3. Чем `num_turns` этой трассы отличается от модельных ходов других harness?
4. Что произойдёт с output tokens при суммировании `step_update` и итогового aggregate?
5. Какие ограничения реально действуют при `--print-timeout 0` и `--budget-mode observed`?
6. Можно ли сдать работу с независимым `fail`, и почему это отличается от `aborted` без оценки?

## Источники

- [README и ограничения адаптера](../../experiments/antigravity-cli/README.md), [NOTES](../../experiments/antigravity-cli/NOTES.md), [offline evidence 20.09.2026](../../experiments/antigravity-cli/smoke/2026-09-20.json).
- [Профиль](../../experiments/antigravity-cli/harness.json), [адаптер](../../experiments/antigravity-cli/adapter.mjs), [тесты](../../experiments/antigravity-cli/adapter.test.mjs), [runtime](../../experiments/antigravity-cli/run-cli.mjs), [release manifest](../../experiments/antigravity-cli/releases/1.2.7.json), [Dockerfile](../../experiments/antigravity-cli/Dockerfile).
- [Протокол](../method.md), [общий workflow](harness-workflow.md), [реестр L010](../harness-ledger.md), [ЛР09](LAB09-agent-campaign.md), [ЛР10](LAB10-ablation.md).
- Первичные ссылки, закреплённые в исследовании репозитория от 20.09.2026: [установка](https://antigravity.google/docs/cli/install/), [headless protocol](https://antigravity.google/docs/cli/headless/). Свойства данной работы привязаны к локально закреплённой версии 1.2.7.
