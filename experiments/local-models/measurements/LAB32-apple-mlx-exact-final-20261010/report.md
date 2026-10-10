# LAB32 — MLX native input-budget qualification

Сессия `apple-mlx-exact-final-20261010`, статус **blocked**. Native MLX input-budget qualification: blocked by OSError: [Errno 48] Address already in use

## Паспорт выполнения

Apple M5 Max /128GiB/macOS26.5/25F71, AC/mode0. MLX-LM0.32.0/MLX0.32.3/Python3.12.14; Qwen3.5-9B MLX4bit affine/group64 revision938d8919941c6e7efd3c7150eff7fe9d12afa631, отдельный VLM artifact в text-only inference. Исходнаяconversion revision неизвестна. [Artifact](raw/artifact-manifest.json), [runtime](raw/runtime-manifest.json), [267prestartpins](raw/prestart-pins.json), actual before/after loaded-images и device proofs вctx* directories. System frameworks закреплены macOSbuild, отдельноfilehashне заявлен.

Context hardcap **null**:8192/16384/32768 — labels input budgets, не KVreservation и не server caps. Один active server127.0.0.1:8081, seed1/temp0/top_p1/output2048/thinkingfalse/prefill2048/concurrency1. Prompt cache size0, full precision KV, без operator memory tuning. Observed entry wrapper не меняет оригинальные MLX-LM generation sources; его hash — часть конфигурации.

## Гипотеза и протокол до запуска

[Protocol](raw/protocol.md) и source-registration.json закреплены commit до каждого исполнения. Четыре chat/tool JSON/SSE fixtures, long и cancel/recovery: warmup+3 наbudget, новый owned server междуbudgets. Expected values exact LAB_READY/LAB_VALUE_42/LAB_SENTINEL_42, однаallowlisted lookup_lab_value/keyalpha/nonemptyid. Код модели не исполняется. Actualusage/tokenizer equality, DONE/finish, no-cacheusage, memoryguard2s/gap15s/free+spec8GiB/pressure1/ACmode0/swap0/RSS24GiB, wall900s/request240s. Послеотказаfuturebudgetnot-run.

## Ход выполнения

Source pins→CPUtokenization/shape/budget preparation→offlineallowlist→native server→shortprotocols→long→cancel/recovery→cleanup. [Controller](raw/run_series.py), [request hashes](raw/request-hashes.json), [offlineallowlist](raw/allowlist.json). Все rawrequests/responses/assembled/usage/errors сохранены; realagentepisodes не выполнялись, run_ids=[].

Три сессии разделены: исходная `apple-mlx-protocol-20261010` ошибочнопосчиталаlen(BatchEncoding)=2 и отправила113613actualtokens. Это protocol-invalid, не8Kопыт;контроллеротказалпослеusage mismatch иcleanup. `apple-mlx-tokenids-20261010` исправила flatIDs/count4085, но получила **LAB_SENTINEL_42** и отказалаexact-final. `apple-mlx-exact-final-20261010` отдельно запретилаMarkdown вlonginstruction и связала stop/end с одним nativeGenerationContext. Старые failures остаются неизменными; normalization не введена.

## Результаты

Attempts: {"completed": 25, "failed": 0, "not-run": 51, "planned": 0}. Warmup не включается в median/p95; здесь приведены индивидуальные наблюдения. `context_tokens` вTSV пуст: hardcapнеизвестен. Runtime samples/RSS/allocator peaks/swap/exit/signal в [summary](raw/runtime-summary.json).

