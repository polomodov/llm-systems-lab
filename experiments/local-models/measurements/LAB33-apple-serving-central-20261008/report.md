# LAB33 — централизованные Ollama и LM Studio на M5 Max

Статус: **blocked на MLX-ветви**. Централизованная установка выполнена; Ollama и LM Studio/GGUF прошли короткие API-контракты. MLX загрузился, но первый chat-запрос завершился закрытием соединения и исчезновением исходного GUI-процесса. Причина не установлена, полный допуск не заявлен.

## Паспорт выполнения

| Поле | Условие |
| --- | --- |
| Исполнитель / дата | Codex по запросу владельца, 08.10.2026 |
| Машина / питание | Apple M5 Max18CPU/40GPU,128GiB,macOS26.5; AC/powermode0 по timeline. Предыдущий Battery preflight отдельным blocked отчётом |
| GGUF | unsloth/Qwen3.5-9B-GGUF @3885219b6810b007914f3a7950a8d1b469d598a5; Q6_K,7458301152bytes, SHA25691898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59 |
| MLX | mlx-community/Qwen3.5-9B-MLX-4bit @938d8919941c6e7efd3c7150eff7fe9d12afa631; отдельные files/hashes,4bit group64 affine; weights5950221072bytes, не размер GGUF |
| Ollama | /Applications/Ollama.app0.40.1, CLI через PATH; actual llamacpp runner631109b34, Metal/M5,33/33GPU layers, tensor capability=true |
| LM Studio | /Applications/LM Studio.app0.4.25+1, CLI69d945a; actual llama.cpp runtime2.54.0/448147d, MLX1.13.1 M5/NAX package |
| Context / slots / params | Все model loads8192/parallel1; outputcap2048,temp0,seed1,top_p1. Ollama/direct threads8, LM GGUF observed13; default KV/cache/template LMS не полностью закреплены |
| Reasoning | Ollama low для boolean-thinking; direct auto + enable_thinking=true, без budget128. LMS native defaults, reasoning_effort не отправлялся |
| Harness / agent IDs | Аппаратный HTTP-пробник; run_ids=[], реальных агентных попыток нет |
| Evidence | [Фактические deployments](raw/deployment-manifest.json), [summary](raw/summary.json), primary logs/requests/timelines |

В [preflight runtime-manifest](raw/runtime-manifest.json) direct-объект наследует сведения о бинарнике и источниках LAB32; его context/budget поля не описывают новую серию. Actual command/props/context8192 и отсутствие request budget128 указаны в deployment-manifest. Это различие сохранено явно, исходный preflight файл не переписан.

## Гипотеза и протокол до запуска

[Новый protocol](raw/protocol.md) зарегистрирован до импорта/инференса, с [предыдущим протоколом](raw/prior-protocol.md) как контекстом. Commit72bcce7 предшествует модельным запросам; timestamp manifest — утверждение оператора. Прогрев +три повтора каждой клетки chat/tool JSON/SSE; точные LAB_READY/LAB_VALUE_42, tool allowlist/key/ID, matching tool_call_id, stop/DONE и usage. Экспорт заново проверяет эти primary contracts, а не только controller accepted.

Протокол имеет отдельные сохранённые amendments до соответствующих запусков: port/identity перед Ollama retry, selector перед MLX, [новый resource condition](raw/mlx-resource-amendment.md) перед MLX retry. Первая free-only ветвь MLX остановилась при free14.208GiB ещё до load; cached-file чтение и memory pressure95% показаны отдельно. Новые MLX попытки требуют free+speculative≥16GiB, pressure free≥50%, swap0/AC/powermode0, app treeRSS≤24GiB; это иной guard, не изменение результатов первого условия. macOS memory/power knobs не менялись, cache не очищался и искусственный pressure не создавался.

Критерий отмены: curl exit28, отсутствующий DONE, native cancellation в выделенном окне, точное recovery≤60s в том же owned server. Время освобождения GPU отдельно неизвестно. На первой ошибке ветвь останавливается, дальнейшие клетки not-run; независимые deployments выполняются последовательно.

## Ход выполнения

