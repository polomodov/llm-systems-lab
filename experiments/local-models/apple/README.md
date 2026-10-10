# Apple M5 Max / 128 GB / macOS

Второй стенд кампании локальных моделей. Профили дополнены первыми аппаратными измерениями от 07–09.10.2026; условия и ограничения сохранены в отчётах. Матрица моделей общая с Ryzen, но совместимость архитектуры, размер MLX-артефакта и бюджет GPU проверяются заново. `hardware.json` ссылается на архивированный паспорт LAB28 для RAM/ОС; резервы остаются гипотезами, свободный GPU budget — неизвестным.

Последнее продолжение от 09.10.2026:

- [LAB08: новая native квалификация и pilot на 16K](../measurements/LAB08-apple-native-requalification-20261010/report.md): короткие 8K и 16K квалификации прошли. T002 на 8K остановился на overflow; отдельно сохранён отказ resource guard. Новый 16K pilot: 16 turns / 244 с / exit 0 / **length**, awaiting_review. Полный допуск ждёт независимого judge.
- [LAB32: свежий MLX повтор с полными model pins](../measurements/LAB32-apple-mlx-identity-repeat-20261010/report.md): **72/72 протокольных cases** для input budgets 8K/16K/32K, плюс startup/allowlist — 76 успешных шагов. Все 12 MLX файлов и 278 pins проверены до Popen; RSS peak 5,193 GiB, allocator peak 7,056 GiB, swap 0, штатный cleanup. Hard cap/overflow и физическое освобождение GPU остаются unverified. Старые серии с GGUF pins не подтверждены задним числом.
- [LAB32: нативные MLX протоколы на 8K input budget](../measurements/LAB32-apple-mlx-exact-final-20261010/report.md): **24/24 функциональных cases**, включая четыре отмены и recovery; allocator peak 6,306 GiB, штатный cleanup. Аудит обнаружил, что prestart pins выбрали GGUF вместо 12 MLX файлов: **execution-time model identity unverified**, допуск конкретного MLX deployment отозван до свежего повтора. Исходные ошибки token counter и Markdown сохранены в отдельных сессиях. [Продолжение 16K](../measurements/LAB32-apple-mlx-budget-resume-20261010/report.md) прошло короткие протоколы, но long-вход получил отказ resource guard при free+spec 7,425 GiB; 32K не запускалась. Hard context cap и physical GPU release остаются unverified.
- [LAB08: первая реализация изолированного Pi bridge](../measurements/LAB08-apple-provider-bridge-20261009/report.md): local provider / sealed deployment fingerprint / native Metal supervisor / reverse broker; Pi tool round-trip и запреты сети проверены в настоящем Docker с mock. 171 offline tests и две Docker-проверки прошли. Два T002 runs **aborted**: первый на readiness до агента; второй после 12 полных HTTP-ответов — timeout с разрывом телеметрии 913,904 s, причина неизвестна. Cleanup exit 0 / один SIGINT. Wall/stale guards усилены программно; новая нативная квалификация и независимо оценённый pilot ещё нужны, **LAB08 blocked**. Это первый Pi/T002/macOS путь, остальные adapters pending.
- [LAB35: новый tensor-повтор с полными хешами dylib](../measurements/LAB35-apple-tensor-pinned-20261009/report.md): **11/11 шагов, 8/8 HTTP-запросов** после регистрации протокола в `76ad1b3`. Два executables и все 21 dylib path семи семейств проверены до Popen и сохранены в новом startup record; `libraries_verified_at_execution=true`. Те же Qwen3.5-9B Q6_K / b8407+tile16 / context 8192 / один slot, chat/load с прогревом и тремя повторами. Median HTTP latency **3.937 / 39.085 s**, RSS peak **7.642 GiB**, swap 0, native exit 0 / один SIGINT. Отдельный повтор completed; библиотечный пробел прежней серии сохраняется, полная LAB35 по-прежнему ждёт Ryzen и LAB08/LAB09.
- [LAB35: Apple qualification и подготовка общей пары](../measurements/LAB35-apple-http-preregistered-20261009/report.md): исходный Metal и отдельная tensor/tile16 сборка прошли **16/16** общих chat/load случаев с warmup + тремя repeats, context 8192 / concurrency 1. Median chat **3,771 / 4,803 s**, load **34,316 / 40,031 s**, completion usage соответственно 242 / 2048 одинаков в обеих ветвях. RSS peak около **7,640 GiB**, swap 0, штатный cleanup. Порядок standard→tensor и отсутствие thermal measurements не позволяют приписать разницу одному tensor API. Review correction: tensor startup проверил только executables; 21 dylib pins добавлены после серии, execution-time library identity остаётся unverified. Все HTTP результаты сохранены, полная tensor qualification именно той серии не подтверждена. **LAB35 blocked:** нет свежей чередованной Ryzen HTTP-серии, SSH/endpoint не предоставлен; agent LAB08/LAB09 pending. Две подготовки с driver path/schema errors сохранены до HTTP. Основная будущая пара — unmodified Metal против HIP b8407, source patch tensor рассматривается отдельно.
- [LAB34: завершённая длительная серия](../measurements/LAB34-apple-sustained-resume-20261009/report.md): direct llama.cpp b8407+tile16 / Metal / Qwen3.5-9B Q6_K / context 8192, один server slot. После свежего прогрева c1 выполнил **35,51 минуты, 48/48 без ошибок**, whole-interval throughput **46,135 completion tokens/s**. Peak native RSS **7,584 GiB**, swap **0**, normal pressure, AC/mode 0; native exit 0, один SIGINT. Девять успешных коротких клеток c1/c2/c4 проверены по primary copies двух предыдущих сессий; новый long использует отдельный процесс. Это допуск клиентской очереди к одному GPU-слоту, без проверки 2/4 одновременных GPU-слотов или максимального GPU budget.
- [LAB34: короткая матрица и предыдущий failed long](../measurements/LAB34-apple-load-power-retry-20261009/report.md): пять новых блоков 12/12 вместе с четырьмя успешными блоками 08.10 дают три повтора для c1/c2/c4. Median throughput отличаются менее чем на 2%, очередь увеличивает latency. Первые 337 секунд long завершились 8 successes/4 errors и SIGKILL неизвестного происхождения; исходный register/evidence сохранён, отчёт остаётся blocked.
- [Первое продолжение LAB34](../measurements/LAB34-apple-load-resume-20261009/report.md) остаётся blocked: r2-c4 retry 11/12 после перехода AC→Battery, один timeout; owned native завершился с одним SIGINT / exit 0. [Первая полная кампания](../measurements/LAB34-apple-load-complete-20261008/report.md) также остаётся blocked после SIGKILL неизвестного происхождения. Исторические copies и ошибки не считаются повторно.
- [Первый нагрузочный опыт](../measurements/LAB34-apple-direct-load-20261008/report.md): memory guard остановил c1 после 1/12; второй SIGINT вызвал teardown assertion. Cleanup исправлен; последующие штатные и guarded завершения с одним SIGINT сохранены отдельно.
- [LAB33: диагностика service lifecycle](../measurements/LAB33-apple-lifecycle-20261008/report.md): MLX прошёл 16/16 chat/tool cases и recovery при сохранённом app PID; native cancellation остаётся unverified. GGUF retry остановлен free-only guard до chat.

