# LAB32 — нативный MLX: протоколы и бюджеты входа

Сессия `apple-mlx-identity-repeat-20261010`, статус **completed**. Native MLX input-budget qualification: qualified budgets 8192,16384,32768; hard cap/physical GPU release unavailable.



## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC / mode 0. MLX-LM 0.32.0, MLX 0.32.3, Python 3.12.14. Qwen3.5-9B MLX 4-bit affine / group64, revision `938d8919941c6e7efd3c7150eff7fe9d12afa631`. Это отдельный VLM-артефакт с текстовым инференсом; исходный commit конвертации неизвестен. [Артефакт](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [278 закреплённых файлов](raw/prestart-pins.json), [model identity](raw/model-identity-summary.json). Фактически загруженные native images и device proofs сохранены в каталогах ctx*. Системные frameworks закреплены версией macOS; отдельные хеши их файлов не заявлены.

Hard context cap — **null**. Значения 8192/16384/32768 обозначают бюджеты входа, не резерв KV и не лимиты сервера. Один сервер на `127.0.0.1:8081`; seed 1, temperature 0, top_p 1, output cap 2048, thinking false, prefill step 2048, concurrency 1. Prompt cache size 0, KV без квантизации, без изменения оператором memory limits. Wrapper наблюдений сохраняет исходные алгоритмы MLX-LM; его хеш входит в условия серии.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration.json закреплены commit до исполнения каждой серии. На условие — прогрев и три повтора четырёх chat/tool JSON/SSE cases, длинного входа и отмены с recovery. Ожидаются ровно LAB_READY, LAB_VALUE_42, LAB_SENTINEL_42; одна lookup_lab_value с key alpha и непустым ID. Код модели не исполняется.

Проверяются actual usage, число токенов, DONE и finish reason. Resource guard: samples каждые 2 с, gap максимум 15 с, free+spec минимум 8 GiB, pressure level 1, AC/mode 0, swap 0, RSS максимум 24 GiB. Wall limit 900 с на условие и 240 с на запрос. После отказа следующие бюджеты не выполняются. В новых сериях дополнительно требуется cached_tokens=0.

## Ход выполнения

Pins → подготовка tokenizer без весов → offline allowlist → native server → короткие протоколы → long → cancel/recovery → cleanup. [Контроллер](raw/run_series.py), [хеши запросов](raw/request-hashes.json), [allowlist](raw/allowlist.json). Сохранены все исходные запросы, ответы, assembled messages, usage и ошибки. Агентных попыток здесь нет, run_ids пуст.

Сессии разделены. `apple-mlx-protocol-20261010` ошибочно посчитала len(BatchEncoding)=2 и отправила 113613 токенов: это нарушение протокола, не опыт на 8K. Контроллер отказал после несовпадения usage и завершил сервер. `apple-mlx-tokenids-20261010` правильно посчитала 4085 токенов, но получила Markdown в final. `apple-mlx-exact-final-20261010` отдельно запретила Markdown и связала stop/end с одним GenerationContext; все 24 cases на 8K прошли, затем отказал port preflight 16K. `apple-mlx-budget-resume-20261010` проверила SO_REUSEADDR и продолжила с 16K; long-вход 12282 токена завершился, но resource guard отказал при free+spec 7.425 GiB. Старые ошибки не переписаны, нормализация final не введена. В отдельной `apple-mlx-identity-repeat-20261010` модели выбран правильный артефакт MLX и все 12 файлов включены до Popen; её результаты оцениваются отдельно.

## Результаты

Attempts: {"completed": 76, "failed": 0, "not-run": 3, "planned": 0}. Прогрев выделен в таблице отдельно. Столбец context_tokens в TSV пуст: hard cap неизвестен. RSS, allocator peaks, swap, gaps и cleanup — в [сводке](raw/runtime-summary.json).

