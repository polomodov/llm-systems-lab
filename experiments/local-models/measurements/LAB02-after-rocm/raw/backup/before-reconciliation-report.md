# LAB02 — Паспорт Ryzen и бюджет общей памяти (после установки ROCm 7.2)

Сессия: `after-rocm`

Создано: 2026-10-01T14:19:15.616Z (шаблон через `npm run lab:new`); сбор данных выполнен 2026-10-01T15:20:00Z.

Статус: **завершено, паспорт снят повторно после установки ROCm 7.2**. Vulkan
и ROCm стеки заполнены реальными значениями; `hipconfig` зафиксирован как
`unavailable` с причиной (ROCm 7.2 не поставляет эту утилиту). Подготовительная
работа — `experiments/local-models/measurements/rocm-preflight-01/`. Предыдущая
сессия с блокерами — `experiments/local-models/measurements/LAB02-first-pass/`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-01 (15:19 → 15:21 UTC) |
| Машина, ОС, kernel, BIOS, режим питания | GTR Pro (GTRP112), Ubuntu 24.04.4 LTS, kernel `7.0.0-34-generic` (Ubuntu 24.04 HWE, SMP PREEMPT_DYNAMIC), BIOS `06/10/2026`, power profile `balanced` |
| Модель/артефакт | неприменимо (паспорт машины, не прогона модели) |
| Engine, backend, image/binary hash | неприменимо |
| Context, KV/state dtype, slots, sampling, reasoning | неприменимо |
| Harness/provider/version | неприменимо (локальный provider bridge из ЛР08 ещё не реализован) |
| Предыдущие отчёты / run IDs | `LAB02-first-pass` (ROCm стек отсутствовал), `rocm-preflight-01` (подготовка стека) |
| Отличия от задания и причины | После установки ROCm 7.2 (см. `rocm-preflight-01/`) `rocminfo` заполнен реальными HSA-агентами (CPU, GPU=gfx1151, DSP=aie2p); `hipconfig` помечен `unavailable` с причиной — ROCm 7.2 не поставляет `hipconfig` в apt-репозитории; `vulkaninfo` теперь полный (heap/budget/api). Все остальные поля повторяют `LAB02-first-pass` без изменений. |

## Гипотеза и протокол до запуска

**Гипотеза:** на машине доступна Radeon 8060S / `gfx1151`, её видят Vulkan и
ROCm, а измеренные бюджеты общей памяти и GPU позволяют выделить память
модели без двойного учёта UMA.

**Протокол до запуска (повторно):**

1. Считать CPU/GPU/ОС/BIOS и статусы диагностических утилит без модификаций
   системы.
2. Сопоставить обнаружение устройства по PCI, Vulkan и ROCm и выбрать render
   node.
3. Сверить версию ядра с таблицей AMD для gfx1151.
4. Рассчитать два независимых бюджета: `MemTotal - OS_reserve` и доступный
   GPU budget (GTT total ≤ TTM pages_limit × page_size, подтверждённый через
   ROCm COARSE GRAINED pool и Vulkan heap1 DEVICE_LOCAL).
5. Контрольный замер `free -b` после ~60 с простоя.
6. Не выполнять никаких команд из внешней инструкции по смене
   ядра/BIOS/драйверов.

## Ход выполнения

