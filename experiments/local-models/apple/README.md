# Apple M5 Max / 128 GB / macOS

Второй стенд кампании локальных моделей. Это профили и методика; аппаратные прогоны ещё не выполнены. Матрица моделей общая с Ryzen, но совместимость архитектуры, размер MLX-артефакта и бюджет GPU проверяются заново. `hardware.json` фиксирует исходное наблюдение RAM и гипотезы резервов; архивируемый паспорт собирается в LAB28.

## Команды планирования

```sh
npm run local:engines -- --hardware apple-m5-max-128gb-macos
npm run local:plan -- --hardware apple-m5-max-128gb-macos
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine all --format json
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine llama-cpp-metal --context 8192
npm run local:plan -- --hardware apple-m5-max-128gb-macos --engine mlx-lm-metal
```

Без `--hardware` обе команды сохраняют Ryzen/Linux независимо от ОС, на которой запущены. `--engine all` относится только к выбранному стенду. Неизвестные hardware/engine — ошибка. Команды не устанавливают движки и не запускают модели.

У Apple `gpu_budget_gib=null`: `hardware-memory-required` означает, что конечный бюджет и headroom неизвестны. Плановые размеры весов/runtime/KV остаются видимыми. После LAB28 и smoke передайте измеренные числа через `--memory-gib` и `--gpu-budget-gib`; они не записываются в профиль и не меняют ОС. Даже числовая оценка сохраняет `fit_verified=false`.

Приоритет статусов: MLX требует своего артефакта (`artifact-required`); GGUF wrapper без калибровки runtime — `engine-memory-required`; известный GGUF/runtime при неизвестной памяти GPU — `hardware-memory-required`; только затем рассчитывается `candidate`, `conditional` или `over-budget`. Без `--engine` используется прежняя грубая GGUF-модель резервов, не универсальная оценка движков.

Все пять профилей имеют `hardware_support=conditional`: общая поддержка Apple Silicon не доказывает сочетание M5 Max, macOS, модели и pinned runtime. Ollama-профиль относится к GGUF/Metal; другой внутренний runner или формат требует отдельного условия. Для MLX не переносятся hashes, quant и размеры GGUF.

## Общий протокол Apple-работ

Маршрут: LAB01 → [LAB28](../../../docs/labs/LAB28-apple-hardware.md) → LAB29 → LAB30/LAB31 → LAB32 → LAB33/LAB34 → LAB35. Нужны Node.js ≥22, Python 3, Git; для сборки — CMake и Xcode Command Line Tools, для MLX — совместимый native arm64 Python. Установку зависимостей исполнитель выполняет отдельно, фиксируя версии. Rosetta и контейнерный GPU-инференс не являются условиями этого маршрута.

Каждая сессия создаётся через `lab:new`, без перезаписи прежней. До исполнения заполните `raw/protocol.md`, `protocol_recorded_at`, `conditions` и `planned_attempts` в manifest v2 по [формату отчёта](../../../docs/labs/report-validation.md). Измерения имеют `kind=measurement`, `run_id=null`; запущенная модель требует `evidence_class=experimental`. Агентные попытки требуют настоящих `run.json`. Начатые failures и неисполненные условия сохраняются с причинами. В TSV неизвестное значение оставляют пустым с `unavailable_reason`; в JSON — `null`.

Для каждой конфигурации: отдельный прогрев и три измеряемых повтора, одинаковые входы/output cap, sampling/reasoning, template, KV/state, slots и cache policy. Холодный старт учитывается отдельно. Не объединяйте новые процессы CLI с прогретым HTTP server в одну метрику. До LAB34 — один model server и concurrency 1. Рост контекста/нагрузки допускается после просмотра предыдущего результата, без автоматического рестарта или cloud fallback.

До серии зафиксируйте допустимые latency/errors, резерв памяти и политику swap. Базовый резерв ОС — 16 GiB; при критическом memory pressure, устойчивом росте swap, OOM, потере readiness или неподтверждённом GPU исполнении остановите серию. Не уменьшайте защитные лимиты macOS и не меняйте power mode внутри сравнения. `recommendedMaxWorkingSetSize` — рекомендация, не свободный heap; `vm_stat` free pages не равны всей доступной RAM. RSS и Metal/MLX allocations могут описывать пересекающиеся страницы.

Во втором терминале собирайте временной ряд (тот же `LAB_DIR`, запустить до опыта, остановить Ctrl-C после):

```sh
while true; do
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  vm_stat
  sysctl vm.swapusage
  memory_pressure -Q
  sleep 5
done > "$LAB_DIR/raw/macos-memory-series.txt" 2>&1
```

Это наблюдение, не генератор pressure: не используйте режимы искусственной нагрузки `memory_pressure`. Периодический сбор может пропустить peak; сохраняйте также runtime peak memory и `/usr/bin/time -l`. Показатель maximum resident set size в macOS time — bytes. Недоступную температуру/энергию отмечайте неизвестной: снижение скорости само по себе не доказывает throttling. Вывод `pmset -g custom` описывает настройки, не измеренную мощность.

Храните журналы как `.txt`: `.log` в репозитории игнорируются. Большие weights, исходники движков, build и venv оставляйте за пределами evidence, не коммитьте их. Архивируйте их версии, команды и hashes. `raw/` и manifest содержат только необходимое доказательство без секретов и серийных номеров устройства.

## Сдача

```sh
npm run lab:check -- --report "$LAB_DIR" --mode submission
npm run check
```

`ready_for_review` означает комплектность, а не правильность вывода. `blocked` с evidence — допустимая сдача, но не успешный аппаратный допуск. Provider bridge остаётся инженерной [LAB08](../../../docs/labs/LAB08-local-bridge.md); `run --provider local` пока не поддерживается.
