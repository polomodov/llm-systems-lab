# LAB32 — нативный MLX: протоколы и бюджеты входа

Сессия `apple-mlx-budget-resume-20261010`, статус **blocked**. Native MLX input-budget qualification: blocked by RuntimeError: owned native process stopped: [{'timestamp': '2026-10-10T08:10:41.359780+00:00', 'reason': 'resource/power guard'}]

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC / mode 0. MLX-LM 0.32.0, MLX 0.32.3, Python 3.12.14. Qwen3.5-9B MLX 4-bit affine / group64, revision `938d8919941c6e7efd3c7150eff7fe9d12afa631`. Это отдельный VLM-артефакт с текстовым инференсом; исходный commit конвертации неизвестен. [Артефакт](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [267 закреплённых файлов](raw/prestart-pins.json). Фактически загруженные native images и device proofs сохранены в каталогах ctx*. Системные frameworks закреплены версией macOS; отдельные хеши их файлов не заявлены.

Hard context cap — **null**. Значения 8192/16384/32768 обозначают бюджеты входа, не резерв KV и не лимиты сервера. Один сервер на `127.0.0.1:8081`; seed 1, temperature 0, top_p 1, output cap 2048, thinking false, prefill step 2048, concurrency 1. Prompt cache size 0, KV без квантизации, без изменения оператором memory limits. Wrapper наблюдений сохраняет исходные алгоритмы MLX-LM; его хеш входит в условия серии.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration.json закреплены commit до исполнения каждой серии. На условие — прогрев и три повтора четырёх chat/tool JSON/SSE cases, длинного входа и отмены с recovery. Ожидаются ровно LAB_READY, LAB_VALUE_42, LAB_SENTINEL_42; одна lookup_lab_value с key alpha и непустым ID. Код модели не исполняется.

Проверяются actual usage, число токенов, DONE и finish reason. Resource guard: samples каждые 2 с, gap максимум 15 с, free+spec минимум 8 GiB, pressure level 1, AC/mode 0, swap 0, RSS максимум 24 GiB. Wall limit 900 с на условие и 240 с на запрос. После отказа следующие бюджеты не выполняются. В новых сериях дополнительно требуется cached_tokens=0.

## Ход выполнения

Pins → подготовка tokenizer без весов → offline allowlist → native server → короткие протоколы → long → cancel/recovery → cleanup. [Контроллер](raw/run_series.py), [хеши запросов](raw/request-hashes.json), [allowlist](raw/allowlist.json). Сохранены все исходные запросы, ответы, assembled messages, usage и ошибки. Агентных попыток здесь нет, run_ids пуст.

Сессии разделены. `apple-mlx-protocol-20261010` ошибочно посчитала len(BatchEncoding)=2 и отправила 113613 токенов: это нарушение протокола, не опыт на 8K. Контроллер отказал после несовпадения usage и завершил сервер. `apple-mlx-tokenids-20261010` правильно посчитала 4085 токенов, но получила Markdown в final. `apple-mlx-exact-final-20261010` отдельно запретила Markdown и связала stop/end с одним GenerationContext; все 24 cases на 8K прошли, затем отказал port preflight 16K. `apple-mlx-budget-resume-20261010` проверила SO_REUSEADDR и продолжила с 16K; long-вход 12282 токена завершился, но resource guard отказал при free+spec 7.425 GiB. Старые ошибки не переписаны, нормализация final не введена. 32K не исполнялась.

## Результаты

Attempts: {"completed": 18, "failed": 1, "not-run": 34, "planned": 0}. Прогрев выделен в таблице отдельно. Столбец context_tokens в TSV пуст: hard cap неизвестен. RSS, allocator peaks, swap, gaps и cleanup — в [сводке](raw/runtime-summary.json).

| Бюджет входа | Case / повтор | Actual input / output | TTFT content, с | Total, с | Статус attempt |
| --- | --- | --- | --- | --- | --- |
| 16384 | chat-1 | 21 / 3 | None | 0.080231917 | completed |
| 16384 | chat-2 | 21 / 3 | None | 0.08044537500000001 | completed |
| 16384 | chat-3 | 21 / 3 | None | 0.083241417 | completed |
| 16384 | chat-stream-1 | 21 / 3 | 0.05826229100000001 | 0.08071575 | completed |
| 16384 | chat-stream-2 | 21 / 3 | 0.058615917000000003 | 0.082940292 | completed |
| 16384 | chat-stream-3 | 21 / 3 | 0.059020500000000004 | 0.081334791 | completed |
| 16384 | chat-stream-warmup | 21 / 3 | 0.061808667 | 0.086707375 | completed |
| 16384 | chat-warmup | 21 / 3 | None | 0.11709504099999998 | completed |
| 16384 | long-warmup | 12282 / 8 | 3.867027167 | 3.9686774999999996 | failed |
| 16384 | tool-1.followup | 364 / 6 | None | 0.20507179199999997 | completed |
| 16384 | tool-1 | 315 / 27 | None | 0.426810583 | completed |
| 16384 | tool-2.followup | 364 / 6 | None | 0.20308262500000002 | completed |
| 16384 | tool-2 | 315 / 27 | None | 0.43156062500000003 | completed |
| 16384 | tool-3.followup | 364 / 6 | None | 0.21421145799999997 | completed |
| 16384 | tool-3 | 315 / 27 | None | 0.45535424999999996 | completed |
| 16384 | tool-stream-1.followup | 364 / 6 | 0.14292279099999994 | 0.20706054100000004 | completed |
| 16384 | tool-stream-1 | 315 / 27 | None | 0.425154459 | completed |
| 16384 | tool-stream-2.followup | 364 / 6 | 0.14756066699999998 | 0.209434375 | completed |
| 16384 | tool-stream-2 | 315 / 27 | None | 0.445733583 | completed |
| 16384 | tool-stream-3.followup | 364 / 6 | 0.14232100000000003 | 0.19919141699999998 | completed |
| 16384 | tool-stream-3 | 315 / 27 | None | 0.43074375 | completed |
| 16384 | tool-stream-warmup.followup | 364 / 6 | 0.14602912499999998 | 0.20473762500000003 | completed |
| 16384 | tool-stream-warmup | 315 / 27 | None | 0.463374583 | completed |
| 16384 | tool-warmup.followup | 364 / 6 | None | 0.20068754199999994 | completed |
| 16384 | tool-warmup | 315 / 27 | None | 0.431388291 | completed |

| Условие отмены | Client exit | Generation end замечен после client exit, с | Stop / end замечены |
| --- | --- | --- | --- |
| — | — | — | Не исполнялась |

## Ошибки и ограничения

RuntimeError: owned native process stopped: [{'timestamp': '2026-10-10T08:10:41.359780+00:00', 'reason': 'resource/power guard'}] Native cancellation в v3 требует client exit 28 без DONE, одинаковый context object, stop flag true, stop до generation end и точный recovery в пределах 60 с. Timeout клиента отдельно не доказывает отмену GPU. Счётчики allocator не измеряют освобождение всех физических GPU-страниц. Cold startup/JIT отличается от прогретых запросов. Первые две неудачные сессии не исполняли отмену; их mutable phase events не используются как доказательство отмены.

Hard cap и overflow не подтверждены; OOM для их имитации не создавали. Максимальный GPU budget, энергия и температура неизвестны. Отказ resource guard при pressure level 1 и swap 0 не доказывает аппаратную несовместимость: наблюдаемые условия не прошли заранее выбранный резерв.

## Вывод по гипотезе

Native MLX input-budget qualification: blocked by RuntimeError: owned native process stopped: [{'timestamp': '2026-10-10T08:10:41.359780+00:00', 'reason': 'resource/power guard'}] Получен полный допуск протоколов на 8K input budget в отдельной exact-final сессии. На 16K прошли короткие протоколы; длинный вход не получил resource admission. 32K и следующая отмена остаются неисполненными. Нельзя сравнивать input-budget label с hard context llama.cpp как одинаковый резерв KV или переносить оценки GGUF Q6_K на MLX 4-bit. Provider bridge для MLX требует отдельной реализации; эти запросы не являются агентными попытками.

## Ответы на контрольные вопросы

1. Non-streaming total включает всю генерацию: TTFT из него не извлекается, остаётся null.
2. Client CTX и architecture max_position_embeddings не задают подтверждённый server cap. IDs считаются с return_dict=False и отдельно сверяются с actual usage.
3. Socket timeout требует подтверждения native stop flag, завершения routine и recovery; физическое освобождение памяти требует другого collector.
4. Cache и reasoning меняют работу и задержки. Здесь thinking false и cache size 0; GGUF с thinking true — другой deployment.

## Комплект сдачи

Manifest, TSV, protocol, source pins, loaded images, device/model identity, запросы и хеши, HTTP/SSE/usage/finals, native events, отмена/recovery, ресурсы и cleanup, offline allowlist и software validation сохранены. Submission проверяет комплектность blocked отчёта. Решение проверяющего: **не проверено**; experiment pass не назначается автоматически.
