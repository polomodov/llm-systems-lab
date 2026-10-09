# ЛР06 — предварительный протокол

Запись плана для сессии `qwen35-9b-rocm`. Зарегистрирован при продолжении сессии:
манифест сессии создан раньше, но реестр протокола и попыток оформлен уже после
первого запуска vLLM. Это не предварительная регистрация — см. `unavailable.protocol_timing`
в manifest.json и раздел «Ошибки и ограничения» в отчёте.

## Гипотеза

Один BF16 native checkpoint `Qwen/Qwen3.5-9B` (revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`)
загружается на gfx1151 в каждом из трёх закреплённых runtime (vLLM v0.29.0, SGLang v0.5.20
из commit `94602c9`, прямой Transformers 5.12.1 `generate`) и выдаёт правильный контрольный
ответ; серверные реализации дополнительно завершают разрешённый tool round trip.

## Изменяемый фактор

- engine: vLLM / SGLang / Transformers (reference).
- context: 4096 (минимальный) и 8192 (расширение для прошедших серверов).
- backend-режим decode: vLLM `--enforce-eager` против SGLang CUDA graph batch 1.

## Константы

- Armor artifact: BF16 native checkpoint, 19 329 314 448 bytes, каталог смонтирован `:ro`, `HF_HUB_OFFLINE=1`.
- GPU: Radeon 8060S Graphics, gfx1151, ROCm/HIP 7.2; устройства `/dev/kfd`, `/dev/dri/renderD128`.
- Одна последовательность (`--max-num-seqs 1` / `--max-running-requests 1`), dtype bfloat16.
- Loopback-порты: vLLM 8000, SGLang 30000. Fixtures `chat-request.json` / `tool-request.json`
  из `docs/labs/fixtures/`; alias модели `lab-model`.
- Parsers: `qwen3` (reasoning) и `qwen3_coder` (tool) у обоих серверов.
- Двигатели запускаются последовательно, с выгрузкой предыдущего.

## Порядок и повторы

1. GPU probe обоих образов (gfx1151 обязателен) — `gpu-probe-03`.
2. vLLM c4096: help, сервер, `/v1/models`, protocol cases chat/chat-stream/tool/tool-stream.
3. SGLang c4096: то же.
4. Transformers reference: greedy, non-thinking, тот же chat-request.
5. vLLM c8192: cold-r1 + warm-r1..r3, затем protocol cases.
6. SGLang c8192: то же.

Численные повторы (cold + 3 warm) — только на 8192. На 4096 protocol cases выполняются
по одному разу; это проверка доступности и round trip, а не сравнение tokens/s.

## Критерий остановки

Ветвь останавливается при падении GPU probe, OOM, отсутствии gfx1151, выходе за бюджет
памяти или незавершённом tool round trip. Ошибка одной ветви не отменяет остальные;
незапущенное помечается `not-run`/`failed` с причиной.

## Правило решения

Гипотеза поддержана, если все три ветви загружают модель на gfx1151, серверы отдают
`LAB_READY` в chat и завершают полный tool round trip до `LAB_VALUE_42`, а reference
даёт `LAB_READY`. Побитовое совпадение текста и равная скорость не требуются.
