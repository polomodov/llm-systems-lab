# LAB33 — отдельная диагностика service lifecycle на M5 Max

Статус **blocked**. MLX короткие API-проверки и recovery прошли; полной отмены и независимого GGUF offload proof нет. Исходная сессия не изменена.

## Паспорт выполнения

08.10.2026, Codex по запросу владельца. Apple M5 Max18CPU/40GPU,128GiB,macOS26.5/25F71, AC/powermode0. LM Studio0.4.25+1, lms69d945a, MLX1.13.1 M5/NAX и GGUF runtime2.54.0. Pinned MLX4bit @938d8919941c6e7efd3c7150eff7fe9d12afa631 и GGUFQ6_K @3885219b6810b007914f3a7950a8d1b469d598a5; файлы/hashes из LAB29 проверены, новых весов нет. Native app уже работал как --run-as-service/PID18402. Context8192/parallel1/gpu max/ttl600; temp0/seed1/top_p1/output2048, native reasoning/cache defaults. GGUF и MLX имеют отдельные артефакты. Agent harness отсутствует, run_ids[].

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md)/hash/register/commitbf64dda предшествуют model runs. Проверяем сохранение процесса и HTTP/tool session при стабильном service lifecycle. Прежнее исчезновение GUI PID303/RemoteDisconnected не заменяется этой серией; user quit/crash/OOM по-прежнему не установлены. Владелец не ответил на вопрос о закрытии приложения.

Четыре chat/tool JSON/SSE клетки по warmup+3, exactfinal/DONE/usage/call allowlist/key/id/result. MLX cache-aware: free+spec>=16GiB, pressure free>=50%,swap0,AC/powermode0,app treeRSS<=24GiB. GGUF сохраняет иной free-only16GiB guard. Timeline2s. На отказе stop, remaining not-run; cleanup только собственного alias/API server, приложение не убивается. Cancel client1s/recovery60s, nativecancel требуется отдельно. No power/cache/kernel settings.

## Ход выполнения

MLX загрузился в существующемservice process и прошёл16коротких случаев. Clientcancel curl28/noDONE, recovery в том же appPID18402. Runtime log не дал cancellation event, поэтому cancelfailed по исходному критерию; cleanup прошёл.

ПервыйGGUFstartup отказал доmodel load: повторныйlmsimport сообщает Target file already exists. До новогоnamespace lms-metal-existing зарегистрировано [исправление подготовки](raw/gguf-existing-registry-amendment.md): проверка существующегоsymlink+SHA вместо повторногоimport, runtime/inferenceусловия прежние. GGUFload прошёл, ноfree-only guard увидел14.982GiB<16 и разгрузил собственныйalias ещё доchat. Originalstartupfailure и resourcefailure сохранены. [Native log offsets](raw/native-log-offsets-before.json) и новые фрагменты не содержат независимых actualdevice/offloadстрок; requestedgpumax не принят за такую проверку.

## Результаты

| Клетка | Успешных / план | Median r1–r3 roundtrip s |
| --- | ---: | ---: |
| lms-mlx-chat | 4/4 | 2.778 |
| lms-mlx-chat-stream | 4/4 | 2.781 |
| lms-mlx-tool | 4/4 | 1.263 |
| lms-mlx-tool-stream | 4/4 | 1.259 |

MLXclienttimeout1.037187s, recoverycompleted4.889602s послеexit, sameappPID18402. Nativecancellation=false/unverified, GPUrelease=null. Appalive во всех25memorysamples, maxtreeRSS8.304GiB, minfree13.385GiB (MLXguard использует free+spec, а неfree-only), swap0. Cachedtokens/promptcache видны в runtime logs; nativecache не уравнен сdirectbranch. JSON TTFT=null; SSE content/reasoning timings сохранены по реально присутствовавшему каналу.

Всего60зарегистрированных попыток:21completed/3failed/36not-run. Counts включают startup/shutdown, это не agent successes. [Summary](raw/summary.json),163TSVobservations. GGUFновойсерии APIlatency неизвестна: ниодногоchat не запущено. LMS/GGUFpackageactualruntime известен, device/offload unverified.

## Ошибки и ограничения

Исходное закрытиеHTTP/исчезновениеGUI не повторилось приservice process. Это сужает диагностику, но не доказывает причинность режима запуска: исходные условия/причина неизвестны и контрольного повторенияGUI не было. Nativecancel MLX не доказан; успешный recovery не измеряет GPUrelease. GGUFостановлен наблюдаемымfree-only guard, не объявленOOM: swap0 и pressure normal не заменяют заранее выбранный критерий. Дополнительныйresourcecondition радиповтораGGUF здесь не вводился.

Runtime packages,KV/cache/template defaults, visionloader и quant разные; чистыйoverhead и чистаяразницаengine неизвестны. RSS включаетGUI/helpers/пересекающиесястраницы, неMetalheap. GPUbudget/energy/temperature неизвестны. ПервичнаяLAB33остаётсяblocked, новаясерия не выдаётся заfulladmission илиagent run.

При сверке 22.10.2026 обнаружено отсутствие двух архивных native logs: `raw/native-main.log` и `raw/native-2026-10-08.1.log`. Их исторические SHA-256 и исходные пути сохранены, но содержимое недоступно. Manifest учитывает их в `unavailable`, а доступными доказательствами остаются сохранённые server fragments, HTTP/metrics и resource timelines. Это ограничивает проверку полного native log; выводы о неподтверждённых cancellation/offload остаются прежними. [Аудит учёта](accounting-audit-20261022.md).

## Вывод по гипотезе

Стабильная MLXservice session поддержана16/16shortfixtures и recoveryбезисчезновенияприложения; полныйLAB33критерий не выполнен из-за nativecancel/offload/resourceguard. ДляLAB34 используется уже квалифицированныйdirectGGUF8K, не новаяMLXветвь. Причинаисходногосбояunknown.

## Ответы на контрольные вопросы

1. GUIversion неpin runtime: actualengine/version/PID сохраненыruntime stream и runtimefilehashes.
2. ИмпортсуществующегосвязногоGGUF повторятьне требуется; symlinktarget+SHAпроверкаподтверждаетexactartifact, aliasсамэтогонедоказывает.
3. Pureoverhead требуетравныхcommits/defaults/cache/threads; разныеdeployments не даюттакоговывода.
4. Clientexit28 означаетзакрытиеsocket; servercancellation,releaseиrecovery — разныеevidence. Здесьrecoveryизмерен, cancellation/release неустановлены.

## Комплект сдачи

Manifestv2/60attempts,protocol/hash,controller-at-first-start и amendment, weights/runtime hashes,actualPID/load logs,JSON/SSE/followups,metrics,timelines,rawnativefragments,offlineexport и163observations. Исторический SHA inventory сохранён неизменным; два отсутствующих native logs перечислены в `unavailable` и исключены из списка доступных `evidence_files`. Submissionlab:check означаеткомплектность, reviewer_decision=null до независимойоценки.
