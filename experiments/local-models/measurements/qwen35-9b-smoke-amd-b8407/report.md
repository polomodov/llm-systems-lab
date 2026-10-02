# Smoke — Qwen3.5-9B на AMD llama.cpp b8407 prebuilt

Сессия: `qwen35-9b-smoke-amd-b8407`

Дата: 2026-10-02

Статус: **smoke завершён**. Модель `Qwen3.5-9B-Q6_K.gguf` загружена
ROCm/HIP backend в AMD prebuilt llama.cpp b8407, успешно отвечает на
chat completions, прогнан `llama-bench`. Backend ROCm/HIP (НЕ Vulkan),
поэтому это не парное сравнение из ЛР04, а однократный runtime smoke
для подтверждения, что стек ROCm 7.2 + HIP runtime + AMD b8407 + GGUF
из ЛР03 совместимы на этой машине.

Связанные артефакты:

- `experiments/local-models/measurements/LAB02-after-rocm/` — паспорт
  машины с реальными бюджетами (Vulkan heap1 budget 65.99 GiB).
- `experiments/local-models/measurements/LAB03-qwen35-9b/` — выбор и
  проверка `Qwen3.5-9B-Q6_K.gguf` (7.46 GiB, SHA-256
  `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`).
- `docs/labs/LAB04-backends.md` — полный протокол сравнения
  Vulkan vs HIP/ROCm (здесь **не** выполняется).
- `docs/local-model-runtime.md` — runbook для gfx1151.

## Что было запущено

| Компонент | Версия / путь |
| --- | --- |
| llama.cpp build | **b8407** (`312cf0332`), `AMD-validated prebuilt` |
| URL | `https://repo.radeon.com/rocm/llama.cpp/linux/rocm-rel-7.2.1/llama-b8407-ubuntu-24.04-rocm-7.2.1-gfx110X-gfx115X-gfx120X-x64.zip` |
| Размер архива | 3.81 GB (`md5 effa4bcd7c2dd6d201cb412847359319`) |
| Распаковка | `/tmp/opencode/llama_b8407/llama-b8407-ubuntu-24.04-rocm-7.2.1-gfx110X-gfx115X-gfx120X-x64/` (6.4 GB на диске с libs) |
| Backend | ROCm/HIP (gfx1151, gfx110X, gfx120X) |
| Зависимости | self-contained: libggml-hip.so, libamdhip64.so.7, libhipblas.so.3, libhipblaslt.so.1, libhsa-runtime64.so.1, librocsolver, librocroller, libroctx64, librocprofiler-register, libamd_comgr.so.3 — все свои |
| LD_LIBRARY_PATH | `<unpack-dir>` (для self-contained libs) |
| Модель | `Qwen3.5-9B-Q6_K.gguf` из ЛР03, SHA-256 `91898433…` |
| Контекст | 4096 токенов × 4 параллельных слота (`-c 4096`, server default) |

## Метрики загрузки

| Метрика | Значение | Источник |
| --- | --- | --- |
| `ggml_cuda_init` devices | **1 ROCm device** (`AMD Radeon Graphics, gfx1151`) | `raw/llama-server.log` |
| Total VRAM, видимый движку | **102400 MiB** (100.00 GiB = GTT cap из ЛР02) | `raw/llama-server.log` |
| Projected device memory (веса+overhead) | **7136 MiB** (6.97 GiB) | `raw/llama-server.log` |
| Свободно после `params_fit` | 110774 MiB (108.18 GiB) для KV cache | `raw/llama-server.log` |
| VMM | NO_VMM=1 (b8407 + gfx1151) | `raw/llama-server.log` system info |
| Слоёв на GPU | **99** (`-ngl 99` = все) | `raw/llama-bench.json` |
| KV type | f16, f16 | `raw/llama-bench.json` |
| `flash_attn` | **false** в JSON, хотя `-fa` передано (известный b8407 quirk) | `raw/llama-bench.json` |
| Cold load до listening | ~15 с (process start → `main: server is listening`) | `raw/llama-server.log` |

## Chat completion (один запрос)

Запрос: `What is the capital of France? Reply with one word only.`

| Метрика | Значение |
| --- | --- |
| HTTP endpoint | `http://127.0.0.1:8089/v1/chat/completions` |
| Wall time | **5.96 с** |
| finish_reason | `stop` |
| prompt_tokens | 23 |
| completion_tokens | 162 (большая часть — `<think>` reasoning) |
| `prompt_per_second` (server timings) | 226.2 t/s |
| `predicted_per_second` (server timings) | 27.83 t/s |
| Содержимое ответа | **`Paris`** (правильно) |
| Reasoning excerpt | `Thinking Process: 1. Analyze the Request... 2. Identify the Answer: the capital of` |

Полный JSON запроса/ответа: `raw/llama-server-request.json`.

## llama-bench (3 повтора, pp2048 + tg128 при depth 4096)

Команда:
```sh
./llama-bench -m <GGUF> -ngl 99 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 2048 -n 128 -d 4096 -r 3 -o json
```

