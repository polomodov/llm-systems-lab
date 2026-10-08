# LAB30 — llama.cpp Metal / Qwen3.5-9B

Сессия: apple-qwen35-9b-metal-20261007. Минимум выполнен; независимое решение проверяющего ещё не выставлено.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Дата / оператор | 07.10.2026, Codex по запросу владельца |
| Машина | Apple M5 Max 18 CPU / 40 GPU, 128 GiB, macOS 26.5 / 25F71, arm64 |
| Source pin | llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a, release reference b8407 |
| Версия бинарника | build_number=1, commit312cf03 из shallow checkout; полный source commit совпадает с Ryzen b8407 |
| Toolchain | CMake4.4.4, AppleClang21.0.0, SDK26.5, Release arm64 |
| Build | GGML_METAL=ON, LLAMA_CURL=OFF, -j8; llama-bench и llama-server |
| GGUF | unsloth/Qwen3.5-9B-GGUF @3885219b6810b007914f3a7950a8d1b469d598a5, Q6_K |
| SHA-256 весов | 91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59 |
| Предыдущие сессии | LAB28-apple-first-20261007; LAB29-apple-qwen35-9b-20261007; Ryzen LAB04-qwen35-9b-prebuilt |
| Agent/harness/API | Не применяются: это backend microbench |

## Гипотеза и протокол до запуска

Гипотеза raw/protocol.md: закреплённый GGUF работает с full GPU layer offload в Metal, без выхода за зарегистрированные memory bounds. Направление разницы с Ryzen заранее не задано. Выбраны PP2048 и TG128 с n_depth4096, одинаковые threads8, batch512/ubatch256, KV f16/f16, FA1 и n_gpu_layers999.

Эти размеры отличаются от примера LAB30 PP512/TG128, чтобы совпасть с имеющимися Ryzen workloads; обязательные PP/decode и три повтора сохраняются. Перед моделями зарегистрировано raw/runtime-observations-before-smoke.md: verbose -v одинаков для всех случаев, tensor API compile probe этой среды не поддержан, standard Metal SIMD работает, shallow checkout меняет только reported build count.

После первичной серии обнаружена неполнота power observability: во время неё питание не логировалось. До дополнительных замеров зарегистрирован raw/power-control-amendment.md. Pilot сохранён отдельно; основной вывод заранее назначен подтверждающей серии с observed AC/powermode0 каждые2s. Выбор по completeness conditions, не по лучшей скорости.

## Ход выполнения

1. Созданы новая сессия и протокол; установлена CMake4.4.4 в отдельный временный venv. Точный commit получен Git fetch --depth1; checkout чистый. Source/build размещены вне Git/evidence.
2. Собраны native arm64 llama-bench/server; configure/build exit0, версии/hashes/dylib зависимости и CMakeCache сохранены. OpenSSL не найден, CURL выключен: HTTPS-клиент отключён, локальный HTTP server target построен. Source tree не исправлялся ради сборки.
3. Smoke PP512/TG64: native exit0, offload33/33, JSON backends=MTL,BLAS, GPU Apple M5 Max, FAtrue. Первый derived checker искал literal Metal и вернул driver exit1. Он исправлен для фактического backend ID MTL; исходный native JSON/log и первоначальный checker result сохранены, модельный результат не подменялся и smoke не повторялся из-за этого.
4. Выполнены отдельные warmup PP2048/TG128@4096, затем три pilot PP/TG пары. Новые CLI процессы, use_mmap=true, внутренний benchmark warmup и файловый cache входят в методику.
5. Дополнительно выполнены три подтверждающие PP/TG пары под power control. Все native exit0; полная GPU offload и workload/FA подтверждены; зарегистрированные пороги free pages≥16GiB/без роста swap/timeout600s не нарушались.
6. vm_stat/swapusage/memory_pressure -Q и power snapshots снимались каждые2s. Process time/RSS — macOS time -l. Сохранены сырые метрики и `results-summary.json`, `buffer-allocation-summary.json`, `ryzen-comparison.json`.

## Результаты

Основная серия с подтверждённым AC/powermode0:

| Тип / повтор | tokens/s | Process wall s | Max RSS GiB | Swap bytes |
| --- | --- | --- | --- | --- |
| PP / 1 | 872.622 | 5.67 | 7.183 | 0 |
| TG / 1 | 63.764 | 7.68 | 7.432 | 0 |
| PP / 2 | 872.171 | 5.66 | 7.183 | 0 |
| TG / 2 | 64.244 | 7.71 | 7.432 | 0 |
| PP / 3 | 873.365 | 5.68 | 7.183 | 0 |
| TG / 3 | 63.861 | 7.70 | 7.432 | 0 |


