# Кандидаты локальных моделей для Ryzen AI Max+ 395, 128 GB

Срез источников: **2026-09-20**. Цель — проверить качество автономной работы на существующих задачах лаборатории, стоимость во времени и объём необходимой обвязки на Linux. Это исследование и очередь испытаний: веса не скачивались, локальные модели не запускались, производительность на машине пользователя пока **unverified**.

Машиночитаемый каталог — [`experiments/local-models/models.json`](../experiments/local-models/models.json). Для каждого кандидата записаны официальный ID, ревизия исходной модели, издатель GGUF, ревизия артефакта, все необходимые shards, размеры в байтах и опубликованные SHA-256. Последние получены из API Hugging Face, а не проверены скачиванием. Перед запуском нужно проверить контрольные суммы локальных файлов.

## Короткий список и порядок

P1 — первый проход, P2 — расширение после успешной проверки runtime и инструментов, P3 — контрольные сравнения. Приоритет не является рейтингом качества. Выбраны 12 моделей из четырёх семейств; одинаковые задачи позволяют проверить и размер модели, и архитектуру, и влияние поколения.

В колонке параметров сначала указано **общее**, затем **активное на токен** число миллиардов параметров из model card. У dense-модели это один и тот же размер. Активные 3B у MoE не означают, что в памяти нужны лишь веса на 3B: для обычного запуска размещается вся выбранная квантизация. `hybrid-*` здесь означает сочетание Gated DeltaNet с полным attention; `dense`/`moe` не исключают sliding-window attention.

**GB = 10⁹ байт, GiB = 2³⁰ байт.** Значения GiB округлены вверх до 0.1. Это сумма файлов весов для текстового запуска, без отдельного vision projector, draft-модели, KV-cache, вычислительных буферов и ОС. GGUF, опубликованный Unsloth или ggml-org, обозначает артефакт этого издателя; он не становится официальной квантизацией автора базовой модели.