| Режим | n_tokens | depth | t/s (avg) | per-rep t/s | per-token |
| --- | ---: | ---: | ---: | --- | ---: |
| **pp2048** | 2048 | 4096 | **744.52** | 752.54 / 748.99 / 732.02 | 1.34 ms |
| **tg128** | 128 | 4096 | **25.74** | 25.68 / 25.81 / 25.74 | 38.85 ms |

stddev: pp 40.85 ms, tg 12.71 ms (стабильные повторы).

## Сравнение с ЛР04 (что это не покрывает)

| Требование ЛР04 | Здесь |
| --- | --- |
| Сборка llama.cpp из исходников по pinned commit SHA | ❌ использован AMD prebuilt b8407 |
| Одинаковый commit для Vulkan и HIP | ❌ только HIP |
| Парные повторы Vulkan → HIP → Vulkan | ❌ только HIP |
| Cold process / filesystem cache отдельно | ❌ не измерялось |
| Tg при пустом контексте vs при заполненном | ❌ только depth 4096 |
| Проверка `HSA_OVERRIDE_GFX_VERSION` и архитектуры | ✅ gfx1151 native, без override |

Этот smoke **не** заменяет полную ЛР04. ЛР04 требует парного сравнения
из одного upstream commit; здесь использован один prebuilt, который не
имеет прямого Vulkan-аналога в этом архиве.

## Что наблюдалось

- **GPU residency подтверждена**: `llama_params_fit_impl: projected to
  use 7136 MiB of device memory vs. 117911 MiB of free device memory`;
  `using device ROCm0 (AMD Radeon Graphics) (0000:c6:00.0) - 118125 MiB
  free`. `n_gpu_layers=99` (все).
- **Модель полностью помещается** в GTT: 7.14 GiB < 100 GiB GTT cap,
  далеко от лимитирующего фактора Vulkan heap1 budget (65.99 GiB).
- **Qwen3.5 = гибрид attention + SSM** (mamba). Метаданные GGUF:
  `qwen35.ssm.state_size=128`, `qwen35.ssm.conv_kernel=4`,
  `qwen35.ssm.time_step_rank=32`, `qwen35.attention.head_count=16`,
  `head_count_kv=4` (GQA 4:1). Это объясняет, почему в benchmarks t/s
  ниже, чем у чистых attention моделей того же размера: SSM kernels
  исполняются отдельно, и b8407 их поддерживает, но не оптимизировал.
- **`thinking = 1` по умолчанию** — Qwen3.5-9B выдаёт
  `<think>...</think>` блок перед `content`. Это видно в
  `reasoning_content` поля JSON. На коротких вопросах это тратит
  большинство токенов. Для инструментального использования в агенте
  нужно отключать через `chat_template_kwargs` (не проверялось здесь).
- **`flash_attn` не активируется** в b8407 при флаге `-fa on` —
  значение `false` в JSON. Это известная проблема сборки b8407; для
  ЛР04 с upstream commit это нужно проверить явно. Здесь замерено без
  FA, что занижает pp/tg относительно потенциала.

## Что не делалось

- Не собирался upstream llama.cpp (компиляция 30+ минут). Использован
  AMD prebuilt.
- Не запускался Vulkan-сборка того же b8407 (нет в этом архиве).
- Не измерялся cold process wall time (load) — только inference wall.
- Не тестировался tool calling / streaming round-trip — только один
  запрос на completion.
- Не сделан `fa` контроль (требует отдельной сборки с фиксом).

## Комплект сдачи

- [x] `raw/llama-server.log` — полный server log со всеми этапами
  (init, model load, params_fit, warmup, listening, health endpoint).
- [x] `raw/llama-bench.json` — JSON результат `llama-bench` с
  build_commit, model info, per-rep timings.
- [x] `raw/llama-bench.log` — startup log llama-bench (ggml_cuda_init).
- [x] `raw/llama-server-request.json` — вызов OpenAI-compatible
  endpoint и ответ с reasoning + final content.
- [x] `raw/llama-server-help.txt`, `raw/llama-bench-help.txt` — help
  output обеих утилит.
- [x] `raw/llama-server-ldd.txt` — динамические зависимости HIP/ROCm.
- [x] `raw/binaries.sha256` — SHA-256 исполняемых файлов и ключевых
  HIP/ROCm библиотек.
- [x] `raw/gguf.sha256` — SHA-256 модели (совпадает с ЛР03).
- [x] `raw/archive.md5` — MD5 исходного zip-архива (для повторной
  загрузки с тем же содержимым).
- [x] `raw/gpu-mem-during.txt` — snapshot `/sys/class/drm/card1/device/mem_info_*`.
- [x] `measurements.tsv` — 25 наблюдений.

## Источники

- [AMD llama.cpp b8407 prebuilt для gfx1151 / Ubuntu 24.04](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/advanced/advancedryz/linux/llm/llamacpp.html).
- [Паспорт машины (LAB02-after-rocm)](../LAB02-after-rocm/report.md).
- [Артефакт модели (LAB03-qwen35-9b)](../LAB03-qwen35-9b/report.md).
- [ЛР04: парное сравнение Vulkan vs HIP](../LAB04-backends.md).