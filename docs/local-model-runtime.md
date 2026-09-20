# Локальный inference: Ryzen AI Max+ 395, 128 GB, Linux

Дата исследования: **2026-09-21**. Пользователь подтвердил Linux. Точная модель компьютера, дистрибутив, ядро, BIOS, режим питания и доступный GPU memory budget пока **unverified**: этот документ подготовлен по первичным источникам, без доступа к целевой машине. Команды ниже — runbook будущих измерений; установка runtime, загрузка весов и inference в этой работе не выполнялись.

Цель — сначала установить, какие конфигурации модели действительно помещаются и сохраняют работоспособность инструментов, затем сравнивать их в автономных задачах. Скорость backend и качество агента — разные измерения. План кандидатов и порядок серий находятся в [исследовании локальных моделей](local-models.md), состав сравнения движков — в [матрице inference engines](local-inference-engines.md). Примеры команд здесь относятся к двум реализациям llama.cpp; это часть общей кампании, а не её полный состав.

## Что подтверждено источниками

| Факт | Статус и условие |
| --- | --- |
| Ryzen AI Max+ 395: 16 ядер / 32 потока, Radeon 8060S с 40 CU, максимум 128 GB LPDDR5x-8000 | Спецификация AMD; фактическую конфигурацию OEM ещё проверить. [Карточка процессора](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html) |
| До 96 GB под графику при 128 GB RAM | Заявление AMD о Variable Graphics Memory. Описание настройки относится к Windows/Adrenalin; это не измеренный Linux heap и не 96 GB дополнительной памяти. [AMD VGM FAQ](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html) |
| `gfx1151` / RDNA 3.5 для семейства Ryzen AI Max 300 | Документировано AMD. Актуальная открытая матрица озаглавлена ROCm **10.0.0**, датирована 2026-08-19; для Ryzen указаны Ubuntu 26.04 / GA 7.0 и Ubuntu 24.04.4 / OEM 6.17. Это матрица конкретного стека, не обещание поддержки любого Linux. [Матрица ROCm](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html) |
| Поддержка Max+ 395 существовала и в ROCm 7.2.1 | Архивная матрица содержит процессор и Ubuntu 24.04.4. Не называть старый раздел `latest` текущей версией всей платформы. [Версионная матрица 7.2.1](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html) |
| ROCm 7.14.1 — опубликованный release; 7.9–7.13 относились к preview-линейке | Release notes датированы 2026-09-02. Ветка установленных пакетов и её матрица фиксируются отдельно от перемещающейся документации `latest`. [Release notes 7.14.1](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html) |
| AMD публикует пакет llama.cpp b8407 / ROCm 7.2.1 / gfx115X / Ubuntu 24.04 | Исторический проверенный вендором вариант для диагностики. Новые архитектуры моделей могут требовать более нового llama.cpp. [AMD llama.cpp binaries](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/advanced/advancedryz/linux/llm/llamacpp.html) |

Документированная поддержка оборудования не подтверждает скорость конкретной квантизации, Flash Attention, KV cache или tool calling. Например, AMD отдельно отмечала пониженную производительность некоторых LLM на Max+ 395 в ROCm 7.2.1. [Ограничения этой версии](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/limitations/limitationsryz.html)

## Обязательная пара llama.cpp: HIP/ROCm и Vulkan

