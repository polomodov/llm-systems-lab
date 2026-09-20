# ЛР06. vLLM, SGLang и Transformers на ROCm

## Паспорт

- Время: 4–8 часов плюс загрузка checkpoint, контейнеров и сборка SGLang.
- Предпосылки: сданы [ЛР03](LAB03-artifacts.md) и [ЛР05](LAB05-context-tools.md); Linux на Ryzen AI Max+ 395, рабочий AMD kernel driver, доступ к `/dev/kfd` и DRM render node, Docker, Git, Python 3.11+, свободный диск под большие образы и BF16 checkpoint.
- Готовность: команды опираются на источники, проверенные 21.09.2026. **Аппаратный запуск в этой лаборатории ещё не выполнен.** Документированная поддержка не гарантирует работоспособность конкретного image/kernel/model сочетания.
- Минимум: один native checkpoint Qwen3.5-9B; по одной конфигурации vLLM, SGLang и прямого Transformers `generate`. Сначала 4096 токенов/одна последовательность; для прошедших серверов — 8192 и HTTP/tools-проверка ЛР05. Другие модели, quants, 16K/32K и tuning — расширение.

## Цель

Проверить три исполнения одного закреплённого native checkpoint на ROCm/gfx1151 и отделить ошибки аппаратного стека, модели, kernels и OpenAI-совместимого сервера.

## Проверяемая гипотеза

«Один BF16 checkpoint Qwen3.5-9B загружается на gfx1151 в каждом из трёх закреплённых runtime и выдаёт правильный контрольный ответ; серверные реализации дополнительно завершают разрешённый tool round trip». Это проверка доступности и совместимости, а не заявление о равной скорости или численно идентичных logits.

## Подготовка

```bash
npm run lab:new -- --lab LAB06 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB06-my-session"
export LAB03_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB05_DIR="$PWD/experiments/local-models/measurements/LAB05-my-session"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
cp "$LAB03_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/fetch_artifact.py"
cp "$LAB05_DIR/raw/http_probe.py" "$LAB_DIR/raw/http_probe.py"
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
docker version > "$LAB_DIR/raw/docker-version.txt"
```

Подставьте свои session IDs. `http_probe.py` — сохранённый открытый HTTP/SSE driver из ЛР05, не агентная обвязка. Сверьте аппаратный паспорт и бюджеты из ЛР02; все двигатели запускаются **последовательно**, с выгрузкой предыдущего. Docker с GPU devices используется координатором исследования; это не sandbox для кода модели.

## Порядок выполнения

