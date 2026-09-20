# Общая процедура лабораторных по агентным обвязкам

Эта инструкция дополняет **ЛР11–19**: конкретные версии, команды сборки, провайдеры, smoke и исследуемые особенности находятся в отдельной работе каждой обвязки. Все команды выполняются из корня репозитория в Bash. `LAB_DIR` берётся из созданного отчёта выбранной работы; `RUN_ID` всегда копируется из фактического вывода `new-run`.

Перед переносимыми примерами ниже задайте единые имена переменных, подставив фактические условия своего задания. В отдельных работах образ может называться `IMAGE_ID`, а provider указываться прямо в команде; Bash не переносит такие значения автоматически:

```bash
HARNESS_ID='<harness из выбранной ЛР, например pi>'
PROVIDER_ID='<его выбранный provider, например anthropic>'
MODEL_ID='<точный ID или managed:mode из своего отчёта>'
IMAGE_REF='<immutable image ID собранной обвязки>'
PROXY_IMAGE_REF='<immutable ID подготовленного proxy image>'
```

## Что считается выполненной лабораторной

Обязательный минимум одной работы — подготовить и проверить выбранную обвязку, выполнить **одну новую T002**, получить независимую оценку и разобрать её трассу. Проверки установки без API можно пройти заранее; они не заменяют модельный опыт. `completed/fail` или `completed/partial` могут быть корректным учебным результатом: оценивается полнота исследования, а не обязательная победа модели. `aborted` сохраняется, но если минимальная серия требует оценённую задачу, одной инфраструктурной ошибки для завершения работы недостаточно. Повтор после исправления получает новый run ID.

Перед исполнением заполните гипотезу, исходы, лимиты, число попыток и порядок в отчёте. Дополнительные задания T001/T003, тройки и абляции назначаются заранее; не добавляйте повторы только до первого успеха.

| Этап | Допустимое свидетельство | Чего он ещё не подтверждает |
| --- | --- | --- |
| Unit/offline smoke | Лог теста/версии/import и его exit code | Доступ модели в аккаунте и качество задачи |
| Prepared | Запечатанные входы и начальное workspace | Выполнение агентом |
| Awaiting review | Трасса, артефакты, финальное workspace | Независимый verdict |
| Completed | Оценка, связанная с hashes результата | Универсальную надёжность по одной попытке |
| Aborted | Причина остановки и все оставшиеся данные | Pass, нулевую стоимость или отсутствующие токены |

## Среда и секреты

Docker выполняет контейнер Linux, даже если координатор работает на другой ОС. Для облачных ЛР11–19 GPU и Ryzen не обязательны. Используйте фактическую поддержанную архитектуру образа из задания; несовместимая архитектура — blocker установки, не ошибка модели.

Значения credentials находятся только в корневом `.env` и передаются через координатор для выбранного provider. Не выполняйте `source .env`, не печатайте переменные/файл и не передавайте весь файл через `docker --env-file`. Редактируйте существующий `.env` без перезаписи других ключей. `npm run harnesses` показывает только имена необходимых переменных и возможности профиля.

В каждом образе и серии сохраняйте exact CLI/SDK version и immutable image ID. До запуска агента проверьте также локальный proxy image из общей инструкции. Smoke без сети и ключей не делает API-вызовов. Команды `run` из заданий, напротив, обращаются к выбранному сервису и могут расходовать его квоту.

Основной режим всех девяти заданий — `--budget-mode observed --timeout 900`. `observed` не ограничивает USD: это явно записанное отклонение от бюджета task contract. Claude Code дополнительно исследует `hard` отдельно от общей серии. Внешний timeout одинаков; native turn/step/iteration limits и их семантика сохраняются такими, как реализованы конкретным адаптером.

## Проверка результата исполнения

После `run` сначала прочитайте состояние, затем выбирайте следующий шаг. Сохраните краткий паспорт из **собственной** записи; код читает только `run.json`, не `.env` и не hidden checks:

```bash
node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/result-$RUN_ID.json"
import { readFileSync } from 'node:fs';
const record = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
console.log(JSON.stringify({
  run_id: record.run_id, status: record.status,
  harness: record.harness, model: record.model,
  permissions: record.permissions, sandbox: record.sandbox,
  image_id: record.execution.image_id, timeout_s: record.execution.timeout_s,
  budget_policy: record.execution.budget_policy,
  exit_code: record.execution.exit_code, timed_out: record.execution.timed_out,
  loop: record.loop, metrics_unavailable: record.metrics_unavailable,
  verdict: record.verdict
}, null, 2));
NODE
```

Сравните агрегаты с исходной трассой выбранной обвязки. Запрошенный model ID и наблюдаемая модель — разные поля; managed selector Amp и selector Copilot нельзя превратить в доказанный exact snapshot. Неполная трасса и native error при exit 0 могут дать `aborted`. При `planned/prepared` модель ещё не запускалась; при `running` сначала выясните состояние своего координатора и контейнера. Не исправляйте JSON вручную для перехода на следующий этап.

Состояние `awaiting_review` разрешает независимую оценку. `aborted` остаётся зарегистрированной неудачной попыткой; его не передают в `judge-run` для превращения в успех. Сохраните stop reason, сведения об ошибке и решение о следующей новой попытке.

## Независимая оценка