| Шаг | Команды / условия | Итог и primary evidence |
| --- | --- | --- |
| Установка | Официальные Ollama ZIP и LMS arm64 DMG; SHA256, ditto /Applications, codesign verify, CLI PATH | [Ollama install](raw/ollama-central-installation.json), [LMS install](raw/lm-studio-central-installation.json); обычные программы и CLI доступны вне лабы |
| Preflight / validator | python3 raw/lab33_runner.py preflight; GGUF/binary hashes, AC/memory; synthetic valid/unknownname/wrongkey/missingID | [preflight](raw/preflight-execution.json), [synthetic](raw/offline-validator-results.json), модель validator не запускал |
| Ollama подготовка | Два bind отказа11434, затем isolated11435; import из существующего GGUF, без quantize/pull; actual FROM blob через /api/show | Отказы сохранены. [Уточнение порта](raw/port-observation-correction.md): последующий lsof/curl не подтвердил listener/restart, возможный TIME_WAIT — только объяснение. [Identity](raw/ollama-startup-weights.json) совпадает с исходным SHA |
| Ollama API | python3 raw/lab33_runner.py ollama; /api/version,/api/show,/v1/models,/api/ps; four cells warmup+3 | 16/16; [show](raw/ollama-startup-show-preview.json), [runtime log](raw/ollama-server.txt), индивидуальные JSON/SSE/metrics |
| Direct baseline | python3 raw/lab33_runner.py direct; новый сервер8192/cache-off с прежним patched binary | 16/16; [command](raw/direct-server-execution.json), [props](raw/direct-startup-props.json), [log](raw/direct-server.txt), exit0 |
| LMS GGUF | python3 raw/lms_runner.py lms-metal; lms import --symbolic-link, load8K/parallel1/gpu max/ttl600; localhost1234 | 16/16; [load](raw/lms-metal-startup-loaded.txt), [weights](raw/lms-metal-startup-weights.json), [actual runtime](raw/lms-metal-server.txt). Exact executed controller saved separately |
| LMS MLX подготовка | Existing pinned directory symlink; files SHA; индекс обновился с задержкой. CLI path selector не принял indexedModelIdentifier, исправлен на actual unique modelKey qwen3.5-9b-mlx | Первый guard и второй selector отказ не удалены, inference ещё не был начат; оба контроллера сохранены |
| LMS MLX load/chat | python3 raw/lms_runner.py lms-mlx; loaded safetensors/path/context8192/parallel1 проверены | [load](raw/lms-mlx-startup-loaded.txt), [actual runtime1.13.1](raw/lms-mlx-server.txt); первый chat RemoteDisconnected, usage/HTTP status неизвестны. [Lifecycle](raw/lms-mlx-lifecycle-observation.json), дальнейшие cases not-run |
| Остановка | Собственные Ollama unload+SIGINT и direct SIGINT; LMS unload labalias/server stop; ordinary apps открыты после серии | Ollama/direct/GGUF штатно остановлены. MLX server stop сообщил «server is not running» после исчезновения GUI; lms ps=[] |

## Результаты

Медианы трёх повторов на клетку, без warmup. Chat — один запрос, tool — сумма initial+followup HTTP durations. Это **разные deployments**, не чистые накладные расходы wrapper.

| Deployment | Runtime pin | Short protocol | Median chat JSON / SSE / tool JSON / SSE, s | Max sampled process-tree RSS, GiB |
| --- | --- | --- | --- | --- |
| Ollama GGUF | 0.40.1 / runner631109b34 | 16/16 | 3.547 / 3.584 / 1.319 / 1.320 | 8.190 |
| Direct llama.cpp | b8407+tile16 /312cf033… | 16/16 | 3.757 / 3.780 / 2.261 / 2.277 | 7.533 |
| LM Studio GGUF | 0.4.25+1 /llama.cpp2.54.0 /448147d | 16/16 | 4.339 / 4.371 / 3.301 / 3.335 | 9.904 |
| LM Studio MLX |1.13.1 M5/NAX | load прошёл; первый chat failed | Неизвестны | Серия не допущена |

RSS — сумма процесса и descendants, может учитывать общие страницы; у LM Studio включает GUI/helper. Не равен Metal allocator и не используется как чистая разница model memory. Сэмплирование2s может пропустить peak. Для трёх прошедших deployments swap0 на всём timeline; minfree Ollama18.480/direct18.134/LMS16.123GiB. GPU allocation ceiling остаётся null.

| Deployment | Client timeout, s | Client exit → recovery завершён, s | GPU slot release |
| --- | --- | --- | --- |
| Ollama |1.049 |5.804 |null: отдельный slot monitor не записан |
| LM Studio GGUF |1.060 |5.880 |null: cancel log/recovery не измеряют release GPU |

[Summary](raw/summary.json) содержит исходные три значения и отдельный warmup. В TSV **542 observations**, измеренное время failed MLX request0.425772s сохранено отдельно от неизвестных usage/throughput. JSON не даёт TTFT; SSE content/reasoning arrival timings есть там, где соответствующий delta присутствовал. Первичный tool stream без content не получает фиктивный нулевой TTFT. GPU/runtimes CLI claims не заменяют actual evidence.

