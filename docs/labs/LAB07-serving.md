# ЛР07. Ollama, LM Studio и Lemonade

## Паспорт

- Время: 3–6 часов плюс установка выбранных приложений/runtime.
- Предпосылки: сдана [ЛР05](LAB05-context-tools.md); сохранены проверенный GGUF, hash manifest, working backend и HTTP driver. Для дополнительного Lemonade/vLLM нужна [ЛР06](LAB06-engines.md).
- Готовность: Linux CLI и import/configuration paths документированы на 21.09.2026; все аппаратные результаты предстоит получить. Установленные версии приложений и выбранные runtime должны пройти собственный smoke.
- Минимум: один контрольный GGUF и **два сервиса на выбор**, по одной backend, уже прошедшей ЛР04. Третий сервис, пары Vulkan/ROCm, второй контрольный GGUF и Lemonade/vLLM — расширения. Для непройденных ветвей оставить `not-run`, не обещать проверку всей матрицы.

## Цель

Проверить, сохраняется ли один артефакт и работоспособный tool protocol при переносе из direct llama-server в разные локальные сервисы, и найти изменения runtime, template, parser и настроек памяти.

## Проверяемая гипотеза

«Два выбранных сервиса импортируют одни и те же bytes контрольного GGUF, используют заявленную GPU backend и проходят одинаковые chat/streaming/tool fixtures при закреплённых настройках». Совпадение весов не означает совпадение prompt или kernels; эти условия проверяются отдельно.

## Подготовка

```bash
npm run lab:new -- --lab LAB07 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB07-my-session"
export LAB03_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB05_DIR="$PWD/experiments/local-models/measurements/LAB05-my-session"
cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
cp "$LAB03_DIR/raw/verification.json" "$LAB_DIR/raw/source-verification.json"
cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
cp "$LAB05_DIR/raw/http_probe.py" "$LAB_DIR/raw/http_probe.py"
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/source-recheck.txt"
```

Задайте `GGUF` абсолютным путём единственного контрольного файла `qwen35-9b` из ЛР03. Для него не нужен special split import. При расширении на split GGUF повторите проверку всех shards и используйте именно поддержанный этой версией импорт без склейки.

В отчёте заранее выберите два сервиса, backend, context 8192, concurrency 1, output budget 2048, режим thinking/sampling из ЛР05. Сначала один сервер и одна модель в памяти; после остановки убедитесь, что runner освободил GPU. Сохраните отдельно baseline direct-server из ЛР05. Приложения являются serving wrappers: Ollama содержит собственную интеграцию llama.cpp, LM Studio выбирает runtime package, Lemonade запускает recipe. Три названия приложений не означают три независимых набора GPU kernels.

## Порядок выполнения

