# ЛР26. Параллельная нагрузка на локальный сервер

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип работы | Ограниченный HTTP load test локального inference service |
| Время | 2–3 часа оператора плюс исполнение; длительность зависит от модели и выбранных timeout |
| Предпосылки | Завершённая ЛР05, аппаратный паспорт и проверенный model server на Ryzen AI Max+ 395 / 128 GB / Linux |
| Готовность | `target-machine`; HTTP driver и его offline tests готовы; bridge ЛР08 для этого опыта не нужен |
| Минимальный объём | Прогрев и три серии по 12 запросов при client concurrency 1, 2 и 4; одна модель и конфигурация сервера |
| Расширение | Три повтора каждого concurrency с балансировкой порядка; затем длительная устойчивость, энергия или другая server configuration |

## Цель

Найти полезный параллелизм для выбранного локального deployment: сколько запросов сервер завершает за единицу времени и какой ценой по задержке, памяти и ошибкам. Получить воспроизводимый профиль на реальной машине, сохранив каждый неуспешный запрос.

## Проверяемая гипотеза

Увеличение client concurrency с 1 до 2 и 4 повышает общую производительность в пределах заранее выбранной допустимой задержки и запаса памяти. До запуска запишите границы приемлемости: timeout запроса, допустимую долю HTTP/protocol errors, резерв доступной RAM и допустимость swap. Не назначайте численные показатели Ryzen до измерения.

Конкурентные HTTP-запросы не гарантируют параллельное исполнение на GPU: сервер может поставить их в очередь. Эта работа измеряет поведение целого deployment при фиксированных server slots и scheduling policy. Увеличение числа server slots — отдельное вмешательство и отдельная серия.

## Подготовка

```bash
npm run lab:new -- --lab LAB26 --session my-session
LAB_DIR='experiments/local-models/measurements/LAB26-my-session'
python3 -B docs/labs/fixtures/concurrency_test.py
python3 -B docs/labs/fixtures/concurrency_driver.py --help
npm run check
```

Используйте проверенный server из ЛР05–07 с закреплёнными weight hashes, backend/build, template, контекстом, KV dtype, sampling/reasoning и launch command. Запишите hardware snapshot, режим питания, фоновые процессы и cache policy. Требуемые команды slots/queue/prefix-cache проверяйте в `--help` и документации **вашего pinned runtime**. Эта методичка не утверждает одинаковую семантику параметров разных движков.

Driver выполняется на том же Linux-host, что и inference service. Разрешены только явно заданные `http://127.0.0.1:PORT/v1/chat/completions` или `http://[::1]:PORT/v1/chat/completions`. Он не читает `.env`, не передаёт auth, не следует redirects, не использует HTTP proxy, не вызывает tools и не повторяет неудачные запросы. Для сервера, требующего авторизацию, этот минимальный driver неприменим: сохраните blocker или подготовьте отдельный проверенный клиент с передачей секретов по правилам репозитория. Не снимайте действующую защиту сервера ради пробы.

## Порядок выполнения

1. **Подготовьте публичный нагрузочный запрос.** [Готовый fixture](fixtures/concurrency-request.json) просит текст с output cap 512. Это нагрузка, не проверка качества модели. Создайте рабочую копию с alias фактически запущенной модели; повторное выполнение не перезапишет файл:

   ```bash
   MODEL_ALIAS='<проверенный alias локальной модели>'
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   data = json.loads(pathlib.Path('docs/labs/fixtures/concurrency-request.json').read_text())
   data['model'] = sys.argv[2]
   with (pathlib.Path(sys.argv[1]) / 'raw' / 'load-request.json').open('x') as out:
       json.dump(data, out, ensure_ascii=False, indent=2)
       out.write('\n')
   PY
   ```

   Допустимы только один текстовый user message, model, `max_tokens` 1…4096, `stream:false` и необязательные `temperature`, `top_p`, `seed`. Если sampling отсутствует в JSON, закрепите серверные defaults. Не добавляйте keys, приватные данные и инструменты. Принятие seed сервером проверяется отдельно и не обещает детерминизма. Сохраните этот один request для всей серии.

2. **Проверьте аппаратный запас и server identity.** Сохраните logs readiness, выбранный GPU/offload, allocations, PID/cgroup и server-side limits. Контекст и число slots должны допускать четыре запросa либо давать явный задокументированный отказ; не увеличивайте лимиты между тремя опытами. Запишите исходные memory/swap по ЛР02. На UMA не складывайте RSS и GPU allocation как независимые расходы общей RAM.

