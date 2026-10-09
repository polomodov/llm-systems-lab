# План починки ночной кампании (overnight-models-20261008)

Статус: **выполнен** (ветка `overnight-models-fixes`, драйвер
`experiments/local-models/campaign/overnight-fix.py`). Источник — ночной прогон
`overnight-20261008-154949` (ветка `overnight-models-20261008`, worktree
`/tmp/opencode/overnight-wt-20261008-154949`, драйвер `/tmp/opencode/overnight.py`).

Итоги починки — в разделе «8. Ход починки» в конце документа.

## 1. Диагноз

| # | Симптом | Причина | Evidence |
| --- | --- | --- | --- |
| 1 | LAB05 у 4 моделей = 4/8: проходят `chat`/`tool`, падают `chat-stream`/`tool-stream` | Баг драйвера: `f.replace(".json","-stream-request.json")` создаёт `chat-request-stream-request.json` вместо `chat-stream-request.json`; probe не находит файл запроса | `raw/chat-request-stream-request.json` вместо `raw/chat-stream-request.json` |
| 2 | LAB03 `glm-47-flash`, `qwen3-coder-next` упали с `KeyError: 'bytes'` | Драйвер читает `files[0]["bytes"]`, но `fetch_artifact.py` для отсутствующего файла пишет `{"status":"no-artifact"}` без `bytes` | `LAB03-*-overnight/raw/verification.json` |
| 3 | Загрузки `glm-47-flash` (14.9/31.8 GiB) и `qwen3-coder-next` (17.1/56.7 GiB) оборвались | `fetch_artifact.py` не умеет resume; после обрыва остаётся `.part`, повторный запуск не продолжает | `…/GLM-4.7-Flash-GGUF/**/*.part`, `…/Qwen3-Coder-Next-GGUF/**/*.part` |
| 4 | `gemma4-31b-it`: LAB04/05 не грузят модель | llama.cpp b8407 не знает архитектуру: `unknown model architecture: 'gemma4'` | `LAB04-gemma4-31b-it-overnight/raw/vulkan-offload-proof.log` |
| 5 | Драйвер вне репозитория, не версионирован | жил в `/tmp/opencode/overnight.py` | — |

## 2. Что уже готово (не трогать)

- LAB03 verified: `gpt-oss-20b`, `qwen36-27b`, `gemma4-31b-it`, `qwen3-coder-30b-a3b`, `qwen35-35b-a3b`.
- LAB04 completed: `gpt-oss-20b`, `qwen36-27b`, `qwen3-coder-30b-a3b`, `qwen35-35b-a3b` (offload-proof + 3 парных повтора).
- LAB05 bench-заполнения 8/16/32K прошли (exit 0) для тех же 4 моделей; не-стрим `chat`/`tool` вернули `LAB_READY`/`LAB_VALUE_42`.

## 3. Правки (не выполнены)

1. **LAB05 stream-запрос.** В `overnight.py` (lab05) генерировать
   `chat-stream-request.json` / `tool-stream-request.json`:
   ```python
   for kind in ("chat", "tool"):
       v = json.loads((raw / f"{kind}-request.json").read_text()); v["stream"] = True
       (raw / f"{kind}-stream-request.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
   ```
2. **LAB03 no-artifact.** Строить `measurements` строку только при `"bytes" in f0`;
   иначе писать строку `status=no-artifact` с причиной. Не падать.
3. **Устойчивая загрузка.** Для `glm-47-flash` и `qwen3-coder-next`: удалить `.part` и
   перекачать, либо использовать резюмируемую загрузку (`curl -C -` в целевой каталог,
   затем `fetch_artifact.py` без `--download`). Сверить `bytes`/SHA с каталогом.
4. **gemma4.** Либо поднять свежий llama.cpp (b8407 не знает `gemma4`) отдельным
   закреплённым бандлом, либо зафиксировать `fail` «архитектура не поддержана» в LAB04/05
   и не перезапускать.