| Сравнение | Совпадает | Различается / неизвестно | Вывод |
| --- | --- | --- | --- |
| Ollama/direct/LMS GGUF | Exact GGUF, входы,8K,slots1,temp0/seed1/top_p1/cap2048 | Commit631109b34/312cf033+patch/448147d, builds, threads8/8/13, cache, defaults/template; LMS device/offload строк нет | Только сравнение deployments; overhead=null |
| LMS MLX против directMLX LAB31 | Source family и pinned MLX files | Native runtime1.13.1/VLM loader vs MLX-LM0.32.0/text loader; HTTP серия MLX не завершилась, baseline повторно не запускался | Latency comparison unavailable; GGUF estimates не переносятся |

## Ошибки и ограничения

- Всего180 попыток:63completed,8failed,109not-run. Повторные подготовки/отказы не замаскированы общим success; исходный Battery report отдельно сохранён. Счётчик completed включает подготовку/shutdown/synthetic, не число агентных успехов.
- Логи Ollama подтверждают Metal/Apple M5 Max,33/33 GPU layers и tensor capability. Это не измерение максимального GPU budget; `available107.5GiB` в engine discovery — runtime report, не доказанная свободная heap.
- LMS GGUF actual runtime Metal package2.54.0/PID8586 подтверждён логами; строки actual device/33of33offload не записаны runtime stream. `--gpu max` — requested setting. Hardware/offload proof остаётся **unverified**, хотя API-клетки прошли.
- LMS1.13.1 loaded MLX package на M5; на первом chat original GUI process303 исчез, HTTP и runtime-log WebSocket закрылись. После этого CLI показал service process и ps=[]; crash report LM Studio/MLX не найден в проверенном каталоге. Причина **unknown**, не установлены OOM, crash или user quit; отдельный вопрос владельцу не заменён догадкой.
- До полного MLX smoke допуск этой ветви к LAB34 отсутствует. Existing files не переобучались/переквантизировались; download новых модельных весов контроллеры не выполняют.
- Приложения устанавливаются вне Git; пакеты/weights остаются на Mac. Общий hardware/engine catalogue остаётся conditional для остальных сочетаний и неизвестного budget.

## Вывод по гипотезе

Для короткого API-контракта **Ollama/Metal и LMS/GGUF поддержаны данными16/16**, cancel/recovery тоже прошли. Полная гипотеза LAB33 **не проверена**: MLX chat failed при исчезновении приложения, а независимый device/offload proof LMS/GGUF неполон. Сессия blocked, исходные ошибки сохранены. Чистый overhead и превосходство движка не утверждаются.

Следующий модельный шаг — отдельная диагностика жизненного цикла MLX и наблюдаемости backend LMS. Параллельно по маршруту допустима подготовка LAB34 на уже проверенном direct/Ollama8K: concurrency1/2/4 и затем30min только после коротких проверок. В этой сессии LAB34 не выполнялся.

## Ответы на контрольные вопросы

1. **Почему версия GUI не pin engine?** LMS при первом запуске выбрал2.54.0/1.13.1 вместо bundled2.41.0/1.11.0; runtime обновляется/выбирается отдельно. Сохраняем actual engine logs/package manifests/hash/version.
2. **Когда импорт меняет протокол?** При новом renderer/chat template/defaults/tools parser/reasoning mapping. Ollama импорт сохранил GGUF hash, но cache/native protocol отличается от direct; same alias ничего не доказывает.
3. **Что нужно для чистого overhead?** Одинаковые commit/build/quant/tokenizer/template/context/slots/sampling/cache и входы; здесь три разных commits и LMS13threads. Вычитать median как GUI overhead нельзя.
4. **Чем observed runner полезнее alias?** Actual logs имеют engineName/version/PID и load path. MLX load действительно выбрал safetensors1.13.1, несмотря на повторно использованный API alias q6-k; проверка format/path предотвратила подмену GGUF.

## Комплект сдачи

Manifest v2,180попыток,542 observations, primary requests/JSON/SSE/logs/timelines, configs/CLI help/install hashes/runtime manifests и все amendments сохранены. Экспорт повторно проверяет exact finals/tool IDs/usage/DONE и cancellation/recovery window. Неизвестные значения имеют причины. Реальных run records нет, потому что автономные агенты не запускались. Комплект проверяется lab:check submission; это комплектность blocked отчёта, не experimental pass.

Решение проверяющего: не проверено.

Два verbose `/api/show` ответа с tokenizer arrays сохранены lossless gzip: [инвентарь исходных SHA256](raw/lossless-primary-archives.json). Сжатие проверено побайтным roundtrip; читаемый preview — производная выборка, не замена primary response.