3. **Выполните отдельный прогрев.** Endpoint должен совпадать с запущенным локальным сервером:

   ```bash
   LOCAL_ENDPOINT='http://127.0.0.1:8080/v1/chat/completions'
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 2 --timeout 120 --out "$LAB_DIR/raw/warmup"
   ```

   Значение `120` — верхняя граница одного запроса, а не прогноз скорости. Если пилот показывает недостаточность этого лимита, сохраните failure и до сравнительных запусков назначьте другой общий timeout, максимум 600 s. Каталог `--out` должен быть новым, его родитель уже существует. Driver сохранит config, исходный request, status/error каждого запроса и ограниченные тела ответов, даже при HTTP error или timeout. Exit 1 означает ошибки запросов; exit 2 — некорректную конфигурацию или ошибку файлов. До следующего шага устраните проблему либо оформите blocker.

4. **Исполните минимальную последовательность 1→2→4.** Запускайте **одну** серию за раз и изучайте её результат до перехода дальше. Пример первой:

   ```bash
   python3 -B docs/labs/fixtures/concurrency_driver.py \
     --endpoint "$LOCAL_ENDPOINT" --request "$LAB_DIR/raw/load-request.json" \
     --concurrency 1 --requests 12 --timeout 120 --out "$LAB_DIR/raw/r1-c1"
   ```

   Для следующей замените concurrency на `2` и output на `r1-c2`, затем на `4` и `r1-c4`. Не меняйте prompt/output/context/cache settings. При потере readiness, OOM или нарушении записанного резерва памяти остановите увеличение нагрузки, сохраните logs и отметьте недостигнутую ступень как blocked. Никакого автоматического restart или retry нет. Закрытие клиентского соединения по timeout не доказывает отмену generation: перед следующей серией проверьте серверную очередь и отсутствие оставшихся запросов.

5. **Разберите измерения и ресурсы.** В каждой output-директории есть:

   - `config.json`, `request.json`: endpoint, concurrency, число запросов, deadline и SHA запроса;
   - `request-NNNN.json` и `.response.bin`: individual latency/status/error/usage и до 1 MiB сырого ответа; `response_truncated` явно отмечает ограничение;
   - `system-memory.jsonl`: Linux `MemTotal`, `MemAvailable`, `pswpin/pswpout` до и после серии и с интервалом около секунды;
   - `summary.json`: wall-clock всей серии, successful requests/s, successful completion tokens/s при полном usage, median/p95/max latency успешных ответов, число ошибок.

   Token usage берётся из ответа сервера. Если usage неизвестен хотя бы для одного успешного ответа, общий successful tokens/s остаётся `null`; ошибок это не скрывает. HTTP 200 с невалидным JSON, пустым assistant text, неожиданным tool call или finish reason вне `stop`/`length` считается protocol error. Обработчик не оценивает правильность написанного текста. `finish_reason=length` допустим для ограниченной нагрузки, но долю таких ответов покажите отдельно.

   Median/p95 относятся к **успешным** ответам; рядом обязательно показывайте failures и их latency, иначе быстрые отказы могут создать ложное улучшение. p95 использует nearest-rank; на 12 наблюдениях это максимум, поэтому минимум работы даёт только грубую оценку хвоста. Это задержка полного ответа с очередью сервера и установлением соединения, без ожидания в очереди client executor. TTFT и decode-only speed не измеряются: `stream:false` не даёт таких данных. Новое соединение на каждый запрос — часть неизменной методики.

   `minimum_sampled_mem_available_bytes` описывает всю машину и может пропустить короткий пик между отсчётами. Дополнительно приложите доступную телеметрию server process/cgroup, GPU allocations и температуры из ЛР02, со способом и частотой измерения. Если engine создаёт workers, RSS одного PID не представляет весь deployment. Для peak allocations без измерителя сохраните `null`, не называйте минимум MemAvailable точным пиком модели. Swap counters системные и требуют учёта фоновой нагрузки.

6. **Постройте профиль масштабирования.** Для каждого concurrency посчитайте отношение successful requests/s к c1 и отношение median latency к c1, если оба значения измерены. Completion tokens/s сравнивайте вместе с количеством output tokens и finish reasons: разная длина ответа меняет нагрузку. Зафиксируйте, где сервер начал очередить, отказывать или вытеснять память, используя logs. Отдельно объясните роль prefix cache: одинаковые запросы могут проверять тёплый cache; вывод не переносится автоматически на уникальные длинные prompts.