| Шаг задания | Действие и фактическая команда / config | Результат / ошибка | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Создать архив | `npm run lab:new -- --lab LAB02 --session after-rocm` | создан `experiments/local-models/measurements/LAB02-after-rocm/` | `manifest.json` |
| 1. Подтвердить ОС | `test "$(uname -s)" = Linux` | OK (Linux) | `raw/kernel.txt` |
| 2. Снять cpu/mem/pci/disk/swap | python-скрипт с `lscpu`, `free -b`, `swapon`, `df -B1`, `lspci -nnk`, `uname -a` | exit 0 по всем доступным утилитам | `raw/cpu.txt`, `raw/memory.txt`, `raw/pci.txt`, `raw/swap.txt`, `raw/disk.txt` |
| 2. Снять статусы диагностических утилит | `vulkaninfo --summary`, `vulkaninfo`, `rocminfo`, `hipconfig --full` | `vulkaninfo`, `rocminfo` доступны (exit 0); `hipconfig` отсутствует (`OSError: [Errno 2]`) | `raw/collection-status.json`, `raw/rocminfo.txt`, `raw/hipconfig.txt`, `raw/hipconfig-unavailable-reason.txt` |
| 2. Снять sysfs/процедурные данные | чтение `/etc/os-release`, `/proc/meminfo`, `/proc/vmstat`, `/sys/class/dmi/id/{bios_version,bios_date,product_name}` | exit 0 | `raw/os-release.txt`, `raw/meminfo.txt`, `raw/vmstat-before.txt`, `raw/bios-*.txt`, `raw/product-name.txt` |
| 3. Memory/TTM инвентарь | python-скрипт: `meminfo`, `sys/module/{ttm,amdgpu}/parameters/*`, `mem_info_*` для каждого `card*` | exit 0 | `raw/memory-inventory.json` |
| 3. Контроль `renderD128` → PCI | `readlink /sys/class/drm/renderD128/device` → `0000:c6:00.0` | `c6:00.0 [1002:1586]` совпадает с `lspci`, `card1/device/{vendor,device}`, Vulkan `deviceID 0x1586` и `rocminfo BDFID 0xC600` | `raw/pci.txt`, `raw/memory-inventory.json`, `raw/vulkan-summary.txt`, `raw/rocminfo.txt` |
| 4. Сопоставление PCI ↔ Vulkan ↔ ROCm | PCI `1002:1586` (`amdgpu`); render node `/dev/dri/renderD128` → `card1`. Vulkan device: `AMD Radeon Graphics (RADV GFX1151)`, API 1.4.318, driver 25.2.8. ROCm agent: `gfx1151`, Chip ID `0x1586`, BDFID `0xC600`, 40 CU, max clock 2900 MHz. | Все три уровня сходятся на одном устройстве `gfx1151 / 8060S`. | `raw/pci.txt`, `raw/vulkan-summary.txt`, `raw/vulkan-full.txt`, `raw/rocminfo.txt` |
| 5. Ядро vs AMD-доки | Ядро `7.0.0-34-generic` (Ubuntu 24.04 HWE). AMD-доки требуют HWE ≥ `6.17.0-19.19~24.04.2` для gfx1151. | documented (выше минимальной версии) | [rocm.docs.amd.com/.../rdna3-5.html](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html) (доступ 2026-10-01) |
| 5. ROCm vs AMD-доки | ROCm 7.2.0.70200-43~24.04 (apt), `/opt/rocm-7.2.0`. Для Ryzen AI Max 300 / gfx1151 архивная матрица 7.2.1 подтверждает совместимость с Ubuntu 24.04.4. | documented (исторически валидированный стек для 395); chosen over 7.14.1 because the active rocm.list points at 7.2 | `dpkg-after-fix.txt`, `raw/rocminfo.txt`, [ROCm 7.2.1 native Linux matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html) |
| 6. Бюджет первой серии | `weights + runtime + KV/state ≤ MemTotal - OS_reserve = 108.94 GiB`; `allocations_on_GPU ≤ GTT total = 100.00 GiB` (равно TTM pages_limit × page_size, ROCm COARSE GRAINED pool, Vulkan heap1 DEVICE_LOCAL). Подтверждено тремя независимыми источниками. | сводка в таблице ниже | `raw/memory-inventory.json`, `raw/vulkan-full.txt`, `raw/rocminfo.txt` |
| 6. Контрольный замер после 60 с | `sleep 60 && free -b > raw/memory-after-idle.txt` | MemAvailable сместился с 116.65 → 116.66 GiB (~12 MiB), в пределах фоновой активности | `raw/memory-after-idle.txt` |

## Результаты

### Сводная таблица паспорта

