# ЛР16. mini-SWE-agent: минимальный native цикл и цена наблюдаемости

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылка | Завершённая [ЛР01](LAB01-reproducibility.md) |
| Обвязка | `mini-swe-agent`, `mode=sdk`; `mini-swe-agent==2.4.6`, Python `3.12.12`, Node.js `24.13.1` |
| Минимум | Сборка, offline smoke, разбор native trajectory и одна реальная A2/T002 с независимой оценкой |
| Время | Ориентир 2–4 часа оператора плюс сборка/судейство; agent execution ≤900 s |
| Условия | Облачный `anthropic` либо `openai`, точный model ID, `baseline`, USD `observed` |
| Расширения | Три заранее назначенных повтора, T001 replay, аудит T003, парная абляция spec |
| Начальное состояние | Эксперимент `not-run`; учебный manifest после создания — `not-started` |

## Цель

Исследовать, как исходный `DefaultAgent` с `LitellmModel`, `LocalEnvironment` и встроенным `mini.yaml` выполняет общий контракт. Проверить полноту trajectory и показать, почему native step limit, число попыток API и стоимость нельзя смешивать в один универсальный счётчик.

## Проверяемая гипотеза

Для T002 достаточно исходного workflow mini-SWE-agent и общей спецификации A2, без дополнительных правил исправления или собственного цикла координатора. Критерий — независимая оценка одной зарегистрированной попытки и перечень компонентов, реально участвовавших в работе. Если возникает `LimitsExceeded`, это повод оценить полученный артефакт, а не автоматически объявить успех или ошибку инфраструктуры.

Проверяемое требование измерителя: `model_stats.api_calls` отражает число попыток, включая неудачные; токены и стоимость публикуются как итог лишь при наличии usage всех таких вызовов. Неполная trajectory не должна превращаться в дешёвый успешный запуск.

## Подготовка

Из корня репозитория под обычным пользователем с Node.js ≥22 и Docker Engine создайте отчёт. Выберите provider и точную доступную модель до подготовки эпизода:

```bash
npm run lab:new -- --lab LAB16 --session my-session
LAB_DIR='experiments/mini-swe-agent/measurements/LAB16-my-session'
PROVIDER_ID='anthropic'
MODEL_ID='<точный доступный ID выбранного провайдера>'
IMAGE_TAG='harness-lab/mini-swe-agent:2.4.6'
```

Для OpenAI укажите `PROVIDER_ID='openai'`. Замените placeholder модели; плавающие алиасы не используйте. В CLI требуется ID **без** `anthropic/`/`openai/`: префикс для LiteLLM добавит адаптер. Нужное имя ключа в корневом `.env` — `ANTHROPIC_API_KEY` либо `OPENAI_API_KEY`. Не выводите значения, не сохраняйте `.env` в raw evidence и не исполняйте его как shell-скрипт. Ключ выбранного provider находится в окружении agent container; host-файл `.env` не монтируется, но это не скрывает ключ от процессов внутри контейнера.

Прочитайте [README](../../experiments/mini-swe-agent/README.md), [harness.json](../../experiments/mini-swe-agent/harness.json), [run.py](../../experiments/mini-swe-agent/run.py), [адаптер](../../experiments/mini-swe-agent/adapter.mjs), [метод](../method.md) и [общий workflow](harness-workflow.md). Локальная модель Ryzen подключается только после отдельной приёмки [ЛР08](LAB08-local-bridge.md) для mini-SWE-agent. Работа ниже использует уже реализованный cloud маршрут.

## Порядок выполнения

