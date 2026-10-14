# LAB08 — повтор local provider bridge на Mac, 12.10.2026

Статус **blocked**. Offline и Docker acceptance прошли; нативная квалификация остановлена ресурсным guard до первого chat. Новый T002 pilot не запускался.

## Паспорт выполнения

Apple M5 Max /128GiB /macOS26.5 (25F71), AC/power mode0; Qwen3.5-9B Q6_K, revision3885219b6810b007914f3a7950a8d1b469d598a5, GGUF SHA25691898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. llama.cpp b8407+tile16/Metal; deployment и все binary/library pins в [manifest](raw/deployment.json). Pi0.73.1, Docker29.5.2. Координатор Node24.19.0; npm12.2.0 из локального cache запускался через npm-cli.js, поскольку npm wrapper не совместим с расположением встроенного Node. Agent image остаётся прежним Node24.13.1.

Context8192/output2048, reasoning auto/thinking=true, temp0/seed1/top_p1, KVf16/f16, slot1, batch512/ubatch256, threads8/offload999, cache off. Исходная LAB08 20261009 не изменена. Путь аппаратного паспорта в deployment перенесён в текущий checkout; содержимое проверено по прежнему SHA256.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) сохранён до запуска. План: повтор software/Docker boundary, native startup/identity/chat/cleanup, stale guard после паузы координатора16s, затем один новый Pi/T002 pilot. При отказе native admission последующие действия не выполняются; повтор/смена условий не предусмотрены. Системные часы и power mode не менялись.

## Ход выполнения

Offline173 tests:171 passed,2 Docker-gated skipped. Обе Docker проверки выполнены отдельно и прошли: native Pi fragmented tool-call → bash tool-result → final,2 mock requests, cloud requests0; изоляция/control denial/cancel и внешний timeout проверены. Нативный server запущен после hash validation, startup identity принят; при следующей verify сработал ресурсный guard. Chat request не был отправлен. Stale pause не выполнена; pilot не создан.

## Результаты

| Проверка | Результат | Evidence |
| --- | --- | --- |
| B01–B10 software |171 passed /2 gated skipped |raw/unit-tests.txt |
| Local Docker |1 passed, native tool round-trip |raw/docker-local.txt |
| Cloud Docker boundary |1 passed |raw/docker-cloud.txt |
| Native admission |failed: free+speculative ниже8GiB |raw/native/resource-guard.json |
| Native stale /T002 pilot |not-run после admission failure |manifest.json |

На момент guard free+speculative **3.470GiB**, server RSS **7.360GiB**, swap **0bytes**, pressure level1/free percentage88%, AC/mode0. Это один sample, не peak/медиана. Показатели free+speculative и memory_pressure описывают разные категории памяти; этот отказ не доказывает исчерпание128GiB или OOM. Причина остаётся срабатыванием текущего консервативного порога, который в этой серии не менялся. [Startup proof](raw/native/startup-process.json) и [shutdown](raw/native/shutdown-process.json): own PID30509, один SIGINT, exit0, без SIGKILL.

## Ошибки и ограничения

Native admission началась и прервана; она не является успешной квалификацией новых stale guards. Модель загрузилась, но ни chat, ни agent-run не исполнены; поэтому run_ids пуст. Никакой скрытой проверки не читалось. Для продолжения нужен отдельно зарегистрированный опыт после освобождения памяти либо доказательное пересмотрение ресурсного admission. Отключение guard не выполнялось. Энергия/температура и независимый verdict неизвестны.

## Вывод по гипотезе

Данных недостаточно для полного допуска LAB08. Software/Docker подтверждают boundary в прежнем deployment. Нативное наблюдение подтверждает штатную остановку собственного сервера по guard; stale qualification и успешный T002 остаются pending.

## Ответы на контрольные вопросы

1. LAN allowlist недостаточен: нужны закреплённые host/port/path и запрет admin/cloud.
2. Alias не доказывает веса: deployment hashes и контролируемый PID/props/template подтверждают identity.
3. Model server вне2GiB task container: weights/KV требуют отдельной native памяти; agent остаётся ограниченным.
4. Backend входит в fingerprint вместе с build/hardware/protocol; смена Metal/Vulkan/ROCm — отдельное условие.
5. Mock проверяет transport/tools, качество T002 требует настоящего run и независимой оценки.
6. Отсутствие usage/энергии не равно0; swap0 здесь измерен, стоимость неизвестна.

## Комплект сдачи

Manifest/протокол/deployment, software/Docker outputs, native logs/startup/resource/shutdown, measurements.tsv и воспроизводимый qualification script сохранены. Старые failures не переписывались. Решение проверяющего: **не проверено**; blocked отчёт не является зачётом LAB08.