Оценщик действует вне agent container и не передаёт скрытую проверку агенту. Для T002 используется `hidden-check`; для T001/T003 — `rubric`, причём оценка T001 учитывает предусмотренную внешнюю проверку. Конкретный запуск скрытого оценщика берётся из его операторской инструкции. Универсальной команды, которая автоматически выносит содержательный verdict для всех задач, в этом проекте нет.

При `awaiting_review` создайте **новый** шаблон; `noclobber` сохраняет уже заполненную оценку при повторном вызове:

```bash
EVALUATION_FILE="$LAB_DIR/raw/evaluation-$RUN_ID.json"
(
  set -o noclobber
  npm run --silent evaluation-template -- --run "$RUN_ID" > "$EVALUATION_FILE"
)
```

Если команда завершилась ошибкой, разберите причину до следующего шага. Судья заполняет `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` и при необходимости `human_notes`. В `check_output` должны быть версия проверки/рубрики, условия применения и наблюдения, обосновывающие verdict. Хеши `artifacts_sha256` и `workspace_sha256`, `run_id` и `method` сохраняются из шаблона. Не редактируйте результаты агента до или после оценки.

```bash
npm run judge-run -- --run "$RUN_ID" --evaluation "$EVALUATION_FILE"
npm run check
```

`judge-run` проверяет привязку оценки и целостность. Он не подменяет судью. После успешного импорта ожидается `completed` с фактическим verdict; при отсутствии оценщика сохраняйте `awaiting_review` и незавершённый статус учебной работы. Перенесите итоговые поля в отчёт после импорта, сохранив исходный паспорт исполнения отдельно.

## Дополнительное задание T001: один архив источников

До серии решите, нужен ли новый discovery run. Если архив ещё не получен, создайте отдельный T001 с `a1-dossier`, подготовьте его с выбранной датой `--as-of`, выполните тем же lifecycle и сохраните `trace/sources.jsonl`. Он должен содержать URL, статусы и **тела ответов**. Discovery не включается в контролируемое сравнение.

Для каждой новой replay-попытки используйте одинаковый архив и дату. Следующие значения заменяются фактическими до выполнения:

```bash
AS_OF_DATE='<дата discovery YYYY-MM-DD>'
SOURCE_ARCHIVE='results/runs/<discovery-run-id>/trace/sources.jsonl'
npm run new-run -- --harness "$HARNESS_ID" --agent a1-dossier --task T001 --provider "$PROVIDER_ID" --model "$MODEL_ID"
RUN_ID='<новый ID из вывода>'
npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --provider "$PROVIDER_ID" --model "$MODEL_ID" --timeout 900 --budget-mode observed
```

Используйте собственный output prefix/run ID для новой оценки и трассы. Replay не догружает отсутствующие страницы; API модели остаётся онлайн. Сохраняйте archive hash и не сравнивайте live/replay как одинаковые входы.

## Дополнительное задание T003: аудит обвязки

```bash
npm run new-run -- --harness "$HARNESS_ID" --agent a3-ledger-auditor --task T003 --provider "$PROVIDER_ID" --model "$MODEL_ID"
RUN_ID='<другой новый ID из вывода>'
npm run prepare-run -- --run "$RUN_ID" --provider "$PROVIDER_ID" --variant baseline
npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE_REF" --provider "$PROVIDER_ID" --model "$MODEL_ID" --timeout 900 --budget-mode observed
```

Оцените по внешней рубрике. Workspace T003 содержит разрешённый снимок именно выбранной обвязки, доступный для чтения, и отдельный записываемый каталог артефактов. Разные harness дают разные входы, поэтому эта серия диагностическая. Самоутверждение агента о полезности компонента не делает ledger row подтверждённой.

## Повторы, сравнение и комплект сдачи

Для тройки назначьте три новых run ID до знания исходов; повторите полный lifecycle. Один pilot не превращайте задним числом в первую из удачных попыток. Сохраняйте все начатые ошибки; `compare` включает начатые aborted в знаменатель и отдельно показывает незавершённые/не начавшиеся записи:

```bash
SERIES_RUN_IDS='<первый ID>,<второй ID>,<третий ID>'
npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare-triple.json"
```

Покажите исходы, покрытие измерений и отдельные groups. Не объединяйте разные модели/providers/policies ради одного рейтинга. Контролируемое сравнение обвязок описано в [ЛР09](LAB09-agent-campaign.md); шесть парных попыток с `baseline/without-spec` — в [ЛР10](LAB10-ablation.md). Абляция не снимает sandbox/network boundaries.

Каждая ЛР11–19 сдаётся со своими заполненными таблицами, `report.md`, учебным `manifest.json`, численными наблюдениями в TSV, raw evidence и ссылками на настоящие `results/runs/<run-id>/`. `harness_id` учебного manifest обозначает выбранную обвязку; он не удостоверяет её выполнение. Не перезаписывайте журналы при смене модели, provider, image или попытки. `*.log` игнорируются Git: сохраните полный архив evidence отдельно от обычного commit.

В `experiments/<harness>/NOTES.md` внесите измеренные ограничения и run IDs. Если добавлялся компонент, одновременно добавьте его запись в [ledger](../harness-ledger.md); до доказательства эффекта не используйте статус «подтверждена». Заключение должно отвечать на гипотезу в пределах условий данной серии.

Источники: [метод](../method.md), [жизненный цикл записей](../../results/README.md), [общая инфраструктура](../../experiments/common/README.md), [матрица обвязок](../harnesses.md), [evaluation-template](../../scripts/evaluation-template.mjs), [judge-run](../../scripts/judge-run.mjs), [compare](../../scripts/compare.mjs).
