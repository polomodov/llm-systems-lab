# ЛР30. llama.cpp на Apple Metal

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Измерение backend / `target-machine` |
| Время | 2–4 часа плюс сборка |
| Предпосылки | LAB28, LAB29; native arm64 CMake/Clang и GGUF |
| Минимум | Один pinned build, GPU smoke, отдельный прогрев и три повтора prefill/decode |

## Цель

Получить воспроизводимую Metal-baseline и подтвердить, какие операции действительно выполняются на GPU.

## Проверяемая гипотеза

Выбранный GGUF работает в pinned llama.cpp на M5 Max с измеренным запасом памяти и без незапланированного CPU fallback. Это не утверждение о скорости до замеров.

## Подготовка

```sh
npm run lab:new -- --lab LAB30 --session apple-metal
export LAB_DIR='experiments/local-models/measurements/LAB30-apple-metal'
export LLAMA_SRC='/absolute/path/to/llama.cpp-checkout'
export LLAMA_BUILD='/absolute/path/to/new-metal-build'
export LOCAL_GGUF='/absolute/path/to/pinned-model.gguf'
export LLAMA_COMMIT='<полный commit из протокола>'
```

Checkout должен быть подготовлен на выбранном commit. Для сравнения с Ryzen нужен тот же commit. Build directory должен быть новым; исходники, build и weights не включаются в evidence. [Общий протокол](../../experiments/local-models/apple/README.md) обязателен.

## Порядок выполнения

1. Зафиксируйте исходники, toolchain и параметры, затем соберите нативно. Остановитесь при отличии SHA или грязном checkout:

   ```sh
   test "$(git -C "$LLAMA_SRC" rev-parse HEAD)" = "$LLAMA_COMMIT" && \
     test -z "$(git -C "$LLAMA_SRC" status --porcelain)" && \
     test ! -e "$LLAMA_BUILD"
   ```

   Только после успешной проверки:

   ```sh
   git -C "$LLAMA_SRC" rev-parse HEAD > "$LAB_DIR/raw/source-commit.txt"
   cmake --version > "$LAB_DIR/raw/cmake-version.txt"
   xcrun clang --version > "$LAB_DIR/raw/clang-version.txt"
   cmake -S "$LLAMA_SRC" -B "$LLAMA_BUILD" -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_OSX_ARCHITECTURES=arm64 -DGGML_METAL=ON \
     > "$LAB_DIR/raw/configure.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/configure-exit.txt"
   ```

   При exit 0 выполните build; при ошибке сохраните blocker:

   ```sh
   cmake --build "$LLAMA_BUILD" --config Release -j 8 \
     --target llama-bench llama-server > "$LAB_DIR/raw/build.txt" 2>&1
   printf '%s\n' "$?" > "$LAB_DIR/raw/build-exit.txt"
   export LLAMA_BIN="$LLAMA_BUILD/bin"
   cp "$LLAMA_BUILD/CMakeCache.txt" "$LAB_DIR/raw/CMakeCache.txt"
   file "$LLAMA_BIN/llama-bench" > "$LAB_DIR/raw/binary-arch.txt"
   shasum -a 256 "$LLAMA_BIN/llama-bench" "$LLAMA_BIN/llama-server" \
     > "$LAB_DIR/raw/binaries.sha256"
   "$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
   "$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   ```

   Закрепите также linked runtime libraries/build flags. Binary hash сам по себе не описывает динамические зависимости.

2. Проверьте flags по сохранённому help; снимите исходную память LAB28 и запустите её временной ряд. Выполните маленький smoke/прогрев:

   ```sh
   "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -p 512 -n 128 -r 1 -o json > "$LAB_DIR/raw/warmup.json" \
     2> "$LAB_DIR/raw/warmup-device.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/warmup-exit.txt"
   ```

   Требуются exit 0, Metal device, фактические offloaded layers и allocations в журнале. CPU-служебные операции нормальны; заявлять полный GPU offload можно только по логу. Если `-ngl 999` не поддержан моделью или лог не подтверждает GPU, результат — blocker или отдельно описанный partial-offload вариант.

3. После успешного smoke выполните по одному запуску для `REPEAT=1`, `2`, `3`, проверяя каждый результат перед следующим. Фиксируйте три сырых повтора отдельно; stdout содержит PP/TG, stderr — macOS time и backend:

   ```sh
   export REPEAT=1
   /usr/bin/time -l "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -p 512 -n 128 -r 1 -o json > "$LAB_DIR/raw/r$REPEAT-bench.json" \
     2> "$LAB_DIR/raw/r$REPEAT-process.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/r$REPEAT-exit.txt"
   ```

   Каждый CLI запускается новым процессом; встроенный benchmark warmup и файловый cache описать. `/usr/bin/time` измеряет весь процесс, PP/TG в JSON — отдельные benchmark kernels. Не объявляйте wall time decode throughput или временем прогретого HTTP-запроса.

4. Сохраните `raw/runtime-manifest.json`: SHA, macOS/SDK/compiler, binary/library hashes, build flags, exact commands, model manifest, threads/batch/defaults, observed GPU/offload. Свяжите с паспортом и снимками памяти. При доступном измеренном рабочем GPU budget пересчитайте `local:plan --gpu-budget-gib`; это operator input, не автоматическая калибровка.

5. Сравните повторы: median и min/max PP/TG, процессный RSS, runtime allocations, swap delta и ошибки. Для HTTP/context испытаний перейдите к LAB32; CPU-versus-Metal или иные threads — дополнительные отдельные серии.

## Таблицы результатов

| Повтор | PP tokens/s | TG tokens/s | Wall s | Max RSS bytes | Runtime allocations | Swap delta | Exit / evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

## Что сдать

Отчёт/TSV/manifest, source/build/toolchain evidence, runtime manifest, hashes и полный набор warmup/трёх повторов с памятью и exit codes. Архивы весов и build не требуются.

## Критерии завершения

- [ ] Пин и native arm64 build подтверждены.
- [ ] Фактический Metal/offload установлен по логам.
- [ ] Есть отдельный прогрев и три повтора либо сохранённые failures/blockers.
- [ ] PP, TG, process wall и память не смешаны.
- [ ] Комплект проверен по общему протоколу.

## Контрольные вопросы

1. Почему Metal build не доказывает GPU-исполнение запроса?
2. Как различаются PP, TG и wall time процесса?
3. Почему одинаковый commit нужен для сравнения с Ryzen?
4. Как shared memory меняет интерпретацию RSS?

## Источники

- [llama.cpp: сборка Metal](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- [llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench).
- [LAB28](LAB28-apple-hardware.md), [LAB29](LAB29-apple-artifacts.md), pinned help и source commit.
