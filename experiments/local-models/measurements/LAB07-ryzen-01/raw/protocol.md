# LAB07 — предварительный протокол (session ryzen-01)

Зафиксировано до первого запроса к модели: 2026-10-15T10:49:50Z.
Хост: GTR Pro (GTRP112), Ubuntu 24.04.4 LTS, kernel 7.0.0-38-generic, x86_64.
Стенд: Ryzen AI Max+ 395 / Radeon 8060S (`gfx1151`), 128 GB UMA. Аппаратный паспорт:
`experiments/local-models/measurements/LAB02-after-rocm/manifest.json`.

## Гипотеза (опровержимая)

Два локальных serving-сервиса — **Ollama v0.34.2 (ROCm)** и
**LM Studio `llmster` CLI + runtime `llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0`** —
импортируют **одни и те же bytes** контрольного `Qwen3.5-9B-Q6_K.gguf` (sha256
`91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`), используют
заявленный GPU-путь (ROCm/gfx1151) и проходят одинаковые chat/streaming/tool
fixtures при закреплённых настройках (context 8192, concurrency 1, output 2048).

Опровержение: импортированный blob не совпадает по SHA-256 с источником, **или**
runner логирует CPU fallback, **или** tool round trip не возвращает разрешённый
call ID и final `LAB_VALUE_42`.

## Изменяемый фактор

Serving wrapper/приложение. Сравниваемые конфигурации:

- `direct` — прямой `llama-server` из ЛР05 (baseline, уже измерен отдельно);
- `ollama-rocm-8k` — Ollama v0.34.2, ROCm backend;
- `lms-rocm-8k` — LM Studio, runtime ROCm;
- `lemonade-rocm-8k` — расширение (ветвь заблокирована до установки совместимых libs).

## Константы

- Артефакт: `unsloth/Qwen3.5-9B-GGUF` rev `3885219b6810b007914f3a7950a8d1b469d598a5`,
  единственный файл `Qwen3.5-9B-Q6_K.gguf`, 7 458 301 152 B.
- Backend: ROCm (HIP на `gfx1151`). Прошёл ЛР04 (`LAB04-qwen35-9b-prebuilt`).
- Context 8192, один слот (concurrency 1), output budget 2048.
- Thinking/sampling: серверные defaults, reasoning извлекается в
  `message.reasoning_content`, как в ЛР05. Собственный template не задаём —
  автоматический шаблон сервиса остаётся частью исследуемой конфигурации.
- Открытые fixtures `chat-request.json` / `tool-request.json`; единственная
  разрешённая функция `lookup_lab_value` с `{'key':'alpha'}`.

## Порядок, повторы, критерий остановки

1. Сначала Ollama: `serve` (ROCm) → `ollama create` из GGUF → probes.
2. Затем LM Studio: `import --copy` → `load` 8K → `server start` → probes.
3. Для сервиса, прошедшего chat: 1 cold + 3 warm повтора chat, затем streaming;
   tool round trip + follow-up. Модель держим загруженной между warm-повторами.
4. Прогрев не входит в измеряемые повторы. Server logs и memory фиксируются
   отдельно для каждого сервиса.
5. Остановка: OOM, GPU reset, устойчивая подкачка, повторный невалидный tool
   call. CPU fallback → `fail` для гипотезы ROCm даже при правильном тексте.
6. Каждый сервис останавливаем и убеждаемся, что runner освободил GPU.

## Правило принятия решения

Гипотеза **поддержана**, если обе ветви (Ollama и LM Studio) прошли chat +
streaming + полный tool round trip, импорт подтверждён по SHA-256, а логи
показывают выбранный GPU. Если хотя бы одна ветвь дала CPU fallback, mismatch
hash или не завершила tool round trip — **не поддержана** с указанием причины.
Третья ветвь (Lemonade/vLLM) — `not-run`, не влияет на минимум.
