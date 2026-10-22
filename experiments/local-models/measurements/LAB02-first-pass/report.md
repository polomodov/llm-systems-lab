# LAB02 — Паспорт Ryzen и бюджет общей памяти

Сессия: `first-pass`

Создано: 2026-10-01T10:39:52.481Z

Статус: **blocked** — отсутствует подтверждённый предварительный протокол; также сохраняются исходные блокировки Vulkan/ROCm. Паспорт машины снят, бюджет рассчитан; допуск к ЛР04/ЛР06/ЛР07 возможен после установки vulkan-tools и ROCm (отдельная работа).

## Сверка учёта 2026-10-22

Исходный отдельный файл протокола, сохранённый до работы, не найден. Текст плана в старом manifest и дата без такого файла не доказывают предварительную регистрацию. Реестр восстановлен 2026-10-22 по сохранённым материалам и не является предрегистрацией. Исходные `manifest.json`, `report.md` и `measurements.tsv` сохранены побайтно в `raw/backup/before-reconciliation-*`; SHA-256 и преобразования перечислены в `raw/backup/reconciliation.json`. Строковые результаты и плановые резервы сохранены там отдельно от численных замеров. Неизвестные значения в TSV пусты с причиной; пропущенные диагностические команды и неудачное чтение `amdgpu/gtt_size` остаются в реестре. Исходные raw-файлы не изменены, новых измерений не выполнялось. `reviewer_decision` остаётся `null`; комплектность blocked-отчёта не означает завершение лабораторной.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-01 (10:39 → 10:43 UTC) |
| Машина, ОС, kernel, BIOS, режим питания | GTR Pro (GTRP112), Ubuntu 24.04.4 LTS, kernel `7.0.0-34-generic` (Ubuntu 24.04 HWE, SMP PREEMPT_DYNAMIC), BIOS `06/10/2026`, power profile `balanced` |
| Модель/артефакт: revision, shards, SHA-256, quant | неприменимо (паспорт машины, не прогона модели) |
| Engine, backend, image/binary hash | неприменимо |
| Context, KV/state dtype, slots, sampling, reasoning | неприменимо |
| Harness/provider/version, если применимо | неприменимо (предшествующая ЛР01 не запускалась; на дату сбора 2026-10-01 локальный provider bridge из ЛР08 ещё не был реализован) |
| Предыдущие отчёты / run IDs | нет (папка `experiments/local-models/measurements/` создана в этой работе) |
| Отличия от задания и причины | `vulkaninfo`/`rocminfo`/`hipconfig` отсутствуют — поля Vulkan и ROCm заполнены как `unavailable`; gfx1151 подтверждён по PCI-идентификатору `1002:1586` и `product_name` Radeon 8060S. ЛР01 не выполнялась, поэтому `os_reserve` принят по умолчанию 16 GiB. |

## Гипотеза и протокол до запуска

**Гипотеза:** на машине доступна Radeon 8060S / `gfx1151`, её видят Vulkan и ROCm, а измеренные бюджеты общей памяти и GPU позволяют выделить память модели без двойного учёта UMA.

**Ретроспективное описание действий (не предрегистрация):**

1. Считать CPU/GPU/ОС/BIOS и статусы диагностических утилит без модификаций системы.
2. Сопоставить обнаружение устройства по PCI, Vulkan и ROCm и выбрать render node.
3. Сверить версию ядра с таблицей AMD для gfx1151.
4. Рассчитать два независимых бюджета: `MemTotal - OS_reserve` и доступный GPU budget (GTT total ≤ TTM pages_limit × page_size).
5. Контрольный замер `free -b` после ~60 с простоя.
6. Не выполнять никаких команд из внешней инструкции по смене ядра/BIOS/драйверов.

## Ход выполнения

