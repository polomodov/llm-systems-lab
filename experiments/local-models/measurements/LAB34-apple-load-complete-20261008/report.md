# LAB34 — concurrency 1/2/4, прерванная серия

Статус **blocked**. Первый повтор c1/c2/c4 и второй c2 завершены без ошибок. Второй c4 прерван завершением сервера; последующие короткие клетки и 30 минут не запускались. Анализ выполнен 09.10.2026, первичные измерения — 08.10.2026.

## Паспорт выполнения

Codex по запросу владельца. Apple M5 Max, 18 CPU / 40 GPU, 128 GiB, macOS26.5/25F71, native arm64. Питание AC/powermode0 во всём записанном timeline. Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5, SHA25691898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. llama.cpp b8407/312cf033… +tile16; exact binary SHA916660e9…, Metal/M5/offload33/33/tensor capability подтверждены startup log.

Loopback18080, context8192, фиксированный один серверный слот, threads8, batch512/ubatch256, KVf16/f16, FAon, Jinja/no-context-shift, reasoningauto/enable_thinking=true, requested prefix cache off. Temp0/seed1/top_p1, max_tokens2048; тот же публичный запрос примерно300слов, что в предыдущей LAB34. Client concurrency1/2/4 здесь измеряет очередь при одном GPU slot. Агентного harness нет, run_ids[].

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md), source hashes, register и commit8b58e00 предшествуют запуску. Три блока по12 для каждой concurrency с чередованием r1=1→2→4, r2=2→4→1, r3=4→1→2; warmup2 отдельно. После полной короткой матрицы — lowest concurrency within95% of maximal median throughput и1800s блоками по12.

Новые operational boundaries зарегистрированы до всей серии: HTTP timeout300s, p95<=240s, errors0; memory free+spec>=8GiB, pressure level1, pressure free>=50%, swap0, nativeRSS<=24GiB, AC/mode0. Прежний отказ при floor16GiB сохранён отдельно; новый floor не исправляет старое измерение и не является GPU allocation budget. Cleanup использует одну locked interrupt operation; monitor и shutdown не могут послать второй SIGINT. Four synthetic cleanup/guard tests прошли до model start.

## Ход выполнения

Startup и warmup2/2 прошли. Все12 запросов в r1-c1, r1-c2, r1-c4, r2-c2 завершились успешно. r2-c4 получил10 успешных ответов и2 ошибки соединения при прекращении процесса. Контроллер записал Own server exited и прекратил дальнейшую кампанию. Shutdown record: native returncode=-9 (SIGKILL), interrupts=[], guard_reason=null. Последняя строка native log содержит cleaning up before exit, но отправитель/первичный сигнал не установлены.

Нет данных, позволяющих приписать завершение OOM, memory guard, двойному SIGINT или самопроизвольному GPU crash. Guard оставался в допуске. Прерывание чата само по себе не доказывает причину последующего SIGKILL. Владелец не сообщил, останавливал ли процесс. Полные первичные ответы, ошибки, native log и timeline сохранены; restart не скрывает этот отказ.

## Результаты

| Блок | Успешно / всего | Median / p95 latency, s | Successful completion tokens/s |
| --- | ---: | --- | ---: |
| warmup | 2/2 | 39.647 / 44.233 | 51.655 |
| r1-c1 | 12/12 | 36.865 / 37.759 | 55.868 |
| r1-c2 | 12/12 | 73.693 / 75.829 | 55.244 |
| r1-c4 | 12/12 | 145.873 / 146.209 | 56.130 |
| r2-c2 | 12/12 | 73.818 / 75.281 | 55.390 |
| r2-c4 | 10/12 | 147.108 / 148.485 | 53.507 |

Throughput делит сумму completion tokens успешных запросов на полный wall блока, включая очередь и failures. Non-streaming latency включает prefill/reasoning/final. Все успешные ответы finish=length/output2048; содержание и300слов не оценивались. В первой тройке throughput около55–56tokens/s, а median latency растёт примерно37→74→146s. Это наблюдение одного повтора и очереди, не итог трёх повторов или доказательство GPU parallelism.

Memory: 1088 samples каждые~2s, min free+spec 26.139GiB, max nativeRSS 7.585GiB, min pressure free 86%, maxswap 0bytes, pressure levels [1]. Энергия, температура, TTFT, decode-only speed и максимальный GPU budget неизвестны. [Сводка](raw/summary.json).

13 attempts:6completed/2failed/5not-run. Запросов62:60successful/2failed, включая warmup. 30-минутный sustained **not-run**, actualduration=null; selection не выполнен, так как полная короткая матрица не завершена. Счётчик attempts включает startup/shutdown, не агентские успехи.

## Ошибки и ограничения

Фоновая серия остановилась08.10.2026 в15:49:48UTC на native SIGKILL, причинаunknown. Это отдельный отказ, не прежняя secondSIGINT assertion. Новая locked cleanup логика присутствовала, но штатное завершение с одним SIGINT в этой серии не проверено: child уже был завершён.

Полного допуска LAB34 нет: отсутствуют r2-c1, r3-c1/c2/c4 и sustained. Частично выполненный r2-c4 не заменён successful повтором. Нельзя объединить эти данные с предыдущим memory-stop условием или новым resident process без указания смены сессии/дня. Cached checkpoint storage виден в native log даже при requested no-cache-prompt; это не доказательство reuse входа: log показывает сброс sequence и полный prefill77tokens.

При возобновлении09.10.2026 pmset показал Battery Power/30%, swap0. Новые GPU измерения не выполняются до AC по зарегистрированному протоколу. Пользовательские приложения/питание/системные лимиты не менялись.

## Вывод по гипотезе

Первая тройка поддерживает рабочий HTTP workload при c1/c2/c4, но throughput gain>=10% не наблюдается в ней. Полная гипотеза scaling/устойчивости не проверена из-за прекращения процесса. Все failures сохраняются; необходима отдельная зарегистрированная серия продолжения и30min после короткого допуска.

## Ответы на контрольные вопросы

1. Client concurrency создаёт очередь; server slot1 сохраняет последовательное GPU исполнение.
2. p95 на12ответах близок к максимуму, один повтор не оценивает устойчивый tail.
3. Общий throughput требует суммы токенов и полного wall interval; среднееblock rates и исключение failures искажают результат.
4. Thermal throttling требует независимых temperature/power измерений; здесь их нет. SIGKILL не устанавливает OOM.

## Комплект сдачи

Manifestv2/register/protocol/source hashes, pinned deployment, props/slots/device/native log, macOS timeline, warmup и5blockdirectories со всеми62request responses/metrics, TSV/summary и evidence hashes. Причины unknown/not-run сохранены. reviewer_decision=null; lab:check — комплектность, не experiment pass.