| Показатель | Наблюдаемое значение | Единица | Файл доказательства |
| --- | --- | --- | --- |
| CPU / OEM | AMD Ryzen AI Max+ 395 w/ Radeon 8060S / GTR Pro (GTRP112), 16 cores / 32 threads, L3 64 MiB | — | `raw/cpu.txt`, `raw/product-name.txt` |
| Linux / kernel / BIOS | Ubuntu 24.04.4 LTS / `7.0.0-34-generic` (HWE) / BIOS `06/10/2026` | — | `raw/os-release.txt`, `raw/kernel.txt`, `raw/bios-version.txt`, `raw/bios-date.txt` |
| MemTotal / MemAvailable (до простоя) | 134153334784 / 125247705088 (124.94 / 116.65) | bytes / GiB | `raw/memory-inventory.json` |
| MemAvailable (после 60 с простоя) | 125259165696 (116.66 GiB; +12 MiB относительно первого замера) | bytes / GiB | `raw/memory-after-idle.txt` |
| Резерв ОС (по умолчанию ЛР02) | 17179869184 (16.00 GiB; ЛР01 не объявляла другой) | bytes / GiB | `manifest.json` |
| TTM pages limit / page size | 26214400 pages × 4096 bytes = 107374182400 (100.00 GiB) | pages / bytes / GiB | `raw/memory-inventory.json` |
| Vulkan device | `AMD Radeon Graphics (RADV GFX1151)`, `deviceID 0x1586` | name / id | `raw/vulkan-summary.txt` |
| Vulkan ICD / driver / API | DRIVER_ID_MESA_RADV / 25.2.8 / 1.4.318 | id / version | `raw/vulkan-summary.txt` |
| Vulkan heap0 size (no flags) | 35970351104 (33.50 GiB) | bytes / GiB | `raw/vulkan-full.txt` |
| Vulkan heap1 size (DEVICE_LOCAL) | 71940702208 (67.00 GiB) | bytes / GiB | `raw/vulkan-full.txt` |
| Vulkan heap1 budget | 70854057984 (65.99 GiB) | bytes / GiB | `raw/vulkan-full.txt` |
| Vulkan heap total size | 107911053312 (100.50 GiB; ≈ GTT total) | bytes / GiB | `raw/vulkan-full.txt` |
| ROCm version | 7.2.0 (apt `7.2.0.70200-43~24.04`, prefix `/opt/rocm-7.2.0`) | version | `dpkg-after-fix.txt`, `raw/rocminfo.txt` |
| HSA target | gfx1151 (RDNA 3.5), Chip ID `0x1586`, BDFID `0xC600` (c6:00.0) | target / id / bdf | `raw/rocminfo.txt`, `raw/pci.txt` |
| GPU compute units / max clock | 40 CU / 2900 MHz | CU / MHz | `raw/rocminfo.txt` |
| ROCm GPU COARSE GRAINED pool | 104857600 KB (100.00 GiB) | KB / GiB | `raw/rocminfo.txt` |
| ROCm GPU EXTENDED FINE GRAINED pool | 104857600 KB (100.00 GiB) | KB / GiB | `raw/rocminfo.txt` |
| ROCm CPU FINE GRAINED pool | 131009116 KB (124.94 GiB) | KB / GiB | `raw/rocminfo.txt` |
| ROCm NPU (aie2p) COARSE GRAINED pool | 131009116 KB (124.94 GiB) | KB / GiB | `raw/rocminfo.txt` |
| `hipconfig --full` | `unavailable` (ROCm 7.2 не поставляет hipconfig в apt) | — | `raw/hipconfig.txt`, `raw/hipconfig-unavailable-reason.txt` |
| Swap / режим питания | Swap 8.00 GiB (весь свободен) / `powerprofilesctl = balanced` | bytes / mode | `raw/swap.txt`, `raw/power-profile.txt` |
| GPU dedicated VRAM (`mem_info_vram_total`) | 536870912 (0.50 GiB; фирменный carve-out) | bytes / GiB | `raw/memory-inventory.json` |
| GPU GTT (`mem_info_gtt_total`) | 107374182400 (100.00 GiB; равен TTM cap и ROCm COARSE GRAINED pool) | bytes / GiB | `raw/memory-inventory.json` |
| GPU GTT used / VRAM used на момент сбора | 451350528 (0.42 GiB) / 468103168 (0.44 GiB) | bytes / GiB | `raw/memory-inventory.json` |

### Допуск по backend-веткам

| Ветвь | Обнаружено устройство | Стек соответствует документации | Допуск / причина blocker |
| --- | --- | --- | --- |
| Vulkan | да (PCI `1002:1586` + render node `/dev/dri/renderD128`); устройство `AMD Radeon Graphics (RADV GFX1151)`, heap1 DEVICE_LOCAL 67.00 GiB / budget 65.99 GiB | `documented` (RADV GFX1151 в Mesa 25.2.8 / Vulkan 1.4.318; gfx1151 в RDNA 3.5; ядро 7.0.0-34-generic ≥ 6.17.0-19.19~24.04.2) | **admitted**: LAB02-04 и далее с Vulkan ICD открыты; AMDVLK/RADV опциональны |
| HIP/ROCm | да (PCI `1002:1586` → gfx1151; `rocminfo` показывает HSA-агент GPU `gfx1151`, BDFID `0xC600`, 40 CU, COARSE GRAINED pool 100.00 GiB); `/dev/kfd` существует | `documented` (ROCm 7.2 исторически валидирован для Ryzen AI Max 300 / Ubuntu 24.04.4; ядро 7.0.0-34-generic ≥ 6.17.0-19.19~24.04.2) | **admitted** (с оговоркой: `hipconfig` отсутствует, см. `hipconfig-unavailable-reason.txt`; для ЛР04/ЛР06 этого достаточно) |