| Бюджет входа | Case / повтор | Actual input / output | TTFT content, с | Total, с | Статус attempt |
| --- | --- | --- | --- | --- | --- |
| 8192 | chat-1 | 21 / 3 | None | 0.09788345799999999 | completed |
| 8192 | chat-2 | 21 / 3 | None | 0.08723370899999999 | completed |
| 8192 | chat-3 | 21 / 3 | None | 0.092287875 | completed |
| 8192 | chat-stream-1 | 21 / 3 | 0.075393625 | 0.097020833 | completed |
| 8192 | chat-stream-2 | 21 / 3 | 0.057795333000000004 | 0.079313125 | completed |
| 8192 | chat-stream-3 | 21 / 3 | 0.055914208 | 0.077310666 | completed |
| 8192 | chat-stream-warmup | 21 / 3 | 0.074152959 | 0.095200292 | completed |
| 8192 | chat-warmup | 21 / 3 | None | 0.10912216700000002 | completed |
| 8192 | long-1 | 4092 / 8 | 1.146687083 | 1.228087542 | completed |
| 8192 | long-2 | 4092 / 8 | 1.2592638329999999 | 1.342201708 | completed |
| 8192 | long-3 | 4092 / 8 | 1.29064575 | 1.369945125 | completed |
| 8192 | long-warmup | 4092 / 8 | 1.145615917 | 1.222975417 | completed |
| 8192 | recovery-1 | 21 / 3 | 0.0792915 | 0.10135420899999999 | completed |
| 8192 | recovery-2 | 21 / 3 | 0.07112575 | 0.093069125 | completed |
| 8192 | recovery-3 | 21 / 3 | 0.066842542 | 0.088285417 | completed |
| 8192 | recovery-warmup | 21 / 3 | 0.072206375 | 0.09352637500000001 | completed |
| 8192 | tool-1.followup | 364 / 6 | None | 0.19470587500000003 | completed |
| 8192 | tool-1 | 315 / 27 | None | 0.418731125 | completed |
| 8192 | tool-2.followup | 364 / 6 | None | 0.19682929099999996 | completed |
| 8192 | tool-2 | 315 / 27 | None | 0.444910583 | completed |
| 8192 | tool-3.followup | 364 / 6 | None | 0.19389945800000002 | completed |
| 8192 | tool-3 | 315 / 27 | None | 0.413891334 | completed |
| 8192 | tool-stream-1.followup | 364 / 6 | 0.138237292 | 0.19065945800000006 | completed |
| 8192 | tool-stream-1 | 315 / 27 | None | 0.401361875 | completed |
| 8192 | tool-stream-2.followup | 364 / 6 | 0.13931908300000007 | 0.192268958 | completed |
| 8192 | tool-stream-2 | 315 / 27 | None | 0.41610400000000003 | completed |
| 8192 | tool-stream-3.followup | 364 / 6 | 0.140263833 | 0.19522874999999995 | completed |
| 8192 | tool-stream-3 | 315 / 27 | None | 0.4029495 | completed |
| 8192 | tool-stream-warmup.followup | 364 / 6 | 0.14000249999999997 | 0.19551145900000005 | completed |
| 8192 | tool-stream-warmup | 315 / 27 | None | 0.397991458 | completed |
| 8192 | tool-warmup.followup | 364 / 6 | None | 0.194866875 | completed |
| 8192 | tool-warmup | 315 / 27 | None | 0.411614541 | completed |
| 16384 | chat-1 | 21 / 3 | None | 0.0805125 | completed |
| 16384 | chat-2 | 21 / 3 | None | 0.078954708 | completed |
| 16384 | chat-3 | 21 / 3 | None | 0.08227166699999999 | completed |
| 16384 | chat-stream-1 | 21 / 3 | 0.057823709 | 0.08044662500000001 | completed |
| 16384 | chat-stream-2 | 21 / 3 | 0.057957542 | 0.08024925000000001 | completed |
| 16384 | chat-stream-3 | 21 / 3 | 0.058527625 | 0.081607833 | completed |
| 16384 | chat-stream-warmup | 21 / 3 | 0.058477167000000004 | 0.08128095799999999 | completed |
| 16384 | chat-warmup | 21 / 3 | None | 0.11029408300000001 | completed |
| 16384 | long-1 | 12282 / 8 | 4.39649975 | 4.489161042 | completed |
| 16384 | long-2 | 12282 / 8 | 4.5148037500000004 | 4.5987195000000005 | completed |
| 16384 | long-3 | 12282 / 8 | 4.6235490829999994 | 4.708260125 | completed |
| 16384 | long-warmup | 12282 / 8 | 4.258054625 | 4.343858417 | completed |
| 16384 | recovery-1 | 21 / 3 | 0.068654917 | 0.09063579199999999 | completed |
| 16384 | recovery-2 | 21 / 3 | 0.06881404199999999 | 0.090699042 | completed |
| 16384 | recovery-3 | 21 / 3 | 0.057373292 | 0.07871800000000001 | completed |
| 16384 | recovery-warmup | 21 / 3 | 0.060464542 | 0.082904708 | completed |
| 16384 | tool-1.followup | 364 / 6 | None | 0.19966404100000001 | completed |
| 16384 | tool-1 | 315 / 27 | None | 0.42632683400000004 | completed |
| 16384 | tool-2.followup | 364 / 6 | None | 0.19819454200000003 | completed |
| 16384 | tool-2 | 315 / 27 | None | 0.411149333 | completed |
| 16384 | tool-3.followup | 364 / 6 | None | 0.20036841600000005 | completed |
| 16384 | tool-3 | 315 / 27 | None | 0.419621875 | completed |
| 16384 | tool-stream-1.followup | 364 / 6 | 0.143756708 | 0.19880016699999997 | completed |
| 16384 | tool-stream-1 | 315 / 27 | None | 0.415026208 | completed |
| 16384 | tool-stream-2.followup | 364 / 6 | 0.144966875 | 0.20186758300000002 | completed |
| 16384 | tool-stream-2 | 315 / 27 | None | 0.408759084 | completed |
| 16384 | tool-stream-3.followup | 364 / 6 | 0.145981458 | 0.20168475000000002 | completed |
| 16384 | tool-stream-3 | 315 / 27 | None | 0.425436125 | completed |
| 16384 | tool-stream-warmup.followup | 364 / 6 | 0.14288208400000002 | 0.197890334 | completed |
| 16384 | tool-stream-warmup | 315 / 27 | None | 0.41771387499999996 | completed |
| 16384 | tool-warmup.followup | 364 / 6 | None | 0.19476891699999999 | completed |
| 16384 | tool-warmup | 315 / 27 | None | 0.417167208 | completed |
| 32768 | chat-1 | 21 / 3 | None | 0.081299834 | completed |
| 32768 | chat-2 | 21 / 3 | None | 0.080501625 | completed |
| 32768 | chat-3 | 21 / 3 | None | 0.08089616599999999 | completed |
| 32768 | chat-stream-1 | 21 / 3 | 0.05938266699999999 | 0.08190291699999999 | completed |
| 32768 | chat-stream-2 | 21 / 3 | 0.057807041999999996 | 0.080092459 | completed |
| 32768 | chat-stream-3 | 21 / 3 | 0.05772558300000001 | 0.079772458 | completed |
| 32768 | chat-stream-warmup | 21 / 3 | 0.05821154099999999 | 0.080469166 | completed |
| 32768 | chat-warmup | 21 / 3 | None | 0.11252120799999998 | completed |
| 32768 | long-1 | 28667 / 8 | 11.323880625000001 | 11.432479167 | completed |
| 32768 | long-2 | 28667 / 8 | 11.661238792 | 11.770259459 | completed |
| 32768 | long-3 | 28667 / 8 | 11.900303790999999 | 12.009798332999999 | completed |
| 32768 | long-warmup | 28667 / 8 | 10.307247209 | 10.413583333999998 | completed |
| 32768 | recovery-1 | 21 / 3 | 0.062897542 | 0.085843542 | completed |
| 32768 | recovery-2 | 21 / 3 | 0.0627665 | 0.085342833 | completed |
| 32768 | recovery-3 | 21 / 3 | 0.061631459 | 0.08333779200000001 | completed |
| 32768 | recovery-warmup | 21 / 3 | 0.063492083 | 0.08586375 | completed |
| 32768 | tool-1.followup | 364 / 6 | None | 0.20074712500000003 | completed |
| 32768 | tool-1 | 315 / 27 | None | 0.424203 | completed |
| 32768 | tool-2.followup | 364 / 6 | None | 0.19927454199999994 | completed |
| 32768 | tool-2 | 315 / 27 | None | 0.423539459 | completed |
| 32768 | tool-3.followup | 364 / 6 | None | 0.19789733400000004 | completed |
| 32768 | tool-3 | 315 / 27 | None | 0.4176015 | completed |
| 32768 | tool-stream-1.followup | 364 / 6 | 0.1441115 | 0.19977120799999998 | completed |
| 32768 | tool-stream-1 | 315 / 27 | None | 0.42902799999999996 | completed |
| 32768 | tool-stream-2.followup | 364 / 6 | 0.14456425000000006 | 0.20108349999999997 | completed |
| 32768 | tool-stream-2 | 315 / 27 | None | 0.420795166 | completed |
| 32768 | tool-stream-3.followup | 364 / 6 | 0.15017920799999995 | 0.205190333 | completed |
| 32768 | tool-stream-3 | 315 / 27 | None | 0.41208408300000005 | completed |
| 32768 | tool-stream-warmup.followup | 364 / 6 | 0.14667024999999995 | 0.21133866699999998 | completed |
| 32768 | tool-stream-warmup | 315 / 27 | None | 0.434165792 | completed |
| 32768 | tool-warmup.followup | 364 / 6 | None | 0.20072483300000005 | completed |
| 32768 | tool-warmup | 315 / 27 | None | 0.429926041 | completed |

