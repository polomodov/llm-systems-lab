# ЛР11. Claude Code: автономное исправление, лимиты и полный usage

## Паспорт

| Поле | Значение |
| --- | --- |
| Обвязка | `claude-code`, CLI `@anthropic-ai/claude-code@2.1.83` |
| Предпосылка | [ЛР01](LAB01-reproducibility.md); Node.js ≥22, Git, Bash, Docker Engine; координатор от обычного пользователя |
| Основной маршрут | Anthropic API, `ANTHROPIC_API_KEY` из `.env`; локальный bridge не требуется |
| Минимальный объём | Offline проверка адаптера и образа, один реальный A2/T002 baseline с независимой оценкой |
| Расширения | Три повтора; T001 discovery/replay; T003; `without-spec`; отдельная проверка `hard` |
| Время | Ориентир: 2–3 часа оператора, сборка и работа оценщика отдельно; один agent execution ограничен 900 s |
| Готовность | Адаптер реализован, установка проверена 20.09.2026 на Linux/arm64; результат на машине учащегося и реальный эпизод — `not-run` до выполнения |

## Цель

Выполнить воспроизводимый эпизод в Claude Code и установить, какие данные подтверждают результат: артефакты и внешняя оценка, наблюдаемый ID модели, полный итоговый usage, причина остановки. Проверить различие между ограничением числа ходов, политикой USD и внешним timeout.

## Проверяемая гипотеза

Claude Code `2.1.83` с baseline-спецификацией способен завершить один A2/T002 в заданном окружении, а его итоговый `result` позволяет восстановить ходы, токены и сообщённую CLI стоимость без повторного сложения cache и `modelUsage`. Выполнение задачи и полнота метрик — два отдельных исхода: `pass` по задаче не доказывает полноту учёта.

До запуска запишите точный model ID, ожидаемые артефакты, правило остановки и правило проверки гипотезы. Результат одного эпизода не обобщается на все задачи или модели.

## Подготовка

Все команды выполняются из корня репозитория. Замените `my-session`, если этот отчёт уже существует; helper не перезаписывает папки. Значения в угловых скобках далее требуется заменить до исполнения. После ненулевого exit code сохраните ошибку и остановите зависимые шаги: наличие старого image tag или файла не подтверждает успех новой команды.

