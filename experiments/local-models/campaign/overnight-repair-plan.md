# План починки ночной кампании (overnight-models-20261008)

Статус: **зафиксирован**, не выполнен. Источник — ночной прогон
`overnight-20261008-154949` (ветка `overnight-models-20261008`, worktree
`/tmp/opencode/overnight-wt-20261008-154949`, драйвер `/tmp/opencode/overnight.py`).

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
