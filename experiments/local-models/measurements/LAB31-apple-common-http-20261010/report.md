# LAB31 — одинаковые HTTP-входы для GGUF и MLX

Сессия `apple-common-http-20261010`, статус **completed**. Common HTTP deployment comparison completed; difference applies to whole quantized deployments.

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. GGUF Q6_K revision 3885219b6810b007914f3a7950a8d1b469d598a5 / llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a tensor tile16 Metal против MLX affine 4-bit/group64 revision 938d8919941c6e7efd3c7150eff7fe9d12afa631 / MLX-LM 0.32.0 / MLX 0.32.3. Exact paths/bytes/hashes: [GGUF](raw/gguf-reference.json), [MLX runtime](raw/runtime-manifest.json), [artifacts](raw/artifact-manifest.json), [full MLX prestart pins](raw/prestart-pins.json). Две MLX safetensors shards не оцениваются по размеру GGUF. VLM artifact используется только для текста. Агентных episodes нет.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration закреплены commit до исполнения. Порядок GGUF → MLX, один собственный сервер. [Входы](raw/shared-inputs.json) совпадают по messages; temp 0, seed 1, top_p 1, output cap 256, thinking false, streaming/include_usage. На каждый вход — один прогрев и три повтора. Final сравнивается буквально, без trim и нормализации. Внутренние templates, token IDs и квантизация могут различаться: оцениваются целые deployments.

## Ход выполнения

[Контроллер](raw/run_common.py) проверяет model/native pins до Popen, отсутствие чужих моделей и порт. GGUF logs/props/slots проверяют M5/tensor/offload 33/33/context 8192. MLX observer проверяет actual default GPU, loaded native images и allocator. Resource guard каждые 2 с: free+spec ≥8 GiB, pressure level 1, swap 0, AC/mode 0, RSS ≤24 GiB, gap ≤15 с, deadline 900 с. HTTP клиент ограничен 120 с. Shutdown: один собственный SIGINT, 30 с, затем own kill при необходимости. ОС и чужие приложения не меняются.

## Результаты

Attempts: {"completed": 20, "failed": 0, "not-run": 0}. API readiness от Popen учитывается отдельно в [runtime summary](raw/runtime-summary.json). TTFT — первое непустое content delta, total — время до полного SSE; usage из первичного ответа.

| Deployment/case/repeat | Статус | Raw final | TTFT, с | Total, с | Input/output tokens |
| --- | --- | --- | --- | --- | --- |
| gguf/chat/1 | completed | 'LAB_READY' | 0.076437208 | 0.10879091599999999 | 21/3 |
| gguf/chat/2 | completed | 'LAB_READY' | 0.079898208 | 0.112745458 | 21/3 |
| gguf/chat/3 | completed | 'LAB_READY' | 0.081706333 | 0.113060208 | 21/3 |
| gguf/chat/warmup | completed | 'LAB_READY' | 0.07170083399999999 | 0.10350800000000002 | 21/3 |
| gguf/math/1 | completed | '2304' | 0.086885542 | 0.152877792 | 38/5 |
| gguf/math/2 | completed | '2304' | 0.078216958 | 0.140562958 | 38/5 |
| gguf/math/3 | completed | '2304' | 0.086700875 | 0.149507791 | 38/5 |
| gguf/math/warmup | completed | '2304' | 0.082754208 | 0.145564416 | 38/5 |
| mlx/chat/1 | completed | 'LAB_READY' | 0.080767291 | 0.10585329099999999 | 21/3 |
| mlx/chat/2 | completed | 'LAB_READY' | 0.079054667 | 0.10055858299999999 | 21/3 |
| mlx/chat/3 | completed | 'LAB_READY' | 0.077916083 | 0.09996825 | 21/3 |
| mlx/chat/warmup | completed | 'LAB_READY' | 0.743652667 | 0.7663239589999999 | 21/3 |
| mlx/math/1 | completed | '2304' | 0.091429333 | 0.13389720800000002 | 38/5 |
| mlx/math/2 | completed | '2304' | 0.08099204099999999 | 0.123695166 | 38/5 |
| mlx/math/3 | completed | '2304' | 0.08191833300000001 | 0.127045875 | 38/5 |
| mlx/math/warmup | completed | '2304' | 0.085290167 | 0.131980084 | 38/5 |

## Ошибки и ограничения

Все зарегистрированные попытки выполнены. Одинаковые messages не означают одинаковый prompt token count. Readiness /v1/models не подтверждает завершение загрузки MLX: model provider загружает веса по первому запросу, его warmup включает загрузку. Hashing заранее прогревает filesystem cache; cold cache не измерялся. Серии короткие, ресурсный collector сделал по одному sample: sampled RSS не называется истинным peak. Поле execution.accepted осталось false из-за неиспользуемого начального значения контроллера; исходный файл сохранён. Итоговый protocol_accepted в runtime summary выводится из полного attempt register, exit/SIGINT и отсутствия guard, а не из этого поля. GGUF резервирует context 8192; MLX short-input budget 8192 не является hard cap. Три повтора не доказывают статистическую эквивалентность. Энергия, температура и максимальный GPU budget неизвестны. Смена формата и quant исключает вывод о влиянии одного Metal/MLX backend.

## Вывод по гипотезе

Common HTTP deployment comparison completed; difference applies to whole quantized deployments. Вывод ограничен этими входами, настройками, версиями и состоянием памяти. Скорость HTTP примитива не означает качество автономного агента.

## Ответы на контрольные вопросы

1. Новая CLI-команда запускает новый процесс и может включать загрузку весов; здесь используется resident HTTP server, cold readiness отделена.
2. 4-bit MLX и GGUF Q6_K используют разные схемы квантования, упаковку, kernels и templates; эффект одного engine не изолирован.
3. RSS измеряет собственный server PID; MLX allocator active/cache/peak наблюдается отдельно. Суммировать пересекающиеся страницы нельзя.
4. /v1/models сообщает alias, но не удостоверяет bytes/revision/runtime. Нужны full prestart hashes, actual model path, native loaded images и pinned source.

## Комплект сдачи

Manifest v2, протокол, source registration, full model/native pins, raw inputs/SSE/finals/metrics, непрерывные ресурсы и cleanup сохранены. TSV хранит отдельные наблюдения с условиями. lab:check submission проверяет комплект; reviewer decision **не проверено**.
