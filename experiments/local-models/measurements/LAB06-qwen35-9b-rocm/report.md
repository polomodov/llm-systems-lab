# LAB06 — vLLM, SGLang и Transformers на ROCm

Сессия: `qwen35-9b-rocm`. Легенда классов доказательств: `experimental`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | agent-harness-lab operator, 2026-10-08 |
| Машина, ОС | AMD Ryzen AI Max+ 395 (Radeon 8060S, gfx1151), native Linux |
| Модель/артефакт | `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, BF16 native, 19 329 314 448 bytes; `raw/native-verification.json` |
| vLLM | `vllm/vllm-openai-rocm@sha256:e5e47f6aaab675c252c381f0dac237b31b10d87bb74d092b07fb4065efd7f5a1`, torch 2.12.0+git6bbd260, HIP 7.2.53211 |
| SGLang | commit `94602c9c2b7cbdb8efd5c52802dac6a1c180089e`; производный образ `lab-sglang:gfx1151-94602c9-fixed` id `32bb7a1b…`; torch 2.9.1+rocm7.2.4, triton 3.7.0+amd |
| Reference | тот же образ SGLang, Transformers 5.12.1, `attn_implementation=sdpa`, greedy, non-thinking |
| Context / concurrency | 4096 и 8192, одна последовательность |
| Harness/provider | не применимо (LAB06 не использует агентную обвязку) |
| Предыдущие отчёты | LAB02-after-rocm, LAB03-qwen35-9b, LAB04/LAB05 (контекст термостата и бюджета) |

## Гипотеза и протокол до запуска

Исходный протокол: `raw/protocol.md` (включён в evidence). Гипотеза: один BF16 checkpoint
Qwen3.5-9B загружается на gfx1151 в vLLM, SGLang и прямом Transformers и даёт корректный
контрольный ответ; серверы дополнительно завершают разрешённый tool round trip.

**Важно о регистрации:** сессия создана 2026-10-08T07:48:57Z, но реестр протокола и попыток
оформлен уже при продолжении, после первого запуска vLLM. Поэтому `protocol_recorded_at`
позднее; это честная поздняя регистрация, а не предварительный план (см.
`unavailable.protocol_timing`). Реальных `run_ids` нет, проверка «протокол раньше запуска»
к этой сессии не применяется.

## Ход выполнения

| Шаг | Действие | Результат | Evidence |
| --- | --- | --- | --- |
| 1 | Закрепление артефакта и offline-проверка | verified | `raw/native-verification.json` |
| 2 | Сборка SGLang из commit 94602c9 | образ собран, но без runtime-зависимостей | `raw/sglang-build.txt`, `raw/sglang-image.json` |
| 2a | Диагностика и производный фикс образа | см. «Ошибки» | `raw/sglang-fix.Dockerfile`, `raw/sglang-fix-build.txt` |
| 3 | GPU probe обоих образов (gpu-probe-03) | exit 0, gfx1151 подтверждён | `raw/gpu-probe-03/` |
| 4 | vLLM c4096 + protocol cases | 4/4 | `raw/vllm-c4096-eager-01/` |
| 5 | SGLang c4096 + protocol cases | 4/4 (после правки клиента) | `raw/sglang-c4096-graph1-03/` |
| 6 | Transformers reference | LAB_READY | `raw/reference-result.json` |
| 7 | vLLM c8192: cold + 3 warm + protocol | 8/8 | `raw/vllm-c8192-eager-01/` |
| 8 | SGLang c8192: cold + 3 warm + protocol | 8/8 | `raw/sglang-c8192-graph1-01/` |

## Результаты

### Runtime и поддержка

| Runtime / image ID | Torch / ROCm / Triton / Transformers | gfx1151 probe | Документированный путь | Локальный статус |
| --- | --- | --- | --- | --- |
| vLLM, `sha256:e5e47f6a…` | 2.12.0+git6bbd260 / HIP 7.2.53211 | ok | vLLM ROCm gfx1151 | сервер 4096 и 8192, 4/4 protocol |
| SGLang fixed, `sha256:32bb7a1b…` | 2.9.1+rocm7.2.4 / HIP 7.2.53211 / triton 3.7.0+amd | ok | Dockerfile gfx1151 @94602c9 | сервер 4096 и 8192, 4/4 protocol |
| Transformers reference | 5.12.1 / 2.9.1+rocm7.2.4 | ok | — | generate LAB_READY |

### Конфигурации

| Configuration | Artifact revision | Context / concurrency | Dtype / cache / graphs / parser | Режим decode | Статус |
| --- | --- | --- | --- | --- | --- |
| vllm-c4096-eager | c2022362… | 4096 / 1 | bfloat16 / no prefix cache / eager / qwen3 + qwen3_coder | eager | completed |
| vllm-c8192-eager | c2022362… | 8192 / 1 | bfloat16 / no prefix cache / eager | eager | completed |
| sglang-c4096-graph1 | c2022362… | 4096 / 1 | bfloat16 / disable radix / cuda-graph bs=1 / qwen3 + qwen3_coder | graph | completed |
| sglang-c8192-graph1 | c2022362… | 8192 / 1 | bfloat16 / disable radix / cuda-graph bs=1 | graph | completed |
| reference-c4096 | c2022362… | 4096 / 1 | bfloat16 / sdpa / greedy, non-thinking | eager | completed |

### Протокол и повторы

| Configuration / repeat | Cold/warm | Chat final | Tools / streaming | Wall / TTFT, s | Output / finish reason | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| vllm c4096 chat / r1 | cold | LAB_READY | chat | 15.71 / — | 202 / stop | `vllm-c4096-eager-01/protocol-r1/` |
| vllm c4096 chat-stream | — | LAB_READY | stream | 15.10 / TTFT 14.94 | — / stop | idem |
| vllm c4096 tool | warm | LAB_VALUE_42 | tool | 6.44 / — | 75 / tool_calls→stop | idem |
| vllm c4096 tool-stream | warm | LAB_VALUE_42 | stream+tool | 5.58 / — | — / tool_calls→stop | idem |
| sglang c4096 chat / r1 | cold | LAB_READY | chat | 88.71 / — | 284 / stop | `sglang-c4096-graph1-03/protocol-r1/` |
| sglang c4096 chat-stream | — | LAB_READY | stream | 42.49 / TTFT 41.88 | — / stop | idem |
| sglang c4096 tool | warm | LAB_VALUE_42 | tool | 16.19 / — | 77 / tool_calls→stop | idem |
| sglang c4096 tool-stream | warm | LAB_VALUE_42 | stream+tool | 12.85 / TTFT 7.24 | — / tool_calls→stop | idem (после правки клиента) |
| reference c4096 | cold | LAB_READY | не применимо | 4.54 | 5 / — | `raw/reference-result.json` |
| vllm c8192 cold-r1 | cold | LAB_READY | chat | 15.70 / — | 202 / stop | `vllm-c8192-eager-01/cold-r1/` |
| vllm c8192 warm-r1..r3 | warm | LAB_READY ×3 | chat | 15.32 / 15.83 / 15.07 | stop ×3 | `vllm-c8192-eager-01/warm-r*/` |
| sglang c8192 cold-r1 | cold | LAB_READY | chat | 82.58 / — | 237 / stop | `sglang-c8192-graph1-01/cold-r1/` |
| sglang c8192 warm-r1..r3 | warm | LAB_READY ×3 | chat | 70.73 / 36.84 / 49.59 | stop ×3 | `sglang-c8192-graph1-01/warm-r*/` |

Reference: `input_tokens=21`, `output_tokens=5`, `peak_allocated_bytes=18 959 007 232` (≈17.66 GiB),
`peak_reserved_bytes=19 008 585 728`. TTFT измеряется только для streaming; `—` означает
неприменимо, а не ноль. `usage` для streaming не запрашивался, поэтому `null`.

Пиковое потребление памяти серверов отдельно не инструментировалось (были заданы только
доли `--gpu-memory-utilization 0.5` / `--mem-fraction-static 0.5`); это зафиксировано в
`unavailable`. Reference измерил Torch peak до/во время `generate`. Бюджет и разделение
UMA описаны в паспорте LAB02 и здесь не складываются.

## Ошибки и ограничения

1. **SGLang: legacy builder и heredoc.** На хосте нет BuildKit (`docker buildx` отсутствует),
   поэтому шаг 22 `rocm-gfx1151.Dockerfile` вида `RUN ... && python3 - <<'PY'` выполнился как
   `python3 -` с пустым stdin: ни одна runtime-зависимость не установилась. Симптом — `orjson`
   отсутствовал при 47 пакетах в `/opt/venv`; повторный запуск → `ModuleNotFoundError`.
   Evidence: `raw/sglang-c4096-graph1-01/server.log`, `raw/gpu-probe-01/sglang-packages.txt`.
2. **SGLang: конфликт metadata torch/triton.** Обычный `pip install` не может сохранить ROCm-стек:
   базовый torch 2.9.1+rocm объявляет зависимость `triton==3.5.1+rocm…`, которой нет в индексе,
   тогда как в образе `triton 3.7.0+amd`. Резолвер откатывается и ставит generic PyPI
   `torch 2.10.0` + CUDA `triton`, ломая gfx1151. Устранено производным слоем
   `raw/sglang-fix.Dockerfile`, устанавливающим замороженный набор (`raw/sglang-extra-requirements.txt`)
   с `--no-deps`, что закрепляет ROCm torch/triton/torchvision.
3. **SGLang: typing_extensions.** Первый производный слой не поднял `typing_extensions` до
   >=4.16.0, нужного anyio (`sentinel`); запуск — `sglang-c4096-graph1-02`, второй фикс добавил
   `typing-extensions==4.16.0`.
4. **Клиент http_probe.py на SGLang streaming.** SGLang отдаёт в чанках явный `"tool_calls": null`,
   и `delta.get('tool_calls', [])` падал (`NoneType not iterable`). Минимальная правка
   `(delta.get('tool_calls') or [])` сохранена как `raw/http_probe.patch`, оригинал —
   `raw/http_probe.orig.py`. vLLM таким чанком не провоцировал падение; результат vLLM не затронут.
5. **Режимы несравнимы.** vLLM — eager, SGLang — CUDA graph bs=1, reference — greedy non-thinking;
   у серверов thinking включён (reasoning_tokens в usage). Поэтому tokens/s между ветвями не
   сравниваются (см. контрольный вопрос 5).
6. **Legacy builder и воспроизводимость.** Производный образ повторяем через `raw/sglang-fix.Dockerfile`
   поверх базового `lab-sglang:gfx1151-94602c9`; сам базовый образ зависит от BuildKit-поведения
   закреплённого Dockerfile.

## Вывод по гипотезе

**Поддержана данными.** Все три ветви загрузили один BF16 checkpoint Qwen3.5-9B на gfx1151
(Radeon 8060S) и дали контрольный `LAB_READY`; оба сервера завершили полный tool round trip
до `LAB_VALUE_42` в обычном и streaming-режимах на 4096 и 8192. GPU подтверждён probe до
модельных выводов; CPU fallback не наблюдался. Оговорки: ветвь SGLang потребовала ремонта
образа (пункты 1–3), а потоковый tool-trip SGLang прошёл только после правки клиента (пункт 4);
побитовое совпадение текста и производительность не проверялись и не заявляются.

## Ответы на контрольные вопросы

1. **Почему safetensors не обозначает точность, а размер GGUF не описывает checkpoint?**
   Формат хранения не задаёт dtype: те же BF16-веса могут лежать в safetensors, а GGUF — это
   отдельная контейнерная упаковка с собственной квантизацией (Q6_K и т.п.). Размер GGUF из ЛР03
   описывает другой артефакт и другую точность, поэтому его нельзя переносить на native checkpoint.
2. **Почему `torch.cuda.is_available()` не доказывает поддержку MXFP4 на gfx1151?**
   Это лишь проверка, что backend HIP инициализировался и видит устройство. Наличие API не
   гарантирует компиляцию/наличие конкретных kernels (MXFP4, attn AOT). Здесь probe подтвердил
   только gfx1151 + HIP; каждый kernel path проверяется отдельным модельным прогоном.
3. **Как отделить ошибку template/parser от ошибки модели?** Прямым reference на той же ревизии
   и tokenizer, без HTTP и parser: `raw/reference.py` рендерит prompt через `apply_chat_template`
   и вызывает `generate`. Совпадение `LAB_READY` с сервером снимает подозрение с модели/template,
   перенося различия на parser/serving.
4. **Что фиксирует image digest и чего не фиксирует Git commit Dockerfile?** Digest фиксирует
   готовый образ побитово. Один commit задаёт только Dockerfile и контекст, но не итог: сборка
   тянет сетевые зависимости и поведение builder'а (здесь legacy vs BuildKit изменило результат),
   поэтому нужен `docker image inspect` и package freeze.
5. **Что мешает прямому сравнению tokens/s?** Разные режимы: vLLM eager против SGLang CUDA
   graph; разные точки измерения (HTTP wall вместе с reasoning против чистого `generate_seconds`);
   preallocated pool против Torch allocated; разное число reasoning-токенов. Равные числа при
   этом не означали бы равенство.

## Комплект сдачи

- [x] Заполнен `manifest.json` (v2), пропуски снабжены причинами.
- [x] Все попытки, включая неудачные, в `planned_attempts`; synthetic отсутствует.
- [x] Сохранены команды, конфигурации и сырые логи без секретов.
- [x] Заполнены таблицы результатов и `measurements.tsv` (21 наблюдение).
- [x] Реальные run IDs не применимы (LAB06 — измерение движков, не агентный прогон).
- [x] Проверены критерии завершения ЛР06.
- [x] Сформулированы вывод, ограничения и ответы на вопросы.
- [ ] `lab:check --mode submission` — заполняется отдельно.

Решение проверяющего: **не проверено**.
