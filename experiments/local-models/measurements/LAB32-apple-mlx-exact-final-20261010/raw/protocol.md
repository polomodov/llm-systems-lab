# LAB32 MLX — протокол до запуска

Отдельная конфигурация Qwen3.5-9B MLX affine4/group64, model revision938d8919941c6e7efd3c7150eff7fe9d12afa631. MLX-LM0.32.0/MLX0.32.3/Python3.12.14, исходники и native binaries закрепляются hashes до Popen. Никаких скачиваний, operator wired/kernel/power tuning.

Порядок input budgets8192→16384→32768: каждый отдельный owned native server на127.0.0.1:8081, --decode-concurrency1 --prompt-concurrency1 --prompt-cache-size0; seed1 исключает batching, full precision KV, temp0/top_p1/output2048/enable_thinking=false/prefill2048. На каждый budget: chat/tool × JSON/SSE, long, cancel+recovery; warmup и три повтора. Между cases проверка exact marker, stop/tool_calls/DONE, usage/token counts и safe telemetry. Не переходить к большему input budget после отказа протокола.

Long: публичный генератор LAB32 с same template/thinkingfalse, target≤budget-4096, exact LAB_SENTINEL_42. Tokenize pinned local AutoTokenizer без весов; actual prompt usage должен равняться локальному count, cache tokens0. Это input-budget, не серверный hardcap/KVreservation. Overflow явно unavailable; не имитировать OOM.

Cancel: curl --no-buffer --max-time1 / long prompt + output2048, запрос на длинный список. Exit28 + связь с server-side stop request/generation exit в60s + exact recovery. Клиентский timeout сам по себе не доказательство GPU cancellation. Отдельная наблюдаемая конфигурация: entry wrapper вокруг оригинальных GenerationContext.stop/ResponseGenerator._serve_single только записывает timestamps/allocator counters в JSONL, не меняет модель/алгоритм/ответы. Последний return доказывает завершение generation routine; сохранённый allocator cache не означает продолжающуюся generation. RSS/device counters после остановки сохраняются; full GPU physical release без независимого collector остаётся unavailable.

Guard2s samples/gap>15s/clockbackwards/ACmode0/pressure1/free+spec≥8GiB/swap0/RSS≤24GiB, CPU process bound caffeinate -i. Per request≤240s, per context global wall900s, owned cleanup≤30s затем kill если нужно. Все реальные failures сохраняются, зависимые attempts not-run. Только одна inference нагрузка; MLX после завершения предыдущего T002/cleanup и отдельного PR.

Offline allowlist четыре cases valid/unknownname/wrongkey/missingid, фиксированная строка инструмента LAB_VALUE_42; модельный код не исполнять. TTFTcontent/reasoning отдельно, unknowns null с причинами. Warmup отдельно от трёх repeats; cold startup отдельно.

## Отдельная поправка token IDs после исходного отказа

Исходная серия LAB32-apple-mlx-protocol-20261010 сохраняется:16shortcases passed, первыйlong113613actualtokens вместо заявленных2. Transformers5.19.0 defaultreturn_dict=True; это coordinator/protocol failure, не измерение8Kконтекста. Исходныйnativecleanup0/одинSIGINT. Здесь return_dict=False + flatlist[int] assertion + prelaunchbudget checks, then actualusage equality; разрешение futurecontexts только после nativeacceptance. Дополнительно cache_tokens0 требуется в actualusage. Новые hashes до Popen, никакого переписывания первой серии.

## Отдельное exact-final условие после native mismatch

Предыдущая tokenids-серия правильнопосчитала4085input tokens и получила совпадающееactualusage, но final **LAB_SENTINEL_42** содержитMarkdown и не принят. Тут только long promptinstruction уточняется: запретMarkdown/кавычек/пояснений/пунктуации. Expected exact LAB_SENTINEL_42 неизменен; normalization не вводится. Chat/tool fixtures/backend/sampling теже. Новая сессия и hashes до запуска, warmup+3. Cancel prompt сохраняетlongвход и дополняеткоманду перечисления; отказ остановитпрогрессиюbudget.

Наблюдаемаяv3конфигурация до первойcancelпопытки: phase закрепляется вgenerationbegin иGenerationContext.__init__, затемstop/end связываются поidэтогоcontext, а не по mutablephase.txt. Требуютсяstopflagtrue,stop≤end и samecontext, clientexit28/noDONE. Getter memory counters не меняетgeneration; realphase association добавляетсятольконаблюдателем. Первые две failedсессииcancelнеисполняли; ихeventsнеиспользуем какcancellationproof.