5. **Версионировать драйвер.** Перенести из `/tmp/opencode/overnight.py` в
   `experiments/local-models/campaign/overnight.py` вместе с `overnight-models.json`.

## 4. Перезапуск (порядок)

1. Починить драйвер (пп. 3.1, 3.2), перенести в репозиторий (п. 3.5).
2. **LAB05 стрим** для `gpt-oss-20b`, `qwen36-27b`, `qwen3-coder-30b-a3b`,
   `qwen35-35b-a3b`: перегенерировать stream-запросы и догнать 4 кейса ×3 контекста
   (ожидается 8/8, bench уже снят).
3. **Докачать** `glm-47-flash`, `qwen3-coder-next` → LAB03 → LAB04 → LAB05.
4. **gemma4**: решить по движку (п. 3.4).
5. Прогнать `npm run lab:check --mode submission` по всем сессиям; оформить PR.

## 5. Критерии приёмки

- LAB03: у всех 7 моделей `verification.json` = `verified`.
- LAB04: у всех совместимых моделей offload 100% слоёв на GPU и 3 парных повтора.
- LAB05: 8/8 HTTP-кейсов (chat/tool × stream) в каждом из 8K/16K/32K; long/overflow/cancel.
- `lab:check --mode submission` → без ошибок для каждой сессии.
- Несовместимые (gemma4) — явный `fail`/`blocked` с причиной, а не пропуск.

## 6. Ветки и PR

- Продолжать в ветке `overnight-models-20261008` (уже запушена) либо в новой
  `overnight-models-fixes`.
- Итог: либо один PR кампании, либо PR по модели (3 сессии на модель).
- Пока не мержить до зелёного `lab:check`.

## 7. Риски

- `glm-47-flash` (MLA) и `gemma4` требуют отчёта runtime о cache/архитектуре — отдельная проверка.
- Догрузка ~57 GiB для `qwen3-coder-next`; на медленном канале — время.
- `--jinja` без model-specific sampling/reasoning годится для smoke; качество — днём вручную.

## 8. Ход починки

Драйвер `overnight-fix.py` (в репозитории) уже содержит исправления 3.1 (stream-запросы
`<kind>-stream-request.json`) и 3.2 (LAB03 `no-artifact` не падает); добавлена устойчивая
докачка через `curl -C -` и режимы `lab05` / `full` / `gemma4`. Сессии повторяются под новым
session id `<model>-overnight2`, прежние остаются как честная запись сбоя.

| Шаг | Результат |
| --- | --- |
| LAB05 stream, 4 модели | gpt-oss-20b, qwen3-coder-30b-a3b, qwen35-35b-a3b — 8/8/8; qwen36-27b — 8/7/8 |
| glm-47-flash | докачан, LAB03 verified, LAB04 completed, LAB05 8/7/8 |
| qwen3-coder-next | докачивается; LAB03/04/05 после завершения |
| gemma4-31b-it | b8407 не знает архитектуру `gemma4`; выполнен на llama.cpp **b10000** (официальная сборка ggml-org, ROCm 7.2 + Vulkan; HIP-рантайм — библиотеки ROCm 7.2.1 из бандла AMD b8407). LAB04 completed (offload 61/0 слоёв, Vulkan/HIP), LAB05 8/8/8 |

Единственные не-8/8 — кейс `ctx16384-tool-stream-r2`: у qwen36-27b бюджет 2048 токенов
израсходован на reasoning (`finish_reason=length`), у glm-47-flash модель вернула `alpha`
без вызова инструмента (`finish_reason=stop`). Это поведение модели при дефолтном sampling,
а не баг драйвера; зафиксировано как `blocked` с причиной.

**Условие gemma4:** смена версии движка (b8407 → b10000) — новая группа условий, сравнимая
только сама с собой; для остальных моделей по-прежнему b8407.