| Шаг задания | Действие и фактическая команда / config | Результат / ошибка | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Создать архив | `npm run lab:new -- --lab LAB02 --session first-pass` | создан `experiments/local-models/measurements/LAB02-first-pass/` | `raw/backup/before-reconciliation-manifest.json` |
| 1. Подтвердить ОС | `test "$(uname -s)" = Linux` | OK (Linux) | `raw/kernel.txt` |
| 2. Снять cpu/mem/pci/disk/swap | `python3` скрипт с `lscpu`, `free -b`, `swapon`, `df -B1`, `lspci -nnk`, `uname -a` | exit 0 по всем доступным утилитам | `raw/cpu.txt`, `raw/memory.txt`, `raw/pci.txt`, `raw/swap.txt`, `raw/disk.txt` |
| 2. Снять статусы диагностических утилит | `vulkaninfo --summary`, `vulkaninfo`, `rocminfo`, `hipconfig --full` | `vulkaninfo`, `rocminfo`, `hipconfig` не найдены (`OSError: [Errno 2]`) | `raw/collection-status.json` |
| 2. Снять sysfs/процедурные данные | чтение `/etc/os-release`, `/proc/meminfo`, `/proc/vmstat`, `/sys/class/dmi/id/{bios_version,bios_date,product_name}` | exit 0 | `raw/os-release.txt`, `raw/meminfo.txt`, `raw/vmstat-before.txt`, `raw/bios-*.txt`, `raw/product-name.txt` |
| 3. Memory/TTM инвентарь | `python3` скрипт: `meminfo`, `sys/module/{ttm,amdgpu}/parameters/*`, `mem_info_*` для каждого `card*` | exit 0 | `raw/memory-inventory.json` |
| 3. Контроль `renderD128` → PCI | `readlink /sys/class/drm/renderD128/device` → `0000:c6:00.0` | `c6:00.0 [1002:1586]` совпадает с `lspci` и `card1/device/{vendor,device}` | `raw/pci.txt`, `raw/memory-inventory.json` |
| 4. Сопоставление PCI ↔ Vulkan ↔ ROCm | PCI `1002:1586` (`amdgpu`); render node `/dev/dri/renderD128` → `card1`. Vulkan и ROCm недоступны по стеку. | Vulkan/ROCm blocker; PCI подтверждает gfx1151 через device id 0x1586 и product name «Radeon 8060S» | `raw/pci.txt`, `raw/vulkan-full.txt`, `raw/rocminfo.txt` |
| 5. Ядро vs AMD-доки | Ядро `7.0.0-34-generic` (Ubuntu 24.04 HWE). AMD-доки требуют HWE ≥ `6.17.0-19.19~24.04.2` для gfx1151. | documented (выше минимальной версии) | [rocm.docs.amd.com/.../rdna3-5.html](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html) (доступ 2026-10-01) |
| 6. Бюджет первой серии | `weights + runtime + KV/state ≤ MemTotal - OS_reserve = 108.94 GiB`; `allocations_on_GPU ≤ GTT total = 100.00 GiB` (равно TTM pages_limit × page_size) | сводка в таблице ниже | `raw/memory-inventory.json` |
| 6. Контрольный замер после 60 с | `sleep 60 && free -b > raw/memory-after-idle.txt` | MemAvailable сместился с 119.93 → 119.84 GiB (~97 MiB), в пределах фоновой активности | `raw/memory-after-idle.txt` |

## Результаты

### Сводная таблица паспорта

