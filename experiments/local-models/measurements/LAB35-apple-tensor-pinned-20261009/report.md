# LAB35 — новый tensor-повтор с полными хешами dylib

Сессия `apple-tensor-pinned-20261009`; статус **completed для отдельного tensor-повтора**. Полный LAB35 по-прежнему ждёт Ryzen-пару и агентную часть.

## Паспорт выполнения

Apple M5 Max / 18 CPU / 40 GPU / 128 GiB / macOS 26.5 (25F71) / arm64; питание AC / mode 0. Qwen3.5-9B Q6_K, revision `3885219b6810b007914f3a7950a8d1b469d598a5`, 7 458 301 152 bytes; SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`.

Llama.cpp base commit `312cf03328496df9c56fe843952cf02a8964c59a` / b8407 и tile16 patch `561c77562a5caad4772bfc0fcf078f9b1c354296e310300c7b460e635f368863`. [Версии и все хеши сборки](raw/metal-tensor/build-reference.json), [аппаратный снимок](raw/apple-hardware.json). Context 8192, один server slot, threads 8, batch 512 / ubatch 256, KV f16/f16, FA on, Jinja / no-context-shift, reasoning auto / enable_thinking=true, no-cache-prompt. Output cap 2048, temperature 0 / seed 1 / top_p 1; non-streaming, без tools. [Фактическая команда](raw/metal-tensor/runtime-manifest.json). Agent harness не запускался; `run_ids=[]`.

## Гипотеза и протокол до запуска

Свежий tensor-процесс завершит общие chat/load запросы с прогревом и тремя повторами после полной проверки библиотек сборки. Отсутствующий или изменённый dylib запрещает запуск. Все пути файлов версий и linker aliases закреплены отдельно; 21 dylib path относится к семи семействам, а не к 21 различной библиотеке.

[Протокол](raw/protocol.md), [source registry](raw/registered-source-hashes.json), controller и offline exporter закреплены до старта в commit `76ad1b3b70daa519d1f2bb3c873859432f76be47`. [Регистрация](raw/preregistration.json) и [13 безопасных снимков за ≥120 секунд](raw/preflight-power.jsonl) предшествуют запуску модели. Входы побайтно совпадают с прежней LAB35; [источник и их SHA-256](raw/prior-reference.json).

## Ход выполнения

Pin audit → новый startup → chat warmup/r1/r2/r3 → load warmup/r1/r2/r3 → штатный shutdown. Каждый шаг содержит один HTTP-запрос при concurrency 1; startup и прогревы исключены из медиан. OS page cache не сбрасывался. Memory/power guard и проверки других загруженных моделей действовали во время серии.

Pin audit: `2026-10-09T21:03:43.776378+00:00`. Повторная проверка 23 хешей: `2026-10-09T21:03:46.986112+00:00`. Вызов Popen: `2026-10-09T21:03:46.986269+00:00`. [Startup record](raw/metal-tensor/startup-process.json) содержит оба executables и все 21 dylib path; [audit](raw/pin-audit-execution.json) совпадает с reference.

Попытки: {'completed': 11}. Новые HTTP-запросы: 8, transport/probe errors: 0. Semantic contracts проверены отдельно по первичным ответам. [Manifest](manifest.json), [summary](raw/summary.json).

## Результаты

| Вход | Три измеряемых повтора | Median HTTP latency, s | Median completion tokens/s | Completion tokens r1/r2/r3 |
| --- | --- | --- | --- | --- |
| chat | completed | 3.937 | 61.442 | [242, 242, 242] |
| load | completed | 39.085 | 52.395 | [2048, 2048, 2048] |

Latency — полное время HTTP-ответа. Tokens/s — completion usage / полный wall одного запроса, включая prefill и HTTP; это не decode-only скорость. Все восемь bodies, responses, usage, summaries и contracts сохранены; 56 строк TSV включают прогревы, а таблица медиан — только r1–r3.

| Native RSS peak, GiB | Min free+speculative, GiB | Max swap, bytes | Pressure levels | Native exit / SIGINT |
| --- | --- | --- | --- | --- |
| 7.642 | 23.747 | 0 | [1] | 0 / 1 |

`libraries_verified_at_execution=true`, `pins_checked_before_popen=true`; missing library pins: 0. [Native log](raw/metal-tensor/server.txt) подтверждает Apple M5 Max / offload 33/33 / tensor capability=true. Finish reasons, включая прогревы: {'stop': 4, 'length': 4}.

## Ошибки и ограничения

Прежний [tensor-процесс LAB35](../LAB35-apple-http-preregistered-20261009/report.md) проверял только executables: его `libraries_verified_at_execution=false` сохранён. Нынешнее совпадение хешей не устанавливает идентичность библиотек уже завершившегося процесса. Этот повтор — отдельные запуск и доказательства; архивные результаты не включены в его counts.

Load требует непустого assistant content и полного usage; finish length допустим, качество 300 слов не проверено. Tensor capability в startup log не доказывает применение tensor kernel каждым оператором. Сравнения скоростей с standard Metal здесь нет; нет чередованной Ryzen-пары, LAB08/LAB09 и агентных verdicts. TTFT, энергия, температура, maximum GPU budget и Ryzen/agent ratios остаются null с причинами. RSS не равен Metal allocation. Новая короткая серия не повторяет 30 минут LAB34 и не подтверждает его исторические библиотеки.

## Вывод по гипотезе

**Гипотеза отдельного повтора поддержана:** свежий tensor deployment выполнил chat/load с прогревом и тремя повторами при полном pre-start library fingerprint, соблюдении guards и штатном cleanup. Полный LAB35 не завершён.

## Ответы на контрольные вопросы

1. **Почему SHA executable недостаточен?** Он не фиксирует исполняемый код динамических библиотек. До нового запуска проверены все bundled dylib paths и executable hashes; ОС закрепляет условия системных frameworks.
2. **Можно ли подтвердить старый процесс новым хешированием?** Нет: нынешний файл не доказывает состояние файла при старом запуске. Нужен самостоятельный опыт с проверкой до запуска.
3. **Что подтверждает tensor log?** Обнаружение capability этой сборкой на M5 Max и GPU offload. Применение kernel каждым оператором из него не следует.
4. **Почему успешные HTTP-запросы не закрывают LAB35?** Для сравнения нужны свежие сопоставимые Ryzen-повторы и реальные агентные runs с принятым bridge. Здесь их нет.
5. **Что ещё нужно для оценки стоимости?** Измеренная энергия и тариф, амортизация, затраты оператора и результат агентной задачи. Model API price=0 не заменяет эти величины.

## Комплект сдачи

Offline Python tests: 60; npm test: 152 passed / 1 skipped (Docker gate). npm run check, lab:check submission и git diff --check прошли. [Проверки](raw/software-validation.json).

Manifest v2, протокол и source pins, preregistration commit, pin audit, runtime/native logs, requests/responses/usage/contracts, memory timeline, cleanup, TSV и SHA inventories сохранены. [Primary inventory](raw/primary-evidence-sha256.json) защищает первичные данные при offline replay. Submission проверяет комплектность, не назначает экспериментальный verdict. Reviewer decision: **не проверено**.
