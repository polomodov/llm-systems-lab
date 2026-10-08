# LAB34 — нагрузка direct Metal на M5 Max

Статус **blocked**: первый короткий блок остановлен по зарегистрированному резерву памяти. Concurrency 2/4 и 30-минутная серия не запускались.

## Паспорт выполнения

08.10.2026, Codex по запросу владельца. Apple M5 Max (18 CPU / 40 GPU), 128 GiB, macOS 26.5 / 25F71, native arm64. Питание AC, powermode=0; фоновые пользовательские приложения продолжали работать. Модель Qwen3.5-9B Q6_K, revision 3885219b6810b007914f3a7950a8d1b469d598a5, SHA256 91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. llama.cpp b8407 / 312cf033… + tensor tile16 patch из LAB30; бинарники и веса проверены перед запуском.

Контекст 8192, фиксированный один серверный слот, threads8, batch512/ubatch256, KV f16/f16, FA on, Jinja, no-context-shift, reasoning auto / enable_thinking=true, prefix cache off. Сервер только 127.0.0.1:18080; занятый чужим процессом порт8080 не затронут. Startup log подтверждает Metal / Apple M5 Max, offload33/33 и tensor capability=true. Output cap2048, temperature0, seed1, top_p1. Реальных агентных попыток нет, run_ids=[].

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), hash, register, [source hashes](raw/registered-source-hashes.json) и commit6061084 сохранены до запуска. После warmup из двух запросов запланированы три блока по12 для каждой concurrency1/2/4 с чередованием порядка. Слоты не меняются: это проверка очереди при одном GPU slot, не обещание одновременного GPU исполнения.

Гипотеза: c2/c4 увеличит median throughput минимум на10% относительноc1, сохраняя error0 и p95<=60s. HTTP timeout120s. После успешной полной короткой матрицы — lowest concurrency within95% of maximum median throughput, затем1800s блоками по12. Выбор должен быть записан до длинной серии.

Новый cache-aware guard: free+speculative>=16GiB, pressure free>=50%, swap0, AC/powermode0, native RSS<=24GiB, timeline каждые2s. Это не free-only условие прежнихGGUF-серий. Foreign models проверяются перед start и примерно каждые20s. ОС/power/cache настройки не меняются, чужие процессы не останавливаются. Процессный caffeinate-i предотвращает idle sleep только на время опыта и убран после него.

## Ход выполнения

Стандартный concurrency driver и10 его offline tests сохранены. Вход — учебный русский текст примерно300слов из общего fixture; max_tokens увеличен с512 до2048 до всей серии, чтобы учитывать reasoning и final. Driver требует непустой assistant content без tools и finish stop/length; смысл текста и число слов не оцениваются. Время включает reasoning и очередь.

Startup и warmup прошли. В r1-c1 первый запрос успешен, затем memory monitor измерил free+speculative ниже16GiB и послал SIGINT только собственному server PID35841. Driver сохранил все12 ответов/ошибок, после чего кампания stopped; remaining9attempts not-run. [Ошибка](raw/campaign-error.json), [timeline](raw/memory-timeline.jsonl), [server log](raw/server.txt) и [cleanup](raw/shutdown-execution.json) сохранены.

В cleanup обнаружена собственная ошибка контроллера: второй SIGINT отправлен ещё завершающемуся серверу. После него native log содержит Received second interrupt и GGML_ASSERT([rsets->data count] == 0), exit -6. Исходный [controller-at-start](raw/run_load-at-start.py) сохранён; исправление предотвращает второй SIGINT и записывает историю остановки. [Erratum](raw/shutdown-controller-erratum.md). Два synthetic regression tests прошли, но новая модельная серия после исправления не выполнялась. Это не доказательство самопроизвольного падения Metal или OOM.

## Результаты

| Блок | Успешно / всего | Median / p95 / max успешных, s | Successful requests/s | Successful completion tokens/s |
| --- | ---: | --- | ---: | ---: |
| Warmup, c1 | 2/2 | 33.943 / 35.025 / 35.025 | 0.029458 | 60.330 |
| r1, c1, interrupted | 1/12 | 38.681 / 38.681 / 38.681 | 0.006302 | 12.906 |

Последний блок включает11 failures после resource stop; его successful-throughput делит токены единственного успешного ответа на полный wall158.692s, включая ожидание/ошибки. Это не штатная decode speed. Все три успешных ответа имели finish=length и2048 completion tokens: partial text допустим нагрузочным контрактом, но не доказывает завершённую смысловую задачу. Warmup не включён в сравнительную статистику.

| Ресурс | Наблюдение |
| --- | --- |
| Memory samples | 62 |
| Min free+speculative | 15.975204 GiB, ниже16GiB примерно на25.39MiB |
| Min pressure free percentage | 87% |
| Max sampled native RSS | 7.583 GiB |
| Max swap used | 0 bytes |
| Native shutdown | -6 после второго SIGINT |
| Sustained1800s | not-run; actual duration=null |

Всего13attempts:2completed/2failed/9not-run;85TSVobservations. Все первичные14request responses/metrics сохранены, включая failures. Linux/proc fields=null с причиной; macOS timeline измерен отдельно. TTFT, decode-only speed, energy, temperature и максимальныйGPUbudget неизвестны. [Summary](raw/summary.json).

## Ошибки и ограничения

Guard сработал из-за конкретного floor, при swap0 и pressure>=87%; это не измерение исчерпания128GiB или неспособности модели поместиться. Free/speculative pages не равны всем reclaimable pages. Изменение порога ради успешного повтора в этой серии не производилось. Фоновые процессы и file cache не изолированы; нельзя приписывать изменение свободных страниц только модели.

Частичный c1 блок не позволяет оценить parallelism, p95 устойчивого deployment, throughput gain или30min stability. Second SIGINT assertion — отдельный cleanup defect; первичные результаты не переписаны после исправления. Fixed slot1 измерял бы очередь сервера, а для GPUparallelism требуется новая серия с иным зарегистрированным server slot count. No thermal throttling claim.

## Вывод по гипотезе

Гипотеза о concurrency gain не проверена: resource admission прекратил опыт до сравнительной матрицы. Для повторения нужны подходящие условия памяти и новый register; исправленный cleanup тоже требует модельной проверки. Текущий результат не допускает sustained series или полного перехода к LAB35. Известные ограничения сохранены, а не заменены фиктивным pass.

## Ответы на контрольные вопросы

1. Client concurrency — число одновременных HTTP-клиентов; один серверный слот сохраняет GPU serialization и очередь.
2. p95 на12наблюдениях близок к максимуму; на одном успешном запросе прерванного блока он не оценивает стабильный tail.
3. Общий throughput требует суммы tokens и полного wall interval, включая паузы/ошибки; среднееblock rates может искажать результат.
4. Для throttling нужны измеренные thermal/power данные; latency и memory floor сами по себе этого не доказывают.

## Комплект сдачи

Manifestv2/register, protocol/hash/source snapshots, deployment/props/slots, native log, macOS pre/during/post memory, обе driver directories со всеми individual responses/metrics,85TSVobservations, error/cleanup/erratum, reproducible exporter и hashes. Sustained не запускался и отмечен not-run. reviewer_decision=null; lab:check проверяет комплектность, не научный pass.
