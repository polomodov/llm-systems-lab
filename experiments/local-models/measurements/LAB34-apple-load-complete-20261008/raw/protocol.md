# LAB34: полная новая серия после memory stop

Предыдущая LAB34-apple-direct-load-20261008 неизменна: warmup2/2, firstc1 block1/12, guardfree+spec<16GiB, secondSIGINT/assertion/native-6. Нельзя объединять новые данные с прежними или стирать failures.

Входной текст примерно300слов, request и параметры модели сохраняются побайтно: max_tokens2048,temp0,seed1,top_p1, reasoningauto/enablethinkingtrue. PinnedQ6_K SHA91898433…, llama.cpp b8407/312cf033… +tile16/serverSHA916660e9…, Metal/M5/offload33/33. Context8192/np1/threads8/b512/ub256/FAon/KVf16/Jinja/no-context-shift/cacheoff; loopback18080. Client concurrency1/2/4 при неизменномserver slot1 измеряет очередь и общуюустойчивость deployment. Это не тест4GPUslots.

До всех запусков новые operational limits: timeout300s и p95<=240s, noerrors. Прежняя latencyоколо33–39s означает, что при4clients вsingle-slot очередь можетпревышать120s. Новые границы — политикадопуска, не улучшениенативнойскорости. РезервОС16GiB вкаталогене меняется; онне равен free-pagefloor.

Новый memorycondition: каждые2s free+speculative>=8GiB, sysctl kern.memorystatus_vm_pressure_level==1 (наблюдаемый исходный normal level; rawvalue сохраняется), memory_pressure-Q freepercentage>=50%, swap0, nativeRSS<=24GiB, AC/powermode0. Всеcollectorcommandsexit0, иначеstop. Free+specfloor8 — зарегистрированная гипотеза для даннойсерии; прежний16GiBfloor сработал приnormalpressure/swap0/RSS7.6GiB, не установивOOM. Neither freepercentage nor floor gives exact allocatableGPUbudget. GPUbudget=null. Не менятьkernel/cache/power knobs и неостанавливатьчужиеприложения. Foreignmodels inventoriesbeforestartup/каждые~20s; обнаружениечужойGPUмоделиостанавливает толькоownedserver.

Cleanupисправлендо опыта: monitor иnormalshutdown используютоднуlocked interrupt(reason), SIGINTнеповторяетсяпригонке, 30s nativeexitdeadline→boundedSIGKILLfallback приtimeout. Собственныйcaffeinate-i assertion действуеттолькововремяcontroller. Interruptedcleanup невыдаётсязаспонтанныйMetalcrash.

Warmup2requests, then3×12 дляconcurrency1/2/4 в порядкеr1=1→2→4,r2=2→4→1,r3=4→1→2. Hypothesis: >=10%medianthroughputgainc2/c4 противc1 безнарушенияграниц. После полнойshortmatrix выбратьlowestconcurrency within95%maxmedianthroughput; selectionзаписатьдосustained. Затем1800s последовательныхblocks12requests, последнийblock можетзакончитьсяпосле1800; actualduration/паузы/ошибкиневычитать. ЛюбойHTTP/protocol/latency/memory/readinessstop прекращаетвсюсерию, futureattemptsnot-run. Послеdeadlineпроверитьserver queue, restartнеподменяетrecovery.

Nonstreamingdriver: непустойassistanttextбезtools, finishstopилиlength;300слов/смыслнеоценивается, capincludesreasoning. Retainallindividualprimaryresponses/metrics, nativeprops/slots/device/log, macOS timeline before/during/after, coldstartup отдельно. TTFT/decode-only/energy/temperature/maxGPUbudgetunknown. Overalltokens/s=sum successfulcompletiontokens/wholewall, неmeanblockrates. Actualstop/lengthсчётчикисохранить. Безагентов/run_ids.