| Показатель | Наблюдаемое значение | Единица | Файл доказательства |
| --- | --- | --- | --- |
| CPU / OEM | AMD Ryzen AI Max+ 395 w/ Radeon 8060S / GTR Pro (GTRP112), 16 cores / 32 threads, L3 64 MiB | — | `raw/cpu.txt`, `raw/product-name.txt` |
| Linux / kernel / BIOS | Ubuntu 24.04.4 LTS / `7.0.0-34-generic` (HWE) / BIOS `06/10/2026` | — | `raw/os-release.txt`, `raw/kernel.txt`, `raw/bios-version.txt`, `raw/bios-date.txt` |
| MemTotal / MemAvailable (до простоя) | 134153334784 / 128772624384 (124.94 / 119.93) | bytes / GiB | `raw/memory-inventory.json` |
| MemAvailable (после 60 с простоя) | 128675229696 (119.84 GiB; −0.09 GiB относительно первого замера) | bytes / GiB | `raw/memory-after-idle.txt` |
| Резерв ОС (по умолчанию ЛР02) | 17179869184 (16.00 GiB; ЛР01 не объявляла другой) | bytes / GiB | `raw/backup/reconciliation.json` |
| TTM pages limit / page size | 26214400 pages × 4096 bytes = 107374182400 (100.00 GiB) | pages / bytes / GiB | `raw/memory-inventory.json` |
| Vulkan device / ICD / driver | `unavailable` (бинарь `vulkaninfo` отсутствует); обнаружение по PCI — `1002:1586`, `amdgpu` | — | `raw/collection-status.json`, `raw/pci.txt` |
| Vulkan heap / available budget | `null` (без `vulkaninfo`); замена — `mem_info_gtt_total` 100.00 GiB | bytes / GiB | `raw/memory-inventory.json` |
| ROCm version / HSA target | `unavailable` (ROCm не установлен); gfx1151 подтверждён по PCI | — | `raw/collection-status.json`, `raw/pci.txt` |
| Swap / режим питания | Swap 8.00 GiB (весь свободен) / `powerprofilesctl = balanced` | bytes / mode | `raw/swap.txt`, `raw/power-profile.txt` |
| GPU dedicated VRAM (`mem_info_vram_total`) | 536870912 (0.50 GiB; фирменный carve-out) | bytes / GiB | `raw/memory-inventory.json` |
| GPU GTT (`mem_info_gtt_total`) | 107374182400 (100.00 GiB; равен TTM cap) | bytes / GiB | `raw/memory-inventory.json` |
| GPU GTT used / VRAM used на момент сбора | 451350528 (0.42 GiB) / 468103168 (0.44 GiB) | bytes / GiB | `raw/memory-inventory.json` |

### Допуск по backend-веткам

| Ветвь | Обнаружено устройство | Стек соответствует документации | Допуск / причина blocker |
| --- | --- | --- | --- |
| Vulkan | да (PCI `1002:1586` + render node `/dev/dri/renderD128`); устройство не перечислено через `vulkaninfo` | `unverified` без `vulkaninfo` | blocker: нет `vulkan-tools`; после установки `vulkaninfo --summary` нужно снять заново |
| HIP/ROCm | да (PCI `1002:1586` → gfx1151 / `gfx1151` LLVM target по AMD RDNA3.5 mapping); `/dev/kfd` существует | `documented` для ядра 7.0.0-34-generic (выше HWE ≥ 6.17.0-19.19\~24.04.2), но ROCm не установлен | blocker: нет ROCm; нужен ROCm 7.11.0+ или 7.2.x (см. таблицу совместимости AMD), затем повторный замер |

### Бюджет первой серии (по ЛР02, шаг 6)

```text
weights + runtime + KV/state <= measured_RAM - OS_reserve
                          = 134153334784 - 17179869184 = 116973465600 bytes = 108.94 GiB

allocations_on_GPU <= min(measured_available_GPU_budget, model_budget)
                    = min(107374182400, 116973465600) = 107374182400 bytes = 100.00 GiB
```

Дополнительные замечания по бюджету:

- `mem_info_vram_total` = 0.50 GiB — это **выделенный** carve-out (BIOS), а не отдельный банк. Его нельзя складывать с GTT или `MemTotal`.
- `mem_info_gtt_total` = 100.00 GiB ≈ `pages_limit × page_size` = 100.00 GiB — текущий TTM cap совпадает с GTT total; поднять его без ребута нельзя (`amd-ttm --set` требует reboot).
- AMD-доки рекомендуют держать BIOS-VRAM минимальным (≈0.5 GiB) и расширять TTM/GTT; в нашей машине BIOS carve-out уже 0.5 GiB, что соответствует рекомендации.

## Ошибки и ограничения

