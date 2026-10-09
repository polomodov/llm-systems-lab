# LAB34: отдельное продолжение длительной серии

## Гипотеза и история

После нового явного запроса «Продолжи лабу» свежий resident deployment завершит ≥1800 секунд c1 без ошибок, с p95≤240 секунд и соблюдением границ памяти/питания. Ни одна предыдущая failed попытка не заменяется. Предыдущие три учитываемые сессии: 150 начатых запросов / 7 ошибок. Старый sustained 337.251 секунды / 8 successes / 4 errors не складывается с новым.

Короткая матрица уже имеет по три successful блока c1/c2/c4: четыре клетки 08.10 и пять новых 09.10. Primary copies закреплены hashes и источниками PID в prior-short-reference.json. Их offline audit не является новым инференсом. Новая длительная серия выполняется в третьем по отношению к успешной матрице resident процессе, после свежего прогрева; отличие restart явно учитывается.

## Протокол

До GPU-старта 13 admission samples за ≥120 секунд требуют AC/mode 0 и прежних memory boundaries. Затем short-evidence-audit → свежий startup → warmup 2 requests → выбор c1 по median requests/s девяти успешных клеток → sustained ≥1800 секунд → shutdown. Правило выбора: минимальная concurrency в пределах 95% максимальной median среди c1/c2/c4. Оно даёт c1; результат пересчитывается offline до запуска и фиксируется перед long. Новых коротких повторов нет: они уже завершены, а fresh warmup проверяет текущий deployment.

Неизменны pinned GGUF Qwen3.5-9B Q6_K revision 3885219b6810b007914f3a7950a8d1b469d598a5 / SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59; patched llama.cpp b8407/312cf03328496df9c56fe843952cf02a8964c59a+tile16 / server SHA916660e9bfe7f4d2fda420136f6bd192688def8cbd6581f23d08b06ead2e571f. Model/binary hashes заново проверяются. Native log новой сессии подтверждает M5/Metal, offload 33/33, tensor capability.

Context8192, один GPU-слот, threads8, batch512/ubatch256, KV f16/f16, FA on, Jinja, no-context-shift, reasoning auto, enable_thinking=true, no-cache-prompt, port18080. Тело load-request.json неизменно: max_tokens2048, temperature0, seed1, top_p1, non-streaming, no tools. Latency включает очередь; throughput whole interval = successful completion tokens / whole wall.

## Границы и остановка

HTTP deadline300s, p95 успешных ответов≤240s, zero errors в допускаемой серии. Guard каждые2s: free+speculative≥8GiB, pressurelevel1, pressurefree≥50%, swap0, AC/mode0, nativeRSS≤24GiB, all collector commands exit0. Foreign models LM Studio/Ollama проверяются перед стартом и примерно каждые20s; при их появлении останавливается только owned server. ОС/питание/cache/kernel limits и чужие приложения не меняются. Резерв ОС16GiB в каталоге не меняется.

Sustained — последовательные блоки по12 запросов до whole wall≥1800; последний блок заканчивается целиком, поэтому actual может превысить30минут. Паузы клиента входят в wall; непрерывная максимальная GPU occupancy не утверждается. Любая ошибка останавливает remaining attempts, failed primary blocks включаются в series register даже при native exit до возврата Campaign.block. Cleanup locked: один SIGINT, затем bounded exit deadline30s и SIGKILL fallback с причиной. При явном KeyboardInterrupt owned HTTP client завершается отдельно, чтобы не оставлять orphan. Caffeinate-i только во время жизни controller.

## Доказательства

Все individual requests/responses, usage/finish reason/latency, headers/config/summary, native log/runtime/props/slots, macOS timeline и cleanup сохраняются. Неизвестны TTFT, энергия, температура, максимальный GPU budget; сокращение скорости само по себе не доказывает throttling. Finish length не доказывает качество текста. Новая completed не стирает исторические failed campaigns. Агентный harness отсутствует, run_ids=[].
