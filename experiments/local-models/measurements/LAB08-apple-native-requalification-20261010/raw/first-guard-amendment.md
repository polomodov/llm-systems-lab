# Поправка сохранения первичного resource guard

Серия16K4/4HTTP остановилась при free+spec8358920192bytes(7.785GiB)<8GiB, pressure90%/level1/swap0. Реальная причина есть в последнем sample; следующая ps-проверка PID затёрла guard. Первичный отчёт/resource-guard не редактируем. Неизвестно, какой внешний процесс/кеш изменил free+spec; порог не ослабляем.

В новом supervisor first guard сохраняется, sample первой unsafe строки записывается в resource-guard.json, после guard polling прекращается. Пустой/нечисловой/нулевой psRSS теперь ошибка, не0измерения. Code revision отдельно закрепляется до запуска.

Новый допуск:120s без модели,2s samples, free+spec≥16GiB/ACmode0/pressurelevel1/freepercentage≥50/swap0/gap≤15s. После pass отдельный16Kretry warmup+3, idle20s, guards прежние8GiB/RSS24GiB; новыйactualpilot900s только после pass. Исходный failed16K и несостоявшийсяpilot сохраняются. При повторномresourcefail дальнейшийT002не запускается; independent аппаратные серии требуют ownadmission.