| Условие отмены | Client exit | Generation end замечен после client exit, с | Stop / end замечены |
| --- | --- | --- | --- |
| ctx16384/cancel-1.proof | 28 | 3.5676259994506836 | True / True |
| ctx16384/cancel-2.proof | 28 | 3.5710530281066895 | True / True |
| ctx16384/cancel-3.proof | 28 | 3.3196558952331543 | True / True |
| ctx16384/cancel-warmup.proof | 28 | 3.823653221130371 | True / True |
| ctx32768/cancel-1.proof | 28 | 11.971235036849976 | True / True |
| ctx32768/cancel-2.proof | 28 | 11.972403049468994 | True / True |
| ctx32768/cancel-3.proof | 28 | 11.71133017539978 | True / True |
| ctx32768/cancel-warmup.proof | 28 | 11.191971778869629 | True / True |
| ctx8192/cancel-1.proof | 28 | 0.25229978561401367 | True / True |
| ctx8192/cancel-2.proof | 28 | 0.2561190128326416 | True / True |
| ctx8192/cancel-3.proof | 28 | 0.25598716735839844 | True / True |
| ctx8192/cancel-warmup.proof | 28 | 0.25171828269958496 | True / True |

## Ошибки и ограничения

Протоколы исследованных input budgets завершены; hard cap и физическое освобождение GPU остаются unverified. Native cancellation в v3 требует client exit 28 без DONE, одинаковый context object, stop flag true, stop до generation end и точный recovery в пределах 60 с. Timeout клиента отдельно не доказывает отмену GPU. Счётчики allocator не измеряют освобождение всех физических GPU-страниц. Cold startup/JIT отличается от прогретых запросов. Первые две неудачные сессии не исполняли отмену; их mutable phase events не используются как доказательство отмены.

