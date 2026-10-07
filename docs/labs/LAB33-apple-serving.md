# ЛР33. Ollama и LM Studio на Apple Silicon

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Сервисные приложения / `target-machine` |
| Время | 3–5 часов плюс установка |
| Предпосылки | LAB32; соответствующие manifests LAB29–31 |
| Минимум | Ollama/Metal GGUF, LM Studio/Metal GGUF и LM Studio/MLX: smoke каждого либо evidence blocker |

## Цель

Проверить удобство и корректность API сервисных приложений и отличить накладные расходы wrapper от изменения внутреннего inference runtime.

## Проверяемая гипотеза

Приложение сохраняет требуемый tool/streaming протокол при закреплённых weights, runtime и настройках. Накладные расходы можно изолировать только при совпадении внутреннего движка и всех существенных условий с direct baseline.

## Подготовка

Приложения устанавливаются отдельно на закреплённых версиях, не обновляются во время серии. Сохраните версии приложения, CLI и runtime package. [Общий протокол](../../experiments/local-models/apple/README.md) и LAB32 определяют контекст/повторы.

```sh
npm run lab:new -- --lab LAB33 --session apple-serving
export LAB_DIR='experiments/local-models/measurements/LAB33-apple-serving'
ollama --version > "$LAB_DIR/raw/ollama-version.txt" 2>&1
ollama create --help > "$LAB_DIR/raw/ollama-create-help.txt" 2>&1
lms --help > "$LAB_DIR/raw/lms-help.txt" 2>&1
lms runtime --help > "$LAB_DIR/raw/lms-runtime-help.txt" 2>&1
lms import --help > "$LAB_DIR/raw/lms-import-help.txt" 2>&1
lms load --help > "$LAB_DIR/raw/lms-load-help.txt" 2>&1
lms server start --help > "$LAB_DIR/raw/lms-server-help.txt" 2>&1
```

Отсутствующий CLI/runtime записывается как blocker выбранной ветви. Не заполняйте version по имени installer или GUI alone.

## Порядок выполнения

1. Подготовьте отдельные условия `ollama-metal`, `lm-studio-metal`, `lm-studio-mlx` и direct baseline. Для первых двух используйте **те же** GGUF hashes из LAB29, для третьего — отдельный pinned MLX artifact. Импорт не должен менять исходные файлы или автоматически обновлять веса. Для shard-импорта сверяйте поддержку выбранной версии; один первый shard без остальных не является моделью.

2. Пример Ollama для поддержанного single-file GGUF. Перед записью `Modelfile` убедитесь, что путь не содержит кавычек/переводов строки; подставьте уже закреплённый absolute path:

   ```sh
   cat > "$LAB_DIR/raw/Modelfile" <<'MODEL'
   FROM /absolute/path/to/pinned-model.gguf
   PARAMETER num_ctx 8192
   MODEL
   ollama create lab-apple-gguf -f "$LAB_DIR/raw/Modelfile" \
     > "$LAB_DIR/raw/ollama-import.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/ollama-import-exit.txt"
   ollama show lab-apple-gguf --modelfile > "$LAB_DIR/raw/ollama-modelfile.txt" 2>&1
   ollama show lab-apple-gguf > "$LAB_DIR/raw/ollama-model.txt" 2>&1
   ```

   Импорт выполняется только после замены placeholder. Закрепите template/defaults и blob hashes; same alias не доказывает идентичность. Используйте один собственный loopback server; при CLI-запуске, после остановки фонового экземпляра приложения:

   ```sh
   OLLAMA_HOST=127.0.0.1:11434 ollama serve > "$LAB_DIR/raw/ollama-server.txt" 2>&1
   ```

   Если сервер уже управляется приложением, не запускайте второй — архивируйте журналы существующего. Подтвердите Metal, runner и offload по логам. Если реально выбран другой engine/artifact, оформите отдельное deployment condition; этот GGUF-профиль не доказывает применимость к MLX runner.

