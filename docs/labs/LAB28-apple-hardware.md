# ЛР28. Паспорт Apple M5 Max и unified memory

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Аппаратное измерение / `target-machine` |
| Время | 1–2 часа |
| Предпосылки | LAB01; сам M5 Max / 128 GB, native macOS |
| Минимум | Паспорт, два снимка памяти с интервалом 60 секунд, плановый бюджет и решение о допуске |

## Цель

Отделить физическую RAM, состояние памяти macOS и рекомендации Metal от реально доступного бюджета модели.

## Проверяемая гипотеза

Стенд соответствует заявленной конфигурации и пригоден для начального smoke одной модели с резервом ОС 16 GiB. Неизвестный GPU budget не считается подтверждением размещения.

## Подготовка

Прочитайте [общий Apple-протокол](../../experiments/local-models/apple/README.md). Создайте сессию и заполните протокол до сбора:

```sh
npm run lab:new -- --lab LAB28 --session apple-first
export LAB_DIR='experiments/local-models/measurements/LAB28-apple-first'
```

Никаких изменений лимитов памяти, macOS, Xcode или режима питания в ходе сбора. Данные серийного номера, UUID и полного списка приложений не требуются.

## Порядок выполнения

1. Сохраните минимальный паспорт. Ошибка команды остаётся в её файле и реестре статусов, а не заменяется нулём:

   ```sh
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, subprocess, sys
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   commands = {
       'os': ['sw_vers'], 'arch': ['uname', '-m'],
       'cpu': ['sysctl', 'machdep.cpu.brand_string', 'hw.ncpu', 'hw.memsize'],
       'gpu': ['system_profiler', 'SPDisplaysDataType'],
       'developer-path': ['xcode-select', '-p'], 'compiler': ['xcrun', 'clang', '--version'],
       'sdk': ['xcrun', '--show-sdk-version'], 'power': ['pmset', '-g', 'custom'],
       'memory-before': ['vm_stat'], 'swap-before': ['sysctl', 'vm.swapusage'],
       'pressure-before': ['memory_pressure', '-Q'],
   }
   status = {}
   for name, command in commands.items():
       try:
           p = subprocess.run(command, capture_output=True, text=True, timeout=60)
           body, code = p.stdout + p.stderr, p.returncode
       except (OSError, subprocess.TimeoutExpired) as e:
           body, code = str(e), None
       (raw / (name + '.txt')).write_text(body)
       status[name] = {'command': command, 'exit_code': code}
   (raw / 'collection-status.json').write_text(json.dumps(status, indent=2))
   PY
   ```

2. Проверьте `arm64`, имя SoC, CPU/GPU cores, версию/build macOS и SDK. `hw.memsize / 2**30` — физическая RAM в GiB; не делите это значение повторно как десятичные 128 GB. Сохраните ошибки `xcrun` как blocker сборки, не устанавливайте SDK незаметно в ходе опыта.

3. Если Command Line Tools готовы, получите рекомендацию Metal короткой программой. Она не выделяет память для модели:

   ```sh
   cat > "$LAB_DIR/raw/metal-device.swift" <<'SWIFT'
   import Metal
   import Foundation
   guard let device = MTLCreateSystemDefaultDevice() else {
       fputs("Metal device unavailable\n", stderr)
       exit(1)
   }
   let data: [String: Any] = [
       "name": device.name,
       "has_unified_memory": device.hasUnifiedMemory,
       "recommended_max_working_set_bytes": device.recommendedMaxWorkingSetSize,
       "max_buffer_length_bytes": device.maxBufferLength
   ]
   let encoded = try JSONSerialization.data(withJSONObject: data, options: [.prettyPrinted, .sortedKeys])
   print(String(decoding: encoded, as: UTF8.self))
   SWIFT
   xcrun swift "$LAB_DIR/raw/metal-device.swift" \
     > "$LAB_DIR/raw/metal-device.json" 2> "$LAB_DIR/raw/metal-device-errors.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/metal-device-exit.txt"
   ```

   Рекомендация working set и max buffer length имеют разный смысл; ни одна не является свободным бюджетом GPU. При ошибке сохраните `null` с причиной.

4. После 60 секунд обычного простоя повторите `vm_stat`, `sysctl vm.swapusage`, `memory_pressure -Q` в файлы `raw/*-after-idle.txt`. Запишите питание от сети/батареи и фоновые нагрузки. Не складывайте compressed, resident и GPU-память как независимые банки.

5. Зафиксируйте `gpu_budget_gib=null` до выбора обоснованного безопасного рабочего бюджета и smoke LAB30/31. Для первой небольшой модели опишите отдельно tentative ceiling и запас; не называйте его измеренным allocation limit. Команда должна показать неизвестный итоговый бюджет:

   ```sh
   npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --format json \
     > "$LAB_DIR/raw/initial-plan.json"
   ```

6. Решите, к каким следующим работам стенд допущен: сборка, подготовка артефактов, начальный smoke. Сохраните паспорт в `raw/hardware-snapshot.json` с единицами, путями к исходным файлам и явно неизвестным GPU budget; укажите его в `conditions.hardware_snapshot`.

## Таблицы результатов

| Показатель | Значение | Единица | Evidence / причина неизвестности |
| --- | --- | --- | --- |
| SoC / CPU cores / GPU cores | | | |
| macOS build / SDK / arm64 | | | |
| hw.memsize | | bytes / GiB | |
| Metal recommended working set / max buffer | | bytes | |
| Swap до / после; memory pressure | | bytes / исходный вывод | |
| Резерв ОС / рабочий GPU budget | | GiB | |
| Допуск к LAB30 / LAB31 | | | |

## Что сдать

Отчёт, TSV, manifest v2; `collection-status.json`, паспорт, вывод системных команд и Metal-пробы, план и протокол. Для недоступных команд — exit code и причина. `run.json` не нужен.

## Критерии завершения

- [ ] Подтверждены машина, ОС, архитектура и физическая память.
- [ ] Сохранены два снимка и условия питания.
- [ ] Рекомендация Metal не выдана за свободную память.
- [ ] Определены резерв, неизвестные поля и допуск/blocker каждой ветви.
- [ ] Выполнен `lab:check --mode submission` по общему протоколу.

## Контрольные вопросы

1. Почему 128 GB в названии и 128 GiB в sysctl нельзя автоматически трактовать одинаково на другом стенде?
2. Чем recommended working set отличается от свободного GPU budget?
3. Почему сумма RSS и Metal allocations может завышать расход?
4. Что доказывает паспорт, а что сможет показать только загрузка модели?

## Источники

- [MTLDevice.recommendedMaxWorkingSetSize](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize).
- [Apple M5 Pro и M5 Max: заявления производителя](https://www.apple.com/newsroom/2026/03/apple-debuts-m5-pro-and-m5-max-to-supercharge-the-most-demanding-pro-workflows/).
- Локальные `man vm_stat`, `man memory_pressure`, `man time`; версии и raw output приложить.