Hard cap и overflow не подтверждены; OOM для их имитации не создавали. Максимальный GPU budget, энергия и температура неизвестны. Отказ resource guard при pressure level 1 и swap 0 не доказывает аппаратную несовместимость: наблюдаемые условия не прошли заранее выбранный резерв.

## Вывод по гипотезе

Native MLX input-budget qualification: qualified budgets 8192,16384,32768; hard cap/physical GPU release unavailable. Полностью квалифицированные бюджеты этой сессии: [8192, 16384, 32768]. Это учитывает все model pins до Popen и все 24 cases на условие; функциональные данные старых сессий не подменяют эти требования. Нельзя сравнивать input-budget label с hard context llama.cpp как одинаковый резерв KV или переносить оценки GGUF Q6_K на MLX 4-bit. Provider bridge для MLX требует отдельной реализации; эти запросы не являются агентными попытками.

## Ответы на контрольные вопросы

1. Non-streaming total включает всю генерацию: TTFT из него не извлекается, остаётся null.
2. Client CTX и architecture max_position_embeddings не задают подтверждённый server cap. IDs считаются с return_dict=False и отдельно сверяются с actual usage.
3. Socket timeout требует подтверждения native stop flag, завершения routine и recovery; физическое освобождение памяти требует другого collector.
4. Cache и reasoning меняют работу и задержки. Здесь thinking false и cache size 0; GGUF с thinking true — другой deployment.

## Комплект сдачи

Manifest, TSV, protocol, source pins, loaded images, device/model identity, запросы и хеши, HTTP/SSE/usage/finals, native events, отмена/recovery, ресурсы и cleanup, offline allowlist и software validation сохранены. Submission проверяет комплектность blocked отчёта. Решение проверяющего: **не проверено**; experiment pass не назначается автоматически.
