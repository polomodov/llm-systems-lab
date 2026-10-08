# LAB06 — предварительный протокол (preregistration)

Записан ДО запусков сессии `qwen35-9b-rocm-prereg`. Этот файл и `planned_attempts`
в `manifest.json` фиксируют гипотезу и план до первого запуска движка; момент
регистрации подтверждается отдельным git-коммитом (`LAB06: preregistration …`)
до коммита с результатами.

## Гипотеза

Один BF16 native checkpoint `Qwen/Qwen3.5-9B` (revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`)
загружается на gfx1151 в каждом из трёх закреплённых runtime (vLLM v0.29.0 по digest,
SGLang v0.5.20 из commit `94602c9`, прямой Transformers 5.12.1 `generate`) и выдаёт
правильный контрольный ответ; серверные реализации дополнительно завершают разрешённый
tool round trip.

## Изменяемый фактор

- engine: vLLM / SGLang / Transformers (reference);
- context: 4096 (минимум) и 8192 (для прошедших серверов);
- decode: vLLM `--enforce-eager` против SGLang CUDA graph batch 1.

## Константы

- Артефакт: BF16 native checkpoint, 19 329 314 448 bytes, `:ro`, `HF_HUB_OFFLINE=1`.
- GPU: Radeon 8060S, gfx1151, ROCm/HIP 7.2; `/dev/kfd`, `/dev/dri/renderD128`.
- Одна последовательность, dtype bfloat16; порты vLLM 8000, SGLang 30000; alias `lab-model`.
- Parsers `qwen3` и `qwen3_coder`; fixtures `chat-request.json` / `tool-request.json`.
- Двигатели запускаются последовательно, с выгрузкой предыдущего.

## Порядок и повторы

1. GPU probe обоих образов (gfx1151 обязателен).
2. vLLM c4096: help, сервер, `/v1/models`, protocol cases chat/chat-stream/tool/tool-stream.
3. SGLang c4096: то же.
4. Transformers reference: greedy, non-thinking, тот же chat-request.
5. vLLM c8192: cold-r1 + warm-r1..r3, затем protocol cases.
6. SGLang c8192: то же.

Численные повторы (cold + 3 warm) — только на 8192; на 4096 protocol cases по одному разу.

## Критерий остановки

Ветвь останавливается при падении GPU probe, OOM, отсутствии gfx1151, выходе за бюджет
или незавершённом tool round trip. Ошибка одной ветви не отменяет остальные; незапущенное
помечается `not-run`/`failed` с причиной.

## Правило решения

Гипотеза поддержана, если все три ветви загружают модель на gfx1151, серверы отдают
`LAB_READY` в chat и завершают полный tool round trip до `LAB_VALUE_42`, а reference даёт
`LAB_READY`. Побитовое совпадение текста и равная скорость не требуются.

## Известные заранее условия (из сессии `qwen35-9b-rocm`)

Сборка SGLang из закреплённого commit на хосте без BuildKit требует производного слоя
для runtime-зависимостей; это закладывается в план как часть шага сборки и фиксируется
в evidence. Результаты прошлой сессии не переносятся: измерения выполняются заново.
