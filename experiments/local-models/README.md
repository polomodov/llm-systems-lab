# Локальные модели: Ryzen/Linux и Apple/macOS

Apple M5 Max / 128 GB / macOS имеет [отдельный маршрут LAB28–35 и профили](apple/README.md). Выбор: `--hardware apple-m5-max-128gb-macos` для `local:plan` и `local:engines`. Без флага используются приведённые ниже исходные Ryzen-файлы; автоматического определения стенда нет.

Это исследовательская кампания, а не десятая обвязка. Один локальный inference server будет обслуживать разные существующие обвязки; backend, модель и обвязка учитываются раздельно. Здесь пока **план**, без запусков моделей и экспериментальных результатов.

Для пошагового выполнения используйте [лабораторный практикум](../../docs/labs/README.md). `npm run lab:new -- --lab LAB02 --session first-pass` создаёт в `measurements/LAB02-first-pass/` пустой отчёт, manifest и таблицу измерений. Учебный manifest не заменяет `results/runs/<run-id>/run.json`; реальные агентные попытки записываются отдельно.

В расширенном практикуме ЛР25 сравнивает качество при разной квантизации, ЛР26 измеряет параллельную нагрузку. Общие ЛР20–27 тоже сохраняют отчёты в `measurements/`. [Учебные упражнения без API](../../docs/labs/practice.md) находятся отдельно в `practice/`; их синтетические traces не подтверждают аппаратную совместимость или качество модели. [lab:check](../../docs/labs/report-validation.md) проверяет комплектность отчётов и учёт неудачных/пропущенных попыток.

[`runbook.md`](runbook.md) — сводный операторский лист ЛР02–ЛР05 для одной сессии на стенде: те же команды с подставленными путями. Нормативны сами лаборатории; дрейф источников проверяется `sha256sum -c experiments/local-models/runbook.sources.sha256`.

- [Порядок тестирования и критерии отбора](../../docs/local-models.md).
- [Кандидаты, форматы весов и первичные источники](../../docs/local-model-candidates.md).
- [Linux preflight и runbook backend](../../docs/local-model-runtime.md).
- [Разные движки и ROCm/Vulkan](../../docs/local-inference-engines.md) — 12 профилей в `engines.json`; kernels и serving layers учитываются раздельно.
- `models.json` — датированный каталог кандидатов; размеры являются оценкой или метаданными файлов, не замерами RAM.
- `hardware.json` — аппаратная гипотеза и консервативные резервы памяти.

Из корня репозитория:

```bash
npm run local:plan
npm run local:plan -- --context 32768
npm run local:plan -- --format json
npm run local:engines
npm run local:plan -- --engine llama-cpp-rocm
npm run local:plan -- --engine vllm-rocm --model gpt-oss-20b
npm run local:plan -- --engine all --format json
```

После измерения доступной памяти можно пересчитать план, например:

```bash
npm run local:plan -- --memory-gib 125 --gpu-budget-gib 90
```

Числа последней команды — пример, не характеристики машины владельца. `--memory-gib` означает измеренный общий usable RAM; planner отдельно вычитает резерв ОС. `--gpu-budget-gib` — безопасный бюджет GPU allocation, установленный после preflight. Значения не меняют файл и не настраивают ОС.

`candidate` означает, что модель проходит грубый расчёт резервов; `conditional` — дополнительную оговорку каталога; `over-budget` — превышение выбранного бюджета. Ни один статус не означает, что модель уже помещалась на железе. Реальный KV/state, staging buffers, kernel workspace и ограничения единичной allocation выясняются запуском.

С `--engine` дополнительно появляются `artifact-required` (нужен собственный артефакт для выбранного движка, размеры/quant GGUF не используются) и `engine-memory-required` (веса GGUF известны, расход serving runtime пока неизвестен). `hardware_support` описывает документированную поддержку отдельно от `fit_verified=false`. Без `--engine` остаётся прежний расчёт GGUF; это не универсальная оценка всех движков.

Команда не скачивает веса, не обращается к серверу, не создаёт run records и не планирует фоновое выполнение. До агентных прогонов требуется локальный provider bridge: нынешние профили и egress допускают только перечисленные облачные API. Команда `run --provider local` пока не поддерживается.