1. **Запишите план до исполнения.** В отчёте зафиксируйте T002/A2, baseline, provider/model, Git revision и изменённое дерево. Целевой бюджет T002 — USD 2, но в этом профиле `observed` не обеспечивает hard cap. Внешний timeout 900 s обязателен. Native `step_limit=30` ограничивает `n_calls`, а `cost_limit=0` отключает встроенный постфактум cost stop; 0 здесь не означает бесплатный inference.

   ```bash
   git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
   git status --short > "$LAB_DIR/raw/git-status.txt"
   node --version > "$LAB_DIR/raw/node-version.txt"
   docker version > "$LAB_DIR/raw/docker-version.txt"
   npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
   node --test experiments/mini-swe-agent/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Переходите к следующему этапу только после проверки exit code и evidence текущего. Unit-тесты синтетические, не используют провайдера или hidden checks.

2. **Соберите образ и выполните offline smoke.** Не устанавливайте SDK на host: эксперимент выполняется внутри общего Docker-контейнера. Основной пакет закреплён; один полученный image ID сохраняет транзитивные зависимости на всю серию.

   ```bash
   docker build -t "$IMAGE_TAG" -f experiments/mini-swe-agent/Dockerfile experiments/mini-swe-agent > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
   printf '%s\n' "$IMAGE_ID" > "$LAB_DIR/raw/image-id.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE_ID=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   printf '%s\n' "$PROXY_IMAGE_ID" > "$LAB_DIR/raw/proxy-image-id.txt"
   docker run --rm --network none --read-only --user 1000:1000 \
     --cap-drop ALL --security-opt no-new-privileges \
     --tmpfs /tmp:rw,nosuid,noexec,mode=1777 --env HOME=/tmp --workdir /tmp \
     --mount "type=bind,src=$PWD/experiments/mini-swe-agent,dst=/control,readonly" \
     --entrypoint python "$IMAGE_ID" /control/run.py --smoke > "$LAB_DIR/raw/sdk-smoke.txt" 2>&1
   docker run --rm --network none --entrypoint python "$IMAGE_ID" -c \
     "from importlib.metadata import version; print(version('mini-swe-agent'))" > "$LAB_DIR/raw/sdk-version.txt"
   ```

   Ожидается metadata `2.4.6`. Smoke собирает настоящие agent/model/environment и проверяет `printf sdk-ready` через `LocalEnvironment`; `agent.run()`/модель не вызываются. Зафиксируйте фактический вывод и status. Успех smoke не подтверждает доступность model ID, тариф LiteLLM или выполнение T002.

3. **Исследуйте состав native workflow.** В `run.py` найдите загрузку `mini.yaml`, переопределение `step_limit`, `cost_limit`, `output_path`, создание `LitellmModel`/`LocalEnvironment` и вызов `agent.run()`. Подкласс `TracedAgent` меняет только `add_messages`, чтобы сохранить события. В отчёте укажите, кто выбирает команды, обрабатывает format errors и завершает задачу: эти действия остаются в исходном `DefaultAgent`, а не в отдельном агенте лаборатории.

   Найдите в адаптере запрет hard USD. Объясните, почему встроенная проверка после расхода не равна жёсткому бюджету до вызова. `LITELLM_LOCAL_MODEL_COST_MAP=True` использует встроенную таблицу установленного пакета; отсутствие цены может завершить upstream ошибкой. Это ограничение следует зарегистрировать, не заменяя цену нулём и не подменяя модель ради получения успешной строки.

4. **Создайте свежую запись и запечатайте входы.** Не переиспользуйте run ID из ЛР01 или другого прогона:

   ```bash
   npm run new-run -- --harness mini-swe-agent --harness-version 2.4.6 \
     --agent a2-janitor --task T002 --provider "$PROVIDER_ID" --model "$MODEL_ID"
   RUN_ID='<run ID из new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider "$PROVIDER_ID" > "$LAB_DIR/raw/prepare-$RUN_ID.txt" 2>&1
   ```

   Проверьте `prepared`, seed commit, выбранный provider и API domains в `inputs/control/harness.json`/network policy. В контейнер не передаются исходный репозиторий лаборатории, её run records и hidden checks. Контракт задачи не меняйте, `tasks/*/check/` при решении не открывайте. После подготовки нельзя редактировать snapshot — для изменения условий создают новую запись.

5. **Запустите T002 и зафиксируйте состояние.** Только этот этап обращается к реальному провайдеру:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_ID" --proxy-image "$PROXY_IMAGE_ID" \
     --model "$MODEL_ID" --provider "$PROVIDER_ID" --timeout 900 --budget-mode observed
   node --input-type=module - "$RUN_ID" <<'NODE'
   import { readFileSync } from 'node:fs';
   const r = JSON.parse(readFileSync(`results/runs/${process.argv[2]}/run.json`, 'utf8'));
   console.log(JSON.stringify({ status:r.status, model:r.model, loop:r.loop, unavailable:r.metrics_unavailable }, null, 2));
   NODE
   ```

   Возможный `Submitted` означает native завершение, а `LimitsExceeded` — остановку по пределу; ни одно не заменяет независимый verdict. При provider error, timeout или нарушении identity сохраняется `aborted`. Не перезаписывайте его успешным retry; каждое повторное исполнение получает новый ID.

6. **Разберите trajectory и полноту учёта.** Получите короткую сводку, не дублируя весь текст сообщений:

   ```bash
   node --input-type=module - "$RUN_ID" > "$LAB_DIR/raw/mini-trajectory-$RUN_ID.json" <<'NODE'
   import { readFileSync } from 'node:fs';
   const text = readFileSync(`results/runs/${process.argv[2]}/trace/stdout.jsonl`, 'utf8');
   const events = text.split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
   const trajectory = events.findLast(e => e?.type === 'lab_mini_result')?.trajectory;
   const responses = (trajectory?.messages ?? []).filter(m => m.role === 'assistant').map(m => m.extra?.response);
   console.log(JSON.stringify({ mini_message_events:events.filter(e => e?.type === 'mini_message').length,
     has_final:!!trajectory, exit_status:trajectory?.info?.exit_status ?? null,
     model_stats:trajectory?.info?.model_stats ?? null, assistant_responses:responses.length,
     responses:responses.map(r => ({ model:r?.model ?? null, usage:r?.usage ?? null })) }, null, 2));
   NODE
   ```

   Сверьте число response entries с `api_calls`; это условие полноты usage, а не повод скрыть failed calls. Суммируйте `prompt_tokens`/`completion_tokens` только при полном покрытии попыток. Цена `instance_cost` — оценка LiteLLM. Если итог отсутствует, укажите `null` и `metrics_unavailable`. `response.model` является источником наблюдаемой identity; сравните его с requested ID с учётом добавленного provider prefix. Несколько разных моделей или mismatch требуют отдельного разбора. Не считайте `mini_message` независимым от финальной trajectory повторным расходом.

7. **Передайте T002 независимому оценщику.** При `awaiting_review` создайте JSON-шаблон:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   В соответствии с [общим workflow](harness-workflow.md) оценщик вне agent container выполняет скрытую проверку T002, сохраняет manifests и заполняет `result`, `evaluator`, `check_output`. Только после получения содержательного решения примените оценку:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run --silent compare -- --runs "$RUN_ID" > "$LAB_DIR/raw/comparison.json"
   npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
   ```

   `judge-run` связывает оценку с evidence hashes; он не выполняет содержательный суд вместо оценщика. Без оценщика запись остаётся `awaiting_review`, без completed evidence работа остаётся незавершённой.

8. **Завершите отчёт и запланируйте расширение.** Запишите run IDs, native события, неизвестные метрики и ограничения в manifest, report и [NOTES](../../experiments/mini-swe-agent/NOTES.md). Расширение на три повтора требует заранее назначенных новых слотов и одного image ID. Для T001 используйте frozen archive, для T003 оценивайте собственную конфигурацию mini-SWE-agent — это иные входы, чем у других harness. `mini.yaml` содержит workflow исправления репозитория даже в T001/T003: исследуйте влияние этого условия, не переписывайте конфигурацию между попытками под видом baseline. Парная `without-spec`-серия и учёт изменений — по [ЛР10](LAB10-ablation.md); команды T001/T003 — в [общем workflow](harness-workflow.md).

## Таблицы результатов

| Условие/проверка | План | Измеренное значение | Evidence path |
| --- | --- | --- | --- |
| Пакет / image IDs | 2.4.6 / agent и gateway | — | — |
| Offline environment smoke | Shell без вызова модели | — | — |
| Native limit / USD | `step_limit=30` / observed | — | — |
| API calls / responses с usage | Полное покрытие или причина отсутствия | — | — |
| Model identity | Requested и response отдельно | — | — |

| Слот | Run ID | Native exit status | API calls | Tokens in / out | USD / источник | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, not-run | — | — | — | — | — | — | — |

| Компонент | Роль в эпизоде | Доказательство | Можно ли проверить удалением |
| --- | --- | --- | --- |
| `DefaultAgent` и `mini.yaml` | — | — | — |
| `LocalEnvironment` | — | — | — |
| Traced `add_messages` | — | — | — |
| LiteLLM cost map | — | — | — |

Все измерительные ячейки до запуска остаются пустыми. `not-run` не является допустимой заменой `run.json` verdict.

## Что сдать

Заполненные report/manifest/таблицы, вывод adapter tests и offline smoke, версии и image IDs, разбор финальной trajectory, ссылки на полные архивы всех начатых попыток и независимую оценку минимум одной T002. Добавьте объяснение неизвестных метрик, используемого native workflow и отклонения USD policy. Секреты не копируйте; вывод модели не выдавайте за вывод судьи.

## Критерии завершения

- [ ] Версии, exact provider/model, образ и все условия записаны до исполнения.
- [ ] Выполнены offline adapter tests и native environment smoke.
- [ ] Одна реальная T002 имеет `completed` и независимый `pass`, `fail` либо `partial`; сохранены все `aborted` попытки.
- [ ] Разобраны native step/API counters, полнота usage, model identity и цена LiteLLM.
- [ ] Показана роль `mini.yaml`, заполнены NOTES и ответы, `npm run check` проходит.

Для завершения не требуется успешный `pass`; требуется оценённый эксперимент. Недоступность модели/цены/судьи фиксируется как причина `blocked` учебного отчёта с сохранением выполненных шагов, а не выдуманным завершением.

## Контрольные вопросы

1. Чем `step_limit`, `model_stats.api_calls` и число сообщений отличаются друг от друга?
2. Почему `cost_limit` после расхода не обеспечивает hard USD cap?
3. Что означает `cost_limit=0` в данной сборке адаптера?
4. Почему отсутствие usage одного failed call не позволяет назвать сумму остальных вызовов полной?
5. Какие сведения `response.model` добавляет к requested ID?
6. Как workflow `mini.yaml` может влиять на T001/T003 и почему это нельзя скрыть в сравнении?

## Источники

Закреплённые файлы проекта: [README mini-SWE-agent](../../experiments/mini-swe-agent/README.md), [Dockerfile](../../experiments/mini-swe-agent/Dockerfile), [harness.json](../../experiments/mini-swe-agent/harness.json), [runtime](../../experiments/mini-swe-agent/run.py), [adapter](../../experiments/mini-swe-agent/adapter.mjs), [adapter tests](../../experiments/mini-swe-agent/adapter.test.mjs), [метод](../method.md), [ledger L012](../harness-ledger.md), [границы контейнера](../../experiments/common/README.md). Доступность аккаунта, модели и полный реальный usage остаются `unverified` до зарегистрированного прогона; эта работа не обновляет pinned SDK.
