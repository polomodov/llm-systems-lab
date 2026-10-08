# ЛР35. Apple против Ryzen на одинаковых задачах

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Сравнительная агентная кампания / `implementation-required` |
| Время | 4–8 часов оператора плюс исполнение и независимая оценка |
| Предпосылки | LAB04, LAB08, LAB09, LAB32, LAB34; manifests обеих машин |
| Минимум | Один общий GGUF, один task/agent/harness, по три попытки на стенд и сопоставимая серия инференса |
| Ограничение | Агентная часть ждёт принятого local provider bridge LAB08; один лишь HTTP server её не разблокирует |

## Цель

Сравнить полезность двух стендов на общих входах, отделив производительность инференса от успешности законченной агентной задачи.

## Проверяемая гипотеза

Различия в latency/throughput двух deployments приводят к измеримому изменению времени или доли успешных решений при одинаковом контракте и бюджете. Более высокий tokens/s сам по себе не доказывает лучшее качество агента.

## Подготовка

```sh
npm run lab:new -- --lab LAB35 --session apple-vs-ryzen
export LAB_DIR='experiments/local-models/measurements/LAB35-apple-vs-ryzen'
npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --engine llama-cpp-metal --format json \
  > "$LAB_DIR/raw/apple-plan.json"
npm run --silent local:plan -- --hardware ryzen-ai-max-395-128gb-linux --engine llama-cpp-vulkan --format json \
  > "$LAB_DIR/raw/ryzen-plan.json"
npm run check
```

Это только планы. Нужны реальные manifests и пройденные проверки LAB08; существующий `run --provider local` не поддерживается. Не запускайте облачную модель под видом локальной. При отсутствии bridge оформите `blocked` агентной части; инфраструктурные измерения можно провести отдельной сессией.

## Порядок выполнения

1. До запуска создайте матрицу условий в `raw/protocol.md`. Основная пара: один GGUF с одинаковыми hashes, одинаковый llama.cpp commit, tokenizer/template, prompt/output budgets, sampling/reasoning, KV/state, offload policy, threads и server slots. Apple backend — Metal, Ryzen — заранее выбранный Vulkan либо ROCm по LAB04. Если доступны оба Ryzen backend, это два отдельных сравнения, не выбор победителя после просмотра результатов.

2. Проверьте сопоставимость: OS/ISA/GPU отличаются по определению. Сохраните паспорта, compiler/build flags, питание, background load и network placement. Основная baseline — concurrency 1; cache policy фиксирована. При несовпадении runtime flags или weights запишите отличие и трактуйте результат как сравнение deployment целиком. Для MLX добавьте отдельную дополнительную пару с собственными quant/artifacts, не объединяйте с контролируемым GGUF-сравнением.

3. Повторите один публичный HTTP prompt LAB32 и нагрузочный fixture LAB34 на обоих стендах: отдельный warmup и три повтора на одинаковом допущенном контексте. Измеряйте TTFT только streaming-клиентом; non-streaming driver даёт полную latency. Чередуйте стенды по протоколу, холодный старт и prefix cache оформляйте отдельно. Архивы raw перенесите в новый отчёт вместе с source session IDs и hashes; существующие результаты не изменяйте.

4. После принятия LAB08 выберите одну поддержанную обвязку, агентскую спецификацию и один существующий эпизод. Для первого опыта используйте T002/a2-janitor согласно LAB08/09. Зафиксируйте **один** harness version/image, permission/sandbox/network policy и входной snapshot. Лимиты turns/USD берутся из sealed task contract; новые defaults не добавляются. Если один image нельзя исполнить на обеих архитектурах одинаково, используйте одинаковый agent host для двух inference endpoints через принятый bridge или явно оформите разные harness deployments; нельзя скрывать emulation/разные образы.

5. Пройдите lifecycle LAB09: new-run → prepare → execution → независимая оценка. Конкретную команду локального provider возьмите из реализованного и проверенного интерфейса LAB08, не из предположения о флагах. Проведите один отдельный pilot, затем по три заранее зарегистрированных попытки для каждой основной пары. Модельный прогрев — отдельный от учётных агентских попыток. Не читайте и не меняйте `tasks/*/check/`; не меняйте task contracts. Сохраняйте все started failures в настоящих run records, отсутствие usage/cost — `null` с причиной, не 0.

6. Перед сравнением убедитесь, что metadata и compare уже различают hardware/deployment fingerprints, как требует LAB08. При отсутствии этой поддержки итоговое агентное сравнение blocked. Для выбранных реальных IDs:

   ```sh
   export RUN_IDS='<реальные run IDs через запятую>'
   npm run --silent compare -- --runs "$RUN_IDS" > "$LAB_DIR/raw/agent-comparison.json"
   ```

   Это не команда создания результатов. Свяжите IDs в manifest и planned attempts. Покажите pass/total, каждое wall time, tokens/turns/cost completeness и errors. Начатые неудачи входят в знаменатель, not-run перечисляются отдельно. Три попытки дают начальную оценку разброса, не статистическое доказательство превосходства.

7. Сформулируйте практический вывод по заранее выбранному правилу: годится ли каждый стенд для данной задачи и условий, где ограничение качества/latency/memory, какие данные ещё нужны. Энергетическую эффективность сравнивайте только при одинаковой методике измерения энергии; model API price=0 не означает нулевую стоимость компьютера и электричества.

## Таблицы результатов

| Условие | Hardware / OS | Engine SHA / backend | Weights / template hash | Context / cache / slots | Различия / evidence |
| --- | --- | --- | --- | --- | --- |
| Apple GGUF | | | | | |
| Ryzen GGUF | | | | | |
| MLX дополнительно | | | | | |

| Условие / повтор | Run ID | Verdict | Wall s | Tokens / turns | Cost USD / полнота | Ошибка / not-run |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

| Пара | Inference latency / throughput | Pass / total | Разброс wall time | Что выводимо / что неизвестно |
| --- | --- | --- | --- | --- |
| | | | | |

## Что сдать

Отчёт/TSV/manifest, протокол сравнений, обе аппаратные/артефактные/runtime идентичности, HTTP raw evidence, run IDs и независимые verdict, compare JSON либо конкретный blocker интеграции. Учебный manifest не заменяет run.json.

## Критерии завершения

- [ ] Контролируемый GGUF и дополнительный MLX deployment не смешаны.
- [ ] Bridge/metadata/изоляция приняты до агентных запусков.
- [ ] На каждой машине три учётные попытки, включая failures, либо blocked с причиной.
- [ ] Общий контракт, evaluator и run records сохранены без изменения скрытых проверок.
- [ ] Вывод связан с задачей, условиями и evidence, а не только tokens/s.
- [ ] Выполнены `lab:check --mode submission` и `npm run check`.

## Контрольные вопросы

1. Почему сравнение Metal и ROCm одновременно включает влияние ОС и аппаратуры?
2. Когда можно говорить о чистом эффекте движка, а когда только о deployment?
3. Как одинаковый task budget влияет на сравнение скорости и качества?
4. Почему started failures нельзя исключать из pass/total?
5. Какие дополнительные измерения нужны для стоимости успешной задачи?

## Источники

- [Протокол эксперимента](../method.md), [LAB08](LAB08-local-bridge.md), [LAB09](LAB09-agent-campaign.md).
- [LAB04](LAB04-backends.md), [LAB32](LAB32-apple-context-tools.md), [LAB34](LAB34-apple-load.md).
- [Схема run records](../../results/schema.json), [сравнение](../../scripts/compare.mjs).
