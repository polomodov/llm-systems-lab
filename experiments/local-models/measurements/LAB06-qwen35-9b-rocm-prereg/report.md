# LAB06 — vLLM, SGLang и Transformers на ROCm (preregistered)

Сессия: `qwen35-9b-rocm-prereg`. Класс: `experimental`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | agent-harness-lab operator, 2026-10-08 |
| Машина, ОС | AMD Ryzen AI Max+ 395 (Radeon 8060S, gfx1151), native Linux |
| Модель/артефакт | `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, BF16, 19 329 314 448 B; `raw/native-verification.json` |
| vLLM | `vllm/vllm-openai-rocm@sha256:e5e47f6a…`, torch 2.12.0+git6bbd260, HIP 7.2.53211 |
| SGLang | commit `94602c9`; образ `lab-sglang:gfx1151-94602c9-fixed` id `32bb7a1b…`; torch 2.9.1+rocm7.2.4, triton 3.7.0+amd |
| Reference | тот же образ, Transformers 5.12.1, `sdpa`, greedy, non-thinking |
| Context / concurrency | 4096 и 8192, одна последовательность |
| Harness/provider | не применимо (LAB06 не использует агентную обвязку) |

## Гипотеза и протокол до запуска

Протокол: `raw/protocol.md`, зарегистрирован до запусков (`protocol_recorded_at`
= 2026-10-08T14:38:33Z) отдельным коммитом `LAB06: preregistration …`. Гипотеза: один
BF16 checkpoint Qwen3.5-9B загружается на gfx1151 в vLLM, SGLang и прямом Transformers
и даёт корректный контрольный ответ; серверы завершают tool round trip.

## Ход выполнения

| Шаг | Действие | Результат | Evidence |
| --- | --- | --- | --- |
| 1 | GPU probe обоих образов | gfx1151, exit 0 | `raw/gpu-probe-01/` |
| 2 | Сборка SGLang (commit 94602c9) + производный слой | образ `32bb7a1b…` | `raw/sglang-fix-build.txt` |
| 3 | vLLM c4096 + protocol cases | 4/4 | `raw/vllm-c4096-eager-01/` |
| 4 | SGLang c4096 + protocol cases | 4/4 | `raw/sglang-c4096-graph1-01/` |
| 5 | Transformers reference | LAB_READY | `raw/reference-result.json` |
| 6 | vLLM c8192: cold + 3 warm + protocol | 8/8 | `raw/vllm-c8192-eager-01/` |
| 7 | SGLang c8192: cold + 3 warm + protocol | 8/8 | `raw/sglang-c8192-graph1-01/` |

## Результаты

### Runtime и поддержка

| Runtime / image ID | Torch / ROCm | gfx1151 probe | Статус |
| --- | --- | --- | --- |
| vLLM `sha256:e5e47f6a…` | 2.12.0+git6bbd260 / HIP 7.2.53211 | ok | сервер 4096 и 8192, 4/4 protocol |
| SGLang fixed `sha256:32bb7a1b…` | 2.9.1+rocm7.2.4 / triton 3.7.0+amd | ok | сервер 4096 и 8192, 4/4 protocol |
| Transformers reference | 5.12.1 / 2.9.1+rocm7.2.4 | ok | generate LAB_READY |

### Конфигурации

| Configuration | Context / concurrency | Dtype / cache / graphs / parser | Режим decode | Статус |
| --- | --- | --- | --- | --- |
| vllm-c4096-eager / vllm-c8192-eager | 4096, 8192 / 1 | bfloat16 / no prefix cache / eager / qwen3 + qwen3_coder | eager | completed |
| sglang-c4096-graph1 / sglang-c8192-graph1 | 4096, 8192 / 1 | bfloat16 / disable radix / cuda-graph bs=1 | graph | completed |
| transformers-reference-c4096 | 4096 / 1 | bfloat16 / sdpa / greedy, non-thinking | eager | completed |

### Протокол и повторы

| Configuration / repeat | Cold/warm | Chat final | Tools / streaming | Wall / TTFT, s | Output / finish reason |
| --- | --- | --- | --- | --- | --- |
| vllm c4096 chat / r1 | cold | LAB_READY | chat | 16.85 / — | 217 / stop |
| vllm c4096 chat-stream | — | LAB_READY | stream | 15.33 / 15.17 | — / stop |
| vllm c4096 tool | warm | LAB_VALUE_42 | tool | 5.88 / — | 69 / tool_calls→stop |
| vllm c4096 tool-stream | warm | LAB_VALUE_42 | stream+tool | 10.91 / — | — / tool_calls→stop |
| sglang c4096 chat / r1 | cold | LAB_READY | chat | 74.88 / — | 184 / stop |
| sglang c4096 chat-stream | — | LAB_READY | stream | 38.99 / 38.39 | — / stop |
| sglang c4096 tool | warm | LAB_VALUE_42 | tool | 12.96 / — | 63 / tool_calls→stop |
| sglang c4096 tool-stream | warm | LAB_VALUE_42 | stream+tool | 14.78 / 9.39 | — / tool_calls→stop |
| reference c4096 | cold | LAB_READY | не применимо | 4.80 | 5 / — |
| vllm c8192 cold-r1 | cold | LAB_READY | chat | 17.16 / — | 217 / stop |
| vllm c8192 warm-r1..r3 | warm | LAB_READY ×3 | chat | 15.34 / 15.86 / 14.35 | stop ×3 |
| sglang c8192 cold-r1 | cold | LAB_READY | chat | 81.57 / — | 236 / stop |
| sglang c8192 warm-r1..r3 | warm | LAB_READY ×3 | chat | 66.71 / 36.04 / 47.78 | stop ×3 |

Reference: `peak_allocated_bytes=18 959 007 232` (≈17.66 GiB). Пиковое потребление памяти
серверов не инструментировалось (задана только доля 0.5) — отмечено в `unavailable`.
TTFT — только для streaming; `—` ≠ ноль. `usage` для streaming не запрашивался (`null`).

## Ошибки и ограничения

1. **Сборка SGLang.** Хост без BuildKit: закреплённый Dockerfile не устанавливает runtime-зависимости
   через heredoc; плюс pip заменяет ROCm torch/triton на generic. Заложено в план как часть шага сборки,
   решено производным слоем `raw/sglang-fix.Dockerfile` (`--no-deps`, сохранён ROCm-стек).
2. **Клиент tool-stream.** Патч `raw/http_probe.patch` (`tool_calls: null` → `or []`, оригинал
   `raw/http_probe.orig.py`) — клиентская правка, внесена до серии и применена ко всем probing.
3. **Режимы несравнимы** (eager / graph / greedy) — tokens/s между ветвями не сравниваются.
4. **Пиковая память серверов** не измерена отдельно.

## Вывод по гипотезе

**Поддержана данными.** Все три ветви загрузили один BF16 checkpoint Qwen3.5-9B на gfx1151 и дали
`LAB_READY`; оба сервера завершили полный tool round trip до `LAB_VALUE_42` в обычном и streaming
режимах на 4096 и 8192. Предварительная регистрация протокола выполнена до запусков отдельным коммитом.

## Ответы на контрольные вопросы

1. **safetensors vs точность/GGUF.** Формат не задаёт dtype; GGUF из ЛР03 — другая упаковка и точность, его размер не переносится на native checkpoint.
2. **Почему `torch.cuda.is_available()` не доказывает MXFP4 на gfx1151.** Это лишь инициализация HIP; наличие kernels проверяется модельным прогоном.
3. **Как отделить template/parser от модели.** Reference на той же ревизии без HTTP: `LAB_READY` у reference и сервера переносит различия на parser/serving.
4. **Что фиксирует digest и чего не фиксирует commit.** Digest фиксирует образ побитово; commit не задаёт сетевые зависимости и поведение builder'а.
5. **Что мешает сравнению tokens/s.** Разные режимы, точки измерения (HTTP wall vs `generate_seconds`), reasoning-токены, preallocated pool vs allocated.

## Комплект сдачи

- [x] `manifest.json` (v2), preregistered, 7 попыток, 20 наблюдений.
- [x] Неудачные/пропущенные попытки отсутствуют; perevtornost' через cold+warm.
- [x] Сырые логи, конфигурации и команды без секретов.
- [x] Критерии завершения ЛР06 соблюдены.
- [x] `lab:check --mode submission` — см. PR.
- [x] Реальные run IDs не применимы (движковое измерение, не агентный прогон).

Решение проверяющего: **не проверено**.