| Input-budget label | Case/repeat | Actualinput/output | TTFTcontent,s | Total,s | Attemptstatus |
| --- | --- | --- | --- | --- | --- |
| 8192 | chat-1 | 21 / 3 | None | 0.098039625 | completed |
| 8192 | chat-2 | 21 / 3 | None | 0.076780292 | completed |
| 8192 | chat-3 | 21 / 3 | None | 0.095514209 | completed |
| 8192 | chat-stream-1 | 21 / 3 | 0.073529917 | 0.09457825 | completed |
| 8192 | chat-stream-2 | 21 / 3 | 0.055674333000000006 | 0.0774975 | completed |
| 8192 | chat-stream-3 | 21 / 3 | 0.074389333 | 0.095478542 | completed |
| 8192 | chat-stream-warmup | 21 / 3 | 0.068297417 | 0.08944020800000001 | completed |
| 8192 | chat-warmup | 21 / 3 | None | 0.142784875 | completed |
| 8192 | long-1 | 4092 / 8 | 1.140837208 | 1.217611416 | completed |
| 8192 | long-2 | 4092 / 8 | 1.142244125 | 1.218963 | completed |
| 8192 | long-3 | 4092 / 8 | 1.341974209 | 1.4270684169999999 | completed |
| 8192 | long-warmup | 4092 / 8 | 1.142390542 | 1.2194755000000002 | completed |
| 8192 | recovery-1 | 21 / 3 | 0.080596208 | 0.105359958 | completed |
| 8192 | recovery-2 | 21 / 3 | 0.07795454199999999 | 0.09992320900000001 | completed |
| 8192 | recovery-3 | 21 / 3 | 0.0761595 | 0.09785554099999999 | completed |
| 8192 | recovery-warmup | 21 / 3 | 0.07912512499999999 | 0.10126233399999998 | completed |
| 8192 | tool-1.followup | 364 / 6 | None | 0.19006004200000004 | completed |
| 8192 | tool-1 | 315 / 27 | None | 0.406730125 | completed |
| 8192 | tool-2.followup | 364 / 6 | None | 0.19198279100000004 | completed |
| 8192 | tool-2 | 315 / 27 | None | 0.40942779100000004 | completed |
| 8192 | tool-3.followup | 364 / 6 | None | 0.19061016600000003 | completed |
| 8192 | tool-3 | 315 / 27 | None | 0.40535175 | completed |
| 8192 | tool-stream-1.followup | 364 / 6 | 0.13793083300000003 | 0.19028974999999998 | completed |
| 8192 | tool-stream-1 | 315 / 27 | None | 0.40448825 | completed |
| 8192 | tool-stream-2.followup | 364 / 6 | 0.13797187500000002 | 0.19043737500000008 | completed |
| 8192 | tool-stream-2 | 315 / 27 | None | 0.40362237500000003 | completed |
| 8192 | tool-stream-3.followup | 364 / 6 | 0.13832241699999998 | 0.19073024999999993 | completed |
| 8192 | tool-stream-3 | 315 / 27 | None | 0.407461666 | completed |
| 8192 | tool-stream-warmup.followup | 364 / 6 | 0.13778300000000004 | 0.18996508299999998 | completed |
| 8192 | tool-stream-warmup | 315 / 27 | None | 0.40503795800000003 | completed |
| 8192 | tool-warmup.followup | 364 / 6 | None | 0.19048504200000005 | completed |
| 8192 | tool-warmup | 315 / 27 | None | 0.40418729200000003 | completed |

| Cancel condition | Clientexit | End observed after clientexit,s | Stop/end observed |
| --- | --- | --- | --- |
| ctx8192/cancel-1.proof | 28 | 0.25728726387023926 | True / True |
| ctx8192/cancel-2.proof | 28 | 0.26172590255737305 | True / True |
| ctx8192/cancel-3.proof | 28 | 0.26157069206237793 | True / True |
| ctx8192/cancel-warmup.proof | 28 | 1.55373215675354 | True / True |

## Ошибки и ограничения

OSError: [Errno 48] Address already in use Native generation cancellation требуетclientexit28/noDONE + samecontextobject/stopflagtrue/stop≤end и exactrecovery ≤60s в наблюдаемойv3конфигурации. Clienttimeout отдельно не доказывает GPUcancel. Getter allocator counters не измеряет физическоеосвобождениевсехGPUстраниц. Coldstartup/JIT отличается отwarmrequests. Первые две failedсессииcancelнеисполняли, ихmutablephaseeventsнеиспользуемкакcancelproof. Hardcap/overflowне имитируемOOM. Energy/thermal/maxGPUunknown с причинами.

## Вывод по гипотезе

Native MLX input-budget qualification: blocked by OSError: [Errno 48] Address already in use Результаты дают допуск только перечисленным input-budget protocols. Нельзя сравнивать label32K сllama.cpp hardcontext32K как одинаковуюKVreservation или переносить GGUFQ6_K size/performance наMLX4bit. НастоящийagentbridgeдляMLX остаётся отдельной инженерной задачей; эти HTTPзапросы неagentattempts.

## Ответы на контрольные вопросы

1. Non-streamingtotal включаетполнуюgeneration;TTFTиз него не извлекается, null.
2. ClientCTX и architecturemaxposition не задаютadmittedservercap. TokenIDs считаются явноreturn_dict=False и actualusage подтверждается отдельно.
3. Sockettimeout не прерываетGPUсам по себе: нужныnative stopflag/routineexit/queue recovery;physicalrelease требуетдругогоcollector.
4. Cache/reasoning меняютработуиTTFT: здесьthinkingfalse/cache0/seed1, usagecached0проверяется отдельно вновыхсериях;Gguf thinkingtrue — другойdeployment.

## Комплект сдачи

Manifest/TSV/protocol/sourcepins/loadedimages/device/modelidentity, requests/hashes, allHTTP/SSE/usage/finals, nativeevents/cancel/recovery, continuousresources/cleanup, offlineallowlist иsoftwarevalidation. Submissioncheck оцениваеткомплектностьblockedотчёта; reviewerdecision **не проверено**, experimentpassнеавтоматический.
