# LAB28 — Паспорт Apple M5 Max и unified memory

Сессия: apple-first-20261007. Обязательный минимум выполнен; решение проверяющего не выставлено.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Дата / оператор | 07.10.2026; Codex по запросу владельца |
| Машина | Apple M5 Max, 18 CPU / 40 GPU cores, unified memory |
| ОС | macOS 26.5, build 25F71; native arm64 |
| Физическая RAM | 137438953472 bytes = 128 GiB |
| Toolchain | Command Line Tools; Clang 21.0.0; SDK 26.5 |
| Питание | AC Power; battery 100%; AC powermode=0 |
| Исходники | Commit 8ef1cef6b2a9dfed69ee9c1c75e22ed6996e84e3; новые отчёты вне commit |
| Предпосылка | LAB01-apple-prerequisite-20261007: подготовка и 30 synthetic tests |
| Модель / harness | Не применяются к аппаратному паспорту |

## Гипотеза и протокол до запуска

Протокол raw/protocol.md зарегистрирован до измерений. Проверялись идентичность стенда, наличие Metal/toolchain, два снимка памяти с интервалом ≥60 s и допуск дальнейших работ. Резерв ОС 16 GiB и исходный tentative ceiling 32 GiB — политики планирования. После наблюдения фонового изменения памяти рекомендуется первый smoke с суммарной оценкой weights/runtime/state ≤24 GiB, ниже предварительного потолка. Это решение анализа, а не изменённая задним числом гипотеза или измеренный GPU limit.

## Ход выполнения

1. Собраны версии ОС, arm64, SoC/cores/RAM, GPU, developer path/compiler/SDK, питание. Все десять inventory commands вернули exit 0. Из GPU JSON сохранены только поля GPU; display identities исключены. В power-source исключён необязательный идентификатор батареи.
2. Выполнена Swift-проба Metal без выделения памяти модели: exit 0, stderr пуст.
3. Скрипт raw/collect-memory.py снял vm_stat, swapusage и memory_pressure -Q дважды. Фактический интервал начала снимков — 60.014106875 s. Компиляция и synthetic tests завершены до интервала; стресс-нагрузка не запускалась. Фоновые приложения продолжали работать.
4. Сохранён initial-plan.json: effective GPU budget null, все строки hardware-memory-required. Дополнительная read-only проверка зависимостей обнаружила отсутствие CMake в PATH и native bundled Python 3.12.14.
5. Сохранены hardware-snapshot.json, TSV и hashes сырых доказательств. Повторные аппаратные измерения после прерывания чата не выполнялись.

## Результаты

| Показатель | До | После / значение | Единица | Evidence |
| --- | --- | --- | --- | --- |
| CPU / GPU cores | — | 18 / 40 | count | raw/cpu.txt, raw/gpu.txt |
| Физическая RAM | — | 128 | GiB | raw/cpu.txt |
| Metal recommended working set | — | 107.5200043 | GiB | raw/metal-device.json |
| Metal maxBufferLength | — | 80.6399994 | GiB | raw/metal-device.json |
| vm_stat free pages | 48.0638275 | 45.6169128 | GiB | raw/memory-before.txt, raw/memory-after-idle.txt |
| Swap used | 0 | 0 | bytes | raw/swap-before.txt, raw/swap-after-idle.txt |
| Swapouts counter | 0 | 0 | count | raw/memory-before.txt, raw/memory-after-idle.txt |
| memory_pressure reported free percentage | 95 | 95 | percent | raw/pressure-before.txt, raw/pressure-after-idle.txt |
| OS reserve — политика | — | 16 | GiB | raw/protocol.md |
| Рекомендуемый первый smoke — политика | — | ≤24 total | GiB | raw/hardware-snapshot.json |
| Свободный GPU allocation budget | — | null, не измерен | GiB | raw/hardware-snapshot.json |

95% из memory_pressure нельзя превращать в MemAvailable или 121.6 GiB гарантированно свободной памяти. Free pages из vm_stat — другой показатель. За минуту free pages изменились на −2.45 GiB без swap; фоновая память не постоянна. Рабочий GPU budget нельзя получить из recommended working set.

| Следующая работа | Допуск | Условия |
| --- | --- | --- |
| LAB29 | Допущена | Закрепить небольшие GGUF/MLX-артефакты, проверить SSD и hashes |
| LAB30 | Условный | Clang/SDK/Metal query готовы; нужны CMake, pinned build и веса из LAB29 |
| LAB31 | Условный | Native Python 3.12.14 доступен; нужны отдельное pinned окружение MLX/MLX-LM и weights |

## Ошибки и ограничения

Все обязательные аппаратные команды успешны. GPU allocation capacity, модельная совместимость, inference peak memory, энергия и thermal state не проверялись. CMake в текущем PATH отсутствует. Системный Python 3.9.6 отличается от bundled arm64 Python 3.12.14; версия окружения следующего опыта должна быть закреплена отдельно. Полный перечень фоновых приложений не собирался. LAB28 не подтверждает будущий успешный инференс.

## Вывод по гипотезе

Идентичность стенда и Metal unified-memory query подтверждены. В двух снимках нет swap, но есть фоновое изменение свободных страниц. Данных достаточно для подготовки артефактов LAB29 и осторожного будущего smoke после подготовки runtime. Свободный GPU budget остаётся null; никаких model fit или tokens/s не заявлено.

## Ответы на контрольные вопросы

1. Название комплектации 128 GB не задаёт точное число bytes; здесь sysctl измеряет 137438953472 bytes, то есть 128 GiB. На другом стенде нужна собственная проверка.
2. Recommended working set — рекомендация Metal по рабочему набору; свободный budget требует учёта занятости и фактической allocation-пробы.
3. RSS и GPU allocations могут ссылаться на одни физические страницы UMA; их сумма может учитывать память повторно.
4. Паспорт доказывает устройство, ОС, RAM и доступность API/toolchain. Только загрузка выбранной модели покажет совместимость kernels/формата, peak state, allocations и устойчивость.

## Комплект сдачи

- [x] Протокол, inventory/status, Metal source/output/exit, две memory snapshots сохранены.
- [x] Hardware snapshot, runtime manifest, TSV и hashes заполнены.
- [x] У каждого неизвестного поля есть причина; OS reserve и ceiling помечены политиками.
- [x] Определён допуск/blocker LAB29/30/31; модель не запускалась.
- [x] Контрольные вопросы и вывод заполнены.

Сдача проверяется lab:check --mode submission; reviewer_decision=null до независимого просмотра. Это не verdict агентской задачи.
