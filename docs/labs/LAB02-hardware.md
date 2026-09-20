# ЛР 02. Паспорт Ryzen AI Max+ 395 и доступной памяти Linux

## Паспорт

| Поле | Значение |
| --- | --- |
| Время-ориентир | 45–90 минут при наличии диагностических утилит |
| Предпосылки | Выполнена ЛР 01; работа непосредственно на целевом Ryzen под Linux; Node.js и Python 3 доступны |
| Статус готовности | Инструкция готова; параметры машины и аппаратный smoke пока `unverified` |
| Результат | Паспорт CPU/GPU/ОС, исходные бюджеты RAM и GPU, решение о допуске к следующим работам |

Выполняйте команды из корня лабораторного репозитория на целевой Linux-машине. Эта работа читает состояние системы и создаёт архив наблюдений. Она не устанавливает пакеты, не меняет BIOS, ядро, TTM/GTT, драйверы или профиль питания.

## Цель

Установить фактическую конфигурацию Ryzen AI Max+ 395 и объём памяти, который можно безопасно запланировать под одну локальную модель, оставив резерв ОС и обвязке.

## Проверяемая гипотеза

На машине доступна Radeon 8060S / `gfx1151`, её видят Vulkan и ROCm, а измеренные бюджеты общей памяти и GPU позволяют выделить память модели без двойного учёта UMA. Наличие «128 GB» в описании компьютера само по себе эту гипотезу не подтверждает.

## Подготовка

- Закройте активные inference-процессы самостоятельно; не завершайте незнакомые пользовательские процессы.
- Запишите модель компьютера, режим питания, наличие питания от сети, активный рабочий стол и существенные фоновые нагрузки. Не публикуйте серийный номер.
- Выберите новый `session-id`. В примере это `my-session`; повторная работа получает другое имя.
- Отсутствующие `vulkaninfo`, `rocminfo`, `hipconfig` отмечайте как `unavailable`. Установка отсутствующего стека — отдельная работа, после которой паспорт снимают заново.

## Порядок выполнения

1. Создайте архив лабораторной и проверьте целевую ОС:

   ```sh
   npm run lab:new -- --lab LAB02 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB02-my-session'
   test "$(uname -s)" = Linux
   test -d "$LAB_DIR/raw"
   ```

   Если это macOS, WSL или другая машина, остановитесь и укажите причину в отчёте. Для этой серии требуется native Linux на Ryzen; чужой результат или виртуальная машина не заменяют паспорт владельца.