1. **Закрепите новый артефакт и пересчитайте память.** GGUF из ЛР03 нельзя подставить вместо BF16 native checkpoint. Выбран официальный `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. Только его safetensors занимают **19 306 310 880 bytes**, около **17,982 GiB**; runtime, cache и временные буферы сверху. Сохраните metadata и manifest без загрузки весов:

   ```bash
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, sys, urllib.request
   out = pathlib.Path(sys.argv[1]) / "raw"
   repo = "Qwen/Qwen3.5-9B"
   rev = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
   url = f"https://huggingface.co/api/models/{repo}/revision/{rev}?blobs=true"
   with urllib.request.urlopen(url, timeout=60) as response:
       metadata = json.load(response)
   assert metadata["sha"] == rev
   (out / "native-publisher-metadata.json").write_text(json.dumps(metadata, indent=2))
   files = []
   for item in metadata["siblings"]:
       name = item["rfilename"]
       if name.endswith((".safetensors", ".json", ".txt", ".jinja")) or name == "LICENSE":
           files.append({"path": name, "bytes": item["size"],
                         "sha256": item.get("lfs", {}).get("sha256"),
                         "git_blob_id": item.get("blobId")})
   manifest = {"model_id": repo, "quantization": "BF16 native checkpoint",
               "artifact": {"repository": repo, "revision": rev, "files": files,
                            "total_bytes": sum(f["bytes"] for f in files)}}
   (out / "native-artifact.json").write_text(json.dumps(manifest, indent=2) + "\n")
   print(manifest["artifact"]["total_bytes"])
   PY
   ```

   Проверьте `config.json`/quantization metadata и отсутствие неожиданной замены архитектуры. Для маленьких Git-файлов HF может не публиковать SHA-256: сохранённый `git_blob_id` и локально вычисленный SHA — разные поля. После проверки диска и бюджета загрузите и проверьте файлы скриптом ЛР03:

   ```bash
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/native-artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/native-download.json"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/native-artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/native-verification.json"
   export NATIVE_MODEL_DIR="$LAB_STORAGE/Qwen/Qwen3.5-9B/c202236235762e1c871ad0ccb60c8ee5ba337b9a"
   ```

   Одинаковый каталог монтируется read-only во все три runtime. Условия `HF_HUB_OFFLINE=1` препятствуют незаметной догрузке другой ревизии. Отсутствующие files → `no-artifact`, а не выдуманный размер 0. FP8/AWQ/GPTQ/MXFP4 и dequantized gpt-oss — новые артефакты: support конкретного kernel на gfx1151 проверяется отдельно. Native BF16 крупных MoE не допускается лишь потому, что GGUF этой семьи поместился.

2. **Подготовьте закреплённые runtime.** Для vLLM используйте опубликованный ROCm image v0.29.0 по digest, а не изменяемый `latest`:

   ```bash
   export VLLM_IMAGE='vllm/vllm-openai-rocm@sha256:e5e47f6aaab675c252c381f0dac237b31b10d87bb74d092b07fb4065efd7f5a1'
   docker pull "$VLLM_IMAGE" > "$LAB_DIR/raw/vllm-pull.txt" 2>&1
   docker image inspect "$VLLM_IMAGE" > "$LAB_DIR/raw/vllm-image.json"
   ```

   Upstream перечисляет gfx1151 и ROCm ≥7.0.2 для Ryzen AI; контейнер не заменяет host kernel driver. Не ставьте поверх образа произвольные новые Torch/Triton. Несовместимость образа с этим устройством фиксируется как `fail` с логом.

   Для SGLang v0.5.20 есть отдельный Dockerfile gfx1151. Generic MI300/CDNA image не является эквивалентом. Соберите из закреплённого commit:

   ```bash
   git clone --filter=blob:none --no-checkout https://github.com/sgl-project/sglang "$LAB_DIR/raw/sglang-src"
   git -C "$LAB_DIR/raw/sglang-src" checkout --detach 94602c9c2b7cbdb8efd5c52802dac6a1c180089e
   git -C "$LAB_DIR/raw/sglang-src" rev-parse HEAD > "$LAB_DIR/raw/sglang-commit.txt"
   docker build --progress=plain -f "$LAB_DIR/raw/sglang-src/docker/rocm-gfx1151.Dockerfile" -t lab-sglang:gfx1151-94602c9 "$LAB_DIR/raw/sglang-src" > "$LAB_DIR/raw/sglang-build.txt" 2>&1
   export SGLANG_IMAGE="$(docker image inspect --format '{{.Id}}' lab-sglang:gfx1151-94602c9)"
   docker image inspect "$SGLANG_IMAGE" > "$LAB_DIR/raw/sglang-image.json"
   ```

   Dockerfile закрепляет AMD base image с ROCm 7.2.4/PyTorch 2.9.1 и применяет wave32/gfx1151 patches; `SGLANG_USE_AITER=0` и Triton attention существенны. Автор исходного PR проверял Qwen3.5-9B на 395/8060S **в WSL2**. Здесь проверяется native Linux; это дополнительное условие, а не уже выполненная валидация. Часть build dependencies Dockerfile разрешает при сборке: commit не гарантирует побитово одинаковый повторный образ. Сохраните package freeze и используйте полученный image ID для всей серии; при необходимости архивируйте образ через `docker image save` и hash архива.

3. **Проверьте GPU до загрузки модели.** В Bash укажите render node из ЛР02, не выбирайте его по предположению:

   ```bash
   set -euo pipefail
   export LAB_RENDER=/dev/dri/renderD128
   test -c "$LAB_RENDER"
   test -c /dev/kfd
   export GPU_PROBE_DIR="$LAB_DIR/raw/gpu-probe-01"
   mkdir "$GPU_PROBE_DIR"
   GPU_ARGS=(--device=/dev/kfd --device=/dev/dri --group-add "$(stat -c '%g' /dev/kfd)" --group-add "$(stat -c '%g' "$LAB_RENDER")" --security-opt seccomp=unconfined --ipc=host)
   for RUNTIME in vllm sglang; do
     if [ "$RUNTIME" = vllm ]; then LAB_IMAGE="$VLLM_IMAGE"; else LAB_IMAGE="$SGLANG_IMAGE"; fi
     if docker run --rm "${GPU_ARGS[@]}" --entrypoint python3 "$LAB_IMAGE" -c 'import json,torch; assert torch.version.hip; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); print(json.dumps({"torch":torch.__version__,"hip":torch.version.hip,"device":p.name,"arch":p.gcnArchName,"total_memory":p.total_memory})); assert "gfx1151" in p.gcnArchName' > "$GPU_PROBE_DIR/$RUNTIME-gpu.json" 2> "$GPU_PROBE_DIR/$RUNTIME-gpu.stderr"; then
       printf '0\n' > "$GPU_PROBE_DIR/$RUNTIME-exit.txt"
     else
       LAB_PROBE_EXIT=$?
       printf '%s\n' "$LAB_PROBE_EXIT" > "$GPU_PROBE_DIR/$RUNTIME-exit.txt"
       printf 'GPU probe failed: %s; stop before loading models.\n' "$RUNTIME" >&2
       exit "$LAB_PROBE_EXIT"
     fi
     docker run --rm --entrypoint python3 "$LAB_IMAGE" -m pip freeze > "$GPU_PROBE_DIR/$RUNTIME-packages.txt"
     printf '%s\n' "$LAB_IMAGE" > "$GPU_PROBE_DIR/$RUNTIME-ready-image.txt"
   done
   ```

   Выполняйте блок в отдельной Bash-сессии: ненулевой probe явно завершает её до загрузки моделей, сохраняя исходный exit code. Файл `ready-image.txt` появляется только после успешной проверки данного image. Повтор пробы получает новый каталог, например `gpu-probe-02`; прежний `mkdir` намеренно не разрешает перезапись. Не используйте старый marker после смены driver или image. В терминалы запуска перенесите актуальные `GPU_PROBE_DIR`, image variables и массив `GPU_ARGS` — Bash-массив автоматически не экспортируется. Имя `torch.cuda` штатно используется PyTorch и на ROCm. Наличие API не доказывает, что все model kernels поддержаны. Измерьте свободную память и наблюдайте пик средствами ЛР02/05, включая page cache и временную загрузку. Доля `0.5` ниже — начальное ограничение; в vLLM и SGLang это **разные** механизмы, не одинаковое число bytes. Сначала сопоставьте его с опубликованным runtime объёмом и бюджетом ОС.

4. **Запустите vLLM.** Сохраните `--help` образа до исполнения. Команда содержит минимальный контекст, одну последовательность, BF16, отключённые prefix caching и CUDA/HIP graphs, явные parsers для Qwen3.5:

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/vllm-ready-image.txt")" = "$VLLM_IMAGE"
   export LAB_CONTEXT=4096
   export LAB_CONFIG=vllm-c4096-eager-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   mkdir "$SERVER_EVIDENCE"
   docker run --rm --entrypoint vllm "$VLLM_IMAGE" serve --help > "$SERVER_EVIDENCE/help.txt" 2>&1
   docker run --rm --name lab06-vllm "${GPU_ARGS[@]}" -p 127.0.0.1:8000:8000 -v "$NATIVE_MODEL_DIR:/model:ro" -e HF_HUB_OFFLINE=1 "$VLLM_IMAGE" --model /model --served-model-name lab-model --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len "$LAB_CONTEXT" --max-num-seqs 1 --gpu-memory-utilization 0.5 --enforce-eager --no-enable-prefix-caching --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder > "$SERVER_EVIDENCE/server.log" 2>&1
   ```

   Это foreground-команда в отдельном терминале. `LAB_CONFIG` включает engine/context и уникальный номер старта; для перезапуска даже тех же настроек выберите следующий номер. `mkdir` без `-p` останавливает блок при попытке повторно использовать архив. В другом терминале задайте те же `LAB_CONFIG`/`SERVER_EVIDENCE`, проверьте `/v1/models`, затем контрольный запрос по шагу 7. Следите за compile errors, attention backend и реальной offload/residency. После измерения остановите **этот** контейнер командой `docker stop lab06-vllm`, зафиксируйте освобождение памяти. Не заменяйте `--model` сетевым alias при ошибке local path.

