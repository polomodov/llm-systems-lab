# Диагностика tensor API — протокол до исполнения

Гипотеза: в b8407 tensor probe падает из-за неявной Metal languageVersion; явный Metal 4.0 позволяет скомпилировать те же f16/bfloat ядра на M5 Max/macOS26.5 без полного Xcode. Проверяется локально, не по общему заявлению о поддержке.

Сначала точные probe kernels b8407: default, explicit 3.2, explicit 4.0; библиотека и pipeline, полный NSError, без model inference. Затем отдельная копия того же source commit312cf03328496df9c56fe843952cf02a8964c59a, diagnostic-only patch и language4 patch. Не форсировать has_tensor и не отключать проверки. Исходная baseline остаётся неизменной. Источники/build вне Git, patch и hashes в evidence.

Успех активации: f16/bfloat probes проходят, has_tensor=true и smoke full offload33/33 с exit0; отдельно проверить выбор tensor matmul kernel, а не только feature flag. После smoke — один прогрев и три повтора PP2048 и TG128@depth4096. Та же Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5 SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59, threads8/batch512/ubatch256/FA1/KVf16. Новые CLI процессы, внутренний llama-bench warmup, cold start не считается PP/TG.

Admission: AC/powermode0, free pages>=16GiB, no swap growth, timeout600s; OS reserve16GiB, total RSS ceiling24GiB. Остановить при OOM/ошибке GPU/nativeexit, росте swap, потере AC/power condition или неподтверждённом tensor/offload. Не менять системные лимиты и developer selection. При неудаче сохранить failed/not-run с причиной. Агентные задачи не запускаются. Доказательство активации не является доказательством качества модели или корректности каждого tensor operator.

Метрика: median/min/max по трём отдельным сырым PP/TG наблюдениям, RSS процесса и swap. Baseline ранее зарегистрированной AC серии приводится исторически, без утверждения о чистом причинном ускорении; при необходимости отдельная контрольная серия tensor disable в том же patched binary регистрируется до запуска.