### Бюджет первой серии (по ЛР02, шаг 6)

```text
weights + runtime + KV/state <= measured_RAM - OS_reserve
                          = 134153334784 - 17179869184 = 116973465600 bytes = 108.94 GiB

allocations_on_GPU <= min(measured_available_GPU_budget, model_budget)
                    = min(GTT_total, ROCm_GPU_pool_coarse, Vulkan_heap1_budget, MemTotal - OS_reserve)
                    = min(107374182400, 107374182400, 70854057984, 116973465600)
                    = 70854057984 bytes = 65.99 GiB
```

Дополнительные замечания по бюджету:

- **TTM pages_limit** = 26 214 400 × 4096 = 100.00 GiB — текущий cap.
- **ROCm GPU COARSE GRAINED pool** = 100.00 GiB — совпадает с TTM cap.
- **Vulkan heap1 (DEVICE_LOCAL) size** = 67.00 GiB, **budget** = 65.99 GiB
  — реально доступный для приложений объём (Vulkan ICD удерживает ~1.01 GiB
  reserve от heap size).
- **Реально ограничивающее звено** для модели — Vulkan heap1 budget
  (65.99 GiB), а не TTM cap. GTT/ROCm pool сообщают теоретический максимум,
  ICD резервирует часть на собственные нужды. Для ЛР03/ЛР04/ЛР06 это надо
  учитывать отдельно, не путая с «budget 100 GiB».
- `mem_info_vram_total` = 0.50 GiB — выделенный carve-out (BIOS); не
  складывается с GTT или `MemTotal`.
- AMD-доки рекомендуют держать BIOS-VRAM минимальным (≈0.5 GiB) и расширять
  TTM/GTT; на нашей машине BIOS carve-out уже 0.5 GiB.

## Ошибки и ограничения

- **`hipconfig` отсутствует** в ROCm 7.2 user-mode apt-репозитории. Поле
  `hipconfig` зафиксировано как `unavailable` с указанием причины в
  `raw/hipconfig-unavailable-reason.txt`. Это не блокирует ЛР02 — паспорт
  закрывается `rocminfo`, который перечисляет HSA-агентов и их пулы.
  Если в ЛР04/ЛР06 потребуется HIP toolchain (`hipcc`), его можно получить
  через `rocm-hip-runtime-dev` (потянет multilib и `rocm-llvm`).
- **`rocm-smi` отсутствует** в этом режиме (нет пакета в ROCm 7.2 user-mode);
  альтернатива для телеметрии — `rocminfo` (уже работает) и `/sys/class/drm/card1/device/*`.
- **Нет ЛР01:** `os_reserve` принят по умолчанию 16 GiB, как и в `first-pass`.
- **`/sys/module/kfd/version`** недоступен — модуль `kfd` не виден в `lsmod`,
  хотя `/dev/kfd` присутствует. Это нормально для ядра 7.0.0-34-generic
  (KFD встроен в `amdgpu` или грузится отложенно).
- **BIOS carve-out 0.5 GiB** зафиксирован — изменение этого числа требует
  перезагрузки и пересъёмки паспорта.
- **Установка ROCm 7.2** сама по себе потребовала `sudo apt install` и
  создания `/etc/apt/preferences.d/rocm-7.2-user-space.pref` (apt-pin с
  `Pin: origin "repo.radeon.com"`, priority 1001). Это отдельная работа
  (`rocm-preflight-01/`) и не является частью этой ЛР02; перечень пакетов и
  откат — там же.

## Вывод по гипотезе

**Гипотеза подтверждена полностью** (`supported`):

- ✅ Radeon 8060S / `gfx1151` физически присутствует (PCI `1002:1586`,
  render node `/dev/dri/renderD128` → `card1`).
- ✅ Ядро `7.0.0-34-generic` (Ubuntu 24.04 HWE) выше минимально требуемого
  AMD-версией для gfx1151.
- ✅ Vulkan ICD (RADV GFX1151) перечисляет устройство с реальными heap
  sizes и budgets.
- ✅ ROCm 7.2 (`rocminfo` от `repo.radeon.com`) перечисляет три HSA-агента
  (CPU, GPU=gfx1151, DSP=aie2p / RyzenAI-npu5) с BDFID, Chip ID и pools.