5. **Запустите SGLang.** Все зависимости уже входят в собранный image. Сохраните его help и запустите ту же модель:

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/sglang-ready-image.txt")" = "$SGLANG_IMAGE"
   export LAB_CONTEXT=4096
   export LAB_CONFIG=sglang-c4096-graph1-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   mkdir "$SERVER_EVIDENCE"
   docker run --rm --entrypoint python3 "$SGLANG_IMAGE" -m sglang.launch_server --help > "$SERVER_EVIDENCE/help.txt" 2>&1
   docker run --rm --name lab06-sglang "${GPU_ARGS[@]}" -p 127.0.0.1:30000:30000 -v "$NATIVE_MODEL_DIR:/model:ro" -e HF_HUB_OFFLINE=1 -e SGLANG_USE_AITER=0 "$SGLANG_IMAGE" python3 -m sglang.launch_server --model-path /model --served-model-name lab-model --host 0.0.0.0 --port 30000 --dtype bfloat16 --attention-backend triton --context-length "$LAB_CONTEXT" --mem-fraction-static 0.5 --max-running-requests 1 --cuda-graph-max-bs-decode 1 --disable-radix-cache --reasoning-parser qwen3 --tool-call-parser qwen3_coder > "$SERVER_EVIDENCE/server.log" 2>&1
   ```

   Сначала воспроизводится близкая к PR конфигурация graph decode batch 1; это отличается от eager vLLM и фиксируется в сравнении. Ошибка graph capture допускает отдельный диагностический запуск с `--disable-cuda-graph`, после проверки флага в сохранённом help; это **новая конфигурация**. После HTTP-пробы остановите только `lab06-sglang`. Не добавляйте WSL `/dev/dxg` и WSL library mounts в native Linux команду.

6. **Запустите reference непосредственно через Transformers.** Используйте тот же SGLang image ради уже совместимых ROCm/Torch/Transformers, но не вызывайте SGLang server. Получается отдельный execution path с общими библиотеками, а не независимая реализация всех kernels. Сохраните в `$LAB_DIR/raw/reference.py`:

   ```python
   import json, pathlib, time, torch, transformers
   from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

   assert torch.version.hip and torch.cuda.is_available()
   assert "gfx1151" in torch.cuda.get_device_properties(0).gcnArchName
   request = json.loads(pathlib.Path("/evidence/raw/chat-request.json").read_text())
   tokenizer = AutoTokenizer.from_pretrained("/model", local_files_only=True)
   # Явный BF16, SDPA и полный checkpoint; vision inputs в этой пробе отсутствуют.
   model = Qwen3_5ForConditionalGeneration.from_pretrained(
       "/model", dtype=torch.bfloat16, attn_implementation="sdpa",
       local_files_only=True).to("cuda:0").eval()
   template = tokenizer.apply_chat_template(
       request["messages"], tokenize=False, add_generation_prompt=True,
       enable_thinking=False)
   pathlib.Path("/evidence/raw/reference-prompt.txt").write_text(template)
   inputs = tokenizer(template, return_tensors="pt", add_special_tokens=False).to("cuda:0")
   assert inputs.input_ids.shape[1] + request["max_tokens"] <= 4096
   torch.cuda.reset_peak_memory_stats()
   torch.cuda.synchronize()
   start = time.perf_counter()
   with torch.inference_mode():
       outputs = model.generate(**inputs, max_new_tokens=request["max_tokens"], do_sample=False)
   torch.cuda.synchronize()
   elapsed = time.perf_counter() - start
   generated = outputs[0, inputs.input_ids.shape[1]:]
   print(json.dumps({"torch": torch.__version__, "hip": torch.version.hip,
       "transformers": transformers.__version__, "thinking": False,
       "sampling": "greedy", "input_tokens": inputs.input_ids.shape[1],
       "output_tokens": generated.numel(), "generate_seconds": elapsed,
       "peak_allocated_bytes_after_load": torch.cuda.max_memory_allocated(),
       "peak_reserved_bytes_after_load": torch.cuda.max_memory_reserved(),
       "final": tokenizer.decode(generated, skip_special_tokens=True)}, ensure_ascii=False))
   ```

   ```bash
   set -euo pipefail
   test "$(cat "$GPU_PROBE_DIR/sglang-ready-image.txt")" = "$SGLANG_IMAGE"
   docker run --rm "${GPU_ARGS[@]}" -v "$NATIVE_MODEL_DIR:/model:ro" -v "$LAB_DIR:/evidence" -e HF_HUB_OFFLINE=1 "$SGLANG_IMAGE" python3 /evidence/raw/reference.py > "$LAB_DIR/raw/reference-result.json" 2> "$LAB_DIR/raw/reference.stderr"
   ```

   Загрузка через CPU и `.to()` может временно держать дополнительные копии: внешний peak RAM наблюдается отдельно, он не включён в два Torch-счётчика после загрузки. Fast DeltaNet extensions могут отсутствовать; fallback и предупреждения сохраняются, никакой скрытой установки `latest`. Greedy/non-thinking — диагностические условия reference. Они не подменяют авторские sampling settings для quality benchmark. Здесь нет HTTP, TTFT или tools execution; эти поля — `not-applicable`, не нули.

7. **Выполните одинаковые серверные пробы и разберите различия.** Для каждого работающего сервера задайте URL без `/v1`, сохраните `/v1/models` и примените driver ЛР05:

   ```bash
   set -euo pipefail
   export LAB_URL=http://127.0.0.1:8000
   export LAB_ENGINE=vllm
   export LAB_CONFIG=vllm-c4096-eager-01
   export SERVER_EVIDENCE="$LAB_DIR/raw/$LAB_CONFIG"
   export LAB_REPEAT=1
   test -d "$SERVER_EVIDENCE"
   export PROBE_EVIDENCE="$SERVER_EVIDENCE/protocol-r$LAB_REPEAT"
   mkdir "$PROBE_EVIDENCE"
   curl --fail-with-body --silent --show-error "$LAB_URL/v1/models" > "$PROBE_EVIDENCE/models.json"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/chat-request.json" --out "$PROBE_EVIDENCE/chat"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/tool-request.json" --out "$PROBE_EVIDENCE/tool" --follow-tool
   ```

   Для SGLang замените URL на `http://127.0.0.1:30000`, имя на `sglang` и `LAB_CONFIG` на ID реально запущенного сервера. Для следующего повтора увеличьте `LAB_REPEAT`: существующий каталог не переиспользуется. Затем создайте streaming-варианты JSON и повторите полный round trip по ЛР05, сохраняя результаты под отдельными префиксами `$PROBE_EVIDENCE/chat-stream` и `$PROBE_EVIDENCE/tool-stream`; не используйте её жёстко заданный URL `8080`. Первый chat после старта и следующие обращения обозначайте отдельно — tool-запрос после chat уже не является первым запросом сервера. Сохраните фактическое тело запроса, thinking/sampling, parser, template hash, finish reason и final content. При сравнении с reference явно укажите различие режимов; для согласованной серии сначала задайте одинаковый thinking/sampling поддержанным каждой версией способом и сохраните новые JSON.

   После успешного 4K smoke увеличьте только `LAB_CONTEXT` до 8192 и задайте новый `LAB_CONFIG` в шаге запуска, например `vllm-c8192-eager-01`. Остановите прежний сервер до старта нового. В терминале клиента укажите новый `SERVER_EVIDENCE`; перед другими inference-запросами выполните один первый запрос и три повтора:

   ```bash
   set -euo pipefail
   test -d "$SERVER_EVIDENCE"
   for SAMPLE in cold-r1 warm-r1 warm-r2 warm-r3; do
     SAMPLE_DIR="$SERVER_EVIDENCE/$SAMPLE"
     mkdir "$SAMPLE_DIR"
     python3 "$LAB_DIR/raw/http_probe.py" --url "$LAB_URL" --request "$LAB_DIR/raw/chat-request.json" --out "$SAMPLE_DIR/chat"
   done
   ```

   Здесь cold означает первый inference-запрос после запуска нового server process, а не гарантированно пустой OS page cache. Затем выполните protocol cases с новыми каталогами повторов. При ошибке блок останавливается, исходные файлы сохраняются; последующие запросы помечаются `not-run` до решения о новой попытке. 8K в этой минимальной работе означает настройку сервера и короткий protocol smoke, **не подтверждение размещения полного 8K входа**. Не сравнивайте JIT cold с warm, HTTP wall time с чистым `generate_seconds`, preallocated pool с Torch allocated. Три runtime не обязаны выдать побитово одинаковый текст.

   **Отдельное расширение — near-limit input.** Генератор ЛР05 использует специфичные llama.cpp `/apply-template` и `/tokenize` на порту 8080; он не является готовой командой для vLLM/SGLang. До расширения нужен независимо проверенный подсчёт через tokenizer той же native model revision и фактический template выбранного сервера, с теми же special tokens, thinking и tools. Сохраните template hash, rendered prompt и token count; сверяйте count с `usage.prompt_tokens` на коротком запросе. После совпадения подготовьте новый длинный request с явно оставленным output reserve, отдельными configuration/repeat prefixes и проверкой отсутствия truncation. Если воспроизвести effective template или count не удалось, отметьте near-limit как `blocked/not-run`; прежний счётчик llama.cpp не доказывает вместимость этого deployment. Такое расширение не входит в минимум ЛР06.

