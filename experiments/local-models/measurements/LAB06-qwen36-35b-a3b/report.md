# LAB06 — vLLM, SGLang и Transformers на ROCm (Qwen3.6-35B-A3B)

Сессия: `qwen36-35b-a3b`. Статус: **completed**.

Расширение LAB06 на второй native checkpoint: BF16 `Qwen/Qwen3.6-35B-A3B`
(revision `995ad96eacd98c81ed38be0c5b274b04031597b0`). Минимум LAB06 (Qwen3.5-9B) закрыт
прeregistered-сессией `LAB06-qwen35-9b-rocm-prereg`; здесь проверяются совместимость
трёх runtime с крупной MoE и практические лимиты памяти на gfx1151.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | opencode probe pipeline; 2026-10-14 |
| Модель | `Qwen/Qwen3.6-35B-A3B`, BF16 native, 71 926 799 705 B (38 файлов, 26 шардов) |
| GPU / стек | Radeon 8060S, gfx1151, ROCm/HIP 7.2; `/dev/kfd`, `/dev/dri/renderD128` |
| vLLM | `vllm/vllm-openai-rocm@sha256:e5e47f6a…` (v0.29.0) |
| SGLang | `lab-sglang:gfx1151-94602c9-fixed` `sha256:32bb7a1b…` (v0.5.20, gfx1151, производный fix-слой) |
| Transformers | 5.12.1 (в образе SGLang), `Qwen3_5MoeForConditionalGeneration` |

## Гипотеза и протокол до запуска

См. `raw/protocol.md`. BF16 checkpoint загружается на gfx1151 в трёх runtime и проходит
контрольный chat; серверы — полный tool round trip. Константы: одна последовательность,
dtype bfloat16, parsers `qwen3`/`qwen3_coder`, alias `lab-model`, порты 8000/30000.

## Ход выполнения

| Шаг | Результат |
| --- | --- |
| verify артефакта | exit 0 (native-verification.json), 71.9 ГБ |
| GPU probe | vLLM и SGLang: `gfx1151`, HIP 7.2, total_memory 100 GiB |
| vLLM c4096 util 0.90 | **fail**: weights 73.03 GiB → KV −0.27 GiB |
| vLLM c4096 util 0.97 | **успех**: KV 6.73 GiB; chat/stream/tool/tool-stream |
| SGLang c4096 mem-fraction 0.90 | **fail**: HIP OOM (PyTorch 99.38 GiB) |
| SGLang c4096 mem-fraction 0.80 | **успех**: protocol cases |
| reference (dense-класс) | **fail**: MoE-веса MISSING, результат невалиден |
| reference (MoE-класс) | **успех**: `LAB_READY`, greedy non-thinking |

## Результаты

| Runtime / image | Torch / ROCm / Transformers | gfx1151 probe | Локальный статус |
| --- | --- | --- | --- |
| vLLM v0.29.0 | torch 2.12.0+git6bbd260 / hip 7.2.53211 | OK | модель загружена, protocol пройден |
| SGLang v0.5.20 (fixed) | torch 2.9.1+rocm7.2.4 / hip 7.2.53211 | OK | модель загружена, protocol пройден |
| Transformers reference | 5.12.1 (образ SGLang) | OK | greedy non-thinking → LAB_READY |

| Configuration | Context | Dtype/cache/graphs/parser | Peak / KV | Статус |
| --- | --- | --- | --- | --- |
| vllm-c4096 | 4096 | bf16, prefix off, eager, qwen3/qwen3_coder | load 73.03 GiB, KV 6.73 GiB | completed |
| sglang-c4096 | 4096 | bf16, radix off, triton, graph bs=1 | mem-fraction 0.80 | completed |

| Configuration | Cold/warm | Chat final | Tools / streaming | Output / finish | Evidence |
| --- | --- | --- | --- | --- | --- |
| vLLM c4096 | cold | `LAB_READY` | tool + stream → `LAB_VALUE_42` | см. protocol-r1 | raw/vllm-c4096-eager-02/protocol-r1 |
| SGLang c4096 | cold | `LAB_READY` | tool + stream → `LAB_VALUE_42` | + reasoning_content | raw/sglang-c4096-graph1-03/protocol-r1 |
| reference | cold | `LAB_READY` | not-applicable | 3 токена, 6.0 s | raw/reference-moe-result.json |

## Ошибки и ограничения

- **Память.** Модель велика для этого стенда: vLLM загрузил 73.03 GiB и потребовал
  `gpu_memory_utilization 0.97` (KV 6.73 GiB); при 0.90 — fail. SGLang при 0.80 прошёл,
  при 0.90 — HIP OOM. Это практический лимит 35B BF16 на 100 GiB VRAM/UMA при работе через
  эти рантаймы.
- **Reference.** Первый прогон использовал dense-класс `Qwen3_5ForConditionalGeneration`
  вместо MoE — веса были MISSING, результат невалиден (сохранён как `failed`). Правильный
  класс — `Qwen3_5MoeForConditionalGeneration`.
- **Режимы несравнимы.** vLLM eager против SGLang graph bs=1; reference greedy non-thinking.
  Скорость между ветвями не сравнивается (это проверка совместимости).
- **Контекст.** Только 4096 (минимальный). 8192 и near-limit не выполнялись.
- **SGLang fix-образ.** Базовый образ зависит от BuildKit-поведения; запуск через
  производный fix-слой (`sglang-fix`), как и в LAB06 qwen35-9b.
- **Энергия** не измерялась.

## Вывод по гипотезе

**Поддержана.** BF16 Qwen3.6-35B-A3B загрузился на gfx1151 в vLLM и SGLang (при более
высоком лимите памяти, чем для 9B) и прошёл chat/stream/tool/tool-stream; reference
Transformers дал контрольный ответ. Проверка совместимости, не сравнение производительности.

## Ответы на контрольные вопросы

1. safetensors не задаёт точность; размер GGUF не описывает BF16 checkpoint (66.97 GiB vs 71.9 ГБ файлов).
2. `torch.cuda.is_available()` не доказывает поддержку конкретных kernels (напр. MXFP4) на gfx1151.
3. Ошибку template/parser отделяем сравнением с прямым reference (greedy) — здесь reference дал LAB_READY.
4. image digest фиксирует образ; один commit Dockerfile — не побитовый повтор (build deps, BuildKit).
5. Различия graphs/cache/точек измерения мешают прямому сравнению tokens/s.

## Комплект сдачи

- [x] manifest.json, measurements.tsv, report.md, native artifact + verify, image probes, server logs, protocol cases, reference.
- [x] `npm run check` проходит.
