# LAB04 — Vulkan против HIP/ROCm (mistral-small-4-119b)

Сессия: `mistral-small-4-119b-probe`. Статус: **blocked (partial)**.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Модель | `mistralai/Mistral-Small-4-119B-2603`, UD-Q4_K_M (68.69 GiB, 3 шарда) |
| Артефакт | `unsloth/Mistral-Small-4-119B-2603-GGUF@bd93c721…` (LAB03 verified) |
| Engine | llama.cpp b8407 (312cf0332); prebuilt Vulkan и ROCm/HIP |
| Стенд | Ryzen AI Max+ 395 / 128 GB; gfx1151; ROCm 7.2.1 |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (preregistered). Один GGUF полностью выгружается на GPU в обеих
prebuilt-сборках; backend влияет на скорость.

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| Vulkan offload-proof | **прошёл**: 37/37 слоёв на Vulkan, 68.69 GiB, pp8 77.38 t/s, tg1 33.26 t/s |
| Hip offload-proof | **завис** на загрузке: `offloaded 37/37 layers to GPU`, ROCm0 buffer 69794.53 MiB, прогресс-бар без движения >14 ч |
| Парные повторы pp2048/tg128 | не запускались |

## Результаты

| Backend | Offload | pp8 t/s | tg1 t/s | Парные повторы | RSS |
| --- | --- | --- | --- | --- | --- |
| Vulkan | 37/37 на GPU | 77.38 | 33.26 | not-run | not measured |
| HIP/ROCm | stall на загрузке | — | — | not-run | — |

## Ошибки и ограничения

- HIP/ROCm-ветвь не загрузила модель: после «offloaded 37/37 layers to GPU» лог остановился,
  прогресс-бар не продвинулся (>14 ч), GPU buffer 69794.53 MiB. Это не OOM-kill, а stall
  на аллокации/инициализации; ветку не «спасали» CPU-offload'ом.
- Поэтому парная серия и медианы не получены; результат — промежуточный.
- Vulkan offload-proof — единичный прогон, не замена трём повторам.

## Вывод по гипотезе

**Данных недостаточно.** Для Vulkan модель помещается (68.69 GiB) и работает; HIP/ROCm в этом
бюджете не загрузилась. Гипотеза о полной выгрузке в обеих сборках не подтверждена.

## Ответы на контрольные вопросы

- `-ngl 999` — запрос; фактическую раскладку даёт `-v` (37/37).
- Разница backend важна: та же модель загрузилась на Vulkan, но не на HIP.

## Комплект сдачи

- [x] manifest.json (blocked), measurements.tsv, report.md, raw evidence.
- [ ] Полная парная серия — не выполнена (см. unavailable.completion).
