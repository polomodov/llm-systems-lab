# LAB34 — новое продолжение длительной серии

Сессия apple-sustained-resume-20261009; статус **in-progress, подготовка**.

## Паспорт выполнения

M5 Max / 128 GiB / macOS26.5; pinned Qwen3.5-9B Q6_K / llama.cpp b8407+tile16 / Metal. Context8192, один GPU-слот, параметры неизменны; точные hashes/config в протоколе. Агентных попыток нет, run_ids=[].

## Гипотеза и протокол до запуска

Свежий прогретый resident deployment c1 завершит ≥1800 секунд без ошибок и нарушения границ. Короткая матрица уже завершена в двух прошлых сессиях; повторяется только warmup и длительная серия. Все historical failures сохраняются; старые337секунд не прибавляются к новым1800. Протокол и source hashes закрепляются до запуска.

## Ход выполнения

Пять planned attempts: offline short-evidence-audit, startup, warmup2, sustained, shutdown. Требуются13 admission samples AC/mode0 за две минуты.

## Результаты

Нового инференса пока нет, TSV только с заголовком. История трёх учитываемых предыдущих сессий —150requests/7errors; copies не считаются новыми запросами.

## Ошибки и ограничения

Исторические failures остаются blocked; источник двух SIGKILL неизвестен, один stop вызван потерей AC. Новый resident process отличается от процесса успешных коротких клеток. TTFT/energy/temperature/max GPUbudgetunknown.

## Вывод по гипотезе

Данных недостаточно: новая длительная серия не начата.

## Ответы на контрольные вопросы

Будут дополнены после фактических измерений. Один server slot означает queue experiment; для whole throughput нужен весь wall interval; p95 коротких блоков грубый, thermal conclusions требуют thermal evidence.

## Комплект сдачи

Manifest/protocol подготовлены до запуска. Primary evidence, export и submission будут оформлены после серии. Структурная проверка не назначает аппаратный pass.
