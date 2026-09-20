# План сравнения движков инференса на Ryzen AI Max+ 395

Практические задания: [ЛР04 — backend](labs/LAB04-backends.md), [ЛР06 — движки](labs/LAB06-engines.md), [ЛР07 — сервисы](labs/LAB07-serving.md). Общий маршрут и шаблоны — в [практикуме](labs/README.md).

Дополнение от **21.09.2026** к [кампании локальных моделей](local-models.md). Целевая машина — Ryzen AI Max+ 395 / Radeon 8060S (`gfx1151`), 128 GB UMA, Linux. **ROCm — полноценная обязательная ветвь исследования наряду с Vulkan.** Поддержка Max+ 395 явно перечислена в [матрице AMD](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html); AMD также публикует [vLLM-образ для gfx1151](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedryz/linux/llm/build-docker-image.html). Это документированные пути запуска, не наши аппаратные замеры.

## Какие факторы разделяем

| Уровень | Примеры | Что меняется в эксперименте |
| --- | --- | --- |
| Модель и артефакт | Qwen3.6, GGUF Q5, safetensors BF16/MXFP4/AWQ | Веса, точность, template, реальная память |
| Движок | llama.cpp, vLLM, SGLang, Transformers/PyTorch | Kernels, attention, batching, scheduler/cache |
| GPU backend | Vulkan либо HIP/ROCm | Компилятор, GPU библиотеки, ICD/runtime, распределение памяти |
| Сервис поверх движка | Ollama, LM Studio, Lemonade | API, загрузка/выгрузка, шаблоны, ограничения, накладные расходы |
| Агентная обвязка | Pi, OpenCode, mini-SWE-agent, OpenHands | Инструменты и автономный цикл |

