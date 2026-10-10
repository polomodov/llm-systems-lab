# LAB08 — новая native квалификация и Pi T002

Статус **blocked**: короткая аппаратная квалификация и настоящие pilot attempts сохранены. Независимого pass задачи нет.

## Паспорт выполнения

Apple M5 Max / 128GiB / macOS26.5/25F71, AC/mode0; pinned llama.cpp312cf033 + tile16 / Metal, Qwen3.5-9B Q6_K revision3885219b6810b007914f3a7950a8d1b469d598a5. [Deployment8K](raw/deployment.json), [deployment16K](raw/ctx16/deployment.json). Pi0.73.1/native SDK в isolated Docker. Context8192→16384, output2048, slot1/KVf16, temp0/seed1/top_p1/thinkingtrue, no prefix cache. USD budget observed; policy и images находятся в run.json. Source registration ae1b9e2 и083bdcf; поправка16K d1e6cf8.

## Гипотеза и протокол до запуска

[Protocol](raw/protocol.md) до исполнения; [поправка после overflow8K](raw/context-amendment.md) до новой квалификации16K. Warmup+3 exact SSE chat, verify25pins до Popen и после запросов,20s idle, cleanup0/одинSIGINT. Resource samples2s, stale>15s/clock backwards, wall180s. Затем новый sealed T002 pilot с timeout900s. Synthetic negative guard tests остаются отдельным software evidence; suspend/clock на машине не имитировали. Full host suspension не допускает исполнения guard до resume.

## Ход выполнения

Короткая8K серия → настоящий T0028K → сохранённый отказ8265>8192 → отдельная16K qualification и новыйrun. Предыдущие два aborted из LAB08-apple-provider-bridge-20261009 остаются неизменными. Команды и bodies сохранены в raw и primary run traces. Ни одного hidden-check не читали/не выполняли агентом.

## Результаты

8K:4/4 exact LAB_READY,30samples/maxgap2.016s/RSSpeak7.422GiB/swap0, total63.514s включая startup/verify/idle/cleanup. Первая16K qualification дала4/4HTTP, но **не допущена**: free+spec7.785GiB<8GiB. [Исходный результат](raw/ctx16/qualification.json), [первая unsafe строка](raw/ctx16/native/native-memory.jsonl). Последующая ps ошибка затёрла первичныйguard; новый supervisor сохраняет первую причину и прекращает polling. [Поправка](raw/first-guard-amendment.md) и новый retry имеют отдельную регистрацию. Три повтора отделены отwarmup, coldstartup не считается latency запроса.

| Run | Итог | Accepted/jobs | Agent wall,s | Max gap,s | Peak RSS,GiB |
| --- | --- | --- | --- | --- | --- |
| `2026-10-10-pi-a2-janitor-t002-repo-janitor` | aborted/error | 21/22 | 290 | 2.161 | 7.525 |
| `2026-10-10-pi-a2-janitor-t002-repo-janitor-2` | awaiting_review/length | 16/16 | 244 | 2.015 | 7.779 |

[Primary summary](raw/primary-summary.json) содержит partial usage, samples и cleanup. Partial tokens не выданы за полный итог interrupted request. Cost/energy/temperature/maxGPU остаютсяnull с причиной. Primary inputs/trace inventories доступны в каждом run; native pre-Popen hashes включают все23enginepaths/21dylibpaths, GGUF и passport.

16K pilot: exit0 после16turns/244s, **stop_reason=length**, последний ответ исчерпал2048output tokens. Это завершение процесса, не доказательство завершения задачи. Usage всех16HTTP известно:68121input/3701output; SDK final получен. Awaiting_review/pending сохраняется до независимого judge; нельзя считать length успешнымfinal. Native RSSpeak7.779GiB/maxgap2.015s/swap0, cleanup0/одинSIGINT. Короткий16Kretry:4/4HTTP/64.371s/guardnull. Stable preflight120.023s/59samples/minfree+spec21.029GiB.

## Ошибки и ограничения

8K pilot22-й запрос: HTTP400 `exceed_context_size_error`,8265prompttokens>8192. 21ответ принят, nativeexit0/одинSIGINT,146samples/maxgap2.161s/swap0. Это другой отказ, не повтор прежнего telemetry gap. Менять задним числом context или aborted нельзя. Новый16K — отдельная конфигурация с новымfingerprint и run ID. Ни CLIexit0, ни tool transport не заменяют независимую оценку задачи. При awaiting_review отчёт остаётся draft, пока judge pending; aborted не judge-ятся как pass. Идентичность/runtime safeguards проверены, вклад bridge в качество не установлен.

## Вывод по гипотезе

Native короткая8K квалификация поддержала непрерывность telemetry в наблюдавшемся интервале. T0028K выявил ограничение длины, bridge сохранил ошибку и cleanup. По16K выводы только из нового run/qualification. Полный LAB08 допуск требует independently judged successful pilot; агентную LAB09 кампанию не расширять до этого. Независимая MLX HTTP LAB32 может идти дальше.

## Ответы на контрольные вопросы

1. LAN allowlist не ограничивает модельный endpoint; internal broker принимает только fixed chat API, target выбирает trusted worker.
2. Alias не удостоверяет weights; manifest hashes, PID, command, props/template удостоверяют deployment.
3. GPU model вне2GiB container: это граница agent harness; отдельный native guard контролирует Mac.
4. Backend/context/build/OS входят в fingerprint;16K не объединяется с8K.
5. Mock подтверждает transport, настоящий T002 требует own run и independent verdict.
6. SDKprice0 не измеряет energy/железо;costnull. Отсутствующее usage canceled/rejected запроса тожеnull.

## Комплект сдачи

Manifest/TSV/protocol/amendment, deploymentpins, rawHTTP/usage/serverlogs, continuous samples/cleanup, sealed inputs/trace и tests сохранены. Software/lab integrity проверка сохраняется отдельно в raw. Reviewer decision: **не проверено**. Полнота blocked отчёта не означает passT002.
