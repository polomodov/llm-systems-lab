# Google Antigravity CLI

Практическое задание: [ЛР14 — Antigravity CLI, Gemini API и наблюдаемость](../../docs/labs/LAB14-antigravity-cli.md). Включает offline smoke, полный T002 с внешним судейством и дополнительные серии.

Реализован адаптер официального бинарного CLI **`agy` 1.2.7**. Это отдельный продукт Antigravity; пакет Gemini CLI не используется. Образ проверен 20.09.2026 на Linux/arm64 без credentials и доступной сети. Реальное выполнение эпизодов с Gemini API остаётся **unverified**. [Исходные проверки](smoke/2026-09-20.json) относятся к инфраструктуре.

```bash
docker build --build-arg HARNESS_VERSION=1.2.7 \
  -t harness-lab/antigravity-cli:1.2.7 experiments/antigravity-cli
```

Установщик использует [снимок релиза](releases/1.2.7.json), закреплённые URL и SHA-512 для Linux arm64/x64 из официальных release manifests. Сборка не запрашивает `latest`; для новой версии нужно сначала добавить проверенный manifest. x64-архив закреплён, но локально не запускался.

В `.env` нужен `GEMINI_API_KEY`. `settings.json` задаёт `modelProvider: gemini`: согласно документации запросы идут напрямую в Gemini API. Runtime копирует этот файл в временный HOME внутри контейнера; credentials хоста не подключаются. Для подготовки выберите `--harness antigravity-cli`, провайдер — `google`; для запуска нужны точный ID доступной модели, образ и `--budget-mode observed`. Общий цикл описан в [корневой инструкции](../../README.md).

Используется `--output-format stream-json`, явная модель и пропуск интерактивных разрешений внутри внешнего контейнера. Разворачивание slash-команд отключено. `--print-timeout 0` передаёт ограничение времени общему runner. Лимиты USD и внутренних ходов не подтверждены интерфейсом; обязательные значения отклоняются, отсутствие ограничений в исследовательском режиме фиксируется.

Парсер использует только последний итоговый `result`; накопительные счётчики не суммируются со `step_update`. USD и модельные ходы неизвестны: `num_turns` считает запросы пользователя. `tokens_out` берётся из итогового usage. Семантику cache/input нужно подтвердить реальным прогоном, поэтому `tokens_in` пока неизвестно. `init.model` отражает настройку, а не независимое доказательство модели ответа: `observed_id=null`.

Первичные источники: [установка и Gemini API key](https://antigravity.google/docs/cli/install/), [headless protocol](https://antigravity.google/docs/cli/headless/), [официальный установщик](https://antigravity.google/cli/install.sh). Конкретные флаги сверены с `agy --help` в образе. Для повторной проверки нужны unit/smoke, проверка credentials/network и записанный эпизод с внешней оценкой; строка компонента — **L010**.