7. **Расширьте серию, меняя один фактор.** Для трёх повторов дополните порядок `2→4→1` и `4→1→2`, по 12 новых запросов на ступень, с новыми `r2-*` и `r3-*` директориями. Между опытами проверяйте readiness и одинаковые начальные условия. Это 108 сравнительных запросов плюс прогрев. Для устойчивости заранее назначьте ограниченное число таких batch за 30–60 минут и верхний предел общего числа запросов; driver принимает не более 256 запросов за одно исполнение. Плановое окончание и аварийное прекращение сохраняйте как разные исходы. Отдельными сериями можно исследовать server slots, другой context, Vulkan/HIP или другой движок — не менять их внутри сравнения concurrency.

8. **При наличии реального измерителя добавьте энергию.** Зафиксируйте прибор, точку измерения всей системы, точность/частоту и timestamps; отдельно измерьте idle того же компьютера с загруженной моделью. Для интервала всей серии сохраните total Wh и число успешных запросов, затем `Wh / successful request`; при нуле успешных запросов показатель не определён. Покажите gross energy и, если вычитаете idle, отдельный расчёт с длительностью и допущением постоянного idle. TDP и nominal power limit не заменяют измеренных watts. При отсутствии прибора энергия остаётся `null`; работа всё равно может быть завершена.

## Таблицы результатов

| Deployment fingerprint | Backend / slots / queue policy | Context/output | Sampling / reasoning / cache | Hardware manifest / telemetry |
| --- | --- | --- | --- | --- |
| | | | | |

| Повтор / concurrency | Success / total | HTTP / protocol / timeout errors | Median / p95 / max latency, s | Requests/s | Completion tokens/s / usage coverage | Output tokens / length stops |
| --- | --- | --- | --- | --- | --- | --- |
| 1 / 1 | | | | | | |
| 1 / 2 | | | | | | |
| 1 / 4 | | | | | | |

| Повтор / concurrency | Min sampled MemAvailable, bytes | Server peak / метод | GPU allocation / метод | Swap delta / фон | Температура / throttling evidence | Raw directory |
| --- | --- | --- | --- | --- | --- | --- |
| 1 / 1 | | | | | | |
| 1 / 2 | | | | | | |
| 1 / 4 | | | | | | |

| Серия / прибор | Интервал | Gross Wh | Idle W / отдельный интервал | Wh / successful request | Ограничения |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Что сдать

Отчёт, учебный manifest, request и SHA, точную launch command/server identity, таблицы и **все** новые output-директории driver, server logs и доступную аппаратную телеметрию. Отдельно приложите protocol/budget plan и причину каждой остановленной ступени. Заполните [проверку комплектности](report-validation.md). Это HTTP probes, поэтому их нельзя выдавать за T002 `run.json`, agent verdict или реальную автономную работу.

## Критерии завершения

- [ ] Driver offline tests проходят; loopback endpoint и pinned deployment подтверждены.
- [ ] До запуска закреплены один request, лимиты, server slots и cache policy.
- [ ] Выполнены прогрев и все три ступени либо оформлен конкретный аппаратный blocker; ошибки сохранены.
- [ ] Метрики успешных ответов показаны вместе с полным числом failures; неизвестный usage не превращён в 0.
- [ ] Сохранены memory/swap observations, ограничения sampling и UMA учтены.
- [ ] Не смешаны полный response latency, TTFT, decode speed и агентное качество.
- [ ] Энергия подтверждена измерителем или явно отсутствует; `npm run check` проходит.

Ступень с явными 429/503 при работающем сервере может быть завершённым наблюдением предела, а не поводом удалить её из отчёта. При недоступной машине или невозможном стартовом deployment результат — `blocked`, а не успешное исследование Ryzen.

## Контрольные вопросы

1. Чем client concurrency отличается от GPU batch и числа server slots?
2. Почему рост requests/s может сопровождаться ухудшением пользовательской задержки?
3. Как короткие отказы и отсутствующий usage искажают красивый график throughput?
4. Почему при 12 запросах p95 почти не даёт информации отдельно от max?
5. Что не позволяет измерить данный non-streaming driver?
6. Как prefix cache и thermal state влияют на переносимость результата?
7. Почему Wh/request и tokens/s ещё не отвечают на вопрос о стоимости успешной агентной задачи?

## Источники

- [Открытый driver](fixtures/concurrency_driver.py), [offline mock tests](fixtures/concurrency_test.py), [нагрузочный request](fixtures/concurrency-request.json).
- [Python: HTTPConnection и timeout сетевых операций](https://docs.python.org/3/library/http.client.html), [ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html). Driver дополнительно ограничивает общий deadline запроса watchdog и не следует redirects.
- [Паспорт и телеметрия Linux](LAB02-hardware.md), [контекст и protocol preflight](LAB05-context-tools.md), [engine profiles](../local-inference-engines.md).
- Версия/help и runtime documentation выбранного deployment прилагаются исполнителем. Поддержка конкретных scheduling/cache flags не предполагается без проверки.