**Обе ветви входят в обязательный baseline:** llama.cpp + HIP/ROCm с target `gfx1151` и llama.cpp + Vulkan. ROCm на Ryzen AI Max+ 395 документирован AMD; заранее считать его запасным или менее подходящим оснований нет. Какой backend быстрее и стабильнее при конкретном контексте и quant, определяют измерения. `llama.cpp` документирует обе Linux-сборки. [Инструкция upstream](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

Для обеих ветвей проверить ОС/ядро/драйвер и пройти smoke; недоступность одной записать как конкретный инфраструктурный blocker. Использовать один commit llama.cpp и одинаковые GGUF, контекст, KV precision, batch, число потоков и sampling. Зафиксировать ROCm components и Vulkan ICD с версиями. Сравнение Vulkan новой версии с AMD b8407 меняет сразу backend и версию движка; его можно сохранить как исследовательское, но нельзя приписать разницу одному HIP.

vLLM, SGLang, PyTorch/Transformers, Ollama и LM Studio рассматриваются в общей кампании по [матрице движков](local-inference-engines.md): их нельзя отсеивать только из-за наличия альтернативы на Vulkan. Runtime engine, формат весов, backend и сервисная оболочка учитываются как разные факторы. Поддержка движка на AMD не означает поддержку всех quant и архитектур на `gfx1151`.

Для unsupported стека не подменять архитектуру через `HSA_OVERRIDE_GFX_VERSION` в baseline. Если такая ветвь понадобится, она получает отдельную конфигурацию и статус experimental. NPU — отдельное исследование. Windows и WSL находятся за рамками подтверждённой пользователем Linux-конфигурации; чужой smoke на WSL не заменяет проверку native Linux.

## Preflight на целевой машине

Сначала снять состояние, ничего не меняя в BIOS, kernel cmdline, памяти GPU, драйверах или power profile. Зафиксировать модель OEM и прошивку, подключение к питанию, текущий профиль мощности, наличие графического рабочего стола и фоновых нагрузок. Утилиты, которых нет, отметить как unavailable; не превращать диагностику в неявную установку.

Пример read-only сбора в новый каталог серии на Linux:

```sh
set -eu
mkdir -p experiments/local-models/measurements
LOCAL_EVIDENCE=$(mktemp -d experiments/local-models/measurements/preflight.XXXXXX)
date -u +%FT%TZ > "$LOCAL_EVIDENCE/time.txt"
cat /etc/os-release > "$LOCAL_EVIDENCE/os-release.txt"
uname -a > "$LOCAL_EVIDENCE/kernel.txt"
lscpu > "$LOCAL_EVIDENCE/cpu.txt"
cat /proc/meminfo > "$LOCAL_EVIDENCE/meminfo.txt"
free -b > "$LOCAL_EVIDENCE/memory-bytes.txt"
swapon --show --bytes > "$LOCAL_EVIDENCE/swap.txt"
df -B1 . > "$LOCAL_EVIDENCE/disk.txt"
if command -v lspci >/dev/null; then
  lspci -nnk > "$LOCAL_EVIDENCE/pci.txt"
fi
if command -v vulkaninfo >/dev/null; then
  vulkaninfo --summary > "$LOCAL_EVIDENCE/vulkan-summary.txt" 2>&1
  vulkaninfo > "$LOCAL_EVIDENCE/vulkan-full.txt" 2>&1
fi
if command -v rocminfo >/dev/null; then
  rocminfo > "$LOCAL_EVIDENCE/rocminfo.txt" 2>&1
fi
if command -v hipconfig >/dev/null; then
  hipconfig --full > "$LOCAL_EVIDENCE/hipconfig.txt" 2>&1
fi
```

Проверить, что Vulkan видит **Radeon 8060S**, а не программный renderer. Для HIP проверить `gfx1151`. Сохранить фактические memory heaps/budgets и доступность устройства в том же окружении, в котором будет inference; host и контейнер могут видеть разные устройства и библиотеки. Путь `/dev/dri/renderD128` нельзя предполагать: сопоставить render node с выбранным GPU. Серийные номера машины в публикуемый архив не требуются.

У AMD есть отдельные требования к исправлениям KFD для `gfx1151`: Ubuntu HWE от `6.17.0-19.19~24.04.2`, OEM от `6.14.0-1018`, для остальных дистрибутивов ядро от `6.18.4` в описанной таблице AMD prebuilt. Проверять также backports и матрицу конкретного релиза. Предел TTM в `/sys/module/ttm/parameters/pages_limit` выражен в страницах; AMD рекомендует для Linux небольшой BIOS carve-out и использование общей памяти. Это основание измерить текущее состояние, а не автоматически менять его. [AMD RDNA3.5 system optimization](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html)

Память считать в байтах и отдельно отображать GiB (`bytes / 2^30`). Надпись «128 GB» не подставлять вместо измеренного `MemTotal`. VRAM и GTT на этой APU не независимые физические банки; их простая сумма может удвоить доступную RAM. Для допуска конфигурации одновременно нужны:

1. Фактический GPU budget покрывает размещённые веса, KV/state cache и compute buffers с запасом.
2. Для ОС, файлового кеша и обвязки остаётся резерв, заданный общим планом серии.
3. Длительное выполнение не создаёт устойчивую подкачку, OOM, reset GPU или скрытый переход на CPU.

Размер GGUF — нижний ориентир, а не peak memory. Для MoE учитывать **все** загруженные эксперты, а не только active parameters. Для recurrent/hybrid моделей не применять обычную формулу KV без проверки архитектуры. Если контекст увеличен с 8K до 32K или добавлен второй слот, допуск по памяти нужно измерить заново.

## Зафиксировать движок и веса

До скачивания выбранной партии получить immutable revision репозитория весов, список всех GGUF shards и их суммарный размер. После получения сохранить SHA-256 каждого файла. Зафиксировать исходную модель, лицензию, автора квантизации, метод/тип quant, tokenizer и встроенный chat template. Сторонний GGUF не становится официальным только потому, что исходная модель официальная.

Для runtime сохранить commit SHA, `--version`, `--help`, compiler/CMake versions, build flags, linked libraries и хеш бинарников. При контейнеризации дополнительно сохранить image digest и host GPU stack: образ не фиксирует ядро и драйвер машины. Изменяемые URL `master`/`latest` в источниках ниже служат для чтения; запуск всегда привязывается к конкретному артефакту.

После подготовки pinned checkout команды сборки имеют следующий вид. Они не устанавливают зависимости и не загружают модели:

```sh
cmake -S "$LLAMA_SOURCE" -B "$LLAMA_SOURCE/build-vulkan" \
  -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$LLAMA_SOURCE/build-vulkan" --config Release -j 8

HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -S "$LLAMA_SOURCE" -B "$LLAMA_SOURCE/build-hip" \
  -DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_BUILD_TYPE=Release
cmake --build "$LLAMA_SOURCE/build-hip" --config Release -j 8
```

`LLAMA_SOURCE` должен указывать на уже проверенный checkout. До применения команд сверить flags с документацией выбранного commit; сборки держать в разных каталогах. Пример нацелен на AMD HIP SDK, не требует PyTorch. Основа flags — [build.md llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

## Серия A: память и скорость без обвязки

Сначала один небольшой кандидат, один слот, полный GPU offload, контекст 8K. По логам подтвердить фактический backend, число выгруженных слоёв и объёмы buffers. Если часть вычислений ушла на CPU, сохранить это как отдельный вариант, не смешивать с full-offload. Не запускать две модели одновременно.

Начальные настройки серии — проектные условия, не рекомендация «оптимальных» параметров: 8 CPU threads, batch 512, microbatch 256, KV `f16`, Flash Attention явно `on`. Несовместимость FA/quant/model записать как failure конфигурации; fallback `off` создаёт отдельную конфигурацию. В дальнейшем разрешена отдельная абляция KV `q8_0` после проверки качества; нельзя молча заменять KV precision ради красивого fit.

`llama-bench` измеряет prompt processing (`pp`), generation (`tg`) и совместный режим (`pg`), умеет заполнять контекст через `-d`. Его время не включает tokenization и sampling. Сохранить сырые повторы, а не только среднее. [Семантика llama-bench](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)

После одного прогрева — 3 измеряемых повтора каждого выбранного случая, как в общем плане. Один набор для заданного контекста включает несколько режимов pp/tg, но не становится несколькими агентскими попытками. Пример для уже скачанного `LOCAL_GGUF` и установленного `LLAMA_BIN`; output directory должен быть новым:

```sh
"$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 512,2048,8192 -n 0 -r 3 -o json \
  > "$LOCAL_EVIDENCE/pp.json" 2> "$LOCAL_EVIDENCE/pp.log"

"$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 0 -n 128 -d 0,8192 -r 3 -o json \
  > "$LOCAL_EVIDENCE/tg.json" 2> "$LOCAL_EVIDENCE/tg.log"
```

Значение `8192` здесь — **глубина до генерации**, поэтому фактическая вместимость должна быть не меньше `8192 + 128`. Проверка 32K выполняется только после допуска по памяти и с запасом для выходных токенов. Синтаксис `-fa` менялся; применять приведённые команды только если pinned `--help` подтверждает `on`. Прогрев upstream обычно выполняет сам; сохранить help и отметить, выполнялся ли дополнительный прогрев, не включать его в измеряемые повторы.

В параллельном процессе с интервалом около секунды собирать MemAvailable, swap-in/out, RSS/PSS процесса, доступную GPU telemetry и температуру. RSS не равен физическому расходу всей системы при mmap/UMA: не складывать RSS, page cache и GPU allocation без проверки пересечений. Отдельно фиксировать peak по доступным счётчикам и их источники. Неподдерживаемый GPU sensor — `null` с причиной. Энергию — внешним ваттметром на розетке, если он есть; software power одной APU не считать потреблением всей машины.

Отчёт содержит median/min/max и raw repeats, load time, pp/tg при конкретной depth, память и стабильность. Порядок Vulkan/HIP чередовать между повторами/сериями; режим мощности и фоновые нагрузки фиксировать. Холодную загрузку процесса и тёплый файловый кеш учитывать отдельно, не очищая глобальный page cache в фоне без отдельного плана.

## Серия B: HTTP, templates и инструменты

После допуска по памяти поднять один `llama-server` только на loopback, явный контекст и один slot. Это **runtime smoke**, ещё не запуск агента через лабораторный runner:

```sh
"$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" \
  --host 127.0.0.1 --port 8080 -ngl 999 -c 8192 -np 1 \
  -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on --jinja
```

Chat template и reasoning задавать по карточке модели. Сервер поддерживает извлечение reasoning и связанные настройки, но `reasoning-format` сам по себе не включает и не отключает thinking. Записать effective settings и видимый ответ. Для модели с обязательным reasoning не заявлять, что его отключили общим флагом. [API и параметры сервера](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Проверить round trip инструментов на синтетических безвредных fixtures: чтение фиксированного значения, одна функция с JSON arguments, результат tool и последующий final answer. Для streaming — корректную сборку `tool_calls`, аргументов и `call_id` по delta-событиям. Затем две последовательные функции и отказ неизвестному инструменту. Не выполнять произвольные команды из smoke-ответа модели.

Tool-aware template обязателен; совместимость обычного chat endpoint не доказывает function calling. Сохранить `/props`, хеш шаблона, запрос и ответ без секретов, grammar/parser configuration. Если помогает изменённый template/parser, это уже компонент, который требует строки в harness ledger и отдельного сравнения. [Function calling llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)

Измерить HTTP TTFT (от отправки запроса до первого содержательного токена), полное время ответа и токены сервера; для streaming исключить служебные пустые события. Проверить ограничения output length, отмену запроса, overflow контекста и освобождение slot. Chat Completions, Responses API и Anthropic-style API — разные контракты; наличие одного не считать поддержкой остальных. Для изоляции фактора harness оставить один backend/model/template и одинаковые sampling settings.

## Серия C: подключение к обвязкам — после bridge

**Текущий статус: pending.** Существующий `experiments/common/egress.mjs` блокирует private IP; готового универсального `--provider local` в runner нет. Поэтому команды `new-run → prepare-run → run` нельзя выдавать за уже работающий локальный inference. Планирование кандидатов не снимает это ограничение.

Следующее изменение инфраструктуры должно дать агентскому контейнеру доступ только к одному доверенному endpoint модели. Не открывать весь localhost/host network и не давать агенту GPU devices. Backend запускает координатор; weights mount read-only, без репозитория задач, `.env`, hidden checks, workspace или Docker socket. У самого backend нет инструментов исполнения и необязательных внешних загрузок. Bridge разрешает только нужные inference routes; загрузка/выгрузка моделей, административные операции и произвольный proxy недоступны агенту.

До реальных задач проверить контракт конкретной обвязки, запись exact model identity (GGUF hashes + server alias), usage, stop reason и все доступные budget controls. Если adapter ожидает Responses API, проверить его операции отдельно. Managed обвязку без подтверждённого custom endpoint помечать unsupported, не подменять её цикл собственным агентом.

Сетевую границу T001 replay и T002 dependency gateway сохранить. Локальный backend — явное исключение на один сервис, а не общий доступ к LAN. Boundary-тесты должны подтвердить запрет соседних портов/private endpoints, redirect обходов и доступа к backend admin routes. Для нового bridge нужна запись ledger в том же изменении.

## Запись результатов и стоп-критерии

До запуска агента подготовить обычный `run.json` и отдельно приложить backend manifest/trace как доказательства; связь runtime configuration → run ID обязательна. Микробенч не выдавать за завершённый агентский run и не присваивать ему hidden-check pass. Самостоятельные backend-пробы допустимы до bridge: хранить их в `experiments/local-models/measurements/<probe-id>/` с `metadata.json` и raw logs. В текущей работе подготовлен **план**, измерений пока нет. Новые local-поля `run.json` требуют описанного в общем плане расширения схемы; вручную обходить validator нельзя.

В manifest нужны: дата, машина/ОС/ядро/firmware, ICD или ROCm версии, llama.cpp SHA, binary/image hashes, GGUF shard hashes, quant, effective chat template, context/slots/KV, offload, threads/batch, reasoning/sampling, seed, все launch arguments и route контракт. Неподтверждённые поля остаются `null` с причиной.

Остановить конфигурацию при OOM, GPU reset, невалидных/нестабильных tool calls, устойчивой подкачке, превышении зарезервированной памяти или повторяемой ошибке данных. Сохранить failure и причину; уменьшение контекста/quant/CPU offload — новый вариант, а не исправление старого результата. Отсутствие API-биллинга не равно нулевой полной стоимости: энергия и время учитываются отдельно; неизвестная стоимость не заменяется нулём.

Аппаратный smoke, пригодность конкретных моделей и сравнение Vulkan/HIP на машине пользователя остаются **unverified** до выполнения этого протокола.
