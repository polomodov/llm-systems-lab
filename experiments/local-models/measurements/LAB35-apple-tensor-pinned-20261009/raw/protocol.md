# LAB35: повтор tensor-серии с полными хешами библиотек

## Гипотеза и область

Свежий процесс llama.cpp / Metal tensor / tile16 на M5 Max завершит общие chat/load запросы после проверки всех библиотек сборки до запуска. Для каждого входа выполняются отдельный прогрев и три повтора. Это новый опыт по замечанию PR26. У прежней серии сохраняется `libraries_verified_at_execution=false`; новые данные не подтверждают её задним числом. Сравнение с Ryzen и агентные попытки в этот повтор не входят.

## Закреплённые условия

Qwen3.5-9B Q6_K GGUF, revision `3885219b6810b007914f3a7950a8d1b469d598a5`, 7 458 301 152 bytes, SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`. Llama.cpp base commit `312cf03328496df9c56fe843952cf02a8964c59a` / b8407 и patch tile16 SHA-256 `561c77562a5caad4772bfc0fcf078f9b1c354296e310300c7b460e635f368863`. Reference содержит 23 пути: llama-server/bench и 21 dylib, включая файлы версий и linker aliases семи семейств. Протокол, программы, source registry и references закрепляются в Git до запуска модели.

Проверка требует canonical libggml/base/cpu/metal/blas/libllama/libmtmd, хеши всех `*.dylib` в build/bin и совпадение каждого SHA-256. Отсутствующая, изменённая или новая незакреплённая библиотека запрещает Popen. Системные frameworks учитываются версией macOS 26.5 / 25F71 и SDK из build provenance; OS shared cache не копируется. После source audit и непосредственно перед Popen повторно проверяются модель, executables и библиотеки. Хеши и время проверки сохраняются в `startup-process.json`; отдельно фиксируется время вызова Popen.

Context 8192, server slot 1, threads 8, batch 512 / ubatch 256, KV f16/f16, flash attention on, Jinja / no-context-shift, reasoning auto / enable_thinking=true, no-cache-prompt, loopback port 18080 / alias lab-model. Оба JSON-входа побайтно совпадают с исходными LAB35 core requests: temperature 0 / seed 1 / top_p 1 / max_tokens 2048, non-streaming, без tools и request extensions.

## Порядок и критерии

13 admission samples за ≥120 секунд → регистрация в Git → pin audit → новый startup → chat warmup/r1/r2/r3 → load warmup/r1/r2/r3 → shutdown. Каждый прогрев и повтор — один HTTP-запрос при concurrency 1. Startup и прогревы исключаются из медианы трёх повторов. Chat требует `content.strip() == LAB_READY`; load — непустого assistant content, полного usage и отсутствия tool calls. Finish stop/length допустим; качество ответа на запрос о 300 словах не оценивается. Новый native log должен подтвердить M5 Max, offload 33/33 и tensor capability; это не доказательство исполнения каждого оператора через tensor kernel.

HTTP deadline 300 s, p95 успешных ответов ≤240 s. Resource guard каждые 2 s: free+speculative ≥8 GiB, pressure level 1, pressure free ≥50%, swap 0, AC / mode 0, native RSS ≤24 GiB, все collector commands exit 0. LM Studio/Ollama не должны иметь загруженных моделей до запуска и при проверках примерно каждые 20 s. Чужие процессы не останавливаются. При ошибке последующие шаги становятся not-run; завершаются только собственные client/server. Cleanup посылает один SIGINT под блокировкой; deadline 30 s, затем SIGKILL fallback. Caffeinate -i действует только на время controller process. Настройки питания, caches и kernel limits не меняются; веса не скачиваются.

## Доказательства и вывод

Сохраняются протокол/source hashes/commit, pin audit и 23 хеша в startup record, command/runtime/props/slots/native log, точные bodies/records/responses/usage/contracts, timeline памяти, cleanup, TSV/summary и SHA inventory. Отдельный offline exporter проверяет первичные данные. При неполном usage, memory или library proof статус completed не присваивается. TTFT, энергия, температура и maximum GPU budget неизвестны с причинами; RSS не равен Metal heap.

Критерий этого повтора: все 11 попыток completed, восемь HTTP-ответов соответствуют контрактам, execution-time pins полны и проверены до Popen, ресурсные и latency границы соблюдены, native exit 0 / один SIGINT. Полный LAB35 по-прежнему требует свежей чередованной Ryzen-пары и LAB08/LAB09. Agent harness не запускается; `run_ids=[]`.
