# agent-harnesses-exps

Лаборатория для запуска одинаковых автономных агентов на одинаковых задачах в разных обвязках. Измеряем не только успех, стоимость и время, но и то, какие инструкции, ограничения и инструменты понадобились обвязке. Затем удаляем необязательные компоненты и повторяем эпизод.

## Что уже работает

- Общий цикл `new-run → prepare-run → run → judge-run → compare`.
- Адаптеры **всех девяти обвязок**: Claude Code, OpenCode, Codex, Antigravity CLI, Pi, mini-SWE-agent, OpenHands, Copilot CLI и Amp. Закреплены версии CLI/SDK; параметры и ограничения доступны через `npm run harnesses`.
- Три задачи: A1/T001 — досье по источникам; A2/T002 — исправление маленького репозитория; A3/T003 — аудит конфигурации.
- Docker изолирует агента от скрытых проверок, `.env` и метаданных результатов. Исходящий доступ проходит через отдельный gateway.
- Снимки входов с SHA-256, исходные трассы, неизвестные метрики с причинами, независимая оценка с привязкой к результату.
- Сравнение только одинаковых условий; `pass@3` и `pass^3` по полным тройкам. Абляция спецификации через `--variant without-spec`.

**Состояние на 22.10.2026:** есть аппаратные измерения Ryzen и Apple и 11 записей агентных запусков. Три Pi/local/T002 независимо оценены: два `fail` и один `pass`; ещё шесть записей — `aborted`, одна — `awaiting_review`, одна — `prepared`. Полных троек с одинаковыми условиями и сравнения разных обвязок пока нет. Фактическое покрытие и ограничения приёмки собраны в [статусах лабораторных](docs/labs/README.md#состояние-выполнения-на-22102026). Проверки инфраструктуры не заменяют оценку качества агентов.

**05.11.2026:** комплекты измерений локальных моделей (около 150 МБ с бинарными журналами) вынесены из дерева в [архив по коммиту](experiments/local-models/measurements/README.md); документация ссылается на permalink. Дерево `experiments/` уменьшилось со 155 МБ до 2 МБ.

## Лабораторные работы

[Практикум из 52 лабораторных работ](docs/labs/README.md) включает отдельную работу для каждой из девяти обвязок, воспроизводимость, исследования моделей на Ryzen, Vulkan/HIP, движки, сервисы, агентные сравнения и абляции. ЛР20–27 добавляют калибровку оценивания, память, инструменты, восстановление, делегирование, квантизацию, параллельную нагрузку и регрессии после обновлений. В каждой работе есть пошаговые задания, таблицы, комплект сдачи и контрольные вопросы. ЛР28–35 добавляют Apple M5 Max / 128 GB / macOS: Metal, MLX, сервисы, контекст/tools, нагрузку и сравнение с Ryzen. ЛР36–42 (платформа песочниц SPACE), ЛР43–47 (Kubernetes и GPU) и ЛР48–52 (AWS и Terraform) с 05.11.2026 **заморожены**: это методички без измерений, они ждут выделения в отдельный учебный репозиторий и не открывают новых сессий.

```bash
npm run labs
npm run lab:new -- --lab LAB01 --session first-pass
```

`lab:new` создаёт пустой комплект отчёта и сохраняет существующие файлы. После ЛР01 можно сразу проходить **ЛР11–19 по всем harness**, затем облачное сравнение ЛР09 и абляцию ЛР10. Отчёт отдельной обвязки сохраняется в `experiments/<harness>/measurements/`, отчёт работы SPACE — в `experiments/space/measurements/`, работы ветки Kubernetes и GPU — в `experiments/k8s-gpu/measurements/`, работы ветки AWS и Terraform — в `experiments/aws/measurements/`. ЛР02–07 выполняются на Ryzen; в ЛР08 реализован локальный Pi/T002 bridge для native llama.cpp. Ryzen/ROCm имеет оценённые pilot, Apple/Metal ждёт оценки; остальные локальные адаптеры требуют реализации и допуска.

Для подготовки без API есть [четыре синтетических упражнения](docs/labs/practice.md) и [публичные многошаговые эпизоды](docs/labs/episodes/README.md). Они не создают экспериментальных результатов. [Проверка комплектности отчёта](docs/labs/report-validation.md) учитывает все плановые попытки, включая ошибки и пропуски:

```bash
npm run lab:practice -- --scenario retry-429 --session first-pass
npm run lab:check -- --report experiments/local-models/measurements/LAB01-first-pass
```

Для сдачи заполненного отчёта добавьте `--mode submission`. ЛР21–24 требуют инженерных расширений, ЛР25 — принятой ЛР08; учебные traces не заменяют эти допуски или реальные модельные серии.

## Локальные модели

Для машины **Ryzen AI Max+ 395 / 128 GB / Linux** есть [план исследования](docs/local-models.md), [каталог](docs/local-model-candidates.md), [Linux runbook](docs/local-model-runtime.md) и реальные отчёты ЛР02–06, 08, 26. `npm run local:plan` показывает кандидатов; `npm run local:plan -- --context 32768` пересчитывает запас под контекст. Сам planner не скачивает и не запускает веса. Реальные Pi/T002 используют отдельный [local provider](experiments/pi/README.md#local-provider-bridge--первая-реализация-lab08) и запечатанную конфигурацию; наблюдения одного deployment не подтверждают весь каталог.

[Матрица движков](docs/local-inference-engines.md) включает равноправные llama.cpp Vulkan/HIP, vLLM и SGLang на ROCm, Transformers reference, Ollama, LM Studio и Lemonade. `npm run local:engines` выводит 12 профилей; `npm run local:plan -- --engine all --format json` строит пространство исследований. Для native checkpoint вместо GGUF и неизмеренного расхода сервиса planner сохраняет неизвестную память, не обещая fit.

Второй стенд — [Apple M5 Max / 128 GB / macOS](experiments/local-models/apple/README.md). `npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine all` выбирает Apple, `npm run local:engines -- --hardware apple-m5-max-128gb-macos` показывает пять профилей. Без `--hardware` сохраняется Ryzen. Измерены конкретные Metal/MLX deployments и нагрузка; LAB32 квалифицирована частично, LAB33 и полная LAB35 не завершены. Максимальный GPU budget Apple остаётся неизвестным; GGUF и MLX имеют отдельные manifests. Apple pilot LAB08 исполнен и ожидает независимого verdict.

## Требования и образы

Нужны Node.js ≥22, Git, Bash и работающий Docker Engine. Координатор запускается обычным пользователем, не root. npm-зависимостей у координатора нет. Образы используют Node.js 24.13.1; версии CLI задаются при сборке. Версии девяти обвязок собраны и проверены без запросов к модели 20.09.2026. Пример двух образов:

```bash
docker build --build-arg HARNESS_VERSION=2.1.83 \
  -t harness-lab/claude-code:2.1.83 \
  -f experiments/claude-code/Dockerfile experiments/claude-code

docker build --build-arg HARNESS_VERSION=1.18.29 \
  -t harness-lab/opencode:1.18.29 \
  -f experiments/opencode/Dockerfile experiments/opencode

docker pull node:24.13.1-bookworm-slim
test -e .env || cp .env.example .env
```

Заполните в `.env` ключ выбранного провайдера — нужные имена перечислены в `.env.example` и `npm run harnesses`. Координатор передаёт только credentials из выбранного профиля, не исполняет shell-подстановки и не наследует credentials из домашней папки. Для Pi, mini-SWE-agent и OpenHands провайдера можно выбрать через `--provider anthropic` или `--provider openai` на стадии подготовки. Идентификаторы собранных образов фиксируются в каждой записи; для серии используйте один образ, а не пересобирайте его между повторами. `--proxy-image` позволяет выбрать другой подготовленный образ Node.js, его ID тоже записывается.

Остальные закреплённые образы:

| `--harness` | Image/tag | Ключ `.env` |
| --- | --- | --- |
| `codex` | `harness-lab/codex:0.155.1` | `CODEX_API_KEY` |
| `antigravity-cli` | `harness-lab/antigravity-cli:1.2.7` | `GEMINI_API_KEY` |
| `pi` | `harness-lab/pi:0.73.1` | `ANTHROPIC_API_KEY` или `OPENAI_API_KEY` |
| `mini-swe-agent` | `harness-lab/mini-swe-agent:2.4.6` | `ANTHROPIC_API_KEY` или `OPENAI_API_KEY` |
| `openhands` | `harness-lab/openhands:1.49.2` | `ANTHROPIC_API_KEY` или `OPENAI_API_KEY` |
| `copilot-cli` | `harness-lab/copilot-cli:1.0.86` | `COPILOT_GITHUB_TOKEN` |
| `amp` | `harness-lab/amp:0.0.1789920039-gafe14b` | `AMP_API_KEY` |

Сборка: `docker build --build-arg HARNESS_VERSION=<pin> -t harness-lab/<harness>:<pin> experiments/<harness>`. Подробности, первичные источники и результаты offline smoke — в [матрице](docs/harnesses.md) и README каждой обвязки. Эти же теги уже собраны в текущем Docker окружении.

## Первый прогон

Пример для локальной задачи без изменяющихся web-источников:

```bash
npm run new-run -- --harness claude-code --agent a2-janitor --task T002
RUN_ID='<идентификатор из вывода new-run>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" \
  --image harness-lab/claude-code:2.1.83 \
  --model '<точный model ID в Anthropic API>' --timeout 900
```

`new-run` никогда не перезаписывает существующий прогон, включая повторный `--n`. `prepare-run` выполняет setup в отдельной папке, фиксирует спецификацию, контракт, конфиг, код координатора и начальное дерево. `run` проверяет, что они не изменились, определяет версию CLI внутри образа и запускает агента. Лимиты ходов и USD берутся из задачи. Таймаут — жёсткий внешний предел в секундах. Выходные артефакты лежат в `results/runs/$RUN_ID/artifacts/`, трасса — в `trace/`.

После успешного исполнения состояние — **awaiting_review**, а не `pass`. Ненулевой выход, таймаут, смена модели или ошибка координатора дают **aborted**. Повтор — всегда новая запись, чтобы не терять неудачные попытки. После принудительного завершения самого координатора через SIGKILL проверьте контейнеры с label `harness-lab=true` и незавершённую запись; автоматическое возобновление не реализовано.

Для остальных восьми обвязок выберите соответствующие harness/image и добавьте `--budget-mode observed`: жёсткая USD-граница ими не подтверждена. Это исследовательский прогон с отклонением от бюджета контракта; отчёт отделяет его от режима `hard`. Для CLI без native turn limit остаётся внешний timeout; SDK применяют собственные ограничения шагов. Неизвестные метрики не заменяются нулём.

Пример Codex:

```bash
npm run new-run -- --harness codex --agent a2-janitor --task T002 --provider openai
RUN_ID='<новый идентификатор>'
npm run prepare-run -- --run "$RUN_ID"
npm run run -- --run "$RUN_ID" --image harness-lab/codex:0.155.1 \
  --model '<доступный exact model ID>' --budget-mode observed
```

Amp не выбирает точную underlying модель: укажите `--model managed:low`, `managed:medium`, `managed:high` или `managed:ultra`. В записи сохраняются managed selector и `model.lock=true`; их нельзя сравнивать с exact model как одинаковые условия. Другие обвязки требуют явный model ID/поддерживаемый selector; независимое подтверждение модели ответа записывается отдельно.

## Независимая оценка

Скрытый скрипт или рубрика применяются **оператором вне контейнера агента**. Координатор не читает скрытые проверки и не передаёт их модели. Формат JSON одинаков для обоих способов. T002 заранее помечается `hidden-check`, T001/T003 — `rubric`; для T001 оценщик учитывает скрипт и рубрику. Укажите версию проверки/рубрики и наблюдения в `check_output`, имя оценщика — в `evaluator`.

Создайте заготовку после исполнения:

```bash
node scripts/evaluation-template.mjs --run "$RUN_ID" \
  > "results/runs/$RUN_ID/evaluation.draft.json"
```

Заполните `result` (`pass`, `fail`, `partial`), `evaluator`, `check_output` и при необходимости `human_notes`. Хеши не меняйте: они связывают оценку с артефактами и финальным workspace. Наличие обязательных файлов проверяется дополнительно, но содержательную оценку делает внешний судья.

```bash
npm run judge-run -- --run "$RUN_ID" \
  --evaluation "results/runs/$RUN_ID/evaluation.draft.json"
npm run check
npm run compare
```

`judge-run` отклоняет изменённые входы/результаты и оценку от другой записи. После импорта состояние — `completed`. Исходный JSON оценки сохраняется в trace. Для T002 дополнительно сохраняется `trace/change.patch` относительно начального коммита; рабочий Git-репозиторий остаётся в игнорируемом workspace.

## Повторы, источники и абляция

Создайте три отдельные записи с одинаковыми моделью, образом, задачей, вариантом, бюджетом и таймаутом. `compare` группирует по условиям, показывает покрытие метрик и строит непересекающиеся тройки в порядке run ID. Два прогона не превращаются в `pass^3`; начатые, но прерванные исполнения остаются неуспехами. `planned`, `prepared`, `running`, `awaiting_review` показываются отдельно. Можно выбрать записи: `npm run compare -- --runs ID1,ID2,ID3`.

Для T001 дата задаётся `prepare-run --as-of YYYY-MM-DD`. Живые страницы могут изменяться, поэтому такой прогон — сбор исходного архива, а не доказательство контролируемого сравнения. Ответы GET сохраняются в `trace/sources.jsonl`; их получает агент через gateway. Для последующей одинаковой серии:

```bash
npm run prepare-run -- --run "$RUN_ID" --as-of 2026-09-20 \
  --source-archive 'results/runs/<исходный-прогон>/trace/sources.jsonl'
```

Все сравниваемые прогоны должны использовать один архив. Он копируется в снимок входов; отсутствующая в архиве страница не загружается заново. Доступны исходные ссылки и обнаруженные на них ссылки глубины 1. API модели остаётся онлайн.

Для абляции создайте новую запись и подготовьте её с `--variant without-spec`: спецификация исключается из prompt, контракт и обязательные границы сохраняются. Это не удаление файлов спецификаций из естественного содержимого аудируемого репозитория T003. Сравните отдельные группы baseline/without-spec; эффект компонента записывайте в реестр только после измерений.

## Проверки и карта

```bash
npm test
npm run test:docker
npm run check
```

Обычные тесты не используют API и скрытые проверки. Docker smoke включается отдельно, использует локальный proxy image и синтетическую нагрузку. Для Colima временный mount создаётся в домашней папке; путь можно задать через `HARNESS_DOCKER_TMPDIR`.

`npm run check` дополнительно сверяет пин каждой обвязки в четырёх местах (профиль, Dockerfile, эта страница, README обвязки) и читает лимиты ходов и USD из контрактов задач. Пин версии задаётся один раз в `experiments/<harness>/harness.json`: Dockerfile его утверждает, `run` сравнивает с версией, которую сообщает сам образ, и прерывает прогон до старта агента при расхождении. `npm test` и `npm run check` выполняются в GitHub Actions (`.github/workflows/ci.yml`); Docker-граница проверяется отдельной job на `main` и по кнопке.

- `docs/method.md` — протокол и ограничения интерпретации.
- `docs/harnesses.md` — реализованные адаптеры и кандидаты с первичными источниками.
- `docs/harness-ledger.md` — добавленные компоненты и основания для абляции.
- `docs/local-models.md`, `experiments/local-models/` — план исследований, каталог, расчёт памяти и отчёты фактических измерений на Ryzen и Apple.
- `agents/` и `tasks/` — независимые спецификации, неизменяемые контракты задач.
- `experiments/<harness>/` — адаптеры, конфигурации, образы и заметки.
- `results/schema.json`, `scripts/` — формат записи и координатор.

Граница credentials ограничена: API key находится в окружении обвязки и доступен процессам внутри её контейнера. Host-файл `.env` не монтируется; для недоверенных задач, требующих скрыть ключ даже от bash агента, нужен отдельный credential broker. Оценённые Pi/local/T002 результаты не подтверждают качество остальных обвязок. Cloud-эпизоды, полнота отдельных usage-полей и доступность конкретной модели в аккаунте остаются **unverified**; для девяти адаптеров сохранены подготовка и offline проверки установки/SDK. Где проверять — в README адаптеров и матрице.