1. **Закрепите приложение и runtime до первого запроса.** Если приложение отсутствует, установите Linux-вариант по официальной инструкции из источников, выбрав совместимый с вашей ОС release. Сохраните URL установочного файла, версию, дату, SHA-256 архива/пакета и команды установки в `raw/install-notes.md`. Установку не включать в время inference. Во время серии не обновлять приложение, models или runtime.

   ```bash
   ollama --version > "$LAB_DIR/raw/ollama-version.txt" 2>&1
   lms --version > "$LAB_DIR/raw/lms-version.txt" 2>&1
   lemonade --version > "$LAB_DIR/raw/lemonade-version.txt" 2>&1
   lemond --help > "$LAB_DIR/raw/lemond-help.txt" 2>&1
   ```

   Выполняйте только команды выбранных приложений. Отсутствующая команда — `not-run: runtime-not-installed`, не ошибка модели. Для Ollama конкретный кандидат — [v0.34.2](https://github.com/ollama/ollama/releases/tag/v0.34.2); AMD Linux требует основной пакет и ROCm runtime того же release. Для Lemonade — [v11.9.0](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0). Для LM Studio version GUI и version `lms` записываются раздельно, а runtime выбирается в шаге 3: изобретать имя пакета `gfx1151` нельзя. Уже установленную иную версию можно исследовать, но её результаты относятся именно к ней.

2. **Ветка Ollama: импорт и backend.** Запустите отдельный сервер в foreground на свободном loopback-порту. `OLLAMA_MODELS` задаёт отдельное хранилище; проверьте диск с учётом копии весов. Для ROCm:

   ```bash
   mkdir -p "$LAB_DIR/raw/ollama-models"
   export LAB_OLLAMA_CONFIG=ollama-rocm-8k
   OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS="$LAB_DIR/raw/ollama-models" OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_DEBUG=1 OLLAMA_VULKAN=0 ollama serve > "$LAB_DIR/raw/$LAB_OLLAMA_CONFIG-server.log" 2>&1
   ```

   Убедитесь, что в окружении нет оставшегося из прежнего опыта `ROCR_VISIBLE_DEVICES=-1`. В другом терминале с тем же `LAB_DIR` и `GGUF` создайте Modelfile и импортируйте без requant:

   ```bash
   python3 - "$GGUF" "$LAB_DIR/raw/Modelfile" <<'PY'
   import pathlib, sys
   model = pathlib.Path(sys.argv[1]).resolve()
   assert model.is_file() and "\n" not in str(model) and '"' not in str(model)
   pathlib.Path(sys.argv[2]).write_text(
       f'FROM "{model}"\nPARAMETER num_ctx 8192\nPARAMETER num_predict 2048\n')
   PY
   OLLAMA_HOST=127.0.0.1:11435 ollama create lab-model -f "$LAB_DIR/raw/Modelfile" > "$LAB_DIR/raw/ollama-import.txt" 2>&1
   OLLAMA_HOST=127.0.0.1:11435 ollama show --modelfile lab-model > "$LAB_DIR/raw/ollama-effective-modelfile.txt"
   ```

   Сверьте путь `FROM` в effective Modelfile с локальным blob и посчитайте его `sha256sum`: для single GGUF он должен совпасть с исходным. Не исполняйте строку `FROM` как shell. Сохраните template, stop tokens и параметры, фактический context из runner log. Образец исходного Modelfile не задаёт собственный template; различия автоматического шаблона сервиса с ЛР05 остаются частью исследуемой конфигурации.

   Выполните шаг 5 с URL `http://127.0.0.1:11435`, model `lab-model`. Лог должен явно показывать ROCm/gfx1151 и распределение слоёв; выключение Vulkan само по себе этого не доказывает. CPU fallback → `fail` для гипотезы ROCm, даже если текст правильный.

   Для дополнительной Vulkan-конфигурации остановите **созданный здесь** foreground-процесс, дождитесь освобождения памяти, задайте `LAB_OLLAMA_CONFIG=ollama-vulkan-8k` и повторите serve с `OLLAMA_VULKAN=1 ROCR_VISIBLE_DEVICES=-1`; задайте `GGML_VK_VISIBLE_DEVICES` по обнаруженному Vulkan device index. Новый `$LAB_OLLAMA_CONFIG-server.log` сохраняется отдельно от ROCm. Это диагностический способ исключить HIP-discovery, а фактический выбор всё равно подтверждается логом. Если CPU выбран снова, не называйте эту пробу Vulkan. Hash артефакта и Modelfile сохраняются; backend и конфигурация получают новое имя.

3. **Ветка LM Studio: приложение и runtime разделены.** Подготовьте локальный LM Studio/`lms`, затем:

   ```bash
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes-before.txt"
   lms runtime get
   lms runtime select
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes-selected.txt"
   lms import "$GGUF" --copy --user-repo lab/qwen35-9b --yes > "$LAB_DIR/raw/lms-import.txt" 2>&1
   lms ls > "$LAB_DIR/raw/lms-models.txt"
   ```

   В интерактивном выборе запишите точные runtime ID/version и backend Vulkan либо ROCm. Если нужный package уже установлен, `get` пропускается. Linux ROCm документирован, но точный package/device stack всё равно требует проверки на 395. Импорт по умолчанию перемещает файл, поэтому `--copy` существенен; после него найдите destination из вывода и проверьте его bytes/SHA-256. Не заменяйте импорт загрузкой похожего имени из каталога LM Studio.

   Выберите точный `model_key` из `lms ls` и сохраните его в `LMS_MODEL_KEY`, затем:

   ```bash
   lms load "$LMS_MODEL_KEY" --estimate-only --gpu max --context-length 8192 > "$LAB_DIR/raw/lms-estimate.txt"
   lms load "$LMS_MODEL_KEY" --gpu max --context-length 8192 --identifier lab-model > "$LAB_DIR/raw/lms-load.txt" 2>&1
   lms ps > "$LAB_DIR/raw/lms-loaded.txt"
   lms server start --port 1235 --bind 127.0.0.1 > "$LAB_DIR/raw/lms-server-start.txt" 2>&1
   lms log stream > "$LAB_DIR/raw/lms-prompt-log.txt" 2>&1
   ```

   Последняя команда работает в foreground в отдельном терминале. Убедитесь по runtime log, что `--gpu max` действительно offload на нужное устройство. Выполните шаг 5 с URL `http://127.0.0.1:1235`. Сохраните effective load/inference settings из приложения: flash attention, KV dtype, context, seed/sampling и template. `--estimate-only` — оценка LM Studio, не измерение RAM.

   Native tool parsing и default tool fallback — разные условия. Fallback может дописывать инструкции и преобразовывать сообщения; сохраните фактический model input из `lms log stream` для открытых fixtures и укажите режим. Если режим установить не удалось, запишите `unverified`, не делайте вывода о равных prompt. После опыта остановите свой log stream, выгрузите `lms unload lab-model`; созданный лабораторный server остановите через `lms server stop`. Вторая backend — новый выбранный runtime и отдельная конфигурация.

4. **Ветка Lemonade: собственный llama.cpp binary и exact GGUF.** Для наиболее строгого сравнения используйте каталог `bin` рабочей ROCm либо Vulkan сборки из ЛР04. Он должен содержать `llama-server` и необходимые libraries, а его прямой запуск должен уже пройти ЛР05. Задайте `LAB_LLAMA_BIN` абсолютным путём, `LAB_BACKEND=rocm` либо `vulkan`. Создайте отдельные config/cache, не меняя системный сервис:

   ```bash
   export LAB_BACKEND=rocm
   mkdir -p "$LAB_DIR/raw/lemonade-config" "$LAB_DIR/raw/lemonade-cache"
   python3 - "$LAB_DIR" "$GGUF" "$LAB_LLAMA_BIN" "$LAB_BACKEND" <<'PY'
   import json, pathlib, sys
   lab, gguf, binary, backend = sys.argv[1:]
   assert backend in {"rocm", "vulkan"}
   assert (pathlib.Path(binary) / "llama-server").is_file()
   assert pathlib.Path(gguf).is_file()
   config = {"host": "127.0.0.1", "port": 13315, "ctx_size": 8192,
       "max_loaded_models": 1, "broadcast": False, "offline": True,
       "auto_check_model_updates": False, "auto_update_models": False,
       "no_fetch_executables": True,
       "extra_models_dir": str(pathlib.Path(gguf).resolve().parent),
       "llamacpp": {"backend": backend, backend + "_bin": str(pathlib.Path(binary).resolve())}}
   pathlib.Path(lab, "raw/lemonade-config/config.json").write_text(json.dumps(config, indent=2))
   PY
   sha256sum "$LAB_LLAMA_BIN/llama-server" > "$LAB_DIR/raw/lemonade-backend-hash.txt"
   lemond "$LAB_DIR/raw/lemonade-cache" "$LAB_DIR/raw/lemonade-config" --port 13315 --host 127.0.0.1 --no-broadcast > "$LAB_DIR/raw/lemonade-server.log" 2>&1
   ```

   `extra_models_dir` сканируется для local GGUF; в минимуме родительский каталог должен содержать только выбранный контроль, иначе явно проверьте список. В отдельном терминале сохраните `curl --fail-with-body http://127.0.0.1:13315/v1/models` в `raw/lemonade-models.json`. Из списка определите импортированное имя и используйте **`extra.NAME`** как model ID в шаге 5. Canonical prefix отличает импортированный файл от совпавшего built-in/user alias. Запрос сам инициирует загрузку; не выполняйте `pull` для этого опыта.

   Лог должен показать нужный recipe, абсолютный binary, GGUF path, context, GPU backend и child command. Сохраните также inherited library environment, использованное при direct запуске ЛР04: одинаковый executable без одинаковых libraries не гарантирует одинаковый runtime. Если custom binary несовместим с Lemonade, сохраните `fail`; переход на builtin — отдельная deployment-конфигурация со своим binary hash. После пробы остановите только созданный `lemond` и проверьте отсутствие его оставшихся model runners.

5. **Выполните общие пробы для каждой выбранной конфигурации.** Пример для Ollama; для других сервисов замените URL, configuration ID и model ID из предыдущих шагов:

   ```bash
   export LAB_URL=http://127.0.0.1:11435
   export LAB_CONFIG=ollama-rocm
   export LAB_CASE=smoke-8k-cold-r1
   export LAB_MODEL_ID=lab-model
   python3 - "$LAB_DIR" "$LAB_MODEL_ID" "$LAB_CONFIG" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / "raw"
   for kind in ["chat", "tool"]:
       request = json.loads((raw / f"{kind}-request.json").read_text())
       request["model"] = sys.argv[2]
       (raw / f"{sys.argv[3]}-{kind}-request.json").write_text(json.dumps(request, ensure_ascii=False))
   PY
   curl --fail-with-body --silent --show-error "$LAB_URL/v1/models" > "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-api-models.json"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/$LAB_CONFIG-chat-request.json" --out "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-chat"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/$LAB_CONFIG-tool-request.json" --out "$LAB_DIR/raw/$LAB_CONFIG-$LAB_CASE-tool" --follow-tool
   ```

   Повторите streaming-вариант и полный round trip по ЛР05. Успех: final `LAB_READY`; разрешённый tool с аргументом `alpha`, соответствующий call ID и final `LAB_VALUE_42`. HTTP 200, текст с похожим JSON или `finish_reason=length` сами по себе не означают успех. Сохраните отклонённые/игнорируемые параметры и различие reasoning/final. В Ollama OpenAI API context задаётся через Modelfile, а наличие Chat Completions не доказывает все возможности Responses или поддержку конкретной агентной обвязки.

   Для каждой прошедшей конфигурации получите один cold и три warm повтора. Для каждого случая/типа запроса укажите, модель уже загружена или нет: tool, отправленный после chat, не является холодной загрузкой. Например, после первого chat задайте `LAB_CASE=smoke-8k-warm-r1` и повторите только chat-команду; далее `smoke-8k-warm-r2`, `smoke-8k-warm-r3`. Для streaming используйте `LAB_CASE=stream-8k-warm-r1` и соответствующий сохранённый request. Cache mode, model keep-alive, loading time, prefix reuse и concurrency запишите явно. Для второй backend/контекста создавайте отдельный raw-подкаталог до запуска и перенаправляйте туда все команды, request files и server logs; исходный лог не перезаписывать. Настоящий near-limit 8K probe и наблюдение memory выполняются по методике ЛР05; длина короткого fixture не становится 8K от одного флага сервера. Не переносите llama.cpp-specific `/tokenize` и `/apply-template` на эти сервисы: возьмите сохранённый JSON длинного fixture ЛР05, замените `model`, проверьте фактические input tokens/template и отсутствие обрезания по usage/logs этого сервиса, оставьте запас под output. Если токенизацию/обрезание подтвердить нельзя, near-limit fit остаётся `unverified`; если запрос не выполнялся — `not-run: tokenizer-accounting-unavailable`. Короткие HTTP/tools-пробы остаются самостоятельными результатами.

6. **Сопоставьте сервис с direct baseline.** Сравните manifests по слоям: weights → binary/runtime → backend → template/parser → effective generation settings → API. Только когда эти условия совпали, разность latency можно исследовать как влияние serving wrapper. В противном случае назовите результат сравнением deployments и перечислите различия. В частности, LM Studio fallback tools и Ollama patched runner не исчезают из описания лишь из-за одинакового GGUF. Для компонента, добавляемого далее в агентную обвязку, понадобится строка ledger и отдельная ЛР08, а не новый флаг несуществующего `local` provider.

7. **Расширение: Lemonade/vLLM после ЛР06.** Сначала сохраните версию Lemonade и его `backend_versions.json`, per-arch pin и recipe/model-family defaults. Это экспериментальный ROCm путь, у автора проверенный на gfx1151; он использует собственный relocatable bundle vLLM/Torch/Triton. Проверьте kernel/CWSR prerequisites из официальной инструкции. Создайте отдельный экземпляр/config для этой ветви: ограничения `offline`/`no_fetch_executables` из шага 4 специально запрещают установку. На этапе подготовки разрешите загрузку только выбранного release с конкретным `vllm.rocm_bin`, затем выполните `lemonade --host 127.0.0.1 --port 13315 --no-discovery backends install vllm:rocm` для **своего** экземпляра и сохраните фактический downloaded tag/hash и arch. После установки верните offline/no-fetch для серии.

   Выбранный native checkpoint должен иметь новый manifest и проверенные shards из ЛР06. Регистрация `user.*` recipe с одним HF именем без immutable revision не доказывает равенства checkpoint. Проверьте разрешение local snapshot/cache в вашей версии и фактический child `--model`; если закреплённый artifact путь не удалось обеспечить, оставьте `no-artifact` для парного сравнения. Не подменяйте его built-in FP16 либо FP8-моделью. Память BF16/FP16/native quant пересчитывается отдельно от GGUF.

   Выполните chat/tools и сравните child args с direct vLLM. Сервис управляет model, served name, host/port, context и частью cache/graph flags, добавляет family parser settings. Нельзя просто перенести всю команду ЛР06 в строку `vllm.args`. Сохраните health/backend URL только в evidence координатора; прямой `/metrics` child не является публичной возможностью общего API. Эта ветвь не входит в минимальный зачёт; неподготовленный bundle/точный artifact оставляет явный `not-run`/`no-artifact`.

## Таблицы результатов

| Сервис | App / CLI version | Runtime ID / binary hash | Backend / GPU доказательство | Выбран в минимум | Статус / причина |
| --- | --- | --- | --- | --- | --- |
| Ollama | | | | | |
| LM Studio | | | | | |
| Lemonade / llama.cpp | | | | | |
| Lemonade / vLLM, расширение | | | | | |

| Configuration | Source/imported SHA-256 | Template / tool mode | Context / cache / thinking / sampling | Отличия от direct baseline |
| --- | --- | --- | --- | --- |
| | | | | |

| Configuration / repeat | Cold / warm | Chat / streaming / full tools | Wall / TTFT, s | Peak RAM / GPU, bytes | Evidence / verdict |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Что сдать

Отчёт по двум выбранным конфигурациям, установочные/runtime pins, source и imported file hashes, команды импорта, effective Modelfile/runtime/configuration, открытые model prompts, server/runner logs, raw HTTP/SSE и memory observations. Для каждой непроверенной ветви указать причину и следующий конкретный шаг. В выводе отметить, где сравним wrapper overhead, а где меняется весь deployment.

## Критерии завершения

- [ ] Два сервиса рассмотрены на одном артефакте; для каждого есть измерение или воспроизводимый `fail` с evidence.
- [ ] Импортированный GGUF проверен по bytes/hash; загрузка alias не подменяет provenance.
- [ ] App version, runtime version и фактическая GPU backend записаны раздельно.
- [ ] Сохранён полный tool round trip и streaming; native/fallback parsing указан явно.
- [ ] Direct baseline сравнивается с известными условиями, отсутствующие метрики не заполнены нулями.
- [ ] Третья/дополнительные ветви отмечены `not-run`, если не выполнялись; Lemonade/vLLM не унаследовал память GGUF.

## Контрольные вопросы

1. Почему сравнение Ollama и LM Studio не равно сравнению двух полностью независимых inference engines?
2. Что нужно проверить после успешного импорта GGUF, кроме его отображения в списке моделей?
3. Как tool fallback изменяет вопрос «помогла ли обвязка модели»?
4. Почему `--gpu max` или `OLLAMA_VULKAN=0` сами по себе не доказывают нужный GPU path?
5. При каких условиях можно приписать разность latency именно serving wrapper?

## Источники

- Ollama: [Linux install](https://docs.ollama.com/linux), [GPU/gfx1151 и выбор backend](https://docs.ollama.com/gpu), [GGUF import](https://docs.ollama.com/import), [Modelfile](https://docs.ollama.com/modelfile), [OpenAI API limits](https://docs.ollama.com/api/openai-compatibility).
- LM Studio: [Linux download](https://lmstudio.ai/download), [runtime CLI](https://lmstudio.ai/docs/cli/runtime/runtime), [import](https://lmstudio.ai/docs/cli/local-models/import), [load](https://lmstudio.ai/docs/cli/local-models/load), [server start](https://lmstudio.ai/docs/cli/serve/server-start), [native/default tools](https://lmstudio.ai/docs/developer/openai-compat/tools).
- Lemonade: [установка и supported platforms](https://lemonade-server.ai/docs/guide/install/), [CLI и выбор экземпляра](https://lemonade-server.ai/docs/guide/cli/), [configuration и custom binary](https://lemonade-server.ai/docs/guide/configuration/), [local extra models и canonical IDs](https://lemonade-server.ai/docs/guide/configuration/custom-models/), [experimental vLLM recipe и ограничения](https://lemonade-server.ai/docs/guide/configuration/vllm/).
- [Матрица движков и сервисов](../local-inference-engines.md), [общие fixtures](fixtures/README.md), [метод исследования](../method.md).
