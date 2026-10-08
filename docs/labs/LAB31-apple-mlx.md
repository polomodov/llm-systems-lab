# ЛР31. Нативный инференс MLX-LM

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Независимый движок / `target-machine` |
| Время | 2–4 часа плюс подготовка окружения |
| Предпосылки | LAB28, LAB29; отдельный MLX artifact и native arm64 Python |
| Минимум | Одна модель, pinned mlx/mlx-lm, прогрев и три повтора; сопоставление с LAB30 при наличии |

## Цель

Измерить MLX как самостоятельную конфигурацию и установить, какие различия с GGUF объясняются форматом и входным протоколом.

## Проверяемая гипотеза

MLX-вариант выбранной модели выполняется на GPU с достаточным запасом памяти. Разница с llama.cpp не приписывается одному движку, если quantization или template отличаются.

## Подготовка

Создайте окружение вне Git и закрепите версии, совместимые с выбранной архитектурой. Числа версий выбираются по документации модели и сохраняются до установки; `latest` не является pin.

```sh
npm run lab:new -- --lab LAB31 --session apple-mlx
export LAB_DIR='experiments/local-models/measurements/LAB31-apple-mlx'
export MLX_ENV='/absolute/path/to/new-mlx-venv'
export LOCAL_MLX='/absolute/path/to/pinned-mlx-model'
export MLX_VERSION='<точная версия mlx>'
export MLX_LM_VERSION='<точная версия mlx-lm>'
python3 -m venv "$MLX_ENV"
"$MLX_ENV/bin/python" -m pip install "mlx==$MLX_VERSION" "mlx-lm==$MLX_LM_VERSION" \
  > "$LAB_DIR/raw/install.txt" 2>&1
printf '%s\n' "$?" > "$LAB_DIR/raw/install-exit.txt"
```

При ошибке остановитесь. [Общий Apple-протокол](../../experiments/local-models/apple/README.md) определяет память, повторы и сдачу; LAB30 не обязательна для отдельного допуска MLX.

## Порядок выполнения

1. Сохраните версии, архитектуру и интерфейс GPU:

   ```sh
   "$MLX_ENV/bin/python" -m pip freeze > "$LAB_DIR/raw/python-lock.txt"
   "$MLX_ENV/bin/python" -c 'import platform; print(platform.machine()); print(platform.python_version())' \
     > "$LAB_DIR/raw/python-platform.txt"
   "$MLX_ENV/bin/python" -m mlx_lm.generate --help > "$LAB_DIR/raw/generate-help.txt" 2>&1
   "$MLX_ENV/bin/python" -m mlx_lm.server --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   "$MLX_ENV/bin/python" - <<'PY' > "$LAB_DIR/raw/mlx-device.json" 2> "$LAB_DIR/raw/mlx-device-errors.txt"
   import json, mlx.core as mx
   info = mx.device_info() if hasattr(mx, 'device_info') else mx.metal.device_info()
   print(json.dumps(info, indent=2))
   PY
   ```

   Наличие API зависит от pin: ошибка — evidence, а не нулевой memory limit. Проверяйте выбранный GPU и следуйте рекомендованным значениям; не вызывайте `set_memory_limit`/wired-limit tuning в baseline.

2. Подготовьте одинаковый публичный prompt и настройки reasoning/sampling по карточке модели. Сохраните prompt, hash tokenizer/template и exact command. Пример smoke (проверить flags в pinned help):

   ```sh
   printf '%s\n' 'Объясни три причины проверять hashes модельных весов.' > "$LAB_DIR/raw/prompt.txt"
   "$MLX_ENV/bin/python" -m mlx_lm.generate --model "$LOCAL_MLX" \
     --prompt "$(cat "$LAB_DIR/raw/prompt.txt")" --max-tokens 128 --temp 0 --seed 1 \
     > "$LAB_DIR/raw/warmup.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/warmup-exit.txt"
   ```

   Model path должен указывать на локальный закреплённый артефакт. Не используйте remote model alias, допускающий автоматическую смену weights. CPU fallback, неподдержанная архитектура или неожиданная загрузка другой модели — blocker.

3. После smoke снимите память и запустите временной ряд LAB28. Выполните команду по одному разу для `REPEAT=1`, `2`, `3`; при ошибках/pressure остановитесь:

   ```sh
   export REPEAT=1
   /usr/bin/time -l "$MLX_ENV/bin/python" -m mlx_lm.generate --model "$LOCAL_MLX" \
     --prompt "$(cat "$LAB_DIR/raw/prompt.txt")" --max-tokens 128 --temp 0 --seed 1 \
     > "$LAB_DIR/raw/r$REPEAT-generate.txt" 2> "$LAB_DIR/raw/r$REPEAT-process.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/r$REPEAT-exit.txt"
   ```

   Зафиксируйте реально произведённые токены, prompt/generation throughput и peak memory из runtime, если версия их сообщает. Не подставляйте cap 128 вместо фактического output. Отсутствующая метрика — `null`. Каждая команда создаёт новый процесс: это повтор CLI с прогретым файловым cache, а не residency warm HTTP.

4. В отдельном терминале запустите сервер с тем же artifact/окружением, сохранив вывод:

   ```sh
   "$MLX_ENV/bin/python" -m mlx_lm.server --model "$LOCAL_MLX" --host 127.0.0.1 --port 8081 \
     > "$LAB_DIR/raw/server.txt" 2>&1
   ```

   В рабочем терминале после readiness:

   ```sh
   curl --noproxy '*' --max-time 10 -sS http://127.0.0.1:8081/v1/models \
     > "$LAB_DIR/raw/server-models.json"
   ```

   Зафиксируйте реальный model identifier, допустимый pinned server; alias не является доказательством weights. Остановите свой сервер Ctrl-C перед запуском другой конфигурации. HTTP streaming/tools и длинный контекст проверяются в LAB32.

5. Запишите `runtime-manifest.json`: Python/MLX/MLX-LM, lock, artifact manifest, device, flags/defaults, template/reasoning и наблюдаемые allocations. Для сравнения с LAB30 приложите таблицу различий. `llama-bench` synthetic PP/TG и MLX chat prompt не идентичная нагрузка: сопоставимое HTTP-измерение делается в LAB32/35.

## Таблицы результатов

| Повтор | Prompt tokens | Output tokens | Prompt tokens/s | Generate tokens/s | Runtime peak GiB | Process RSS bytes | Wall s / exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

| Различие с GGUF | Значение | Можно ли изолировать эффект engine? |
| --- | --- | --- |
| Source revision / quant / tokenizer / template / prompt | | |

## Что сдать

Отчёт/TSV/manifest, lock и install provenance, device info, artifact/runtime manifests, prompt и все outputs/time/memory evidence. Веса и venv не коммитить.

## Критерии завершения

- [ ] Подтверждены native arm64 и точные версии.
- [ ] MLX-веса учтены отдельно от GGUF.
- [ ] Smoke и три повтора выполнены либо оформлен blocker.
- [ ] Зафиксированы фактический output, память и ограничения сравнения.
- [ ] Комплект проверен `lab:check --mode submission`.

## Контрольные вопросы

1. Почему новая CLI-команда не измеряет прогретый resident server?
2. Почему 4-bit MLX и Q4_K_M не контролируют quantization как один фактор?
3. Какие процессы входят в RSS, а какие метрики даёт runtime?
4. Почему `/v1/models` недостаточно для доказательства deployment identity?

## Источники

- [MLX-LM](https://github.com/ml-explore/mlx-lm).
- [MLX device API](https://ml-explore.github.io/mlx/build/html/python/devices_and_streams.html).
- [MLX-LM server source](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py).