| Очередь | Модель и первичный источник | Параметры, B total / active | Архитектура | Выбранный GGUF и источник | Размер файлов | Допуск по памяти | Что проверяем |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | 9 / 9 | hybrid-dense | [Q6_K](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5) | 7.46 GB / ≤7.0 GiB | `candidate` | Малый контроль: скорость и нижняя граница качества |
| P1 | [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 35 / 3 | hybrid-moe | [UD-Q5_K_M](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/tree/a483e9e6cbd595906af30beda3187c2663a1118c) | 26.46 GB / ≤24.7 GiB | `candidate` | Актуальная MoE; агентный код и сохранение reasoning |
| P1 | [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) | 27 / 27 | hybrid-dense | [Q5_K_M](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/tree/82d411acf4a06cfb8d9b073a5211bf410bfc29bf) | 19.51 GB / ≤18.2 GiB | `candidate` | Dense-контроль качества против MoE |
| P1 | [Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) | 80 / 3 | hybrid-moe | [Q5_K_M](https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF/tree/b82fb7382639d97b38fa7672e526c760c2fb358e) | 56.71 GB / ≤52.9 GiB | `candidate` | Специализация на coding agents; non-thinking |
| P1 | [gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b) | 21 / 3.6 | moe | [MXFP4](https://huggingface.co/ggml-org/gpt-oss-20b-GGUF/tree/ef9b12f2ff56c69cf32153a02784e7a3c88bf524) | 12.11 GB / ≤11.3 GiB | `candidate` | Независимая компактная семья; Harmony и reasoning |
| P1 | [GLM-4.7-Flash](https://huggingface.co/zai-org/GLM-4.7-Flash) | 30 / 3 | moe | [Q8_0](https://huggingface.co/ggml-org/GLM-4.7-Flash-GGUF/tree/7559e96b7e324ab405897dc2b91492b0f376ad4a) | 31.84 GB / ≤29.7 GiB | `candidate` | Независимая MoE с MLA; качество при Q8 |
| P2 | [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 30.5 / 3.3 | moe | [Q5_K_M](https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/tree/b17cb02dd882d5b6ab62fc777ad2995f19668350) | 21.73 GB / ≤20.3 GiB | `candidate` | Full-attention MoE против hybrid Coder-Next |
| P2 | [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b) | 117 / 5.1 | moe | [MXFP4](https://huggingface.co/ggml-org/gpt-oss-120b-GGUF/tree/238abdd290bb874b90a5da1b4549881b7d05c091) | 63.39 GB / ≤59.1 GiB | `conditional` | Масштабирование той же семьи до 117B |
| P2 | [Qwen3.5-122B-A10B](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) | 122 / 10 | hybrid-moe | [Q4_K_M](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF/tree/51eab4d59d53f573fb9206cb3ce613f1d0aa392b) | 76.54 GB / ≤71.3 GiB | `conditional` | Большая hybrid MoE; граница практического размера |
| P2 | [gemma-4-31B-it](https://huggingface.co/google/gemma-4-31B-it) | 30.7 / 30.7 | dense | [Q5_K_M](https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/tree/c1ac76e99d5513b141e8adde7288b85c3f9c32ec) | 21.66 GB / ≤20.2 GiB | `candidate` | Независимая dense-семья; native function calling |
| P3 | [Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) | 35 / 3 | hybrid-moe | [Q5_K_M](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/tree/bc014a17be43adabd7066b7a86075ff935c6a4e2) | 26.25 GB / ≤24.5 GiB | `candidate` | Парный контроль поколения Qwen3.5→3.6 |
| P3 | [GLM-4.5-Air](https://huggingface.co/zai-org/GLM-4.5-Air) | 106 / 12 | moe | [Q4_K_M](https://huggingface.co/unsloth/GLM-4.5-Air-GGUF/tree/506d64aa8c5cfe9dbbf00bc7a15739438f83204d) | 72.98 GB / ≤68.0 GiB | `conditional` | Большая альтернативная MoE с полным attention |

`candidate` означает, что размер весов оставляет заметный резерв в 128 GB; это **fit-estimate**, не `fit-verified`. `conditional` требует отдельного допуска по фактической памяти backend: файл помещается в общий объём, но GPU-доступная память, KV, рабочие буферы и кратковременные копии при загрузке могут изменить результат. Ни одна строка не гарантирует приемлемую скорость.

Для всех строк первый проход: **8 192 → 16 384 → 32 768 токенов**, одна модель и один слот одновременно. Следующий размер допускается только после успешного предыдущего с зафиксированным пиком памяти. Это размер всего контекста, включая историю инструментов, reasoning и будущий ответ. Не подставлять нативные 128K/256K автоматически. Для Qwen официальный автор рекомендует длинный контекст для сложного reasoning; поэтому этот проход измеряет поведение при ограниченном локальном бюджете, а не воспроизводит максимальные vendor scores. Для финалистов возможны отдельные 64K/128K после допуска по памяти. [Рекомендация Qwen](https://huggingface.co/Qwen/Qwen3.5-9B#quickstart).

## Вес модели и память процесса — разные величины

Рабочая оценка: `resident weights + KV/state cache + compute buffers + runtime/driver + ОС/обвязка`. На UMA память CPU и iGPU берётся из одного физического объёма: их заявленные ёмкости нельзя складывать. Размер GGUF нужен для предварительного отсева; окончательное решение принимается по логам allocator и измерениям системы. mmap, копии CPU/GPU и shared pages могут приводить к двойному счёту при простом сложении RSS процессов.

Для обычного full-attention GQA с одинаковым размером K/V оценка FP16 cache для одного слота:

```text
KV_bytes = 2 × full_attention_layers × kv_heads × head_dim × context_tokens × 2
```

Первое `2` учитывает K и V, последнее — байты FP16. Ни квантизация весов Q4/Q5/Q8, ни число активных экспертов не задают тип KV. Для нескольких одновременных последовательностей расход обычно растёт; стратегия выделения cache также зависит от backend.

Примеры расчёта для **32 768 токенов, одного слота, FP16 cache** по официальным конфигурациям, без allocator overhead:

| Модель | Расчётная часть KV | Условия и что остаётся вне расчёта |
| --- | --- | --- |
| Qwen3.5-9B | 1.00 GiB | 8 attention-слоёв, 4 KV-heads × 256; дополнительно state Gated DeltaNet |
| Qwen3.6-27B | 2.00 GiB | 16 attention-слоёв, 4 × 256; дополнительно state Gated DeltaNet |
| Qwen3.5/3.6-35B-A3B | 0.625 GiB | 10 attention-слоёв, 2 × 256; дополнительно state Gated DeltaNet |
| Qwen3-Coder-Next / Qwen3.5-122B-A10B | 0.75 GiB | 12 attention-слоёв, 2 × 256; дополнительно state Gated DeltaNet |
| Qwen3-Coder-30B-A3B-Instruct | 3.00 GiB | 48 full-attention слоёв, 4 × 128 |
| GLM-4.5-Air | 5.75 GiB | 46 full-attention слоёв, 8 × 128 |

Это расчёты по [Qwen3.5-9B config](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/config.json), [Qwen3.6-27B config](https://huggingface.co/Qwen/Qwen3.6-27B/blob/main/config.json), [Qwen3.6-35B config](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/blob/main/config.json), [Coder-Next config](https://huggingface.co/Qwen/Qwen3-Coder-Next/blob/main/config.json), [Qwen3.5-122B config](https://huggingface.co/Qwen/Qwen3.5-122B-A10B/blob/main/config.json), [Coder-30B config](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/blob/main/config.json), [GLM-Air config](https://huggingface.co/zai-org/GLM-4.5-Air/blob/main/config.json). Ревизии этих моделей зафиксированы в каталоге; значения не являются замерами лаборатории.

Для GLM-4.7-Flash требуется отдельная проверка реализации **MLA**: хранит ли backend сжатое латентное состояние или развёрнутые K/V. Общая формула GQA здесь вводит в заблуждение. У gpt-oss чередуются local и global attention, у Gemma 4 также есть sliding/global attention и shared K/V; нужен отчёт runtime о реально выделенном cache. [GLM-Flash config](https://huggingface.co/zai-org/GLM-4.7-Flash/blob/main/config.json), [gpt-oss config](https://huggingface.co/openai/gpt-oss-120b/blob/main/config.json), [Gemma 4 config](https://huggingface.co/google/gemma-4-31B-it/blob/main/config.json).

## Условия корректного сравнения

- **Qwen3-Coder-Next и Coder-30B** — non-thinking модели. Не включать для них искусственный режим reasoning. Для Qwen3.5/3.6 отдельно фиксировать thinking, preservation истории и sampling. [Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next), [Coder-30B](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct).
- **gpt-oss** требует формат Harmony. Проверить, что server и harness сохраняют tool calls и корректно отделяют каналы. MXFP4 — конкретный формат весов; нужно подтвердить его поддержку выбранным Linux GPU backend. Проверить reasoning `low/medium/high` отдельно, не смешивать их результаты. Заявление автора, что 120b рассчитана на одну 80 GB GPU, не является проверкой Ryzen. [Карточка OpenAI](https://huggingface.co/openai/gpt-oss-20b).
- **GLM-4.7-Flash** требует проверки parser инструментов и режима сохранения thinking между ходами. Первая квантизация Q8_0 оставляет запас памяти и позволяет сначала проверить интеграцию. Только затем добавлять Q5/Q4 как отдельные варианты. [Карточка Z.ai](https://huggingface.co/zai-org/GLM-4.7-Flash).
- **Gemma 4 31B** — dense-модель с заявленными 30.7B параметров и native function calling. Проверить шаблон чата, system-role, parser tools и thinking на конкретном runtime. Текстовые задачи первой серии не проверяют её визуальные возможности. [Карточка Google](https://huggingface.co/google/gemma-4-31B-it).
- **Qwen3.6-35B UD-Q5_K_M и Qwen3.5-35B Q5_K_M** — разные опубликованные рецепты квантизации. Первое сравнение показывает результат этих артефактов, а не чистый эффект поколения. Для такого вывода нужен дополнительный проход с одинаковым рецептом, например доступными Q8_0, и одной версией runtime.
- Одна модель сначала проходит структурированный tool-call smoke: вызов инструмента, возврат результата, второй вызов, завершение. Плохой parser не считать доказательством плохой модели. После smoke выполнять те же задачи лаборатории и внешний verdict по общему протоколу.
- В run record нужны backend/version/commit, драйвер, параметры памяти, модель и GGUF SHA-256, chat template, parser, контекст, KV dtype, число слотов, offload, sampling, reasoning, реальные токены, время и пик памяти. Результаты модели на разных backend/квантизациях сравнивать раздельно. Маркетинговые benchmark numbers не переносить в `results/runs/`.

## Что не входит в первую серию

Полные BF16 больших MoE не являются целевыми вариантами для 128 GB: например, один официальный репозиторий Qwen3.5-122B содержит около 250 GB файлов. Выбранный Q4 занимает 76.54 GB. Даже Q8_0 этой модели — около 129.87 GB файлов, ещё до cache и ОС. Для Q5_K_M (~91.52 GB / 85.3 GiB) остаётся гораздо меньше резерва, поэтому это только условная последующая абляция. [Оригинальные файлы](https://huggingface.co/Qwen/Qwen3.5-122B-A10B/tree/main), [GGUF-артефакты](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF/tree/51eab4d59d53f573fb9206cb3ce613f1d0aa392b).

Название **GLM-4.7-Air** не подтверждено в проверенных первичных источниках. В каталог включены существующие **GLM-4.7-Flash** и **GLM-4.5-Air** (106B total / 12B active по авторской карточке). [GLM-4.5-Air](https://huggingface.co/zai-org/GLM-4.5-Air). У Hugging Face автоматическое число параметров иногда отличается от авторского округления; память оценивается по файлам выбранного артефакта.

Qwen3.5-27B и дополнительные 32B/70B dense-модели оставлены вне первой серии, чтобы не раздувать матрицу: актуальный Qwen3.6-27B уже даёт dense-контроль, а Gemma добавляет независимую семью. Qwen3.5-35B сохранена для парного сравнения поколений. Не включены неидентифицируемые «uncensored», merged и distilled community variants: сначала нужна воспроизводимая базовая линия по официальным моделям.

Все выбранные GGUF вместе занимают **436.62 GB (~406.63 GiB)** на диске до временных файлов и результатов. Одновременная загрузка всех моделей в RAM не предполагается; скачивать достаточно очередную модель или небольшой пул. Перед загрузкой новых ревизий обновить каталог и повторить memory/tool smoke. Скорость tokens/s, время решения и качество на Ryzen остаются **unverified** до выполнения плана.