## Таблицы результатов

| Runtime / image ID | Torch / ROCm / Triton / Transformers | gfx1151 probe | Документированный путь | Локальный статус и evidence |
| --- | --- | --- | --- | --- |
| vLLM | | | | |
| SGLang | | | | |
| Transformers reference | | | | |

| Configuration | Artifact revision / hash manifest | Context / concurrency | Dtype / cache / graphs / parser | Peak RAM / GPU, bytes | Статус |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

| Configuration / repeat | Cold или warm | Chat final | Tools / streaming | Wall / TTFT, s | Output tokens / finish reason | Evidence / причина отсутствия |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

## Что сдать

Заполненный отчёт, новый native artifact manifest и проверку файлов, image inspect/package freeze/build log, GPU probes, команды запуска, server logs, raw HTTP/SSE и reference output, таблицу 4K и допустимых 8K проб. В выводе разделить «поддержка описана автором», «runtime собран», «модель загружена», «протокол прошёл» и «измерена производительность».

## Критерии завершения

- [ ] Native checkpoint закреплён и его память рассчитана независимо от GGUF.
- [ ] Каждая из трёх ветвей имеет наблюдение либо `fail`/`not-run`/`no-artifact` с конкретной причиной.
- [ ] Реальный gfx1151/ROCm подтверждён до вывода о GPU работе; CPU fallback не назван успехом ROCm.
- [ ] Для успешно загруженных серверов сохранены chat и полный tool round trip, включая streaming.
- [ ] Изменения context, graph/cache, sampling и kernel path отражены как условия конфигурации.
- [ ] Ни один engine smoke не выдан за агентный run; подключение обвязок остаётся задачей ЛР08.

