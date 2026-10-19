# LAB08 · Протокол интеграции (Ryzen/Linux, сессия ryzen-linux-bridge)

Записан: 2026-10-12T12:36:28Z (до первого реального запуска; консолидирует решение,
зафиксированное вместе с session id и deployment-моделью до прогонов).

## Контракт endpoint

- Один доверенный endpoint: `http://127.0.0.1:18080`, транспорт HTTP, IPv4-лиз, `LD_LIBRARY_PATH` = каталог бинарника.
- Разрешённые маршруты agent-facing: `GET /health`, `POST /v1/chat/completions`. Остальное (`/props`, `/slots`, `/models`, admin, LAN, cloud) запрещено брокеру.
- Один запрос одновременно; body ≤ 1 MiB, response ≤ 4 MiB; upstream deadline 300 s; SSE буферизуется до finish/DONE (TTFT не измеряется).
- Tool protocol `openai-chat`, streaming only, `parallel_tool_calls=false`; dummy auth marker публичный, upstream auth нет, cloud fallback отсутствует.

## Identity и ресурсы

- Identity: sealed deployment v1 (weights/revision/hashes/quant, tokenizer/template SHA, engine/commit/backend/build, hardware passport, power mode 0).
- Проверка до Popen — хеши всех перечисленных файлов; после старта — `/props` (`model_alias`, `model_path`, `total_slots`, `build_info`, `n_ctx`, `chat_template` SHA) и лог `offloaded N/N layers to GPU` + device marker (`ROCm0`).
- Admission: свободная память ≥ 8 GiB, PSI `pressure_level=1`, swap ≤ 1 GiB, AC не offline; guard каждые 2 s, RSS ≤ 24 GiB.
- Linux-отличие от Apple: ресурсы берутся из `/proc`,`/sys` (нет `vm_stat`/`pmset`/`lms`), нет `caffeinate` (idle-sleep assertion не применяется), обязателен `LD_LIBRARY_PATH`.

## План и группы

- Обвязка: Pi 0.73.1 (`mode=sdk`), T002/a2-janitor, local provider, alias `lab-model`, budget `observed`, native turn cap 30.
- Модель: `unsloth/Qwen3.5-9B-GGUF` @ `3885219b6810b007914f3a7950a8d1b469d598a5`, Q6_K; engine llama.cpp `b8407` (commit `312cf033…`) ROCm 7.2.1 gfx1151.
- Группы контекста: 8192 (run `…janitor`), 16384 (`-2`, `-3`), отдельная группа **32768 + timeout 1800 s** (`-4`) — объявлена до запуска, как допускает ЛР09 для медленных локальных моделей.
- Критерий опровержения: доступ к другому адресу/порту/admin/cloud; потерянный tool-result; две конфигурации в одной группе; отсутствующий usage выдан за 0.
