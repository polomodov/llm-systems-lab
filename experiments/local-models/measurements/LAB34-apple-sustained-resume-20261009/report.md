# LAB34 — отдельная длительная серия на M5 Max

Сессия `apple-sustained-resume-20261009`. Статус **completed**; 2026-10-09T16:49:17.812948+00:00 — 2026-10-09T17:25:58.062203+00:00.

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), arm64. Qwen3.5-9B Q6_K GGUF, revision `3885219b6810b007914f3a7950a8d1b469d598a5`, SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`. Patched llama.cpp b8407 / commit `312cf03328496df9c56fe843952cf02a8964c59a` + tile16; server SHA-256 `916660e9bfe7f4d2fda420136f6bd192688def8cbd6581f23d08b06ead2e571f`. [Build](raw/build-reference.json), [runtime](raw/runtime-manifest.json), [лог Metal/M5/offload/tensor](raw/server.txt).

Новый native PID 68489. Context 8192, один GPU-слот, threads 8, batch 512 / ubatch 256, KV f16/f16, FA on, Jinja/no-context-shift, reasoning auto/enable_thinking=true, no-cache-prompt. [Тело запроса](raw/load-request.json): max_tokens 2048, temperature 0, seed 1, top_p 1, без streaming/tools. Агентный harness отсутствует, run_ids=[].

## Гипотеза и протокол до запуска

Свежий прогретый resident deployment c1 завершит ≥1800 секунд без ошибок, с p95≤240 секунд и прежними границами памяти/питания. [Протокол](raw/protocol.md), [source hashes](raw/registered-source-hashes.json) и manifest пяти planned attempts закреплены до GPU-старта в commit `9fab350`. [13 admission samples](raw/preflight-stable-power.jsonl) за ≥120 секунд подтверждают AC / mode 0 и memory boundaries.

Короткая матрица выполнена ранее: четыре успешные клетки 08.10 и пять 09.10. [Primary copies](raw/prior-short-reference.json) проверены offline, а не объявлены новыми запусками. Новая длинная серия имеет отдельный resident процесс и свежий прогрев; это отличие явно учтено. Старые 337.251 секунды не прибавляются к новому интервалу. Три прошлые кампании сохраняют blocked и свои failures.

## Ход выполнения

| Шаг | Статус | Доказательство |
| --- | --- | --- |
| short-evidence-audit | completed | [raw](raw/short-evidence-audit-execution.json) |
| startup | completed | [raw](raw/startup-execution.json) |
| warmup | completed | [raw](raw/warmup/summary.json) |
| sustained | completed | [raw](raw/sustained/series.json) |
| shutdown | completed | [raw](raw/shutdown-execution.json) |

Порядок: offline audit → новый startup → warmup из двух запросов → selection → sustained → shutdown. Правило выбора — минимальная concurrency в пределах 95% максимальной median requests/s успешной короткой матрицы. Выбор c1 пересчитан и записан [до long](raw/sustained-selection.json). Client concurrency проходит через один GPU-слот.

## Результаты

| Серия | Успех / всего | Ошибки | Median / p95 / max latency, s | Wall, s | Completion tokens/s |
| --- | --- | --- | --- | --- | --- |
| warmup | 2/2 | 0 | 32.768 / 32.923 / 32.923 | 65.539 | 62.498 |
| sustained/block-0001 | 12/12 | 0 | 46.701 / 51.194 / 51.194 | 555.425 | 44.247 |
| sustained/block-0002 | 12/12 | 0 | 43.335 / 44.662 / 44.662 | 519.334 | 47.322 |
| sustained/block-0003 | 12/12 | 0 | 43.861 / 45.764 / 45.764 | 525.070 | 46.805 |
| sustained/block-0004 | 12/12 | 0 | 43.787 / 48.540 / 48.540 | 530.694 | 46.309 |

Sustained c1: planned 1800 s, actual **2130.780 s (35.51 min)**; 4 blocks, 48/48 successful, 0 errors. Whole-interval throughput **46.135 completion tokens/s**, 0.022527 requests/s. Он рассчитан по сумме успешных tokens / полному wall interval, включая паузы между блоками. Первый/последний block throughput: 44.247 / 46.309 tokens/s.

Memory timeline: 1070 samples; minimum free+speculative 33.105 GiB; minimum pressure free 87%; pressure levels [1]; maximum swap 0 bytes; native RSS peak 7.584 GiB. [Timeline](raw/memory-timeline.jsonl) и [после cleanup](raw/shutdown-execution.json). RSS не равен выделению Metal или максимальному бюджету GPU.

В новой сессии 50 requests / 0 errors. За три предыдущие учитываемые кампании 150 / 7; вместе **200 / 7**. Исторические copies не прибавлены повторно; более ранняя apple-direct-load-20261008 не входит в эту сумму. TSV содержит только новые наблюдения. Finish reasons новых successful responses: {'length': 50}.

## Ошибки и ограничения

Native exit 0; guard reason None; controller SIGINT count 1. Полный комплект и individual usage/latency проверены offline exporter; zero-error нового интервала не отменяет семь исторических ошибок. Источники старых SIGKILL остаются неизвестными; ещё одна остановка была обусловлена сменой AC→Battery.

Короткая матрица охватывает два дня/процесса, новый sustained — третий процесс по отношению к ней. Последний блок заканчивается целиком, поэтому actual может превышать 30 минут. Последовательные bounded blocks включают короткие паузы клиента и не доказывают непрерывную максимальную GPU occupancy. p95 каждого блока из 12 ответов — грубая оценка хвоста. Finish length/output2048 не доказывает качество текста или выполнение примерно 300 слов. TTFT/decode-only, энергия, температура и максимальный GPU budget неизвестны с причинами. Не приписываем изменение throughput thermal throttling без thermal evidence.

## Вывод по гипотезе

**Поддержана данными в зарегистрированных условиях:** свежий прогретый c1 завершил ≥1800 секунд, все long blocks без ошибок и в границах latency/memory/power; native cleanup штатный. Вместе с сохранённой короткой матрицей выполнен минимум LAB34 для клиентской очереди к одному GPU-слоту. Это не проверка2/4 одновременных GPU-слотов, максимальной памяти или качества модели.

## Ответы на контрольные вопросы

1. Client concurrency не равно GPU parallelism: здесь все запросы обслуживает один server slot; рост числа клиентов увеличивает очередь.
2. p95 на 12 наблюдениях почти максимум, поэтому три коротких повтора не дают точной оценки редких задержек.
3. Среднее block rates игнорирует разные длительности; whole throughput требует суммы tokens / полного wall interval.
4. Для throttling нужны проверенные thermal/power measurements, привязанные ко времени. Снижение скорости само по себе недостаточно.

## Комплект сдачи

Проверки: 43 профильных offline tests, npm test — 152 passed / 1 skipped (Docker gate), npm run check и lab:check submission без ошибок. [Сохранённый результат проверок](raw/software-validation.json).

Manifest v2, protocol/source pins, primary requests/responses/config/usage/latency, series/selection, native log/runtime, macOS timeline, cleanup, summary/TSV и SHA-256 inventory сохранены. Исторические failed attempts остаются в исходных отчётах. Agent run.json не требуется: автономный агент не запускался. `lab:check --mode submission` проверяет комплектность; аппаратный pass остаётся решением проверяющего, **не проверено**.
