# Наблюдение в процессе до первого CLI опыта

Pinned Python CLI запускается через cli_entry.py/runpy mlx_lm, стандартный диспетчер generate; deprecated module mlx_lm.generate не используется. До/после команды observer проверяет default GPU/M5 и снимает точный mx.get_peak_memory в bytes. Generation/model/limits не патчатся, настройки не меняются. CLI stdout сохраняет штатные rounded GB/tokens/s; точный allocator peak отдельно, process RSS/time отдельно. Проба чтения get_wired_limit отсутствует в0.32.3, getter отмечен null; исходная diagnostic ошибка сохранена.
