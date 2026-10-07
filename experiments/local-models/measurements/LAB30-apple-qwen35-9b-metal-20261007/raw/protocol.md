# Предварительный протокол LAB30

Гипотеза: GGUF Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5 с проверенным SHA91898433... успешно работает с full GPU offload в native arm64 llama.cpp Metal; наблюдаем скорость и память, без предсказания направления отличия от Ryzen.
Engine: llama.cpp b8407, commit312cf03328496df9c56fe843952cf02a8964c59a, как Ryzen LAB04. Source clone/fetch только этого commit, чистый checkout. CMake4.4.4 из отдельного временного venv, Xcode CLT Clang21/SDK26.5. Build Release, CMAKE_OSX_ARCHITECTURES=arm64, GGML_METAL=ON, LLAMA_CURL=OFF, targets llama-bench llama-server, -j8. Sources/build вне Git/evidence; install/build не изменяют OS power/memory limits.
Выбранная модель и backend отличаются только от других заранее зарегистрированных условий. Defaults pinned help дополнят runtime manifest до smoke.
Smoke: -m LOCAL_GGUF -ngl999 -t8 -b512 -ub256 -ctk f16 -ctv f16 -fa1 -p512 -n64 -r1 -ojson. Проверить Metal GPU/offload по JSON и verbose backend logs.
После smoke: отдельный прогрев PP2048 (-p2048 -n0) и TG128@4096 (-p0 -n128 -d4096). Измеряемые повторы по три каждого, последовательно PP1/TG1/PP2/TG2/PP3/TG3, осмотр каждой серии до следующей. Все остальные flags одинаковы. Эти размеры отличаются от примера LAB30, чтобы совпасть с Ryzen workload. PP/TG benchmark kernels не равны wall time процесса; CLI новый процесс, файловый cache/внутренний warmup записать.
Память: snapshot before/after каждой команды, sampled timeline каждые2s во время модели, macOS /usr/bin/time -l RSS. Сохраняем swapusage, free pages, memory_pressure -Q; не складываем RSS+Metal allocations как независимую RAM. Питание AC/powermode0 сохраняем.
Stop: ошибки/unsupported flags, отсутствие подтверждения GPU, process timeout600s, swap growth или free pages ниже16GiB => не допускаем следующий этап; own benchmark можно остановить при превышении. Initial total envelope24GiB — политика; GPU allocation limit всё ещё неизвестен. Никакого hidden check, agent-run, provider/API, tuning wired limits, изменения питания или облачного fallback.
Изменения pin/flags после ошибок — отдельный зарегистрированный variant. Результаты не объявляем pure backend effect: hardware/OS/compiler отличаются от Ryzen.

Зарегистрирован: 2026-10-07T16:49:55.366Z