2. Снимите доступные сведения, сохраняя ошибки и отсутствующие утилиты. Скрипт не прерывает весь сбор, если один датчик недоступен:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib, subprocess, time
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   commands = {
       'time': ['date', '-u', '+%FT%TZ'],
       'kernel': ['uname', '-a'],
       'cpu': ['lscpu'],
       'memory': ['free', '-b'],
       'swap': ['swapon', '--show', '--bytes'],
       'disk': ['df', '-B1', '.'],
       'pci': ['lspci', '-nnk'],
       'vulkan-summary': ['vulkaninfo', '--summary'],
       'vulkan-full': ['vulkaninfo'],
       'rocminfo': ['rocminfo'],
       'hipconfig': ['hipconfig', '--full'],
       'power-profile': ['powerprofilesctl', 'get'],
   }
   status = {}
   for name, argv in commands.items():
       try:
           result = subprocess.run(argv, capture_output=True, text=True, timeout=45)
           output = result.stdout + result.stderr
           status[name] = {'command': argv, 'exit_code': result.returncode}
       except (OSError, subprocess.TimeoutExpired) as error:
           output = str(error) + '\n'
           status[name] = {'command': argv, 'exit_code': None, 'reason': str(error)}
       (root / (name + '.txt')).write_text(output)
   for name, source in {
       'os-release': '/etc/os-release',
       'meminfo': '/proc/meminfo',
       'vmstat-before': '/proc/vmstat',
       'bios-version': '/sys/class/dmi/id/bios_version',
       'bios-date': '/sys/class/dmi/id/bios_date',
       'product-name': '/sys/class/dmi/id/product_name',
   }.items():
       try:
           (root / (name + '.txt')).write_text(pathlib.Path(source).read_text())
       except OSError as error:
           status[name] = {'exit_code': None, 'reason': str(error)}
   (root / 'collection-status.json').write_text(json.dumps(status, indent=2))
   PY
   ```

3. Прочитайте только доступные sysfs-параметры UMA и пересчитайте единицы. Скрипт сохраняет как исходные байты, так и GiB; параметры TTM остаются отдельными от объёма RAM:

   ```sh
   python3 - <<'PY'
   import glob, json, os, pathlib, re
   result = {'page_size_bytes': os.sysconf('SC_PAGE_SIZE'), 'memory': {}, 'sysfs': {}}
   for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
       key, value = line.split(':', 1)
       if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
           count = int(value.split()[0]) * 1024
           result['memory'][key] = {'bytes': count, 'GiB': count / 2**30}
   paths = [
       '/sys/module/ttm/parameters/pages_limit',
       '/sys/module/ttm/parameters/page_pool_size',
       '/sys/module/amdgpu/parameters/gtt_size',
   ]
   for card in glob.glob('/sys/class/drm/card*'):
       if re.fullmatch(r'card\d+', pathlib.Path(card).name):
           paths.extend(str(path) for path in pathlib.Path(card, 'device').glob('mem_info_*'))
           paths.extend([card + '/device/vendor', card + '/device/device'])
   for source in sorted(set(paths)):
       try:
           result['sysfs'][source] = {'value': pathlib.Path(source).read_text().strip()}
       except OSError as error:
           result['sysfs'][source] = {'value': None, 'reason': str(error)}
   target = pathlib.Path(os.environ['LAB_DIR']) / 'raw' / 'memory-inventory.json'
   target.write_text(json.dumps(result, indent=2))
   print(json.dumps(result['memory'], indent=2))
   PY
   ```

   `pages_limit × page_size_bytes` — предел страниц TTM, а не гарантированно свободная память GPU. Не складывайте его с `MemTotal`, VRAM или GTT. Shared UMA, dedicated carve-out и API heap могут описывать пересекающуюся физическую память.

4. Сопоставьте три уровня обнаружения: PCI/драйвер, Vulkan device и HSA/ROCm device. Найдите Radeon 8060S в `vulkan-full.txt`, `gfx1151` в `rocminfo.txt`, активный `amdgpu` в `pci.txt`. Программный Vulkan renderer не засчитывается как GPU. Сохраните имена ICD, версии API/драйвера, heap sizes и budgets, если они присутствуют. Если есть несколько устройств, укажите выбранное и его render node; не предполагается, что это всегда `/dev/dri/renderD128`.

5. Сопоставьте ядро и ROCm с **версией** документации AMD. Для gfx1151 AMD описывает необходимые исправления KFD; перечислены Ubuntu HWE от `6.17.0-19.19~24.04.2`, OEM от `6.14.0-1018`, остальные дистрибутивы от `6.18.4` для указанной таблицы prebuilt. Проверьте backports и ограничения своего релиза. Запишите URL, дату доступа и вывод: `documented`, `conditional` либо `unverified`. Никакие команды смены ядра из внешней инструкции в этой работе не выполняются.

6. Запишите бюджет первой серии в отчёт: фактическая RAM, резерв ОС/обвязки, отдельно доступный GPU budget и источник каждого числа. Начальный резерв ОС — 16 GiB, если в ЛР 01 не объявлен другой. Предварительная модельная оценка должна удовлетворять обоим ограничениям:

   ```text
   weights + runtime + KV/state <= measured_RAM - OS_reserve
   allocations_on_GPU <= measured_available_GPU_budget
   ```

   Если budget API не предоставляет, оставьте его неизвестным: последующая проба загрузки нужна для подтверждения. Не подставляйте 96 GB из рекламы вместо наблюдения. Через минуту обычного простоя выполните повторное измерение; заметное изменение требует описать фоновые нагрузки:

   ```sh
   free -b > "$LAB_DIR/raw/memory-after-idle.txt"
   ```

7. Заполните `report.md`, `measurements.tsv` и черновой `manifest.json`, созданные helper. Укажите зависимости на архив ЛР 01 и пути к raw evidence. Не преобразуйте паспорт в `run.json` и не присваивайте ему verdict агентской задачи.

## Таблицы результатов

Пустые ячейки заполняются после выполнения. Неизвестное оформляется как `null` с причиной в отчёте.

| Показатель | Наблюдаемое значение | Единица | Файл доказательства |
| --- | --- | --- | --- |
| CPU / OEM | | | |
| Linux / kernel / BIOS | | | |
| MemTotal / MemAvailable | | bytes и GiB | |
| Резерв ОС | | GiB | |
| TTM pages limit / page size | | pages / bytes | |
| Vulkan device / ICD / driver | | | |
| Vulkan heap / available budget | | bytes и GiB | |
| ROCm version / HSA target | | | |
| Swap / режим питания | | | |

| Ветвь | Обнаружено устройство | Стек соответствует документации | Допуск / причина blocker |
| --- | --- | --- | --- |
| Vulkan | | | |
| HIP/ROCm | | | |

## Что сдать

- `report.md`: паспорт, расчёт резервов, решение о допуске и ответы на вопросы.
- `measurements.tsv`: измеренные числовые поля с единицами.
- `manifest.json`: идентификатор сессии и ссылки на доказательства; это лабораторный черновик.
- `raw/collection-status.json`, `raw/memory-inventory.json`, `raw/meminfo.txt`, `raw/kernel.txt`, `raw/os-release.txt`, `raw/pci.txt`, `raw/vulkan-full.txt`, `raw/rocminfo.txt`, `raw/hipconfig.txt`, `raw/memory-after-idle.txt`; для недоступных данных — сохранённая причина.

## Критерии завершения

- [ ] Подтверждена целевая машина и native Linux.
- [ ] Сняты CPU/GPU/ОС/BIOS и статусы диагностических утилит.
- [ ] RAM, TTM/GTT и GPU budgets не сложены как независимые банки.
- [ ] Для каждой ветви указан допуск или конкретный blocker, включая неизвестное.
- [ ] Резерв ОС обоснован; таблицы опираются на raw-файлы.
- [ ] BIOS, ядро, память и power profile не изменялись в ходе сбора.

Работу можно сдать с blocker одного backend: это корректный результат диагностики, а не успешный допуск к его измерениям.

## Контрольные вопросы

1. Почему надпись 128 GB не равна доказанному бюджету 128 GiB для модели?
2. Чем отличаются `MemAvailable`, TTM pages limit и Vulkan memory budget?
3. Почему `torch.cuda.is_available()` или наличие `gfx1151` ещё не доказывают full GPU offload модели?
4. Какие изменения машины требуют нового паспорта?

## Источники

- [AMD Ryzen AI Max+ 395: спецификация](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
- [AMD VGM FAQ: заявление о 96 GB и разделяемая память](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html).
- [AMD ROCm 7.14.1: RDNA3.5, TTM и требования KFD](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html).
- [Версионная матрица ROCm 7.14.1](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html).
- [Общий практикум](README.md), [шаблон отчёта](templates/report.md), [план локальных моделей](../local-models.md).