## Контрольные вопросы

1. Почему safetensors не обозначает конкретную точность, а размер GGUF не описывает этот checkpoint?
2. Почему успешный `torch.cuda.is_available()` не доказывает поддержку MXFP4 kernels на gfx1151?
3. Как отделить ошибку template/parser от ошибки модели с помощью reference?
4. Что фиксирует image digest, и чего не фиксирует один Git commit Dockerfile?
5. Какие различия графов, cache и измерительных точек мешают прямому сравнению tokens/s?

## Источники

- [vLLM: GPU/ROCm installation и поддержка gfx1151](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/), [v0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0), [metadata закреплённого Docker tag](https://hub.docker.com/v2/repositories/vllm/vllm-openai-rocm/tags/v0.29.0), [server arguments](https://docs.vllm.ai/en/stable/cli/serve/).
- [SGLang: закреплённый gfx1151 Dockerfile](https://github.com/sgl-project/sglang/blob/94602c9c2b7cbdb8efd5c52802dac6a1c180089e/docker/rocm-gfx1151.Dockerfile), [исходный PR и границы WSL2 проверки](https://github.com/sgl-project/sglang/pull/33939), [server arguments](https://docs.sglang.io/docs/advanced_features/server_arguments).
- [Qwen3.5-9B: закреплённый checkpoint и parsers](https://huggingface.co/Qwen/Qwen3.5-9B/tree/c202236235762e1c871ad0ccb60c8ee5ba337b9a), [Transformers Qwen3.5](https://huggingface.co/docs/transformers/model_doc/qwen3_5).
- [AMD: PyTorch installation](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html), [native Linux Ryzen compatibility](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html).
- [Матрица движков и ограничения артефактов](../local-inference-engines.md), [общие fixtures](fixtures/README.md).
