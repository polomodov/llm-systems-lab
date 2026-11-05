# LAB07 — Ollama, LM Studio и Lemonade

Сессия: `ryzen-01`

Создано: 2026-10-15T07:45:29.072Z
Прогон: 2026-10-15, стенд Ryzen AI Max+ 395 / 128 GB / Linux.

Статус: **завершено** для двух сервисов (Ollama + LM Studio, backend ROCm).
Lemonade — `not-run` (расширение, несовместимая сборка). Проверялась гипотеза
переносимости одного артефакта и tool protocol между serving wrapper'ами.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | open (agent) по заданию polomodov; 2026-10-15 |
| Машина, ОС, kernel | GTR Pro (GTRP112), Ubuntu 24.04.4 LTS, kernel 7.0.0-38-generic, x86_64; Ryzen AI Max+ 395 / Radeon 8060S (`gfx1151`) |
| Модель/артефакт | `unsloth/Qwen3.5-9B-GGUF` rev `3885219b6810b007914f3a7950a8d1b469d598a5`, single `Qwen3.5-9B-Q6_K.gguf`, 7 458 301 152 B, Q6_K, sha256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59` |
| Engine, backend | Ollama 0.34.2 (своя llama.cpp, ROCm-либы `rocm_v7_2`); LM Studio runtime `llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0`; backend ROCm |
| Context, KV/state, slots, sampling | 8192; один слот (concurrency 1); output budget 2048; серверные defaults; thinking включён |
| Previous reports | ЛР02 `LAB02-after-rocm`, ЛР03 `LAB03-qwen35-9b`, ЛР04 `LAB04-qwen35-9b-prebuilt`, ЛР05 `LAB05-qwen35-9b-hip-prebuilt` (direct baseline) |
| Отличия от задания | Lemonade заменена на not-run; второй сервис LM Studio установлен как CLI-дистрибутив `llmster` (GUI отсутствует) |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (зафиксирован до первого запроса: 2026-10-15T10:49:50Z,
до старта серверов). Гипотеза: оба сервиса импортируют одни bytes контрольного
GGUF, используют ROCm/gfx1151 и проходят chat/streaming/tool fixtures при
context 8192, concurrency 1, output 2048. Изменяемый фактор — serving wrapper;
константы и правило принятия решения перечислены в протоколе.

## Ход выполнения

| Шаг | Действие / команда | Результат | Evidence |
| --- | --- | --- | --- |
| 1 | Пин и установка приложений (user-space, без sudo) | Ollama 0.34.2 и `llmster` 0.0.25-1 (`lms` commit 69d945a); Lemonade 11.9.0 не стартует | `raw/install-notes.md`, `raw/ollama-version.txt`, `raw/lms-version.txt`, `raw/lemonade-version.txt`, `raw/lemond-help.txt` |
| 2 | Ollama ROCm: `serve` на 127.0.0.1:11435, `ollama create` из GGUF | ROCm0, `gfx1151`, runner 6.6 GiB VRAM; blob sha256 совпал с источником | `raw/ollama-rocm-8k-server.log`, `raw/ollama-import.txt`, `raw/ollama-effective-modelfile.txt`, `raw/ollama-rocm-gpu-proof.txt` |
| 3 | Ollama probes: chat cold + 3 warm, streaming, tool round trip | Все вернули `LAB_READY`; tool call `lookup_lab_value{key:alpha}` + follow-up `LAB_VALUE_42` | `raw/ollama-rocm-smoke-8k-*-chat.*`, `raw/ollama-rocm-stream-8k-warm-r1.*`, `raw/ollama-rocm-smoke-8k-tool.*` |
| 4 | LM Studio ROCm: `import --copy`, `load --gpu max -c 8192 --parallel 1`, `server start` | runtime ROCm, параллельность 1, GTT 8.29 GB; destination sha256 совпал | `raw/lms-import.txt`, `raw/lms-load.txt`, `raw/lms-loaded.txt`, `raw/lms-rocm-gpu-proof.txt`, `raw/lms-prompt-log.txt` |
| 5 | LM Studio probes: chat cold + 3 warm, streaming, tool round trip | Все вернули `LAB_READY`; tool call + follow-up `LAB_VALUE_42`; `reasoning_content` отдельно | `raw/lms-rocm-smoke-8k-*-chat.*`, `raw/lms-rocm-stream-8k-warm-r1.*`, `raw/lms-rocm-smoke-8k-tool.*` |
| 6 | Остановка, проверка освобождения GPU | GTT 8.18/8.29 GB → 0.60 GB в обоих случаях | `raw/ollama-rocm-memory-after-stop.txt`, `raw/lms-rocm-memory-after-stop.txt` |

## Результаты

| Сервис | App / CLI version | Runtime ID / binary | Backend / GPU доказательство | В минимум | Статус |
| --- | --- | --- | --- | --- | --- |
| Ollama | 0.34.2 | своя llama.cpp + ROCm-либы `lib/ollama/rocm_v7_2` | `inference compute … library=ROCm compute=gfx1151 name=ROCm0 description="Radeon 8060S Graphics"`; runner 6.6 GiB VRAM; GTT 8.18 GB | да | passed (chat/stream/tool) |
| LM Studio | `llmster` 0.0.25-1, CLI commit 69d945a | `llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0` | runtime selected + `--gpu max` = GPU offload 100%, estimatedVram 8.73 GB; GTT 8.29 GB | да | passed (chat/stream/tool) |
| Lemonade / llama.cpp | 11.9.0 (`lemonade`,`lemond`) | — | — | нет | `not-run`: сборка Debian 13, не стартует на Ubuntu 24.04 |
| Lemonade / vLLM | — | — | — | нет | `not-run` (требует ЛР06) |

| Configuration | Source/imported SHA-256 | Template / tool mode | Context / cache / thinking / sampling | Отличия от direct baseline (ЛР05) |
| --- | --- | --- | --- | --- |
| `ollama-rocm-8k` | source = imported = `91898433…326c59` | автоматический шаблон Ollama; native tool calls; `reasoning` в отдельном поле (не `reasoning_content`) | 8192; prefix-cache (`cached_tokens`); default sampling; thinking on | своя llama.cpp, OpenAI-compat endpoint; reasoning-поле `reasoning` |
| `lms-rocm-8k` | source = imported = `91898433…326c59` | Qwen `<|im_start|>…<think>` шаблон; native tool calls; `reasoning_content` | 8192; reasoning_tokens в usage; default sampling; thinking on | runtime llama.cpp 2.58.0; REASONING/usage подробнее |

| Configuration / repeat | Cold / warm | Chat / stream / tools | Wall, s | Peak GPU (GTT used) | Verdict |
| --- | --- | --- | --- | --- | --- |
| `ollama-rocm-8k` cold r1 | cold | chat | 10.760 | 8 184 750 080 B | pass (`LAB_READY`) |
| `ollama-rocm-8k` warm r1/r2/r3 | warm | chat | 8.100 / 8.634 / 8.459 | — | pass / pass / pass |
| `ollama-rocm-8k` stream r1 | warm | streaming | 8.050 (content TTFT 7.979) | — | pass |
| `ollama-rocm-8k` tool | warm | full tools (call+follow-up) | 2.993 + 0.429 | — | pass (`LAB_VALUE_42`) |
| `lms-rocm-8k` cold r1 | cold | chat | 8.037 | 8 286 720 000 B | pass (`LAB_READY`) |
| `lms-rocm-8k` warm r1/r2/r3 | warm | chat | 5.874 / 8.932 / 7.189 | — | pass / pass / pass |
| `lms-rocm-8k` stream r1 | warm | streaming | 7.933 (content TTFT 7.861, reasoning TTFT 0.195) | — | pass |
| `lms-rocm-8k` tool | warm | full tools (call+follow-up) | 3.930 + 1.701 | — | pass (`LAB_VALUE_42`) |

Исходные численные строки — в `measurements.tsv`. Медианы chat (warm):
Ollama 8.459 s, LM Studio 7.189 s; сравнение latency не изолировано от различий
runtime/template/parser, поэтому не является чистым эффектом wrapper.

## Ошибки и ограничения

- **Lemonade 11.9.0 — `not-run`.** `.deb` собран под Debian 13; на Ubuntu 24.04
  отсутствуют `libcpp-httplib0.41`, `libmbedcrypto16`, `libwebsockets19t64` и
  нужен `libstdc++>=14`. Бинарь не стартует (`error while loading shared
  libraries`). PPA/snap требуют root. Это расширение, не влияющий на минимум.
- `hipconfig` отсутствует в минимальном ROCm-наборе (`/opt/rocm-7.2.0/bin`) —
  `unavailable`, ROCm подтверждён через `rocminfo` и server logs.
- **Ollama `ttft_reasoning` — `unavailable`:** OpenAI-совместимый ответ Ollama
  кладёт рассуждение в поле `message.reasoning`, а не `reasoning_content`,
  поэтому probe не выделяет TTFT рассуждения (сам текст сохранён в response.json).
- `lms ls` в текстовом режиме показал размер 580 MB (баг отображения); `lms ls
  --json` и байты файла дают корректные 7 458 301 152 B, sha256 совпал.
- Near-limit 8K probe с длинным входом и наблюдением памяти по методике ЛР05 не
  выполнялся — короткие HTTP/tools-пробы самостоятельны. `context=8192` задан
  флагом конфигурации, длина fixture его не заполняет.
- Ollama reasoning-текст (raw-поле `reasoning`) присутствует в каждом ответе,
  `completion_tokens` включает токены рассуждения; указанное в отчёте время —
  полное время запроса без разделения фаз для Ollama.
- LM Studio загружает с `PARALLEL=4` по умолчанию; для concurrency 1 перезагрузка
  выполнена с `--parallel 1`.

## Вывод по гипотезе

**Поддержана для двух выбранных сервисов.** Ollama 0.34.2 и LM Studio
(LLM-движок `llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0`) импортировали
**одни и те же bytes** контрольного `Qwen3.5-9B-Q6_K.gguf` (sha256 совпал для
обоих), использовали ROCm/gfx1151 (подтверждено GPU-логами и ростом GTT до
~8.2 GB) и прошли одинаковые chat/streaming/tool fixtures при context 8192,
concurrency 1, output 2048. Полный tool round trip вернул разрешённый call ID и
final `LAB_VALUE_42` в обоих случаях.

Гипотеза **не поддержана** для Lemonade (extension): сервис не установлен на этой
ОС, это `not-run`, а не результат задачи. Сравнение с direct baseline ЛР05
возможно только как сравнение deployments: различаются engine, template/parser и
API-детали (поле рассуждения), поэтому разность latency нельзя приписать чисто
serving wrapper.

## Ответы на контрольные вопросы

1. **Почему сравнение Ollama и LM Studio не равно сравнению двух независимых
   inference engines?** Оба являются serving wrapper над llama.cpp; Ollama
   включает собственную интеграцию llama.cpp, LM Studio выбирает runtime-пакет.
   Названия приложений не означают разные GPU kernels; отличается слой runtime,
   template и parser, а не фундаментальный engine.
2. **Что проверить после импорта GGUF, кроме отображения в списке?** Совпадение
   bytes/SHA-256 импортированного blob с источником (`sha256` blob Ollama и файл
   LM Studio оба равны `91898433…326c59`), фактический `FROM`/path, template и
   backend по логам runner'а.
3. **Как tool fallback меняет вопрос «помогла ли обвязка модели»?** Если сервис
   подменяет native parsing fallback-ом, он дописывает инструкции и меняет
   сообщения — тогда сравниваются разные prompts, а не равные условия. Здесь оба
   сервиса сделали native tool call с корректным `call_id` (`tools`-запрос).
4. **Почему `--gpu max` / `OLLAMA_VULKAN=0` сами не доказывают GPU path?** Это
   только запрос. Доказательство — server log с `library=ROCm compute=gfx1151`,
   выбор ROCm-runtime и рост GTT; Ollama `OLLAMA_VULKAN=0` сам по себе не
   исключает CPU fallback.
5. **Когда разность latency можно приписать serving wrapper?** Только когда
   совпали weights, binary/runtime, backend, template/parser, effective
   generation settings и API. Здесь условия не совпали (engine/template/API),
   поэтому вывод ограничен сравнением deployments.

## Комплект сдачи

- [x] Заполнен `manifest.json`; пропуски снабжены причинами.
- [x] Все запланированные попытки в `planned_attempts` (включая `not-run`).
- [x] Сохранены исходные команды, конфигурации и сырые логи без секретов.
- [x] Заполнены таблицы результатов и `measurements.tsv`.
- [x] Реальные run records не применимы (лаборатория без агентных попыток).
- [x] Проверены индивидуальные критерии завершения работы.
- [x] Сформулированы вывод, ограничения и ответы на вопросы.
- [x] `lab:check --mode submission` — пройден, `ready_for_review=true`, ошибок нет.

Решение проверяющего: **не проверено**.