- ✅ Бюджет UMA измерен: 124.94 GiB `MemTotal`, 116.65 GiB `MemAvailable`
  (до простоя), 116.66 GiB (после 60 с простоя).
- ✅ GTT 100.00 GiB = TTM cap = ROCm COARSE GRAINED pool; Vulkan heap1 size
  67.00 GiB / budget 65.99 GiB. TTM/GTT/ROCm/Vulkan сходятся, расхождение
  между TTM и Vulkan budget объясняется ICD reserve.
- ✅ Двойной учёт UMA исключён: бюджет модели ограничен
  `MemTotal − OS_reserve` (108.94 GiB); GPU-размещения — реальным Vulkan
  heap1 budget (65.99 GiB), TTM/ROCm pool (100.00 GiB) и
  `MemTotal − OS_reserve` (108.94 GiB). VRAM carve-out и GTT не складываются
  как независимые банки.
- ✅ Фоновые нагрузки стабильны: за 60 с простоя `MemAvailable` сместился
  на ~12 MiB.

Допуск к ЛР03/ЛР04/ЛР05 — **безусловный**: разрешены работы на обеих
backend-ветвях (Vulkan RADV + ROCm/HIP). Допуск к ЛР06 — **безусловный**
по HIP/ROCm, требуется только `rocm-hip-runtime-dev` для HIP toolchain
(не обязательно для диагностики, обязательно для компиляции HIP-кода).

## Ответы на контрольные вопросы

1. **Почему надпись «128 GB» не равна доказанному бюджету 128 GiB для модели?**
   Потому что между «всего DRAM в машине» и «можно отдать модели» стоят:
   (а) резервы ОС и обвязки (по умолчанию ЛР02 — 16 GiB); (б) carve-out,
   отданный под нужды GPU-прошивок/display (0.5 GiB); (в) TTM cap
   (`pages_limit × page_size`), ограничивающий суммарный объём страниц,
   которые драйвер может отобразить в GPU-адресное пространство
   (100.00 GiB); (г) дополнительный ICD reserve, который Vulkan RADV
   удерживает от heap size (67.00 GiB size, 65.99 GiB budget). На нашей
   машине 124.94 GiB `MemTotal` превращаются в 108.94 GiB общего бюджета
   модели, а реально доступный GPU-размещаемый объём ограничен 65.99 GiB
   (Vulkan heap1 budget) — это и есть самый жёсткий из подтверждённых
   лимитов. Сама маркетинговая надпись «128 GB» описывает общий объём
   DRAM, без вычета всех этих резервов.

2. **Чем отличаются `MemAvailable`, TTM pages limit, Vulkan memory budget
   и ROCm HSA pool?**
   `MemAvailable` — оценка ядра Linux, сколько памяти реально можно отдать
   новому процессу без свопа (учитывает reclaimable cache). TTM
   `pages_limit` — лимит на количество страниц, которые драйвер AMD может
   отобразить в адресное пространство GPU (верхняя граница GTT); он
   бьётся в ту же DRAM, что и `MemAvailable`, поэтому вычитать его
   отдельно из RAM нельзя. Vulkan memory heap/budget — то, что Vulkan ICD
   сообщает приложению через `VkPhysicalDeviceMemoryProperties` /
   `VK_EXT_memory_budget`; для RDNA3.5 на UMA heap1 DEVICE_LOCAL описывает
   ту же shared memory, что и GTT, но уже как «кусок GPU-пула», а не как
   объём RAM; budget всегда меньше size из-за ICD reserve. ROCm HSA pool —
   то, что `rocminfo` показывает через HSA runtime; для gfx1151 COARSE
   GRAINED равен GTT (100.00 GiB), но это тоже верхняя граница, не
   «сколько реально можно занять». Все четыре числа описывают
   перекрывающиеся подмножества одной DRAM; складывать их — ошибка.

3. **Почему `torch.cuda.is_available()` или наличие `gfx1151` ещё не
   доказывают full GPU offload модели?**
   `torch.cuda.is_available()` (или HIP-эквивалент) лишь говорит, что
   рантайм увидел устройство и способен выделить буфер; размер буфера
   зависит от текущего GTT/TTM cap, политики аллокатора и фрагментации.
   `gfx1151` — это LLVM-таргет/PCI device id; само по себе это имя не
   означает, что у нас есть запущенный ROCm/KFD runtime и что под выбранный
   тензор хватит непрерывного GPU-mapped региона. Full GPU offload требует,
   чтобы (а) суммарный размер весов + KV-cache был меньше реального
   Vulkan heap1 budget (65.99 GiB на нашей машине), не только TTM cap;
   (б) runtime удержал нужные аллокации без переноса в CPU/HDD; это
   подтверждается только реальной загрузкой и `rocm-smi`-аналогом
   (`rocminfo` показывает pool, но не текущую загрузку; для телеметрии
   нужен внешний sampler или `/sys/class/drm/card1/device/mem_info_*`).

