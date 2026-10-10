# LAB32 — нативный MLX: протоколы и бюджеты входа

Сессия `apple-mlx-protocol-20261010`, статус **blocked**. Native MLX input-budget qualification: blocked by AssertionError: Actual input count differs from pinned tokenizer

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

Attempts: {"completed": 17, "failed": 1, "not-run": 58, "planned": 0}. Прогрев выделен в таблице отдельно. Столбец context_tokens в TSV пуст: hard cap неизвестен. RSS, allocator peaks, swap, gaps и cleanup — в [сводке](raw/runtime-summary.json).

| Бюджет входа | Case / повтор | Actual input / output | TTFT content, с | Total, с | Статус attempt |
| --- | --- | --- | --- | --- | --- |
| 8192 | chat-1 | 21 / 3 | None | 0.07930979199999999 | completed |
| 8192 | chat-2 | 21 / 3 | None | 0.078643875 | completed |
| 8192 | chat-3 | 21 / 3 | None | 0.0793105 | completed |
| 8192 | chat-stream-1 | 21 / 3 | 0.057716332999999995 | 0.080180875 | completed |
| 8192 | chat-stream-2 | 21 / 3 | 0.05668883300000001 | 0.078921458 | completed |
| 8192 | chat-stream-3 | 21 / 3 | 0.05834525 | 0.080361291 | completed |
| 8192 | chat-stream-warmup | 21 / 3 | 0.057179707999999996 | 0.078771333 | completed |
| 8192 | chat-warmup | 21 / 3 | None | 0.10740191700000001 | completed |
| 8192 | long-warmup | 113613 / 8 | 57.756904583 | 57.898133708 | failed |
| 8192 | tool-1.followup | 364 / 6 | None | 0.196241709 | completed |
| 8192 | tool-1 | 315 / 27 | None | 0.415213958 | completed |
| 8192 | tool-2.followup | 364 / 6 | None | 0.193652916 | completed |
| 8192 | tool-2 | 315 / 27 | None | 0.40017712499999997 | completed |
| 8192 | tool-3.followup | 364 / 6 | None | 0.19425745900000002 | completed |
| 8192 | tool-3 | 315 / 27 | None | 0.403914084 | completed |
| 8192 | tool-stream-1.followup | 364 / 6 | 0.13949499999999998 | 0.192793708 | completed |
| 8192 | tool-stream-1 | 315 / 27 | None | 0.40161304200000003 | completed |
| 8192 | tool-stream-2.followup | 364 / 6 | 0.13989866600000006 | 0.192983458 | completed |
| 8192 | tool-stream-2 | 315 / 27 | None | 0.400519334 | completed |
| 8192 | tool-stream-3.followup | 364 / 6 | 0.13975754199999996 | 0.19277562499999995 | completed |
| 8192 | tool-stream-3 | 315 / 27 | None | 0.404421083 | completed |
| 8192 | tool-stream-warmup.followup | 364 / 6 | 0.13982820900000004 | 0.19294133400000002 | completed |
| 8192 | tool-stream-warmup | 315 / 27 | None | 0.401847875 | completed |
| 8192 | tool-warmup.followup | 364 / 6 | None | 0.19572958299999998 | completed |
| 8192 | tool-warmup | 315 / 27 | None | 0.40618641600000005 | completed |

| Условие отмены | Client exit | Generation end замечен после client exit, с | Stop / end замечены |
| --- | --- | --- | --- |
| — | — | — | Не исполнялась |

## Ошибки и ограничения

AssertionError: Actual input count differs from pinned tokenizer Native cancellation в v3 требует client exit 28 без DONE, одинаковый context object, stop flag true, stop до generation end и точный recovery в пределах 60 с. Timeout клиента отдельно не доказывает отмену GPU. Счётчики allocator не измеряют освобождение всех физических GPU-страниц. Cold startup/JIT отличается от прогретых запросов. Первые две неудачные сессии не исполняли отмену; их mutable phase events не используются как доказательство отмены.

Hard cap и overflow не подтверждены; OOM для их имитации не создавали. Максимальный GPU budget, энергия и температура неизвестны. Отказ resource guard при pressure level 1 и swap 0 не доказывает аппаратную несовместимость: наблюдаемые условия не прошли заранее выбранный резерв.

## Вывод по гипотезе

Native MLX input-budget qualification: blocked by AssertionError: Actual input count differs from pinned tokenizer Получен полный допуск протоколов на 8K input budget в отдельной exact-final сессии. На 16K прошли короткие протоколы; длинный вход не получил resource admission. 32K и следующая отмена остаются неисполненными. Нельзя сравнивать input-budget label с hard context llama.cpp как одинаковый резерв KV или переносить оценки GGUF Q6_K на MLX 4-bit. Provider bridge для MLX требует отдельной реализации; эти запросы не являются агентными попытками.

## Ответы на контрольные вопросы

1. Non-streaming total включает всю генерацию: TTFT из него не извлекается, остаётся null.
2. Client CTX и architecture max_position_embeddings не задают подтверждённый server cap. IDs считаются с return_dict=False и отдельно сверяются с actual usage.
3. Socket timeout требует подтверждения native stop flag, завершения routine и recovery; физическое освобождение памяти требует другого collector.
4. Cache и reasoning меняют работу и задержки. Здесь thinking false и cache size 0; GGUF с thinking true — другой deployment.

## Комплект сдачи

Manifest, TSV, protocol, source pins, loaded images, device/model identity, запросы и хеши, HTTP/SSE/usage/finals, native events, отмена/recovery, ресурсы и cleanup, offline allowlist и software validation сохранены. Submission проверяет комплектность blocked отчёта. Решение проверяющего: **не проверено**; experiment pass не назначается автоматически.
