# Заметки · Amp

Экспериментальных прогонов пока нет.

20.09.2026 — инфраструктура без API и ключей: Docker Engine 29.5.2 / Linux arm64, пакет `@ampcode/cli@0.0.1789920039-gafe14b`, Node base `24.13.1-bookworm-slim`. Обычный npm postinstall необходим для размещения native binary. Offline version/help подтверждают `low`, `medium`, `high`, `ultra`, `--executor local`, stream JSON, proxy и settings-file. Старые примеры `smart` / `rush` не используются.

Read-only контейнер с noexec `/tmp` не мог загрузить native addon; отдельный exec tmpfs `/tmp/harness-native` и `TMPDIR` устраняют ошибку. Без `AMP_API_KEY` даже execute mode начинает интерактивную авторизацию; инфраструктурная проверка остановлена без входа, сеть была отключена. Общий координатор проверяет наличие ключа до запуска.

Парсер сохраняет неизвестность model ID, USD и отсутствующего usage. Первый реальный эпизод должен проверить egress, server-side routing, настройки workspace/account и полноту aggregate usage. Записать run ID здесь; источники — [README](README.md).

Повторная проверка точных ограничений координатора: `--version` проходит с `/tmp:rw,nosuid,noexec,size=512m,mode=1777`, `/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777`, памятью 2 GiB и UID 1000. Кеш: 2672 KiB; cgroup `memory.current=4698112`, `memory.peak=161296384` байт. Значения относятся только к указанной версии / Linux arm64 / offline smoke; реальная нагрузка с моделью не измерена.
