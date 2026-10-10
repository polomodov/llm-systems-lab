# LAB08 — изолированный local provider bridge для Pi на M5 Max

Статус **blocked**: первый bridge реализован и проверен синтетически/в Docker; реальные отказы сохранены. Успешного независимо оценённого T002 pilot пока нет. Исправленная после pilot защита от stale telemetry ещё не перепроверена нативно.

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71) / arm64; native llama.cpp b8407 + tile16 / Metal; Qwen3.5-9B Q6_K, GGUF revision `3885219b6810b007914f3a7950a8d1b469d598a5`, SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`. Вход через [LAB32 unrestricted-auto 8K](../LAB32-apple-qwen35-9b-metal-auto-20261007/report.md), полные library pins из [нового tensor-повтора LAB35](../LAB35-apple-tensor-pinned-20261009/report.md).

Pi SDK 0.73.1 / Node image 24.13.1; Docker 29.5.2 / Colima. Agent container: internal network, non-root, 2 GiB, CAP_DROP=ALL, no-new-privileges, read-only root/control, отдельный workspace. Native inference находится на Mac вне task container. Context 8192 / output 2048 / slot 1 / KV f16/f16 / batch 512 / ubatch 256 / threads 8 / offload 999, reasoning auto / enable_thinking=true, temperature 0 / seed 1 / top_p 1, prefix cache disabled. [Полный deployment v1](raw/deployment.json), [runtime summary](raw/runtime-summary.json).

## Гипотеза и протокол до запуска

Agent container → broker → trusted host-worker → один закреплённый loopback inference service. Агент не выбирает target URL/Host/port и не получает доступ к LAN/cloud/admin API. Штатный Pi loop должен сохранить streaming tool-call → native tool-result → final; fingerprint должен различать одинаковый alias при смене существенных условий.

[Исходный контракт](raw/protocol.md) зарегистрирован до реализации в `97c7bd0`. [Поправка сети](raw/network-contract-amendment.md) сделана до модели: Docker не публикует port контейнера только в internal network, поэтому доверенный broker использует bridge + internal, как существующий egress gateway. Сам agent остаётся только в internal network. Host control port опубликован на loopback, требует одноразовой capability; broker не открывает upstream sockets и не выполняет CONNECT.

Разрешены GET /health и POST /v1/chat/completions на agent-facing listener, один request одновременно, body 1 MiB / response 4 MiB, deadline 300 s. SSE буферизуется до finish/DONE; TTFT не измеряется. Text blocks SDK преобразуются в строки; images, неизвестные request fields, другие alias, query/admin/absolute targets и redirects отвергаются. Dummy marker публичный, upstream auth header отсутствует. Cloud credentials не импортируются.

Первая реализация перед pilot: `0883f42`; [регистрация первой попытки](raw/pilot-registration.json). Readiness correction перед вторым pilot: `9b9655048d51e9990ff2b5dbe171ee2834540ed6`; [новая регистрация](raw/pilot-retry-registration.json). Prepare seals полный manifest и sources; run проверяет модель и все 23 engine hashes до Popen, затем actual props/template/context и файлы до/после каждого запроса. Compare разделяет deployment fingerprint и запечатанные bridge/adapter sources.

## Ход выполнения

B01–B10 mock → настоящий Pi SDK в Docker → cloud Docker boundary → первый T002 pilot → отдельный retry после readiness fix → разбор timeout/разрыва наблюдений → программное усиление wall/stale guards. Новая модельная попытка после последнего отказа не запускалась.

Первый unit-запуск выявил ошибку тестового absolute-form URL; первый Docker-запуск — невозможность publish только на internal; второй — typed text blocks SDK. Исходные failed outputs сохранены: [unit](raw/boundary-unit-initial-failed.txt), [publish](raw/docker-local-initial-failed.txt), [SDK](raw/docker-local-sdk-initial-failed.txt). Последующие проверки прошли; это не модельные runs.

171 offline-тест прошёл, 2 Docker-gated теста пропущены в npm test и выполнены отдельно. [Итог npm](raw/npm-tests-after-pilot.txt), [Docker Pi](raw/docker-local-after-pilot.txt), [Docker boundary](raw/docker-cloud-after-pilot.txt). В Docker Pi выполнил два model-mock requests, fragmented tool-call, native bash `printf BRIDGE_TOOL_READY`, сохранил tool-result и BRIDGE_FINAL. Direct LAN/cloud и control API без capability запрещены; canceled request закрыл upstream, mock остался жив; внешний timeout убрал исполняющийся agent process.

## Результаты

| Test ID | Проверенное условие | Доказательство |
| --- | --- | --- |
| B01 | Pi native SDK tool-call → tool-result → final через broker | docker-local-after-pilot.txt |
| B02 | Host/port/LAN/IPv6 policy rejects; direct egress blocked; mock counter 0 | npm-tests-after-pilot.txt; Docker |
| B03 | Host/target/query/admin/control denial; redirect без перехода | npm-tests-after-pilot.txt; Docker |
| B04 | Cloud domains/CONNECT не разрешены; redirect target counter 0 | npm-tests-after-pilot.txt; Docker |
| B05 | Oversized body/response, invalid JSON/SSE, 4xx/5xx, missing DONE | npm-tests-after-pilot.txt |
| B06 | HTTP disconnect/timeout, mock жив; Docker agent kill; wall/stale regressions | Docker; wall-deadline-tests.txt |
| B07 | Weights/template/context/backend изменяют fingerprint; same-alias compare groups разделены | npm-tests-after-pilot.txt |
| B08 | Primary usage missing → null; SDK defaults не считаются измерением | npm-tests-after-pilot.txt; оба настоящих run.json |
| B09 | Sealed manifest/artifact tamper denied; capability не в agent environment/trace; прежний credential redaction test | npm-tests-after-pilot.txt; Docker |
| B10 | Прежние cloud records/profiles и T001 replay/SSRF tests проходят | npm-tests-after-pilot.txt; check-after-pilot.txt |

| Настоящий run | Agent HTTP responses | Итог | Agent wall, s | Native cleanup |
| --- | --- | --- | --- | --- |
| `2026-10-09-pi-a2-janitor-t002-repo-janitor` | 0 | aborted / runner_error | null — агент не стартовал | exit 0 / один SIGINT |
| `2026-10-09-pi-a2-janitor-t002-repo-janitor-2` | 12 | aborted / timeout | 1056 | exit 0 / один SIGINT |

Во втором pilot — 13 leased jobs, **12 полных локальных HTTP-ответов**, один canceled до upstream send; сохранено 12 request/response pairs. Из успешных ответов известно частично: input **43504**, output **1224** tokens. Общие tokens/turns/cost в run.json остаются null: попытка неполна, usage canceled job отсутствует, final SDK result не получен. Эти частичные суммы не выдаются за полные итоги.

По 73 наблюдавшимся resource samples второго pilot: RSS peak **7.518 GiB**, min free+spec **27.537 GiB**, swap **0**, pressure level 1, AC. Между 23:07:14.663Z и 23:22:28.566Z — разрыв **913.904 s**. Измерения не доказывают состояние машины внутри разрыва. Configured timeout **900 s**, фактически записанный agent wall **1056 s**; точная причина задержки/разрыва неизвестна. Native cleanup штатный в обеих попытках. [Первичные records](../../../../results/runs/2026-10-09-pi-a2-janitor-t002-repo-janitor-2/run.json).

## Ошибки и ограничения

Первый pilot остановился на fetch readiness: ручной Host при URL 127.0.0.1 не прошёл строгую broker policy. Native startup был принят, agent container ещё не стартовал; execution.started_at обозначает инфраструктурную фазу. Отказ исправлен URL egress:8080 и отдельной Docker regression. [Разбор](raw/pilot-readiness-amendment.md).

Второй pilot достиг штатных инструментов Pi, но не закончил задачу: timeout / exit 137, без final SDK result и независимого verdict. Тринадцатый job не имеет primary request/response. Разрыв наблюдений 913.904 s не доказывает sleep, suspension или изменение часов: независимых данных о причине нет. Caffeinate -i был частью supervisor, но его непрерывное исполнение в разрыве не подтверждено.

После исполнения добавлены absolute wall deadline check и отказ при stale resource timeline >15 s либо движении часов назад. Новые synthetic clock-jump/stale tests и повтор Docker boundary прошли. Они не подтверждают задним числом старый таймер и не гарантируют остановку во время полной приостановки host: guard действует при возобновлении. В первом regression выявлен непереданный env при Docker kill; исправлено, исходный failed output сохранён. [До/после](raw/wall-deadline-initial-failed.txt), [успешная проверка](raw/wall-deadline-tests.txt).

Нативная квалификация новых guards и успешный независимо оценённый T002 pilot остаются pending. Aborted runs не передаются в judge для превращения в pass. Local scope только Pi/T002/GGUF/Metal/macOS; T001/T003, остальные adapters, MLX/Ryzen и server auth не приняты. Buffered SSE не измеряет TTFT; energy/temperature/max GPU allocation неизвестны. Успех synthetic tool round-trip не доказывает качество агентного решения.

## Вывод по гипотезе

Инженерная часть поддержана mock/Docker данными и 12 реальными HTTP-ответами: isolated route, native tools, pinned identity и primary usage работают в зарегистрированном условии. **Полный допуск LAB08 не получен:** обе реальные попытки aborted; первая до агента, вторая с timeout и telemetry gap. После усиления guards необходимы новая короткая нативная проверка, отдельный новый T002 pilot и независимая оценка. L024/L025 остаются «предложена»; вклад в качество не установлен.

## Ответы на контрольные вопросы

1. **Почему разрешение всей LAN недостаточно?** Оно даёт доступ к другим хостам/портам/admin API. Здесь target выбирает только trusted worker; agent имеет internal route к одному broker API.
2. **Alias и weights/template?** Alias — строка API. Hashes GGUF/libraries, immutable command/PID и props/template доказывают конкретное зарегистрированное deployment; одно /models этого не делает.
3. **Почему model server вне 2 GiB?** Native weights/KV требуют больше памяти; 2 GiB ограничивают agent harness, не GPU service. Состояние Mac наблюдается отдельным guard.
4. **Что разделяет Vulkan/ROCm?** Engine backend/build/version/library pins и hardware/driver/protocol входят в fingerprint; bridge source hash также разделяет условия.
5. **Что доказывает mock?** Transport, native tools и сохранение событий при контролируемых ответах. Реальное решение T002 требует настоящего run и независимого verdict.
6. **Когда стоимость 0 допустима?** Нулевая inference fee требует проверенного local-only маршрута; она не равна нулевой энергии/амортизации. Здесь общей стоимости измерения нет: null, SDK placeholder price не принят.

## Комплект сдачи

Diff bridge/Pi/schema/prepare/run/compare, ledger L024/L025, полный deployment, protocol/amendments, первичные snapshots двух настоящих runs, bodies/responses/usage, native logs/resource timelines/cleanup, TSV, source registrations и tests сохранены. npm test 171 passed / 2 gated skipped; обе Docker проверки выполнены отдельно; npm run check и git diff --check прошли. Submission подтверждает комплектность blocked отчёта, а не успешность LAB08. Reviewer decision: **не проверено**.