```bash
npm run lab:new -- --lab LAB11 --session my-session
LAB_DIR='experiments/claude-code/measurements/LAB11-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Прочитайте [спецификацию A2](../../agents/a2-janitor/spec.md), [открытый контракт T002](../../tasks/T002-repo-janitor/task.md), [профиль](../../experiments/claude-code/harness.json), [настройки](../../experiments/claude-code/settings.example.json) и [общий протокол оценки](harness-workflow.md). Не читайте `tasks/*/check/`, не меняйте контракты задач. Судью и метод `hidden-check` согласуйте до исполнения.

Подготовьте только `ANTHROPIC_API_KEY` в существующем `.env` через редактор. Если файла ещё нет, создайте его по `.env.example`, не затирая существующий. Не включайте значения ключей в команды, отчёт или логи; профиль передаёт credential процессам контейнера, но не монтирует host-файл `.env`. Ключ доступен инструментам внутри этого контейнера: это ограничение среды, описанное в [общей инфраструктуре](../../experiments/common/README.md).

Профиль поддерживает `anthropic` и API-домен `api.anthropic.com`, но не гарантирует доступ к конкретной модели аккаунта. Выберите точный доступный ID из своего API-доступа, без `latest`, `sonnet`, `opus` или другого плавающего алиаса. Зафиксируйте источник подтверждения доступности без секретов. Ни локальная подписка Claude, ни версия CLI на хосте не заменяют API-доступ и версию образа.

## Порядок выполнения

1. **Проверьте адаптер без модели.** Сохраните вывод и exit code; при ошибке завершите подготовку и опишите причину.

   ```bash
   node --test experiments/claude-code/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   По тестам объясните четыре случая: итоговый `modelUsage` не прибавляется повторно к `usage`; неполные cache buckets дают неизвестный input; ID из основного assistant response отличается от модели подагента; error subtype важнее exit 0. Эти синтетические случаи не являются успехом T002.

2. **Соберите и заморозьте образ.** Установка требует сети, следующие smoke-команды выполняются с отключённой сетью и без credentials. Сохраняйте один image ID для всей серии; закрепление CLI не делает свежую сборку системных пакетов побитно одинаковой.

   ```bash
   docker build --build-arg HARNESS_VERSION=2.1.83 \
     -t harness-lab/claude-code:2.1.83 \
     -f experiments/claude-code/Dockerfile experiments/claude-code \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/claude-code:2.1.83)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" claude --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" claude --help > "$LAB_DIR/raw/cli-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Проверьте фактическую версию `2.1.83`. По сохранённой справке найдите `--max-turns`, `--max-budget-usd`, `--permission-mode`, `--settings`, `--setting-sources`, `--output-format`. По адаптеру подтвердите `DISABLE_AUTOUPDATER=1`, режим `dontAsk` и пустые внешние setting sources. Запишите, что `settings.json` разрешает инструменты внутри внешней Docker-границы; сам файл настроек не изолирует скрытые проверки.

3. **Зарегистрируйте минимум: один новый T002.** В manifest отчёта заранее внесите `baseline`, `observed`, timeout 900 и ID образов. Основной маршрут выбирает общую бюджетную политику для сравнения с другими обвязками: USD cap здесь не применяется, native max-turns остаётся. Лимиты берутся из контракта, не редактируются в задаче.

   ```bash
   MODEL_ID='<точный доступный Anthropic model ID>'
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a2-janitor --task T002 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<ID, напечатанный new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Перенесите фактический ID в `manifest.json` отчёта. Проверьте `results/runs/$RUN_ID/inputs/manifest.json`: harness, provider, variant, seed commit и файлы. Снимок агента не должен содержать скрытые проверки или `.env`. После prepare не меняйте snapshot/workspace вручную.

4. **Выполните облачный эпизод.** Эта команда обращается к платному API выбранного аккаунта; `observed` не ограничивает счёт в USD.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   Проверьте `run.json`, `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch` и `artifacts/report.md`. Не исправляйте результат руками. `awaiting_review` означает готовность к оценке; `aborted` сохраняется с причиной. Повтор после ошибки получает новый ID, предыдущая попытка остаётся в отчёте.

5. **Проведите индивидуальный аудит трассы.** В основном `result` найдите `num_turns`, `total_cost_usd`, `usage`/`modelUsage`, `session_id` и причину остановки. Сопоставьте их с `run.json`. Для input используйте либо полную разбивку `modelUsage`, либо полную `usage`: input + cache creation + cache read. Два представления одной работы не складывают. Отдельно сопоставьте запрошенный `model.id` и `model.observed_id` из основного `assistant.message.model`. При отсутствии наблюдения оставьте неизвестность; при model drift текущий runner должен прервать попытку.

   Сохраните объяснение каждого неизвестного поля из `metrics_unavailable`. USD из CLI — сообщённая обвязкой стоимость, не сверка биллинга; количество compactions/подагентов неизвестно, если нет полного счётчика. Не публикуйте весь raw trace без проверки отсутствия чувствительного содержимого задачи.

6. **Получите независимую оценку.** Только для `awaiting_review` сформируйте JSON:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   Внешний оценщик выполняет проверку T002 по [процедуре](harness-workflow.md), заполняет `result`, `evaluator`, `check_output`, при необходимости `human_notes`; generated hashes сохраняются. Agent container не получает проверку, её ответ или возможность исправить результат после оценки. Импортируйте только заполненную оценку:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `fail` и `partial` — допустимые научные результаты завершённой работы. Без независимого судьи run остаётся `awaiting_review`, а минимальная работа не завершена. Для `aborted` судейство не выполняется; сохраните ошибку и сделайте новый пилот, если нужен завершённый эпизод.

7. **Расширение: три повтора и абляция.** До запуска задайте три baseline-слота и три `without-spec`-слота, порядок чередования и неизменные условия. Каждый слот создаётся командой шага 3 с новым ID; для абляции вместо baseline-подготовки выполните:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider anthropic
   ```

   Это альтернативный prepare новой записи, не повторная подготовка существующей. Выполните шаги 4–6 для каждого слота. Минимальный T002 служит pilot и допуском в ЛР09; сравнительные baseline/without-spec тройки всегда состоят из новых попыток. Сохраняйте начатые ошибки и не отбирайте удачные ID. Сравните назначенные ID:

   ```bash
   SERIES_RUN_IDS='<все назначенные run IDs через запятую>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   `without-spec` убирает только текст спецификации из prompt. Docker, gateway и независимый judge сохраняются. Интерпретация парных исходов и ledger — в [ЛР10](LAB10-ablation.md); незавершённые группы не объявляйте `pass^3`.

8. **Расширение: T001 replay и T003.** Для отдельного discovery T001 создайте новую запись и подготовьте её без архива:

   ```bash
   AS_OF_DATE='<зафиксированная дата YYYY-MM-DD>'
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a1-dossier --task T001 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<новый ID discovery>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic --as-of "$AS_OF_DATE"
   ```

   Выполните шаги 4–6; для T001 метод `rubric`, оценщик использует также предусмотренную проверку источников. Сохраните archive `trace/sources.jsonl` с телами и статусами ответов. Затем создайте ещё один T001 через `new-run` выше, присвойте его новый ID и используйте альтернативную подготовку:

   ```bash
   SOURCE_ARCHIVE='<путь к trace/sources.jsonl discovery run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Повторите исполнение и независимое судейство. Контролируемая T001-серия использует один архив и дату, live discovery в неё не входит. Для T003:

   ```bash
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a3-ledger-auditor --task T003 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<новый ID T003>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Выполните шаги 4–6 с методом `rubric`; сдайте `ledger.md` и `ablation-plan.md`. Конфигурации T003 различаются между обвязками, поэтому это аудит конкретного Claude deployment.

9. **Расширение Claude: `hard`.** Создайте и подготовьте отдельный baseline T002 командами шага 3, затем выполните:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode hard
   ```

   Сохраните лимиты из launch, фактическую причину остановки и reported cost. Непревышение бюджета в одном коротком эпизоде не доказывает поведение при исчерпании лимита; если он не достигнут, запишите «срабатывание не наблюдалось». Не меняйте task contract ради достижения лимита. Получите оценку по состоянию run. `hard` и `observed` остаются разными группами сравнения.

10. **Сформулируйте вывод и запишите наблюдения.** В `experiments/claude-code/NOTES.md` добавьте фактические ID, условия и недостатки; новый компонент требует новой строки [реестра](../harness-ledger.md), существующий адаптер — L008. Инфраструктурный smoke и эксперименты разместите в разных строках отчёта.

## Таблицы результатов

| Проверка среды | Наблюдаемый результат | Exit code | Evidence |
| --- | --- | --- | --- |
| Версия CLI, image ID/architecture, proxy ID, parser tests | Заполнить после выполнения | Заполнить | Относительный путь в `raw/` |

| Слот до запуска | Task/variant/budget | Run ID | Status | Verdict оценщика | Stop reason | Wall-clock, s |
| --- | --- | --- | --- | --- | --- | --- |
| Заполнить | T002/baseline/observed | После new-run | После run | После judge | Из record | Из record |

| Метрика | Значение или `null` | Единица/определение | Evidence | Причина отсутствия |
| --- | --- | --- | --- | --- |
| Requested/observed model; turns; input/cache/output; cost | Заполнить | Не смешивать buckets | Run ID + поле/событие | Заполнить при `null` |

| Дополнительная серия | Заранее назначенные ID | Исходы | Что изменено | Что можно заключить |
| --- | --- | --- | --- | --- |
| Повторы/абляция/replay/hard | Заполнить при выполнении | Все исходы | Одно условие | С ограничениями |

## Что сдать

- `report.md`, manifest с гипотезой до запуска, `run_ids` и ссылками на evidence; заполненные таблицы.
- Вывод adapter tests, build/version/help, immutable IDs и архитектуру образов.
- Минимум один реальный T002 с артефактами, исходной трассой, patch и внешней оценкой, связанной с manifests; все ошибочные попытки рядом в списке ID.
- Аудит usage и model identity, ответы на контрольные вопросы, запись в NOTES; результаты расширений, только если они выполнялись.

## Критерии завершения

- [ ] Точная версия и образ подтверждены на своей машине; parser tests проходят.
- [ ] Один T002 прошёл lifecycle до `completed` с независимым `pass`, `fail` или `partial`; ошибка установки или `awaiting_review` оформлена как незавершённость.
- [ ] Основной бюджет `observed` и timeout 900 явно записаны; optional hard не смешан с основной группой.
- [ ] `result`/`modelUsage` не посчитаны дважды; неизвестные метрики не заменены нулями.
- [ ] Запрошенная модель отделена от наблюдаемой, задача отделена от smoke.
- [ ] В отчёте нет credentials, скрытых проверок или вручную исправленных результатов; `npm run check` проходит.

## Контрольные вопросы

1. Чем `modelUsage` отличается от `usage`, и почему их нельзя сложить?
2. Как `observed` изменяет launch Claude и какой предел всё ещё принудительно действует?
3. Почему `dontAsk` и разрешённый `Bash` не дают агенту host workspace?
4. Чем основной `assistant.message.model` полезнее `init.model` для проверки идентичности?
5. Как трактовать `error_max_turns` при exit 0 и при наличии `report.md`?
6. Какое наблюдение действительно подтверждало бы срабатывание USD cap?
7. Что остаётся неизменным в `without-spec`, и почему это требуется?

## Источники

- [README Claude Code](../../experiments/claude-code/README.md), [профиль](../../experiments/claude-code/harness.json), [адаптер](../../experiments/claude-code/adapter.mjs), [тесты](../../experiments/claude-code/adapter.test.mjs), [Dockerfile](../../experiments/claude-code/Dockerfile).
- [Протокол](../method.md), [общая инфраструктура](../../experiments/common/README.md), [независимая оценка](harness-workflow.md), [ЛР10](LAB10-ablation.md).
- Команды и трактовки этой работы закреплены за исходниками текущего репозитория и CLI `2.1.83`; версия и реальный API-доступ проверяются при выполнении, не выводятся из даты документа.