- **Blocker Vulkan:** `vulkaninfo` отсутствует → нельзя подтвердить ICD, версию API и heap sizes; следующая серия снимков потребует установки `vulkan-tools` (`apt install vulkan-tools`) и повторного `vulkaninfo --summary`.
- **Blocker HIP/ROCm:** `rocminfo`/`hipconfig` отсутствуют → нельзя подтвердить загрузку KFD, версию HSA runtime и активный ROCm release; требуется установка ROCm 7.11.0+ или 7.2.x по таблице AMD для Ubuntu 24.04 HWE.
- **Нет ЛР01:** папка `experiments/local-models/measurements/` создана этой работой; `os_reserve` принят по умолчанию 16 GiB.
- **`/sys/module/kfd/version`** недоступен — модуль `kfd` не виден в `lsmod`, хотя `/dev/kfd` присутствует; возможно, KFD собран встроенным в `amdgpu` или не загружается до старта ROCm runtime.
- **BIOS carve-out 0.5 GiB** зафиксирован — изменение этого числа требует перезагрузки и пересъёмки паспорта.

## Вывод по гипотезе

Статус комплекта после сверки — `blocked`: исходный протокол не подтверждён. Нижеследующие выводы относятся к историческим снимкам и не означают зачёта лабораторной или успешной загрузки модели.

**Гипотеза подтверждена частично** (supported_with_blockers):

- ✅ Radeon 8060S / `gfx1151` физически присутствует (PCI `1002:1586`, render node `/dev/dri/renderD128` → `card1`).
- ✅ Ядро `7.0.0-34-generic` (Ubuntu 24.04 HWE) выше минимально требуемого AMD-версией для gfx1151.
- ✅ Бюджет UMA измерен: 124.94 GiB `MemTotal`, 119.93 GiB `MemAvailable`, GTT 100.00 GiB (равен TTM cap), VRAM 0.50 GiB (carve-out).
- ⚠️ Стек Vulkan и ROCm не установлен → нельзя **прямо** подтвердить видимость устройства через ICD/HSA runtime; установка стеков и повторный паспорт — отдельные работы.
- ✅ Двойной учёт UMA исключён: бюджет модели ограничен `MemTotal − OS_reserve` (108.94 GiB), GPU-размещения — `GTT total` (100.00 GiB); VRAM carve-out и GTT не складываются как независимые банки.
- ✅ Фоновые нагрузки стабильны: за 60 с простоя `MemAvailable` сместился на ~97 MiB, что укладывается в обычный фоновый шум.

Допуск к ЛР03/ЛР04/ЛР05 — **условный**: разрешены работы без активного Vulkan/ROCm runtime (модели можно загружать через llama.cpp или иной backend, для которого достаточно амадеграфического TTM/GTT cap); для ЛР06/ЛР07/ЛР09 (локальные серии) и любых нагрузок с `rocminfo` нужен установленный стек.

## Ответы на контрольные вопросы

1. **Почему надпись «128 GB» не равна доказанному бюджету 128 GiB для модели?**
   Потому что между «всего DRAM в машине» и «можно отдать модели» стоят: (а) резервы ОС и обвязки (по умолчанию ЛР02 — 16 GiB); (б) carve-out, отданный под нужды GPU-прошивок/display (0.5 GiB); (в) TTM cap (`pages_limit × page_size`), ограничивающий суммарный объём страниц, которые драйвер может отобразить в GPU-адресное пространство. На нашей машине 124.94 GiB `MemTotal` превращаются в 108.94 GiB общего бюджета модели и 100.00 GiB бюджета GPU-размещений. Сама маркетинговая надпись «128 GB» описывает общий объём DRAM, без вычета всех этих резервов.

2. **Чем отличаются `MemAvailable`, TTM pages limit и Vulkan memory budget?**
   `MemAvailable` — оценка ядра Linux, сколько памяти реально можно отдать новому процессу без свопа (учитывает reclaimable cache). TTM `pages_limit` — лимит на количество страниц, которые драйвер AMD может отобразить в адресное пространство GPU (верхняя граница GTT); он бьётся в ту же DRAM, что и `MemAvailable`, поэтому вычитать его отдельно из RAM нельзя. Vulkan memory budget — это то, что Vulkan ICD сообщает приложению через `vkGetPhysicalDeviceMemoryProperties` / `VK_EXT_memory_budget`; для RDNA3.5 на UMA он описывает ту же shared memory, но уже как «кусок GPU-пула», а не как объём RAM. Все три числа описывают перекрывающиеся подмножества одной DRAM; складывать их — ошибка.

