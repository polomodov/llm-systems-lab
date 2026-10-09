# LAB35 — новый tensor-повтор с полными dylib pins

Сессия apple-tensor-pinned-20261009. Статус **in-progress, подготовка**.

## Паспорт выполнения

M5 Max /128GiB/macOS26.5/25F71/arm64, Qwen3.5-9B Q6_K, llama.cpp b8407 +tile16/Metal. Полные hashes/config в протоколе. Старые результаты не изменяются; run_ids=[].

## Гипотеза и протокол до запуска

Свежий tensor resident process завершит одинаковые chat/load fixtures с прогревом и тремя repeats после полного dylib preflight. Source hashes закрепляются до GPU-startup. Все23entryhashes проверяются вaudit и повторно перед Popen.

## Ход выполнения

11plannedattempts: pin-audit, startup, два warmup и по3repeats, shutdown. Питание/память проверяются13samples за≥120секунд; foreignmodel checks и boundedcleanup сохраняются.

## Результаты

Новых HTTPизмерений ещё нет; таблица TSV с заголовком. Предыдущая tensor серия с library gap — самостоятельная historical evidence, не источник новых successful counts.

## Ошибки и ограничения

Первичный library gap старогоTensor не закрывается задним числом. Новая scope не содержит Ryzen или agent attempts; полный LAB35 остаётся blocked. TTFT/energy/temperature/maxGPUbudget неизвестны.

## Вывод по гипотезе

Данных недостаточно до фактического повторения.

## Ответы на контрольные вопросы

Будут дополнены по новой серии. Динамически загружаемые библиотеки — часть build fingerprint; executable SHA сам по себе недостаточен.

## Комплект сдачи

Source protocol/manifest подготовлены до GPU-startup; logs/requests/responses/process pins и software checks будут оформлены после исполнения. Reviewer decision не назначен.