3. Пример LM Studio (сверить интерфейс по pinned help):

   ```sh
   lms import "$LOCAL_GGUF" > "$LAB_DIR/raw/lms-import.txt" 2>&1
   lms ls > "$LAB_DIR/raw/lms-models.txt" 2>&1
   lms runtime ls > "$LAB_DIR/raw/lms-runtimes.txt" 2>&1
   ```

   Запишите фактический model key из списка и выбранный runtime package/version. Загрузите только эту модель:

   ```sh
   export LMS_MODEL_KEY='<ключ импортированной модели из lms ls>'
   lms load "$LMS_MODEL_KEY" --identifier lab-model --context-length 8192 \
     > "$LAB_DIR/raw/lms-load.txt" 2>&1
   lms server start --port 1234 > "$LAB_DIR/raw/lms-server-start.txt" 2>&1
   lms ps > "$LAB_DIR/raw/lms-loaded.txt" 2>&1
   ```

   В настройках сервера выключите доступ из LAN и проверьте фактический listener; интерфейс зависит от версии. MLX-вариант импортируйте/зарегистрируйте способом, документированным установленным runtime: CLI для GGUF не считать автоматически поддержкой MLX-directory. Если нельзя сохранить exact revision/hash — blocker. Сохраните выбранный runtime и загрузочные логи для обеих LM Studio ветвей, выгружая предыдущую модель перед следующей.

4. Для каждого приложения сохраните `/v1/models`, например:

   ```sh
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:11434/v1/models \
     > "$LAB_DIR/raw/ollama-api-models.json"
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:1234/v1/models \
     > "$LAB_DIR/raw/lms-api-models.json"
   ```

   Выполняйте запрос только к текущему серверу. Создайте свои копии четырёх запросов LAB32 с фактическим alias. На одном допущенном контексте выполните warmup + три повтора chat/tool × JSON/SSE, затем один отменённый запрос и recovery. Сохраните usage, final/IDs, raw SSE, TTFT и memory evidence. Native tool template и fallback template — отдельные условия; не скрывайте fallback после parser failure.

5. Повторите те же HTTP cases direct llama-server/MLX-LM из LAB32 при совпадающем prompt и настройках. Если внутренний commit/build/tokenizer/quant не совпадает или неизвестен, вывод формулируйте как сравнение deployments. Не вычитайте TTFT двух разных engines как «чистый overhead GUI».

6. Запишите deployment manifest каждого приложения: app/CLI/runtime versions, hashes весов, template, context/slots, cache/loading policy, observed backend/runner и процесс. После завершения остановите или выгрузите только свои лабораторные модели штатными средствами приложения.

## Таблицы результатов

| Deployment | App / CLI / runtime pin | Artifact hash | Backend подтверждён | Protocol pass/attempts | Median TTFT / total s | Память / failures |
| --- | --- | --- | --- | --- | --- | --- |
| Ollama GGUF | | | | | | |
| LM Studio GGUF | | | | | | |
| LM Studio MLX | | | | | | |

| Пара с direct baseline | Совпадающие условия | Различия / неизвестное | Overhead или deployment comparison |
| --- | --- | --- | --- |
| | | | |

## Что сдать

Отчёт/TSV/manifest, version/help, import/runtime/identity evidence, deployment manifests, requests и результаты каждого повтора с памятью. Ошибки импорта и недоступные ветви остаются в реестре попыток.

## Критерии завершения

- [ ] Три ветви проверены или имеют конкретный blocker.
- [ ] Exact weights и внутренний runtime различаются от версии GUI.
- [ ] Tool/streaming случаи имеют warmup и три повтора на допущенных ветвях.
- [ ] Чистый overhead не заявлен при неизвестном/разном внутреннем движке.
- [ ] Комплект проверен по общему протоколу.

## Контрольные вопросы

1. Почему версия GUI не является pin inference engine?
2. Когда импорт того же файла всё же меняет входной протокол?
3. Что нужно доказать для измерения чистых накладных расходов wrapper?
4. Чем observed runner полезнее model alias?

## Источники

- [Ollama import](https://docs.ollama.com/import), [GPU](https://docs.ollama.com/gpu), [API compatibility](https://docs.ollama.com/api/openai-compatibility).
- [LM Studio CLI](https://lmstudio.ai/docs/cli), [runtime](https://lmstudio.ai/docs/cli/runtime/runtime), [MLX engine](https://lmstudio.ai/blog/unified-mlx-engine).
