# ЛР05 — Контекст 8/16/32K, streaming и инструменты

Сессия: `mistral-119b`. Backend: **Vulkan** (HIP/ROCm blocked в ЛР04).
Модель: `Mistral-Small-4-119B-2603` UD-Q4_K_M (MoE, 36 слоёв, 128 experts/4 active,
`n_head_kv=1`). Стенд: Ryzen AI Max+ 395 / Radeon 8060S.

Статус: **завершено для 8K/16K/32K на Vulkan**; long/overflow/recovery/tools
пройдены, отмена корректно проверена только на 8K. HIP — blocker (см. ЛР04).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | open (agent); 2026-10-15 |
| Engine / backend | llama.cpp b8407 `312cf0332`, Vulkan0 RADV GFX1151 |
| Артефакт | `unsloth/Mistral-Small-4-119B-2603-GGUF` @ `bd93c721…`, shard 1 (3/3 verified) |
| Context, KV/FA | 8192 / 16384 / 32768; KV f16/f16; FA on; `-np 1`; jinja template |
| Загрузка | `offloaded 37/37 layers`; Vulkan0 model buffer 69 794,50 MiB; KV 180 MiB @8K |
| Предыдущие | `LAB03-mistral-119b`, `LAB04-mistral-119b` |

## Гипотеза и протокол до запуска

Увеличение контекста 8K→16K→32K не нарушает память и протокол. Изменяемый фактор —
context; константы — артефакт, commit, backend, KV/FA, batch, потоки, sampling
(server defaults), template. Число повторов — 2 на case; прогрев отдельно. Контекст
обязан быть заполнен (bench с `-d` и long HTTP-вход), а не только `-c`. Критерий
остановки: OOM/GPU reset/устойчивая подкачка/тихое обрезание.

## Ход выполнения

| Шаг | Действие | Результат | Evidence |
| --- | --- | --- | --- |
| 1 | Проверка SHA весов, help/binaries, fixtures | ок | `raw/verification-before.txt`, `raw/binaries.sha256`, `raw/fixtures.sha256` |
| 2 | Fill-probe `llama-bench -d DEPTH -r 3` (8064/16256/32640) | exit 0 все | `raw/context-*-bench.json`, `raw/context-*-exit.txt` |
| 3 | `llama-server` на каждом контексте + health/props/models | ok=1 все | `raw/server-*.log`, `raw/props-*.json`, `raw/health-*.json` |
| 4 | chat/chat-stream/tool/tool-stream ×2 | выполнено | `raw/ctx*-*.final.json` |
| 5 | offline allowlist (valid/unknown/wrong/missing-id) | 4/4 ожидаемо | `raw/offline-tool-checks.json` |
| 6 | long вход через `/apply-template`+`/tokenize` ×2 | `LAB_SENTINEL_42` | `raw/ctx*-long-*` |
| 7 | overflow + recovery, cancel + recovery | 400 / recovery OK | `raw/ctx*-overflow*`, `raw/ctx*-cancel*` |

## Результаты

| Контекст | Depth + generation | Три bench повтора / raw | Пик RSS / источник | Swap-out / full offload | Допуск |
| --- | --- | --- | ---: | --- | --- |
| 8192 | 8064 + 128 | `context-8192-bench.json` (r=3) | 72 192 568 KiB (`-process.txt`) | 292 371 pages; 37/37 GPU | passed |
| 16384 | 16256 + 128 | `context-16384-bench.json` | 72 191 036 KiB | 268 063 pages; 37/37 GPU | passed |
| 32768 | 32640 + 128 | `context-32768-bench.json` | 72 191 496 KiB | 241 768 pages; 37/37 GPU | passed |

tg128 на глубине: **8K 29,82**; **16K 25,78**; **32K 21,08** t/s (FA on).
Max RSS ≈ 72,19 GiB; `pswpout` растёт на ~0,9–1,1 GiB за прогон.

| Context | Case | HTTP / finish | Final / tool validity | TTFT content, s | Total, s | Raw prefix |
| --- | --- | --- | --- | ---: | ---: | --- |
| 8192 | chat ×2 | 200 / stop | `LAB_READY` ×2 | — | 4,5 / 0,7 | `ctx8192-chat-r*` |
| 8192 | chat-stream ×2 | 200 / stop | `LAB_READY` ×2 | 0,05 | 0,1 | `ctx8192-chat-stream-r*` |
| 8192 | tool ×2 | 200 / tool_calls | call id+args ок; final `42` / `LAB_VALUE_42` | — | 1,7 / 1,6 | `ctx8192-tool-r*` |
| 8192 | tool-stream ×2 | 200 / tool_calls | call ок; `LAB_VALUE_42` ×2 | — | 0,4 | `ctx8192-tool-stream-r*` |
| 16384 | chat ×2 | 200 / stop | `LAB_READY` ×2 | — | 4,4 / 0,7 | `ctx16384-chat-r*` |
| 16384 | tool / tool-stream ×2 | 200 / tool_calls | call ок; final `42` или `LAB_VALUE_42` (см. ограничения) | — | 0,4–1,7 | `ctx16384-*` |
| 32768 | chat ×2 | 200 / stop | `LAB_READY` ×2 | — | 4,3 / 0,7 | `ctx32768-chat-r*` |
| 32768 | tool / tool-stream ×2 | 200 / tool_calls | call ок; final `42` или `LAB_VALUE_42` | — | 0,4–1,6 | `ctx32768-*` |