- PP2048 median **872.622 tokens/s**, min/max 872.171/873.365.
- TG128@4096 median **63.861 tokens/s**, min/max 63.764/64.244.
- Peak observed process max RSS **7.432 GiB**; swap used0 на всех snapshots. Двухсекундный sampler может пропустить краткий peak свободных страниц, а RSS максимум фиксируется time -l.
- Pilot medians: PP872.016, TG63.939 tokens/s. Pilot не используется для основного вывода о подтверждённых power conditions.

Для TG workload depth4096 + output128, runtime выделил n_ctx4352 с padding; это не испытание полного 8K/16K/32K HTTP context. PP runtime context2048. `measurements.tsv` содержит actual allocated context из лога.

Mapped model buffers: MTL0_Mapped7102.33MiB и CPU_Mapped795.70MiB; для TG — MTL KV136MiB, RS50.25MiB, compute250.50MiB, CPU compute12.26MiB. Размеры — объявленные runtime буферы с округлением, не независимые физические банки. Их нельзя складывать с RSS: mapped/UMA страницы могут пересекаться. Возможны CPU вспомогательные операции при offload33/33 layers.

PP/TG относятся к timed kernels benchmark. Process wall включает загрузку, Metal pipeline preparation, depth priming и warmup. Controller observed wall дополнительно включает sampling/wait и не заменяет native process wall. `stddev_ts=0` внутри одного native repetition не означает доказанную детерминированность — разброс считается по трём отдельным повторам.

Предварительное сопоставление с архивом Ryzen на том же GGUF/source commit и совпавших workload/KV/FA/batch/threads:

| Deployment | PP2048 median tokens/s | TG128@4096 median tokens/s |
| --- | --- | --- |
| M5 Max / Metal | 872.622 | 63.861 |
| Ryzen / Vulkan | 857.879 | 29.396 |
| Ryzen / HIP | 765.937 | 26.766 |

Отношение M5/Vulkan: PP1.017×, TG2.172×. Это сравнение deployments: hardware/OS/compiler, source-build против prebuilts и доступные kernel paths отличаются. Исторический Ryzen не измерялся одновременно с Mac. Агентное качество/энергия из этого не выводятся.

## Ошибки и ограничения

- Tensor API f16 compilation probe b8407 не поддержана средой; has_tensor=false. Используется standard Metal SIMD; это не утверждение об отсутствии tensor hardware у M5.
- Начальный checker ошибочно не распознал MTL. Сохранены raw/smoke-execution-initial-checker.json и checker-correction.json, native exit0 и неизменные raw benchmark данные.
- Shallow source reports build_number1 вместо8407, но полный source SHA совпадает; это явно сохранено в runtime manifest.
- Pilot power timeline отсутствует; primary серия исправляет наблюдаемость, не переписывает pilot.
- GPU allocation limit, длительная устойчивость, температура/энергия, длинный HTTP контекст и tools не проверены. gpu_budget_gib=null; безопасный максимум памяти из одной успешной нагрузки не выводится.

## Вывод по гипотезе

Гипотеза подтверждена для заданного GGUF и нагрузки: native Metal full layer offload33/33, FA1, успешные PP/decode повторы и swap0 при observed AC/powermode0. Получена воспроизводимая baseline PP872.62/TG63.86 tokens/s. LAB31 может исследовать отдельный MLX deployment; LAB32 должна отдельно проверить context/tools/stop semantics. Универсальный fit для всех контекстов не заявлен.

## Ответы на контрольные вопросы

1. Сборка включает backend, но GPU execution доказывают observed device, offloaded layers, runtime buffers и JSON/logs конкретного запроса.
2. PP и TG измеряют разные kernel workloads; wall time процесса включает также загрузку/инициализацию/прогрев и depth priming.
3. Один source commit исключает изменение алгоритмов движка как дополнительный фактор сравнения; OS/compiler/hardware всё равно различаются.
4. Shared memory приводит к пересечению mapped CPU/GPU страниц; RSS, buffer sizes и working-set recommendation нельзя суммировать или считать свободной памятью.

## Комплект сдачи

- [x] Source/toolchain pins, binary/library hashes, build/help/version evidence сохранены.
- [x] Smoke, отдельные прогревы и три primary повтора PP/TG выполнены.
- [x] Pilot/primary, checker correction и power amendment сохранены прозрачно.
- [x] Условия GPU/offload, время, RSS, memory/power timeline, TSV и manifests заполнены.
- [x] Сравнение использует копии исходных Ryzen JSON и сохраняет ограничения.

Комплектность проверяется lab:check --mode submission; reviewer_decision=null. Agent run/скрытый verdict здесь не создаётся.