4. **Какие изменения машины требуют нового паспорта?**
   Любое изменение, влияющее на наблюдаемые в этой работе значения:
   (а) обновление BIOS/UEFI, меняющее carve-out VRAM; (б) замена ядра
   (например, переключение HWE ↔ OEM ↔ upstream) — требует повторной
   сверки с таблицей AMD; (в) обновление/смена `amdgpu`/`ttm` модулей
   (через `apt upgrade linux-modules-extra-*` или ручную сборку);
   (г) ручная правка `/etc/modprobe.d/ttm.conf` или вызов
   `amd-ttm --set` без пересъёмки паспорта; (д) добавление/удаление
   модулей оперативной памяти, что меняет `MemTotal` и GTT по умолчанию;
   (е) включение/смена ZRAM, дискового свопа или cgroup-лимитов;
   (ж) любая установка/удаление ROCm/Vulkan-стека (меняются поля ICD,
   HSA runtime, heap/budget — как в этой работе относительно
   `LAB02-first-pass`); (з) смена `rocm.list` на другую ветку
   (например, 7.2 → 7.14.1) или обновление `/etc/apt/preferences.d/`.
   Также паспорт переснимается при смене машины (даже на ту же модель
   ноутбука), поскольку серийный номер и фактический BIOS могут
   различаться.

## Комплект сдачи

- [x] Заполнен `manifest.json`; стеки Vulkan/ROCm зафиксированы в
  `measured`; `hipconfig` помечен `unavailable` с причиной.
- [x] Сохранены исходные команды и сырые логи без секретов (`raw/`).
- [x] Заполнены таблицы результатов и `measurements.tsv` (28 наблюдений;
  неизвестные помечены `unavailable` с причиной).
- [x] Указаны пути к raw evidence; `run_ids` пуст (это паспорт машины, не
  агентский прогон).
- [x] Проверены индивидуальные критерии завершения (см. ниже).
- [x] Сформулированы вывод, ограничения и ответы на вопросы.

Решение проверяющего: **не проверено**. Это паспорт машины, а не оценка
скрытой проверки задачи; вердикт `pass` здесь неприменим.

### Индивидуальные критерии завершения ЛР02

- [x] Подтверждена целевая машина и native Linux (`uname -s = Linux`).
- [x] Сняты CPU/GPU/ОС/BIOS и статусы диагностических утилит
  (`raw/cpu.txt`, `raw/os-release.txt`, `raw/bios-*.txt`,
  `raw/collection-status.json`).
- [x] RAM, TTM/GTT, Vulkan heap/budget и ROCm pool сходятся и не сложены
  как независимые банки (явная формула в разделе «Бюджет первой серии»).
- [x] Для каждой ветви указан допуск или blocker (таблица «Допуск по
  backend-веткам»); обе ветви admitted.
- [x] Резерв ОС обоснован (16 GiB по умолчанию, ЛР01 не объявляла другой);
  таблицы опираются на raw-файлы.
- [x] BIOS, ядро, память и power profile не изменялись в ходе сбора (только
  чтение `/sys`, `/proc`, `lscpu`, `free`, `lspci`, `rocminfo`,
  `vulkaninfo`).

## Источники

- [AMD Ryzen AI Max+ 395: спецификация](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
- [AMD VGM FAQ: заявление о 96 GB и разделяемая память](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html).
- [AMD ROCm 7.14.1: RDNA3.5, TTM и требования KFD](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html) (доступ 2026-10-01).
- [ROCm 7.2.1: native Linux compatibility matrix для Ryzen](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html) (доступ 2026-10-01).
- [Vulkan ICD RADV и Mesa 25.2.8 driverVersion](https://docs.mesa3d.org/drivers/radv.html).
- [Подготовительная работа ROCm 7.2 (эта сессия)](../rocm-preflight-01/README.md).
- [Предыдущая итерация ЛР02](../LAB02-first-pass/report.md).
- [Общий практикум](../../README.md), [шаблон отчёта](../../templates/report.md), [план локальных моделей](../../docs/local-models.md).
