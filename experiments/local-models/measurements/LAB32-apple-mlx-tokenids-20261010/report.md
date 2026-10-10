# LAB32 — MLX native input-budget qualification

Сессия `apple-mlx-tokenids-20261010`, статус **blocked**. Native MLX input-budget qualification: blocked by AssertionError: Exact final mismatch: '**LAB_SENTINEL_42**'

## Паспорт выполнения

Apple M5 Max /128GiB/macOS26.5/25F71, AC/mode0. MLX-LM0.32.0/MLX0.32.3/Python3.12.14; Qwen3.5-9B MLX4bit affine/group64 revision938d8919941c6e7efd3c7150eff7fe9d12afa631, отдельный VLM artifact в text-only inference. Исходнаяconversion revision неизвестна. [Artifact](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [267prestartpins](raw/prestart-pins.json), actual before/after loaded-images и device proofs вctx* directories. System frameworks закреплены macOSbuild, отдельноfilehashне заявлен.

Context hardcap **null**:8192/16384/32768 — labels input budgets, не KVreservation и не server caps. Один active server127.0.0.1:8081, seed1/temp0/top_p1/output2048/thinkingfalse/prefill2048/concurrency1. Prompt cache size0, full precision KV, без operator memory tuning. Observed entry wrapper не меняет оригинальные MLX-LM generation sources; его hash — часть конфигурации.

## Гипотеза и протокол до запуска

[Protocol](raw/protocol.md) и source-registration.json закреплены commit до каждого исполнения. Четыре chat/tool JSON/SSE fixtures, long и cancel/recovery: warmup+3 наbudget, новый owned server междуbudgets. Expected values exact LAB_READY/LAB_VALUE_42/LAB_SENTINEL_42, однаallowlisted lookup_lab_value/keyalpha/nonemptyid. Код модели не исполняется. Actualusage/tokenizer equality, DONE/finish, no-cacheusage, memoryguard2s/gap15s/free+spec8GiB/pressure1/ACmode0/swap0/RSS24GiB, wall900s/request240s. Послеотказаfuturebudgetnot-run.

## Ход выполнения

Source pins→CPUtokenization/shape/budget preparation→offlineallowlist→native server→shortprotocols→long→cancel/recovery→cleanup. [Controller](raw/run_series.py), [request hashes](raw/request-hashes.json), [offlineallowlist](raw/allowlist.json). Все rawrequests/responses/assembled/usage/errors сохранены; realagentepisodes не выполнялись, run_ids=[].

Три сессии разделены: исходная `apple-mlx-protocol-20261010` ошибочнопосчиталаlen(BatchEncoding)=2 и отправила113613actualtokens. Это protocol-invalid, не8Kопыт;контроллеротказалпослеusage mismatch иcleanup. `apple-mlx-tokenids-20261010` исправила flatIDs/count4085, но получила **LAB_SENTINEL_42** и отказалаexact-final. `apple-mlx-exact-final-20261010` отдельно запретилаMarkdown вlonginstruction и связала stop/end с одним nativeGenerationContext. Старые failures остаются неизменными; normalization не введена.

## Результаты

Attempts: {"completed": 17, "failed": 1, "not-run": 58, "planned": 0}. Warmup не включается в median/p95; здесь приведены индивидуальные наблюдения. `context_tokens` вTSV пуст: hardcapнеизвестен. Runtime samples/RSS/allocator peaks/swap/exit/signal в [summary](raw/runtime-summary.json).

| Input-budget label | Case/repeat | Actualinput/output | TTFTcontent,s | Total,s | Attemptstatus |
| --- | --- | --- | --- | --- | --- |
| 8192 | chat-1 | 21 / 3 | None | 0.1007115 | completed |
| 8192 | chat-2 | 21 / 3 | None | 0.095295 | completed |
| 8192 | chat-3 | 21 / 3 | None | 0.077493125 | completed |
| 8192 | chat-stream-1 | 21 / 3 | 0.06887691700000001 | 0.090114917 | completed |
| 8192 | chat-stream-2 | 21 / 3 | 0.07305720900000001 | 0.095116917 | completed |
| 8192 | chat-stream-3 | 21 / 3 | 0.073661 | 0.09489291700000001 | completed |
| 8192 | chat-stream-warmup | 21 / 3 | 0.07563662500000001 | 0.096804833 | completed |
| 8192 | chat-warmup | 21 / 3 | None | 0.105689792 | completed |
| 8192 | long-warmup | 4085 / 10 | 1.262849334 | 1.361566959 | failed |
| 8192 | tool-1.followup | 364 / 6 | None | 0.19040191699999998 | completed |
| 8192 | tool-1 | 315 / 27 | None | 0.408179416 | completed |
| 8192 | tool-2.followup | 364 / 6 | None | 0.19066266599999998 | completed |
| 8192 | tool-2 | 315 / 27 | None | 0.40406891699999997 | completed |
| 8192 | tool-3.followup | 364 / 6 | None | 0.19128370800000005 | completed |
| 8192 | tool-3 | 315 / 27 | None | 0.40559575000000003 | completed |
| 8192 | tool-stream-1.followup | 364 / 6 | 0.138078667 | 0.19093224999999997 | completed |
| 8192 | tool-stream-1 | 315 / 27 | None | 0.406761 | completed |
| 8192 | tool-stream-2.followup | 364 / 6 | 0.13772154200000003 | 0.19008354200000005 | completed |
| 8192 | tool-stream-2 | 315 / 27 | None | 0.404405958 | completed |
| 8192 | tool-stream-3.followup | 364 / 6 | 0.13794854199999995 | 0.19024766699999995 | completed |
| 8192 | tool-stream-3 | 315 / 27 | None | 0.406490708 | completed |
| 8192 | tool-stream-warmup.followup | 364 / 6 | 0.13840770800000002 | 0.19132854200000005 | completed |
| 8192 | tool-stream-warmup | 315 / 27 | None | 0.40436537499999997 | completed |
| 8192 | tool-warmup.followup | 364 / 6 | None | 0.19054966699999998 | completed |
| 8192 | tool-warmup | 315 / 27 | None | 0.404570833 | completed |

| Cancel condition | Clientexit | End observed after clientexit,s | Stop/end observed |
| --- | --- | --- | --- |
| — | — | — | Not executed |

## Ошибки и ограничения

AssertionError: Exact final mismatch: '**LAB_SENTINEL_42**' Native generation cancellation требуетclientexit28/noDONE + samecontextobject/stopflagtrue/stop≤end и exactrecovery ≤60s в наблюдаемойv3конфигурации. Clienttimeout отдельно не доказывает GPUcancel. Getter allocator counters не измеряет физическоеосвобождениевсехGPUстраниц. Coldstartup/JIT отличается отwarmrequests. Первые две failedсессииcancelнеисполняли, ихmutablephaseeventsнеиспользуемкакcancelproof. Hardcap/overflowне имитируемOOM. Energy/thermal/maxGPUunknown с причинами.

## Вывод по гипотезе

Native MLX input-budget qualification: blocked by AssertionError: Exact final mismatch: '**LAB_SENTINEL_42**' Результаты дают допуск только перечисленным input-budget protocols. Нельзя сравнивать label32K сllama.cpp hardcontext32K как одинаковуюKVreservation или переносить GGUFQ6_K size/performance наMLX4bit. НастоящийagentbridgeдляMLX остаётся отдельной инженерной задачей; эти HTTPзапросы неagentattempts.

## Ответы на контрольные вопросы

1. Non-streamingtotal включаетполнуюgeneration;TTFTиз него не извлекается, null.
2. ClientCTX и architecturemaxposition не задаютadmittedservercap. TokenIDs считаются явноreturn_dict=False и actualusage подтверждается отдельно.
3. Sockettimeout не прерываетGPUсам по себе: нужныnative stopflag/routineexit/queue recovery;physicalrelease требуетдругогоcollector.
4. Cache/reasoning меняютработуиTTFT: здесьthinkingfalse/cache0/seed1, usagecached0проверяется отдельно вновыхсериях;Gguf thinkingtrue — другойdeployment.

## Комплект сдачи

Manifest/TSV/protocol/sourcepins/loadedimages/device/modelidentity, requests/hashes, allHTTP/SSE/usage/finals, nativeevents/cancel/recovery, continuousresources/cleanup, offlineallowlist иsoftwarevalidation. Submissioncheck оцениваеткомплектностьblockedотчёта; reviewerdecision **не проверено**, experimentpassнеавтоматический.