| Context | Input count до запуска | usage.prompt_tokens | Output / reasoning | Truncation / shift | Вывод |
| --- | ---: | ---: | --- | --- | --- |
| 8192 | 4090 | 4091 (`task` в логе) | `LAB_SENTINEL_42` | нет | long OK |
| 16384 | 12282 | 12283 | `LAB_SENTINEL_42` | нет | long OK |
| 32768 | 28663 | 28664 | `LAB_SENTINEL_42` | нет | long OK |

Overflow: HTTP **400** на всех контекстах, тело
`exceed_context_size_error` (`ctx8192-overflow.http-error.txt`). Recovery после
overflow и после cancel — `LAB_READY`. Offline allowlist — 4/4 как ожидалось.

## Ошибки и ограничения

- **Tool final flaky.** Первый вызов инструмента всегда валиден (один call,
  `lookup_lab_value`, `{"key":"alpha"}`, есть `id`), follow-up выполняется. Но final
  текст нестабилен: `42` вместо `LAB_VALUE_42` в части повторов
  (`tool-r1` на всех контекстах; `tool-stream` на 16K/32K). Это поведение модели
  (она отдаёт «только значение» = `42`), а не отказ round trip; строгий маркер
  `LAB_VALUE_42` выполнен не во всех повторах.
- **Отмена проверена только на 8K.** 8K: cancel `exit 28`, `.sse` 0 байт —
  реальная отмена. 16K/32K: long-запрос уже был в prefix cache (`long-r2` 0,4–0,5 с),
  cancel-запрос вернулся <1 с (`exit 0`, ~2,7 КБ SSE) — это не проверка отмены.
- **Формат `reasoning_content`.** Модель не отдаёт отдельного reasoning в этих
  пробах (content короткий), поэтому `ttft_reasoning` не измерен.
- **Prompt 573 токена на короткий chat.** Шаблон Mistral добавляет ~556 токенов
  системной части; server log показывает `prompt eval 17 tokens` при общем
  `n_tokens=573` (prefix cache). Это часть effective template сервиса.
- HIP/ROCm ветвь для этой модели blocked (ЛР04): сравнить контексты на втором
  backend не удалось.
- 32K — отдельный вариант: он прошёл fill-probe, long и overflow, но вывод об
  агентной готовности на 32K не делается.

## Вывод по гипотезе

**Поддержана на Vulkan.** Для `mistral-small-4-119b` контексты 8K/16K/32K
проходят заполнение, сервер держит `n_ctx` = 8192/16384/32768, long-вход
возвращает `LAB_SENTINEL_42` без обрезания (4090/12282/28663 токена), overflow
даёт явный HTTP 400, slot восстанавливается после ошибки и отмены. tg128 падает
с 29,82 (8K) до 21,08 t/s (32K), RSS стабилен ~72,19 GiB. Оговорки: отмена
доказана только на 8K; final-маркер tool round trip нестабилен; HIP не проверен.

## Ответы на контрольные вопросы

1. **Почему `-c 32768` и короткий ответ не подтверждают вместимость?** Нужно
   заполнить контекст: fill-probe по глубине и long HTTP-вход с tokenizer-count.
2. **Чем TTFT reasoning отличается от TTFT content?** Reasoning-токен появляется
   раньше; здесь reasoning отдельно не отдавался.
3. **Почему HTTP 200 с `finish_reason=length` может означать незавершённый tool
   round trip?** Модель не успевает отдать tool call/final в пределах output cap.
4. **Чем отказ allowlist отличается от отказа модели?** Allowlist-тест проверяет
   клиент на синтетическом сообщении; он не доказывает поведение модели.
5. **Как prefix cache влияет на повторный prefill?** Повторы `long-r2` выполняются
   за доли секунды; для честного сравнения первый (cold) и повторный (warm) запросы
   помечены отдельно — и это же обесценило cancel на 16K/32K.

## Комплект сдачи

- [x] Fill-проба для каждого контекста (8192/16384/32768).
- [x] По два повтора chat/stream/tool/tool-stream.
- [x] Tool round trip через allowlist без исполнения кода.
- [x] Long-вход посчитан tokenizer и проверен на обрезание.
- [x] Reasoning/final, output cap и finish reason описаны.
- [x] Overflow/cancel/recovery проверены (cancel — только 8K).
- [x] Короткий smoke не выдан за подтверждение 32K; неудачные случаи сохранены.