ROCm — программный стек, HIP — используемый в нём GPU API; это не названия двух независимых inference engines. Ollama содержит закреплённую интеграцию llama.cpp с patches, поэтому в опыте фиксируется её runner, а не предполагается тождество upstream. [Исходник интеграции Ollama](https://github.com/ollama/ollama/blob/6383a0fa9cbf97494b847226e189f6e36b401a08/llama/README.md). LM Studio использует отдельные runtime packages; Lemonade может запускать разные движки. Их результаты не являются независимыми повторениями одной и той же kernel implementation.

## Матрица и очередность

В [engines.json](../experiments/local-models/engines.json) **12 профилей**, включая пары backend. Статус `documented` относится к источникам, `conditional` — к неполной проверке точного стека/устройства, `experimental` — к явно экспериментальному пути автора. Все три статуса оставляют hardware smoke обязательным; ни один не означает «проверено в лаборатории».

| Очередь / профили CLI | Движок или сервис | Веса и статус | Первый опыт |
| --- | --- | --- | --- |
| P1 `llama-cpp-vulkan`, `llama-cpp-rocm` | llama.cpp, две равноправные backend | Один и тот же GGUF и commit; Linux build paths документированы | Все 12 кандидатов по памяти, начиная с Qwen3.5-9B; затем 8K/16K/32K |
| P2 `vllm-rocm` | vLLM | Документированный gfx1151; собственный checkpoint/quant, не автоматический перенос GGUF | Qwen3.5-9B, gpt-oss-20b и Qwen3.6-35B, только после проверки kernels/формата |
| P2 `sglang-rocm` | SGLang | Новая отдельная gfx1151 сборка; native Linux условно до smoke | Те же три модельные семьи, но собственные поддержанные артефакты |
| P2 `transformers-rocm` | Transformers + PyTorch | Документированный AMD Torch; reference `generate`, без готового agent API | Те же три малые/средние модели, если BF16/поддержанный quant проходит память |
| P3 `ollama-rocm`, `ollama-vulkan` | Ollama | Linux ROCm явно включает 395; Vulkan тоже документирован | Два прошедших контрольных GGUF; импорт исходных shards, параметры сервера закреплены |
| P3 `lm-studio-vulkan`, `lm-studio-rocm` | LM Studio / llama.cpp | Обе Linux backend документированы; точный runtime для gfx1151 проверить | Два контрольных GGUF; отдельно version приложения и runtime package |
| P3 `lemonade-vulkan`, `lemonade-rocm` | Lemonade / llama.cpp | Recipe и binary можно закрепить | Два контрольных GGUF; direct server и сервис на одном binary hash, если возможно |
| P3 `lemonade-vllm-rocm` | Lemonade / vLLM | У автора experimental, validation на gfx1151 | Два ранее прошедших native checkpoint из vLLM-ветви |

### Версии и ограничения первичных источников

**llama.cpp.** Собирать Vulkan и HIP из одного immutable commit; команды есть в [Linux runbook](local-model-runtime.md). Архивный AMD b8407/ROCm 7.2.1 годится как диагностический ориентир, но новый model architecture может требовать более свежего commit. Текущий Vulkan и старый HIP нельзя сравнивать как изменение только backend. [Upstream build](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

**vLLM.** Stable GPU guide перечисляет Ryzen AI MAX/AI 300 и `gfx1151`/`gfx1150`; [v0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0) — кандидат версии на дату исследования. AMD также документирует исторический стек `rocm7.2.1_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.16.0`. Не смешивать tag нового сервера с зависимостями старого примера. Выбрать полный совместимый образ, сохранить digest, Torch/Triton/ROCm и проверить GPU/kernel dispatch. GGUF-путь, если потребуется, исследуется отдельно от native checkpoint и не обещает поддержку каждой архитектуры. [GPU install](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/), [пример AMD](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/advanced/advancedryz/linux/llm/build-docker-image.html).

**SGLang.** [v0.5.20](https://github.com/sgl-project/sglang/releases/tag/v0.5.20) включает [добавление отдельного gfx1151 Docker image](https://github.com/sgl-project/sglang/pull/33939). Автор PR проверял 395/8060S в WSL2, а не нашу native Linux машину: контекст 4096, concurrency 1, отдельная wave32 сборка, Triton attention, AITER dispatch выключен. Поэтому не выбирать generic CDNA/MI300 image. Сохранить конкретный gfx1151 image digest и повторить сначала исходный короткий smoke, затем 8K/16K/32K. Поддержка MXFP4 на CDNA не доказывает её наличие на RDNA 3.5: для gpt-oss сначала подобрать поддержанный native/dequantized вариант, записать новый quant и пересчитать память. [AMD GPU guide SGLang](https://docs.sglang.io/docs/hardware-platforms/amd_gpu).

**Transformers/PyTorch.** Reference помогает отличить дефект checkpoint/template от serving integration. AMD публикует отдельные [device-specific пакеты Torch](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html); выбирать проверенную пару Torch/ROCm, а не независимо последние версии каждого пакета. Reference не участвует в agent API сравнении до появления воспроизводимого server adapter. Chat template и tool messages фиксировать согласно [документации Transformers](https://huggingface.co/docs/transformers/chat_extras). AMD отдельно описывает [ограничения производительности прежних PyTorch на Ryzen AI Max](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html); BLAS preference и применение workaround фиксируются отдельными настройками, а не скрытым ускорением одного участника.

**Ollama.** Текущая [аппаратная документация](https://docs.ollama.com/gpu) прямо содержит Ryzen 395 и ROCm v7; Vulkan включается при наличии backend. Фактический выбор подтвердить логом. Импортировать [точный GGUF](https://docs.ollama.com/import) без requant, сохранить manifest, Modelfile, template и `num_ctx`. [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) не тождественна полному API: в частности, ограничения stateful Responses нужно проверить для конкретной обвязки. Auto backend, CPU fallback и auto context не допускаются как неизвестные условия серии.

**LM Studio.** [Linux ROCm описан в релизе](https://lmstudio.ai/blog/lmstudio-v0.3.19), [Vulkan/Linux — в SDK-анонсе](https://lmstudio.ai/blog/introducing-lmstudio-sdk); это не exact395 certification. Зафиксировать результат [`lms runtime ls/get/select`](https://lmstudio.ai/docs/cli/runtime/runtime). [`lms import`](https://lmstudio.ai/docs/cli/local-models/import) по умолчанию перемещает исходный файл — в исследовании использовать copy/hard-link и проверить hash. Native tools и fallback tools различаются: fallback меняет сообщения и prompt, поэтому это отдельный компонент, требующий записи в ledger. [Tool use](https://lmstudio.ai/docs/developer/openai-compat/tools).

**Lemonade.** Закрепить [recipe, backend, binary](https://lemonade-server.ai/docs/guide/configuration/) и [локальные extra models](https://lemonade-server.ai/docs/guide/configuration/custom-models/), без автоматического latest/pull в серии. `llamacpp:rocm` stable/nightly может поставлять собственную сборку и runtime. [vLLM recipe](https://lemonade-server.ai/docs/guide/configuration/vllm/) — отдельный экспериментальный путь с per-architecture пакетом, собственными checkpoint и запускными параметрами. JIT/первичную загрузку измерять отдельно; внутренний backend-only `/metrics` остаётся доступен координатору, не агенту.

## Память: GGUF нельзя подставить вместо native checkpoint

Прежний `models.json` фиксирует **конкретные GGUF**. Их 7–71 GiB не описывают память BF16, FP8, GPTQ, AWQ или развёрнутого MXFP4 в другом движке. Даже совпадение названия «4-bit» не даёт одинаковые веса или kernels. Safetensors — контейнер файлов, а не обозначение точности.

Для vLLM/SGLang/Transformers и Lemonade-vLLM planner возвращает `artifact-required`, `quantization=null`, неизвестные веса/total/headroom. Следующее действие — выбрать поддержанный артефакт, закрепить revision/shards/bytes/hash/quant config и пересчитать resident memory. Это не статус «модель не поддерживается»: исходных данных пока недостаточно. Не молча конвертировать GGUF в BF16 или загружать полный 120B BF16 по тому же alias.

У сервисов с импортом GGUF размер весов известен, но дополнительный runtime/scheduler reserve пока нет: `engine-memory-required`. Резерв 6 GiB прежнего расчёта сохраняется **только как гипотеза llama.cpp**, не как измерение всех движков. KV preallocation, compile workspace, prefix cache и `max_num_seqs`/аналогичные параметры измеряются отдельно. Использовать общий физический бюджет UMA и сохранить резерв ОС; проценты `gpu_memory_utilization`/`mem_fraction_static` нельзя принимать за одинаковое количество байтов между движками.

## Как выполнять сравнение

1. **Две baseline backend llama.cpp.** До 12 моделей × 2 backend × 3 контекста × 3 повтора = **216 наборов** ресурсных измерений, с отсевом после ошибок предыдущего уровня. Каждый набор включает pp/tg, память и HTTP smoke; это не 216 агентных попыток. Проверить весь context, а не только его настройку.
2. **Независимые движки ROCm.** На трёх выбранных семьях провести vLLM/SGLang: до 3 × 2 × 3 × 3 = **54 наборов**. Для SGLang сначала отдельный 4K installation smoke из upstream PR, не включаемый в сравнение 8K. Transformers reference — до 3 × 1 контекст 8K × 3 = **9 наборов**. Недоступный quant/architecture/fit фиксируется как несовместимая клетка; не выдавать все сочетания за готовые.
3. **Serving layers.** Шесть GGUF профилей (Ollama, LM Studio, Lemonade × ROCm/Vulkan) на двух контролях, 16K, 3 повтора: до **36 наборов**. Lemonade-vLLM отдельно: до **6 наборов**, после прямого vLLM. До этого этапа зафиксировать выбранные контрольные модели и причину выбора; предпочтительны Qwen3.5-9B и gpt-oss-20b при подтверждённом импорте/protocol.
4. **Агентный эффект движка.** До 3 финалистов × 2 прошедших engine deployments × T001/T002 × 3 повтора на reference Pi = **36 новых попыток**, максимум 9 часов по 900-секундному timeout, плюс setup/оценка. Это отдельная серия; runtime smoke не заменяет task verdict. Если для модели прошёл только один движок, пары нет и эффект движка не вычисляется.
5. **Эффект агентной обвязки.** Сохранить основной план: для каждой из 3 моделей закрепить один прошедший engine deployment, затем 4 обвязки × 2 задачи × 3 повтора = **72 попытки**. T003 — ещё до 36 отдельных аудитов с прежним ограничением разных входов. Для оценки только обвязки engine не меняется.

Такой порядок не умножает все 12 моделей на все 12 профилей и все обвязки в реальной серии. Полная таблица planner показывает исследовательское пространство; этапы выше задают ограниченную очередь. Времена — лимиты отдельных запусков, не прогноз завершения всей кампании. Загрузки, compilation/JIT и внешний судья оцениваются отдельно.

Для сравнения движков использовать **один внешний HTTP workload driver**: одинаковые тексты/prompts, output budget, tool schema, sampling, slot count и состояние cache. Встроенные `llama-bench`, `vllm bench` и SGLang benchmark имеют разные определения; сохранять их как диагностику, не объединять их tokens/s в один рейтинг. Отдельно TTFT, prefill, decode, полный wall-clock, actual output/reasoning tokens, usage coverage и ошибки. Сравнение tokens/s разных моделей учитывает различие токенизаторов.

Основной workload — один последовательный агент, concurrency **1**, prefix cache выключен или явно согласован; если отключение невозможно, другая группа. После него возможен отдельный throughput опыт concurrency 2/4 на двух малых моделях, только после memory gate. Он не входит в приведённые числа и не определяет победителя для одиночного агента. Сохранять warmup, холодный JIT, тёплый prefix cache и простой сервиса раздельно; чередовать порядок backend/движков по сохранённому seed.

Если совпадают weight hash, quant recipe, template и параметры, можно оценивать эффект движка/backend. Когда native quant и GGUF различаются, вывод относится к **полной конфигурации модели**, а не к одному движку. Для сервисов поверх llama.cpp сравнение накладных расходов допустимо только при совпадении фактического binary/hash; иначе фиксируются также fork/patch/version.

## Что сохранить и что реализовать перед запуском

К паспорту машины и весов добавить engine/version/commit/image digest; backend и реально выбранные kernels; PyTorch/Triton/AITER/ROCm/ICD; quant loader; attention implementation; template/parser; KV dtype и allocation; batch/ubatch/max sequences; prefix cache; compile/graph mode; serving application/runtime versions; полный effective config. Пустое поле остаётся неизвестным с причиной. Одинаковый `model` alias не связывает эти условия автоматически.

Планируемое расширение `results/schema.json`, prepare snapshot и compare должно учитывать **все эти уровни**. Пока `run --provider local` и универсальный engine launcher не реализованы. `local:engines` и `local:plan --engine ...` — только чтение каталога. GPU devices получает отдельный model service; агентские контейнеры сохраняют прежние границы, узкий local proxy и независимого оценщика.

```bash
npm run local:engines
npm run local:plan -- --engine llama-cpp-rocm --context 16384
npm run local:plan -- --engine vllm-rocm --model gpt-oss-20b
npm run local:plan -- --engine all --format json
```

Без `--engine` сохраняется старый расчёт GGUF как совместимый режим planner. Эти команды не ставят ROCm, не скачивают веса, не запускают серверы и не создают фоновые задания.

`ik_llama.cpp` оставлен за GPU-серией: автор отмечает полноценно поддержанными CPU/CUDA, а не ROCm/Vulkan; возможный CPU AVX-512 опыт — отдельный контроль. [Закреплённый README](https://github.com/ikawrakow/ik_llama.cpp/blob/9cba2e3874df6f598fd339c4c6c7d5fc2b44645b/README.md). NPU/ONNX/FastFlowLM, multi-GPU и облачные endpoints не входят в эту GPU-кампанию и требуют отдельного набора артефактов/условий.