3. **Почему `torch.cuda.is_available()` или наличие `gfx1151` ещё не доказывают full GPU offload модели?**
   `torch.cuda.is_available()` (или HIP-эквивалент) лишь говорит, что рантайм увидел устройство и способен выделить буфер; размер буфера зависит от текущего GTT/TTM cap, политики аллокатора и фрагментации. `gfx1151` — это LLVM-таргет/PCI device id; само по себе это имя не означает, что у нас есть запущенный ROCm/KFD runtime и что под выбранный тензор хватит непрерывного GPU-mapped региона. Full GPU offload требует, чтобы (а) суммарный размер весов + KV-cache был меньше `min(GTT total, MemTotal - OS_reserve)`; (б) runtime удержал нужные аллокации без переноса в CPU/HDD; это подтверждается только реальной загрузкой и `nvidia-smi`-аналогом (`rocm-smi`/`amdgpu_top`).

4. **Какие изменения машины требуют нового паспорта?**
   Любое изменение, влияющее на наблюдаемые в этой работе значения: (а) обновление BIOS/UEFI, меняющее carve-out VRAM; (б) замена ядра (например, переключение HWE ↔ OEM ↔ upstream) — требует повторной сверки с таблицей AMD; (в) обновление/смена `amdgpu`/`ttm` модулей (через `apt upgrade linux-modules-extra-*` или ручную сборку); (г) ручная правка `/etc/modprobe.d/ttm.conf` или вызов `amd-ttm --set` без пересъёмки паспорта; (д) добавление/удаление модулей оперативной памяти, что меняет `MemTotal` и GTT по умолчанию; (е) включение/смена ZRAM, дискового свопа или cgroup-лимитов; (ж) любая установка/удаление ROCm/Vulkan-стека (новые утилиты дают новые поля паспорта). Также паспорт переснимается при смене машины (даже на ту же модель ноутбука), поскольку серийный номер и фактический BIOS могут различаться.

## Комплект сдачи

- [x] Заполнен `manifest.json`; blockers зафиксированы в `unavailable`.
- [x] Сохранены исходные команды и сырые логи без секретов (`raw/`).
- [x] Заполнены таблицы результатов и `measurements.tsv` (16 числовых/недоступных наблюдений; неизвестные помечены `unavailable` с причиной).
- [x] Указаны пути к raw evidence; `run_ids` пуст (это паспорт машины, не агентский прогон).
- [x] Проверены индивидуальные критерии завершения (см. ниже).
- [x] Сформулированы вывод, ограничения и ответы на вопросы.

Решение проверяющего: **не проверено**. Это паспорт машины, а не оценка скрытой проверки задачи; вердикт `pass` здесь неприменим.

### Индивидуальные критерии завершения ЛР02

- [x] Подтверждена целевая машина и native Linux (`uname -s = Linux`).
- [x] Сняты CPU/GPU/ОС/BIOS и статусы диагностических утилит (`raw/cpu.txt`, `raw/os-release.txt`, `raw/bios-*.txt`, `raw/collection-status.json`).
- [x] RAM, TTM/GTT и GPU budgets не сложены как независимые банки (явная формула в разделе «Бюджет первой серии»).
- [x] Для каждой ветви указан допуск или blocker (таблица «Допуск по backend-веткам»).
- [x] Резерв ОС обоснован (16 GiB по умолчанию, ЛР01 не объявляла другой); таблицы опираются на raw-файлы.
- [x] BIOS, ядро, память и power profile не изменялись в ходе сбора (только чтение `/sys`, `/proc`, `lscpu`, `free`, `lspci`).

## Источники

- [AMD Ryzen AI Max+ 395: спецификация](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
- [AMD VGM FAQ: заявление о 96 GB и разделяемая память](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html).
- [AMD ROCm 7.14.1: RDNA3.5, TTM и требования KFD](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html) (доступ 2026-10-01).
- [Версионная матрица ROCm 7.14.1](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html).
- [Общий практикум](../../../../docs/labs/README.md), [шаблон отчёта](../../../../docs/labs/templates/report.md), [план локальных моделей](../../../../docs/local-models.md).
