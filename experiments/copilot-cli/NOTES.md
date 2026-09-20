# Заметки · GitHub Copilot CLI

Экспериментальных прогонов пока нет.

20.09.2026 — инфраструктура без API и ключей: Docker Engine 29.5.2 / Linux arm64, пакет `@github/copilot@1.0.86`, Node base `24.13.1-bookworm-slim`. Сборка с `--ignore-scripts` успешна. Offline version/help и вызов argv адаптера проверены; без ключа получен ожидаемый отказ авторизации. Read-only контейнер требует отдельный exec tmpfs для native cache; общий `/tmp` не расширен.

В установленном официальном пакете проверен JSONL formatter `app.js`: терминатор CLI содержит `exitCode`, а события SDK `assistant.usage` / `session.shutdown` фильтруются. Тесты используют этот формат. Реальные token totals, стоимость USD и наблюдаемый ID модели пока не подтверждены. Источники и команды — [README](README.md). Первый эпизод должен проверить provider egress, полноту turn events и влияние вспомогательных моделей; записать run ID здесь и в `results/runs/`.

Повторная проверка ограничения native cache: с `/tmp:rw,nosuid,noexec,size=512m,mode=1777`, `/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777`, памятью 2 GiB и UID 1000 версия проходит. Минимальный проверенный успешный размер native tmpfs — 256 MiB; абсолютный минимум не измерялся. Кеш после `--version`: 161284 KiB. Для 256 MiB cgroup `memory.current=169492480`, `memory.peak=400183296` байт. 128 MiB недостаточно; рабочая конфигурация использует 512 MiB с запасом. Значения относятся только к CLI 1.0.86 / Linux arm64 / offline smoke, не к агентному прогону.
