# LAB35: квалификация Apple и подготовка сопоставимой пары

## Подготовительное исправление до новых запросов

Предыдущая сессия apple-qualification-20261009 сохраняется blocked: standard startup/offload прошёл, HTTP driver завершился с exit2 до отправки chat warmup из-за неверного вложенного пути. Собственный сервер завершился с exit0/одним SIGINT. Новый retry исправляет путь driver на общий raw root; inputs, server/binary/model, sampling и resource boundaries неизменны. Также descriptor client_concurrency в runtime metadata исправлен на [1]; прежний [1,2,4] был унаследован от LAB34, не измерялся в этой qualification. Первичные данные прежней попытки не переписываются.

## Проверка client schema до GPU

Вторая подготовительная сессия apple-qualification-retry-20261009 сохраняется blocked: общий driver path найден, но bounded LAB34 driver отклонил request extensions chat_template_kwargs/cache_prompt до отправки HTTP. Новый body удаляет эти два request extensions; cache_prompt=false закреплён server --no-cache-prompt, enable_thinking=true остаётся закреплённым server --chat-template-kwargs, остальные входы/параметры неизменны. Все шесть root/variant input файлов теперь проходят настоящую load_request проверку до любого native Campaign. Driver API allowlist не расширяется. Обе прошлые подготовки — failed client preparation, ноль HTTP-запросов; их native startup/cleanup и логи сохранены отдельно.

## Область и гипотеза

Это отдельная инфраструктурная сессия LAB35. Проверяем, завершат ли исходный Metal b8407 и дополнительный tensor/tile16 deployment одинаковые публичные chat/load fixtures на context 8192: отдельный warmup и три повтора каждого. Новый сравнительный вывод Mac/Ryzen и агентный pass не назначаются без свежей парной серии и LAB08/LAB09.

Основная будущая пара — unmodified Metal b8407 против Ryzen HIP/ROCm b8407: у HIP имеется LAB05 admission для этого GGUF. Vulkan — отдельная архивная дополнительная ветвь, не выбор победителя после новой серии. Mac tensor/tile16 — отдельный deployment со source patch; его нельзя объявить совпадающим исходником с unpatched Ryzen. Backend эффект не изолируется от OS/ISA/compiler/driver/power.

Общий GGUF: Qwen3.5-9B Q6_K, revision 3885219b6810b007914f3a7950a8d1b469d598a5, 7 458 301 152 bytes, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. Общий upstream commit 312cf03328496df9c56fe843952cf02a8964c59a. У Metal-standard нет tile16 patch и tensor capability ожидается false по старому probe; у дополнительной Metal-tensor ожидается true, версия/hashes отдельные. Binary/model/library hashes проверяются перед каждым fresh startup.

## Входы и порядок до запуска

Два JSON input файла закреплены до запуска: публичный LAB32 prompt «Ответь ровно LAB_READY без пояснений.» и содержимое load fixture LAB34. Model alias обоих унифицирован в lab-model; top_p1 явный в chat. Контекст8192, np 1, threads 8, batch 512 / ubatch 256, KV f16/f16, FA on, Jinja/no-context-shift, reasoning auto / enable_thinking=true, no-cache-prompt, temperature 0, seed 1, max_tokens 2048, non-streaming/no tools. Cache и outputcap внутри серии не меняются.

Порядок qualification: archive/bridge audit → Metal-standard fresh startup → chat warmup из одного запроса + r1/r2/r3 → load warmup из одного запроса + r1/r2/r3 → shutdown → аналогично Metal-tensor. Каждый measured repeat — один HTTP request, concurrency1; это проверка общих inputs, не повтор30минут и не повтор12requestblocks LAB34. Для chat content.strip() должен быть ровно LAB_READY; для load — непустой assistant content/usage/no toolcall; finish stop/length допустим. Length отдельно сохраняется, качество300 слов не оценено. Cold startup отдельно, warmup не входит в median3.

Если Ryzen access станет доступен, после отдельной регистрации проводятся новые paired измерения с чередованием стендов и fresh warmup. Выполненные односторонние Mac qualification repeats не считаются чередованной paired серией. Если access отсутствует, Ryzen и paired попытки not-run с причиной. Архивы LAB04/LAB30 позволяют audit artifact/basecommit/microbench, но не заменяют одинаковый HTTP prompt/runtime/usage. Архив LAB06 BF16/vLLM/SGLang не переносится на GGUF.

## Допуск и остановка

13 samples за ≥120 секунд до GPU требуют AC / mode 0 и допустимую memory state. Guardкаждые 2 s: free+speculative≥8GiB, pressurelevel1, pressurefree≥50%, swap0, RSS ≤24 GiB, allcollectorcommands exit0. HTTP deadline 300 s, p95 ≤240 s. Foreign LMStudio/Ollamamodels не загружены; inventoryкаждые ~20 s. Любая новая ошибка останавливает последующие Mac cases; owned server/client cleanup only, один SIGINT подlock, bounded exit 30 s→SIGKILLfallback. Power/cache/kernellimits и пользовательские приложения не меняются. Energy/thermal/TTFT/max GPUbudgetunknown. Никакого скачивания weights или обучения.

## Агентная часть

Шесть будущих T002/a2-janitor/Pi попыток (по3наhardware) not-run, пока bridge LAB08 и lifecycle LAB09 pending. Harness Pi 0.73.1 выбран заранее; существующийprofile поддерживает только anthropic/openai. Реальных агентных запусков и fake run.json нет. Бюджеты должны читаться изsealedtaskcontract, не копируются вcontroller. Нужны deploymentfingerprints и принятая сетьendpoint перед firstpilot. Hiddenchecks/контракты не читаются и не меняются.

## Доказательства и решение

Все bodies/config/responses/usage/finishreasons/latency, process/binaryhash, runtime/props/slots/log, macOS timeline/cleanup и sourceprovenance сохраняются. Offline audit — exercise, новые HTTPsteps — measurement. Пропуски/null имеют причину; copies не новыеmeasurement. Итог сессии blocked при отсутствии любой обязательной парной/агентной части, даже если обе Mac квалификации completed. Нельзя делать вывод о превосходстве агента по tokens/s.