Для завершения начатой LAB35 нужен доступ к Ryzen и новая парная регистрация с чередованием стендов. Агентная часть требует реализации/приёмки LAB08 и LAB09. Семь ошибок трёх предыдущих учитываемых LAB34-сессий сохраняются; zero-error нового long их не отменяет. GPU budget остаётся null, профили conditional; пользовательские настройки памяти не менялись.

## Первые результаты — 07–08.10.2026

- [LAB01: воспроизводимая подготовка](../measurements/LAB01-apple-prerequisite-20261007/report.md): prepared T002 и 30 synthetic tests; агентская модель не запускалась.
- [LAB28: паспорт M5 Max](../measurements/LAB28-apple-first-20261007/report.md): 18 CPU / 40 GPU, 128 GiB, macOS26.5/arm64, Metal unified memory; два снимка памяти без swap.
- [LAB29: GGUF и MLX](../measurements/LAB29-apple-qwen35-9b-20261007/report.md): Qwen3.5-9B Q6_K и MLX4-bit, 19 pinned files с повторной SHA-256 проверкой. Weights находятся вне Git; source commit конверсии MLX неизвестен.
- [LAB30: Metal microbench](../measurements/LAB30-apple-qwen35-9b-metal-20261007/report.md): тот же GGUF и llama.cpp source commit `312cf03328496df9c56fe843952cf02a8964c59a` (b8407), что Ryzen; Release arm64/Clang21, threads8, batch512/ubatch256, KV f16/f16, FA1, offload33/33. Медиана трёх подтверждённых AC/powermode0 повторов: **PP2048 872.62 tokens/s**, **TG128@depth4096 63.86 tokens/s**, max RSS **7.432 GiB**, swap0.
- [LAB30: активация tensor API](../measurements/LAB30-apple-tensor-api-20261007/report.md): probe b8407 ложно отключал API из-за недопустимого блока8×8. В отдельной копии того же commit две замены на16×16 активировали f16/bfloat и реальные tensor matmul kernels; 14/14 выборочных CPU-reference tests (f16, q6_K и bf16) прошли. Полный Xcode и принудительный `GGML_METAL_TENSOR_ENABLE` не потребовались. В одной patched binary, три повтора каждого режима: tensor/control **PP2048 1305.38/751.06 tokens/s (1.738×)**, **TG128@4096 53.71/58.84**; RSS≤7.434GiB, swap growth0. Decode имеет большой разброс; устойчивый эффект на него не установлен. [Официальный фикс #21048](https://github.com/ggml-org/llama.cpp/pull/21048) делает те же две замены; воспроизводимый patch и команды находятся в отчёте. Новая upstream-сборка целиком не проверялась.
- [LAB31: MLX-LM](../measurements/LAB31-apple-qwen35-9b-mlx-20261007/report.md): native Python3.12.14/MLX0.32.3/MLX-LM0.32.0, языковая часть Qwen3.5-9B MLX4-bit @938d891…; все12 local files повторно проверены. GPU/M5 подтверждён в каждом процессе, thinking=false/temp0/seed1. Прогрев +три CLI повтора: prompt42/output105, медианы **PP405.439 / TG97.170 tokens/s**, allocator peak **4.904GiB**, CLI RSS≤**5.278GiB**, swap growth0. Local HTTP models/chat smoke200, effective EOS248046/im_end; сервер остановлен. Это иной artifact/quant/template и короткий chat, поэтому прямое сравнение скорости с synthetic LAB30 не выделяет эффект движка. Профили остальных моделей и максимальный memory budget не подтверждены; next step — LAB32.
- [LAB32: контекст и инструменты](../measurements/LAB32-apple-qwen35-9b-metal-auto-20261007/report.md), llama.cpp/Metal tensor API / Qwen3.5-9B Q6_K / reasoning=auto: полностью прошли **8K и 16K** — четыре chat/tool JSON/SSE случая, длинный вход, прогрев и три повтора; отмена/slot release/recovery и overflow400/recovery. Long inputs **4083/12287 tokens**, медианы long **18.108/29.205s**, tool round trip JSON **2.298/2.378s**, slot release после disconnect **2.279/9.238s**. Cache отключён, native exit0, swap0. На **32K** прошли короткие chat/tool серии, но long warmup (input28670) исчерпал output cap2048 на reasoning без final content: HTTP200/SSE DONE, finish_reason=length. Серия **blocked** по протоколу; long r1–r3 и cancel/overflow на32K не запускались, исходный cap не менялся. Допуск к LAB08/LAB34 ограничен проверенными 8K/16K; MLX protocol ещё не измерен. [Исходная thinking=false серия](../measurements/LAB32-apple-qwen35-9b-metal-20261007/report.md) отдельно остаётся blocked из-за отсутствующего tool call.
- [LAB32: отдельная диагностика reasoning budget32K](../measurements/LAB32-apple-qwen35-9b-reasoning-budget-20261008/report.md): те же input28670/outputcap2048 и pinned deployment, server budget−1, request `thinking_budget_tokens` отсутствует/128/512. Control4/4 — length/empty-final; **128:4/4 точный sentinel, output137**, median r1–r3 **31.648s**, все16 short chat/tool JSON/SSE тоже прошли. **512:4/4 final contract failed** — ограничитель завершил reasoning, но продолжение оказалось в content (output804), несмотря на sentinel в конце; short16/16 прошли. Logs подтверждают activated128/512 и forced end. Nativeexit0, maxRSS9.805GiB, swap0. Диагностика completed с8 сохранёнными failures; исходная LAB32 blocked и полный32K admission не изменены. Следующая регистрация — полный8K→16K→32K протокол с request budget128, включая cancel/overflow/recovery.
- [LAB32: проверка последовательного budget128 маршрута](../measurements/LAB32-apple-qwen35-9b-metal-budget128-20261008/report.md): 8K прошёл полностью; 16K short cases прошли, но long warmup вернул `LAB_SENTINEL_42.` с лишней точкой. Exact final contract не выполнен, серия **blocked**: 46 completed /1 failed /33 not-run. 32K в этой серии не запускался. Это отдельное условие от исходного unrestricted-auto, где 16K прошёл.
- [LAB32: самостоятельный допуск32K и recovery при budget128](../measurements/LAB32-apple-qwen35-9b-32k-recovery-20261008/report.md): на основании прежней32K диагностики проведена отдельная регистрация с повторной проверкой четырёх short cases и long input28670 (warmup+3), затем cancel/overflow/recovery в одном resident process. **28/28 попыток прошли**. Long median **29.639s**, tool round trip JSON/SSE **2.322/2.335s**. Cancel: curl exit28/DONE отсутствует, active/canceled taskID совпадает; слот освободился через **27.154s после client exit** в заранее зарегистрированном окне60s, recovery успешен без restart. Overflow input **57331** при hard32768 отклонёнHTTP400, recovery успешен. Nativeexit0, maxRSS **9.866GiB**, swap0. Это операционный допуск отдельного32K deployment при budget128; **полныймаршрутLAB32 не завершён** из-за сохранённого16K failure. Отмена не мгновенная; harness должен отдельно принять её задержку. Изменения контроллера и различие окна15/60s описаны в protocol/report.

В архивном Ryzen/Vulkan при совпавших параметрах PP2048 median857.88, TG128@4096 median29.40 tokens/s; отношение исходного Mac/Vulkan — 1.017×/2.172×. Это измеренное сравнение deployments с разными hardware/OS/compiler, не изолированный эффект backend и не агентское качество. Исходная Mac baseline работала на standard Metal SIMD после отказа tensor probe; новая диагностика выше установила причину и проверила исправление отдельно. Полный GPU allocation limit не установлен; HTTP8K/16K подтверждены для LAB32 fixtures, 32K long final contract не прошёл. Failed downloads, checker correction и pilot без power timeline сохранены вместе с подтверждающей серией.


## LAB33 и обычный запуск приложений — 08.10.2026

По запросу владельца установлены `/Applications/Ollama.app`0.40.1 и `/Applications/LM Studio.app`0.4.25+1; `ollama` и `lms` доступны через обычный PATH. Официальные архивы и code signatures проверены; версии/hashes сохранены в [отчёте LAB33](../measurements/LAB33-apple-serving-central-20261008/report.md). Запуск вне лаборатории:

```sh
open -a Ollama
open -a 'LM Studio'
ollama --version
lms --version
lms ls
```

[Исходный Battery preflight](../measurements/LAB33-apple-ollama-qwen35-9b-20261008/report.md) отдельно blocked до модели. Новая AC серия: Ollama16/16 и LMS/GGUF16/16 short chat/tool JSON/SSE, cancel/recovery; direct baseline16/16. Medians tool JSON1.319/3.301/2.261s соответственно — сравнение разных deployments. Actual Ollama Metal/M5/33of33offload подтверждён; у LMS actual package2.54.0 известен, device/offload доказательство неполно. LMS MLX1.13.1 загрузился, но первый HTTP chat оборвался при исчезновении GUI процесса; причина неизвестна, вся LAB33 остаётся blocked. Подробности, resource amendments и failures в отчёте; GPU budget/null и общие conditional профили не изменены.

## Команды планирования

```sh
npm run local:engines -- --hardware apple-m5-max-128gb-macos
npm run local:plan -- --hardware apple-m5-max-128gb-macos
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine all --format json
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine llama-cpp-metal --context 8192
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine mlx-lm-metal
```

Без `--hardware` обе команды сохраняют Ryzen/Linux независимо от ОС, на которой запущены. `--engine all` относится только к выбранному стенду. Неизвестные hardware/engine — ошибка. Команды не устанавливают движки и не запускают модели.

У Apple `gpu_budget_gib=null`: `hardware-memory-required` означает, что конечный бюджет и headroom неизвестны. Плановые размеры весов/runtime/KV остаются видимыми. После LAB28 и smoke передайте измеренные числа через `--memory-gib` и `--gpu-budget-gib`; они не записываются в профиль и не меняют ОС. Даже числовая оценка сохраняет `fit_verified=false`.

Приоритет статусов: MLX требует своего артефакта (`artifact-required`); GGUF wrapper без калибровки runtime — `engine-memory-required`; известный GGUF/runtime при неизвестной памяти GPU — `hardware-memory-required`; только затем рассчитывается `candidate`, `conditional` или `over-budget`. Без `--engine` используется прежняя грубая GGUF-модель резервов, не универсальная оценка движков.

Все пять профилей имеют `hardware_support=conditional`: общая поддержка Apple Silicon не доказывает сочетание M5 Max, macOS, модели и pinned runtime. Ollama-профиль относится к GGUF/Metal; другой внутренний runner или формат требует отдельного условия. Для MLX не переносятся hashes, quant и размеры GGUF.

## Общий протокол Apple-работ

Маршрут: LAB01 → [LAB28](../../../docs/labs/LAB28-apple-hardware.md) → LAB29 → LAB30/LAB31 → LAB32 → LAB33/LAB34 → LAB35. Нужны Node.js ≥22, Python 3, Git; для сборки — CMake и Xcode Command Line Tools, для MLX — совместимый native arm64 Python. Установку зависимостей исполнитель выполняет отдельно, фиксируя версии. Rosetta и контейнерный GPU-инференс не являются условиями этого маршрута.

Каждая сессия создаётся через `lab:new`, без перезаписи прежней. До исполнения заполните `raw/protocol.md`, `protocol_recorded_at`, `conditions` и `planned_attempts` в manifest v2 по [формату отчёта](../../../docs/labs/report-validation.md). Измерения имеют `kind=measurement`, `run_id=null`; запущенная модель требует `evidence_class=experimental`. Агентные попытки требуют настоящих `run.json`. Начатые failures и неисполненные условия сохраняются с причинами. В TSV неизвестное значение оставляют пустым с `unavailable_reason`; в JSON — `null`.

Для каждой конфигурации: отдельный прогрев и три измеряемых повтора, одинаковые входы/output cap, sampling/reasoning, template, KV/state, slots и cache policy. Холодный старт учитывается отдельно. Не объединяйте новые процессы CLI с прогретым HTTP server в одну метрику. До LAB34 — один model server и concurrency 1. Рост контекста/нагрузки допускается после просмотра предыдущего результата, без автоматического рестарта или cloud fallback.

До серии зафиксируйте допустимые latency/errors, резерв памяти и политику swap. Базовый резерв ОС — 16 GiB; при критическом memory pressure, устойчивом росте swap, OOM, потере readiness или неподтверждённом GPU исполнении остановите серию. Не уменьшайте защитные лимиты macOS и не меняйте power mode внутри сравнения. `recommendedMaxWorkingSetSize` — рекомендация, не свободный heap; `vm_stat` free pages не равны всей доступной RAM. RSS и Metal/MLX allocations могут описывать пересекающиеся страницы.

Во втором терминале собирайте временной ряд (тот же `LAB_DIR`, запустить до опыта, остановить Ctrl-C после):

```sh
while true; do
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  vm_stat
  sysctl vm.swapusage
  memory_pressure -Q
  sleep 5
done > "$LAB_DIR/raw/macos-memory-series.txt" 2>&1
```

Это наблюдение, не генератор pressure: не используйте режимы искусственной нагрузки `memory_pressure`. Периодический сбор может пропустить peak; сохраняйте также runtime peak memory и `/usr/bin/time -l`. Показатель maximum resident set size в macOS time — bytes. Недоступную температуру/энергию отмечайте неизвестной: снижение скорости само по себе не доказывает throttling. Вывод `pmset -g custom` описывает настройки, не измеренную мощность.

Храните журналы как `.txt`: `.log` в репозитории игнорируются. Большие weights, исходники движков, build и venv оставляйте за пределами evidence, не коммитьте их. Архивируйте их версии, команды и hashes. `raw/` и manifest содержат только необходимое доказательство без секретов и серийных номеров устройства.

## Сдача

```sh
npm run lab:check -- --report "$LAB_DIR" --mode submission
npm run check
```

`ready_for_review` означает комплектность, а не правильность вывода. `blocked` с evidence — допустимая сдача, но не успешный аппаратный допуск. Provider bridge остаётся инженерной [LAB08](../../../docs/labs/LAB08-local-bridge.md); `run --provider local` пока не поддерживается.

- [LAB33: центральный LM Studio, Metal call path](../measurements/LAB33-apple-sdk-stable-window-20261010/report.md): GGUF SDK chat и четыре sampled load cases прошли; фактический Metal call path наблюдался во всех четырёх ответах, app PID сохранён. Полное число offloaded layers не измерено.
- [LAB33: явная MLX SDK отмена](../measurements/LAB33-apple-sdk-framing-20261010/report.md): три отмены с primary userStopped и три recovery прошли; следующий repeat остановил resource guard free+spec7.699<8GiB и выгрузил свой alias. HTTP disconnect не запускался. Raw SDK final имеет две LF перед LAB_READY; это отдельное API-framing условие, без trim. Physical GPU release unknown; LAB33 остаётся blocked.

- LAB34, 10.10.2026: новая проверка **фактических серверных слотов 1/2/4**, по 8192 токенам на слот, output cap 512. [Первая попытка](../measurements/LAB34-apple-server-slots-20261010/report.md) отказала до Popen: free+spec после hashing 22,199 GiB <24. [Повтор со стабильным окном](../measurements/LAB34-apple-slot-window-20261010/report.md) подтвердил slot1/context8192/M5/tensor/offload33/33 и получил HTTP200/512 completion tokens, но reasoning-only final был пустым: прогрев не прошёл критерий ответа. [Новая конфигурация thinking=false](../measurements/LAB34-apple-slots-final-text-20261010/report.md) не получила 120 с непрерывно ≥24 GiB в течение 600 с и не загрузила модель. Slots2/4 и новая 30-минутная серия **not-run**; пороги не ослаблялись, чужие приложения не закрывались. Это дополнение к прежней очереди клиентов на одном слоте, не подтверждение настоящей параллельной серии.
