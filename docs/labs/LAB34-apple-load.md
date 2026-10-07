# ЛР34. Параллельная нагрузка и устойчивость Mac

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | HTTP load test / `target-machine` |
| Время | 2–4 часа плюс 30-минутная серия |
| Предпосылки | LAB32; LAB33 только при использовании wrapper |
| Минимум | Warmup; по три серии из 12 запросов для concurrency 1/2/4; затем 30 минут для прошедшей конфигурации |

## Цель

Измерить полезный параллелизм и устойчивость deployment на Mac, сохранив задержки, отказы и динамику общей памяти.

## Проверяемая гипотеза

Рост concurrency увеличивает throughput без нарушения заранее выбранных latency/error/memory границ; допущенная конфигурация сохраняет их при длительной работе.

## Подготовка

```sh
npm run lab:new -- --lab LAB34 --session apple-load
export LAB_DIR='experiments/local-models/measurements/LAB34-apple-load'
python3 -B docs/labs/fixtures/concurrency_test.py
python3 -B docs/labs/fixtures/concurrency_driver.py --help
export LOCAL_ENDPOINT='http://127.0.0.1:8080/v1/chat/completions'
export MODEL_ALIAS='lab-model'
```

Используйте [общий Apple-протокол](../../experiments/local-models/apple/README.md). Driver из LAB26 переносим для HTTP, но его `/proc` telemetry предназначена для Linux: на macOS эти поля ожидаемо `null` с причиной. **Обязателен отдельный macOS memory timeline**, запущенный до нагрузки. Отсутствие Linux-метрик не трактуется как нулевой swap или достаточная память.

## Порядок выполнения

1. Запишите endpoint, model identity, context, fixed server slots/queue/cache, output cap, питание и критерии остановки. Сервер использует только loopback. Driver не поддерживает auth: при обязательной авторизации сохраните blocker, не снимайте защиту. Не включайте tools в нагрузочный request.

   ```sh
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   data = json.loads(pathlib.Path('docs/labs/fixtures/concurrency-request.json').read_text())
   data['model'] = sys.argv[2]
   with (pathlib.Path(sys.argv[1]) / 'raw/load-request.json').open('x') as out:
       json.dump(data, out, ensure_ascii=False, indent=2)
   PY
   ```

2. Снимите LAB28 memory/swap и начните временной ряд. Выполните отдельный прогрев:

   ```sh
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 2 --timeout 120 --out "$LAB_DIR/raw/warmup"
   ```

   При ошибке остановитесь. Timeout 120 s — начальная граница, не обещание latency; другой предел (не более 600 s) назначается до всей сравнительной серии.

3. Выполните по одной серии с проверкой summary и памяти после каждой. Порядок: r1 — 1→2→4; r2 — 2→4→1; r3 — 4→1→2. Для первой:

   ```sh
   export REPEAT=1
   export CONCURRENCY=1
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency "$CONCURRENCY" --requests 12 --timeout 120 \
     --out "$LAB_DIR/raw/r$REPEAT-c$CONCURRENCY"
   ```

   После timeout проверьте отсутствие оставшейся generation перед следующей серией. Не меняйте slots вместе с client concurrency: очередь сервера — часть результата. OOM, потеря readiness, устойчивый swap рост, критический pressure или нарушение заранее выбранного запаса — остановка; последующие клетки `not-run` с причиной.

4. Выберите concurrency, прошедший короткие серии. До длинной серии запишите выбор и включите memory timeline. Следующая команда планирует блоки по 12 запросов в течение 1800 секунд; последний блок может закончиться позже (до своего deadline), что отражается в wall time. При первой HTTP/protocol ошибке driver останавливает серию. При memory stop-критерии оператор прерывает Ctrl-C; запись финального статуса сохраняется:

   ```sh
   export CONCURRENCY=1
   python3 - "$LAB_DIR" "$LOCAL_ENDPOINT" "$CONCURRENCY" <<'PY'
   import json, pathlib, subprocess, sys, time
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   target = raw / 'sustained'
   target.mkdir()
   started = time.monotonic()
   blocks, status = [], 'completed'
   try:
       while time.monotonic() - started < 1800:
           out = target / f'block-{len(blocks)+1:04d}'
           command = [sys.executable, '-B', 'docs/labs/fixtures/concurrency_driver.py',
               '--endpoint', sys.argv[2], '--request', str(raw/'load-request.json'),
               '--concurrency', sys.argv[3], '--requests', '12', '--timeout', '120', '--out', str(out)]
           p = subprocess.run(command, check=False)
           blocks.append({'directory':out.name, 'exit_code':p.returncode})
           if p.returncode:
               status = 'failed'
               break
   except KeyboardInterrupt:
       status = 'interrupted'
   finally:
       (target/'series.json').write_text(json.dumps({'planned_seconds':1800,
           'actual_seconds':time.monotonic()-started, 'status':status, 'blocks':blocks}, indent=2))
   if status != 'completed': raise SystemExit(1)
   PY
   ```

   Это последовательные bounded blocks с небольшими паузами клиента. Их wall time включается в длительность кампании; не описывайте её как непрерывную максимальную GPU occupancy. При прерывании проверьте завершение дочернего клиента и очередь сервера до других опытов. Энергия/температура собираются только доступными проверенными средствами, иначе неизвестны.

5. Разберите каждый `summary.json` и individual requests: median/p95/max успешных latency, число/latency failures, successful requests/s и tokens/s при полном usage. p95 на 12 наблюдениях грубый, почти максимум. Driver non-streaming: TTFT и decode-only speed недоступны. Итоговый throughput считайте по суммарным tokens и wall interval, не средним от block rates. Пропуски usage сохраняют общий tokens/s неизвестным.

6. Сопоставьте временные интервалы нагрузки и memory pressure/swap, сравните начало/конец длинной серии. Не приписывайте ухудшение thermal throttling без thermal evidence. Запишите допустимый режим и ограничивающий фактор: очередь, memory, ошибки или latency.

## Таблицы результатов

| Повтор / concurrency | Успех / всего | Median / p95 / max s | Requests/s | Tokens/s | Failures | Swap / pressure | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

| Sustained concurrency | Planned / actual s | Начало / конец throughput | Peak memory / источник | Ошибки / stop reason |
| --- | --- | --- | --- | --- |
| | | | | |

## Что сдать

Отчёт/TSV/manifest, request и deployment conditions, все driver output directories, `sustained/series.json`, отдельный macOS memory timeline и остановки/пропуски. Для неизвестных `/proc`, энергии и температуры — причины.

## Критерии завершения

- [ ] По три серии для 1/2/4 либо документированный stop/blocker.
- [ ] 30-минутная серия имеет actual duration и все блоки, включая failures.
- [ ] macOS memory собрана отдельно; `/proc` null не интерпретирован как ноль.
- [ ] TTFT не выведен из non-streaming latency; usage и failure учтены честно.
- [ ] Комплект проверен по общему протоколу.

## Контрольные вопросы

1. Почему client concurrency не равно GPU parallelism?
2. Как короткие серии ограничивают оценку p95?
3. Почему усреднение block tokens/s даёт неправильный общий throughput?
4. Какие доказательства нужны для вывода о throttling?

## Источники

- [Driver](fixtures/concurrency_driver.py), [offline tests](fixtures/concurrency_test.py), [методика LAB26](LAB26-concurrent-load.md).
- [Паспорт macOS](LAB28-apple-hardware.md), pinned server documentation и локальные man pages.
