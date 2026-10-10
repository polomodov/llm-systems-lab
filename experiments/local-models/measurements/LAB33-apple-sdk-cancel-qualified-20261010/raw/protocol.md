# LAB33 — explicit cancellation и фактический backend

Протокол регистрируется до модельных запусков. Existing LM Studio 0.4.25+1, selected llama.cpp/Metal2.54.0 и MLX/Metal1.13.1. Официальный SDK1.5.0 установлен в отдельный venv; wheels/requirements hashes сохранены. Веса не скачиваются; прежние GGUFQ6_K и MLX4-bit проверяются по полным hashes. Порядок GGUF→MLX, только одна модель, собственные alias; app/root PID сохраняются, чужие модели/процессы не останавливаются.

Admission120s/samples2s/free+spec≥16GiB/ACmode0/pressurelevel1/freepercentage≥50/swap0/gap≤15s. После этого новый owned model/server127.0.0.1:1234/context8192/parallel1/gpu max/TTL600. Считаем context запросом loader; hardcap/полныйoffload не подставляем. Runtime/template/KV/cache/reasoning по app defaults с unknown reasons, SDKtemp0/topP1/output2048; seed в API prediction не навязывается. CLI/SDK/source/model/backend pins до load. Global guard2s/free+spec8GiB/pressure1/swap0/ACmode0/backendmappedRSS≤24GiB/gap15s/backwardclock/wall600s; collector и caffeinate до load. После guard только свой alias unload; центральный app не kill. Foreign model/PID change — отказ. Сервер останавливается только если создан нами и loaded list пуст.

На GGUF: SDK chat warmup+3 exactLAB_READY; четыре отдельные длинные SSE predictions cap2048. Во время каждой 1s OS sample процесса, mapped через конкретный libggml-metal.dylib. Принимаем только attributed Metal call path + полный ответ samealias/DONE/finish; это не счётчик33GPUlayers, не измерениеGPUphysicalrelease. Sample влияет на время: серия квалификационная, latency не сравнивается с unsampled baseline. Pin maps/profile/API/logs сохраняются, неподтверждённые сочетания conditional.

На MLX: SDK chat warmup+3; SDK cancel warmup+3 (1s после start(), затем продолжить iterator до результата; требовать stats.stopReason=userStopped и samealias), каждый с exactSDKrecovery. Native SDK API и HTTP — разные условия. Затем HTTP cancel warmup+3: curl max-time1/noDONE, собрать runtime events только matching alias, same app/recovery. Deprecated stop-without-request-id/Taking no action — negative evidence; ни timeout, ни recovery не заменяют request-id native cancellation proof. HTTP опыт без такого proof сохраняется failed/inconclusive, не превращается в pass. Physical GPU release/null отдельно; unload/registryempty не равны hardwarepagesfree. Никакого scalar normalizing final.

Все ошибки и неисполненные attempts сохраняются. После model/startup/resource/protocol failure будущие dependent случаи not-run. NativeHTTPcancel inconclusive не прерывает независимые повторные diagnostics при safe recovery. Agent episodes/run.json здесь не создаются. Энергия/температура/maxGPU неизвестны. Current memory pressure/resource reserves не ослабляются; controller не закрывает приложения владельца.

SDK final отделяется только по публичному fragment.reasoning_type: конкатенация none, без trim/Markdown normalization; public result.content и все reasoning/tag fragments сохраняются. Native API parser declaration не считается текстом final. Primary SDK stats/userStopped остаются обязательны.

## Новая SDK schema конфигурация

Исходная сессия `apple-cancel-backend-20261010` сохраняется:120s admission/startup прошли, первый SDKfinal=LAB_READY/eosFound, но wrapper получил KeyError identifier; remaining cases not-run. Старый attempt не превращаем в pass. Перед этой новой сессией проверяется реальный registry→source binding каждого файла, его размер/hash против прежнего artifact reference, и новая loaded snapshot path/identifier. Result.model_info.path сверяется с registered path; response alias отсутствует в SDK schema и остаётсяnull с причиной. Fixed loaded handle/одинmodel/native endpoints подтверждаютуправляемыйselector. Public raw result и stats сохраняются.

## Правильный artifact selection до новой модели

В предыдущей schema-сессии регистрация отказала: первыйartifactбылGGUF, егоREADME/weightsнеподходятMLX. Pinfileне создан, controller послеCPUadmission остановилсябезmodelphase. Тут select_artifactтребуетMLX/safetensors/repository/revision(unique). Все12MLXfilesиGGUFsource сверяютсясpublisherreferences/bytes, centralregistryresolve→source подтверждаетсядоload, fullpinsets/SDK/actualbackendlibraries зафиксированы. Никакихретроспективныхпоправокстарыхpins.

## Отдельный retry после baseline resource refusal

Предыдущая full-pin сессия не загрузиламодель: baselinefree+spec16GiB не прошёл. После read-only resource-window120s stablepass регистрируетсяэтотновыйretry. Во всехпрежнихсессияхfailuresнеизменны. Другаяконфигурация/новаясессия, controllerпроверяетadmissionещёраз; пороги/source/model/SDK/APIкритериипрежние.
