# ЛР 04. Сравнение llama.cpp Vulkan и HIP/ROCm

## Паспорт

| Поле | Значение |
| --- | --- |
| Время-ориентир | 2–4 часа после получения весов и зависимостей; большие модели могут потребовать больше времени |
| Предпосылки | Выполнены ЛР 02 и ЛР 03; target Linux; закреплённые GGUF и commit llama.cpp; установлены build dependencies Vulkan и HIP |
| Статус готовности | Команды подготовлены; обе аппаратные ветви требуют выполнения smoke |
| Результат | Парное сравнение backend при одной модели и одном commit |

## Цель

Измерить различия Vulkan и HIP/ROCm на Radeon 8060S, сохранив одинаковые веса, версию движка и параметры. Обе ветви обязательны; отсутствие одной оформляется как blocker, а не как доказательство преимущества другой.

## Проверяемая гипотеза

Один и тот же GGUF может работать с полным GPU offload в обеих сборках llama.cpp. При одинаковой нагрузке backend может влиять на скорость prefill/decode и память; направление и величина эффекта неизвестны до измерений.

## Подготовка

- Из ЛР 03 возьмите локальный GGUF, список всех shards с SHA-256 и карточку модели. Исходники llama.cpp в той работе не готовятся.
- Выберите один конкретный commit llama.cpp по поддержке архитектуры/quant выбранной модели в его документации и истории изменений. Запишите полный SHA из 40 hex-символов и дату выбора в отчёт. Номер release или слово `master` самостоятельно не заменяют SHA. Для первого сравнения обе сборки получают этот же commit, а model-specific template фиксируется отдельно.
- Из ЛР 02 возьмите паспорт и допустимые бюджеты. Начните с малого контрольного кандидата, а не с предельной модели.
- Убедитесь, что `cmake`, compiler, Vulkan headers/shader compiler и HIP SDK уже установлены. Не устанавливайте их автоматически при ошибке сборки.
- Все команды выполняются из корня репозитория. Значения `/absolute/...` замените реальными абсолютными путями; не используйте плавающий `master` как идентификатор сборки.

## Порядок выполнения

1. Создайте отдельный архив и задайте входы:

   ```sh
   npm run lab:new -- --lab LAB04 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB04-my-session'
   export LAB03_DIR='experiments/local-models/measurements/LAB03-my-session'
   export LLAMA_SOURCE='/absolute/path/to/pinned/llama.cpp'
   export LLAMA_COMMIT='<replace-with-40-character-commit-sha>'
   export LOCAL_GGUF='/absolute/path/to/model.gguf'
   test "$(uname -s)" = Linux
   test -f "$LOCAL_GGUF"
   python3 - <<'PY'
   import os, re
   assert re.fullmatch(r'[0-9a-f]{40}', os.environ['LLAMA_COMMIT']), 'set full lowercase commit SHA'
   PY
   test "$(git -C "$LLAMA_SOURCE" rev-parse HEAD)" = "$LLAMA_COMMIT"
   git -C "$LLAMA_SOURCE" rev-parse HEAD > "$LAB_DIR/raw/llama-commit.txt"
   git -C "$LLAMA_SOURCE" status --porcelain > "$LAB_DIR/raw/llama-status.txt"
   cmake --version > "$LAB_DIR/raw/cmake-version.txt"
   hipconfig --full > "$LAB_DIR/raw/hipconfig.txt" 2>&1
   vulkaninfo --summary > "$LAB_DIR/raw/vulkan-summary.txt" 2>&1
   cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
   cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
   sha256sum --check "$LAB_DIR/raw/weights.sha256" \
     > "$LAB_DIR/raw/verification-before.txt"
   ```

   Команды предполагают **уже подготовленный отдельный checkout** в `LLAMA_SOURCE`: выбранный commit должен совпасть с `HEAD`, а `git status --porcelain` должен быть пустым. Если checkout отсутствует, сначала получите исходники отдельно, например командами ниже, затем повторите проверки шага 1. `LLAMA_SOURCE` для клонирования должен быть новым, не занятым пользовательским каталогом:

   ```sh
   git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE"
   git -C "$LLAMA_SOURCE" checkout --detach "$LLAMA_COMMIT"
   ```

   При локальных patch сохраните diff и одинаково примените его к обеим сборкам; это отдельный вариант относительно чистого pin. `weights.sha256` из ЛР 03 содержит все shards с абсолютными путями; JSON manifest не является входом `sha256sum --check`. При ненулевом exit code остановитесь. Хеширование читает веса и прогревает filesystem cache — учтите это в состоянии кеша.

2. Соберите два backend из этого checkout в **разных** каталогах. Это сборка, не установка системных пакетов:

   ```sh
   (
   set -eu
   cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-vulkan" \
     -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release \
     > "$LAB_DIR/raw/configure-vulkan.log" 2>&1
   cmake --build "$LAB_DIR/build-vulkan" --config Release -j 8 \
     > "$LAB_DIR/raw/build-vulkan.log" 2>&1

   HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
     cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-hip" \
     -DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_BUILD_TYPE=Release \
     > "$LAB_DIR/raw/configure-hip.log" 2>&1
   cmake --build "$LAB_DIR/build-hip" --config Release -j 8 \
     > "$LAB_DIR/raw/build-hip.log" 2>&1
   )
   ```

   Проверяйте exit code после каждой команды, перед переходом дальше. Ошибку сохраняйте целиком. Не добавляйте `HSA_OVERRIDE_GFX_VERSION` и не заменяйте target на другую архитектуру ради прохождения baseline.

3. Зафиксируйте итоговые бинарники и убедитесь, что flags совпадают с pinned `--help`:

   ```sh
   for backend in vulkan hip; do
     binary="$LAB_DIR/build-$backend/bin/llama-bench"
     "$binary" --help > "$LAB_DIR/raw/$backend-bench-help.txt" 2>&1
     "$binary" --list-devices > "$LAB_DIR/raw/$backend-devices.txt" 2>&1
     "$LAB_DIR/build-$backend/bin/llama-server" --version \
       > "$LAB_DIR/raw/$backend-version.txt" 2>&1
     sha256sum "$binary" "$LAB_DIR/build-$backend/bin/llama-server" \
       > "$LAB_DIR/raw/$backend-binaries.sha256"
     cp "$LAB_DIR/build-$backend/CMakeCache.txt" "$LAB_DIR/raw/$backend-CMakeCache.txt"
   done
   ```

   Проверьте `-fa on`, `-ctk/-ctv`, `-d`, `-r`, `-o json`. При другом синтаксисе адаптируйте команду по документации выбранного commit и сохраните её. Если устройств несколько, выберите одно и зафиксируйте selection flag из help. Автовыбор допустим только после подтверждения Radeon 8060S в обеих ветвях.

4. Выполните по одному непротоколируемому в итоговой статистике прогреву. Логи прогрева сохраняются:

   ```sh
   (
   set -eu
   for backend in vulkan hip; do
     "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
       -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
       -p 512 -n 128 -r 1 -o json \
       > "$LAB_DIR/raw/$backend-warmup.json" \
       2> "$LAB_DIR/raw/$backend-warmup.log"
   done
   )
   ```

   Найдите в логах фактическое число GPU layers, backend и allocations. `-ngl 999` — запрос, а не доказательство full offload. CPU tokenizer/sampling допустимы; уход весов/слоёв модели на CPU считается отдельной конфигурацией. При OOM, GPU reset, невалидных данных или нарушении бюджета остановите эту ветвь. Не уменьшайте незаметно KV precision, context или offload.

5. Выполните три парных повтора, чередуя порядок `Vulkan → HIP`, `HIP → Vulkan`, `Vulkan → HIP`. Для каждого backend измерьте pp2048 и tg128 при глубине 4096. Не запускайте ветви одновременно:

   ```sh
   (
   set -eu
   test -x /usr/bin/time
   for repeat in 1 2 3; do
     if [ "$repeat" = 2 ]; then set -- hip vulkan; else set -- vulkan hip; fi
     for backend do
       prefix="$LAB_DIR/raw/$backend-r$repeat"
       free -b > "$prefix-memory-before.txt"
       cat /proc/vmstat > "$prefix-vmstat-before.txt"
       /usr/bin/time -v -o "$prefix-pp-process.txt" \
         "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
         -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
         -p 2048 -n 0 -r 1 -o json \
         > "$prefix-pp.json" 2> "$prefix-pp.log"
       /usr/bin/time -v -o "$prefix-tg-process.txt" \
         "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
         -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
         -p 0 -n 128 -d 4096 -r 1 -o json \
         > "$prefix-tg.json" 2> "$prefix-tg.log"
       cat /proc/vmstat > "$prefix-vmstat-after.txt"
       free -b > "$prefix-memory-after.txt"
     done
   done
   )
   ```

   Подоболочка останавливается при ненулевом exit code. Сохраните failure; не включайте частичный JSON как успешный замер. Успешный exit code всё равно требует проверки логов на offload и allocations. `/usr/bin/time` — GNU time, а не shell keyword. Если его нет, сохраните blocker process RSS/wall metrics или подготовьте измеритель отдельно.

6. **Перед выполнением шага 5** в отдельном терминале из корня репозитория повторно задайте `LAB_DIR` из шага 1 и запустите `vmstat -w 1 > "$LAB_DIR/raw/vmstat-series.txt"`. Остановите сбор после серии через Ctrl-C. Используйте доступную GPU/температурную телеметрию из ЛР 02; отсутствующие sensors отмечайте как `null`. RSS процесса, GPU allocation и page cache не складываются без анализа пересечения UMA. По `pswpin/pswpout` до/после и журналу `vmstat` оцените наличие подкачки; единичный шум и устойчивый swap-in/out опишите отдельно.

7. Разделите времена и состояния кеша. Каждый `llama-bench` начинает новый процесс; это не гарантирует холодный SSD/filesystem cache. Его встроенный прогрев исключён из t/s, а время `/usr/bin/time` включает весь процесс. Запишите «process cold / filesystem warm или unknown» и отдельно измеряемую фазу pp/tg. Не называйте process wall time временем загрузки модели. Для отдельной cold-load серии нужен новый объявленный сценарий; глобальный page cache здесь не очищается.

8. Из JSON перенесите три индивидуальных результата в `measurements.tsv`; вычислите median/min/max для одинаковых режимов. Для каждого режима приведите отношение `median_HIP / median_Vulkan`, если обе ветви завершились в одинаковых условиях. При разных quant, FA или offload отношение не интерпретируется как чистый эффект backend. Заполните отчёт и manifest, затем повторите проверки SHA весов и commit.

## Таблицы результатов

| Backend | Commit / binary SHA | GPU / target | Слоёв на GPU / всего | Quant / KV / FA | Допуск |
| --- | --- | --- | --- | --- | --- |
| Vulkan | | | | | |
| HIP/ROCm | | | | | |

| Backend | Повтор | pp2048, tokens/s | tg128 @ depth4096, tokens/s | Max RSS, KiB | Swap delta | Статус / raw prefix |
| --- | --- | --- | --- | --- | --- | --- |
| Vulkan | 1 | | | | | |
| HIP | 1 | | | | | |
| Vulkan | 2 | | | | | |
| HIP | 2 | | | | | |
| Vulkan | 3 | | | | | |
| HIP | 3 | | | | | |

| Режим | Vulkan median [min; max] | HIP median [min; max] | HIP/Vulkan | Ограничения вывода |
| --- | --- | --- | --- | --- |
| pp2048 | | | | |
| tg128 @ depth4096 | | | | |

## Что сдать

- `report.md`, `measurements.tsv`, `manifest.json` с зависимостями на ЛР 02/03.
- `raw/llama-commit.txt`, статус/patch checkout, manifest и результаты проверки SHA всех shards.
- Логи configure/build, `*-CMakeCache.txt`, `*-binaries.sha256`, версии/help/device inventory обеих ветвей.
- Все `*-warmup.*`, `*-r[1-3]-pp.*`, `*-r[1-3]-tg.*`, process metrics и memory/swap observations; не удалять неудачные попытки.
- Записанные launch arguments и режим питания; таблица сравнений без вымышленных нулей.

## Критерии завершения

- [ ] Обе ветви собраны из одного commit и используют одни SHA весов.
- [ ] Подтверждены Radeon 8060S, фактический offload и одинаковые настройки.
- [ ] Сохранён прогрев и три парных повтора либо конкретный blocker.
- [ ] Cold process, filesystem cache и измеряемая фаза описаны отдельно.
- [ ] Проверены swap и бюджеты; не было скрытого fallback.
- [ ] Вывод ограничен проверенной моделью/контекстом и не является рейтингом агентов.

## Контрольные вопросы

1. Почему сравнение разных commit не позволяет выделить эффект Vulkan/HIP?
2. Почему tg128 при пустом контексте недостаточно для оценки агентной нагрузки?
3. Что входит в process wall time и что исключено из `llama-bench` t/s?
4. Как отличить успешный запуск от полного GPU offload?
5. Что нужно пересчитать при смене KV f16 на q8_0?

## Источники

- [llama.cpp: сборки Vulkan и HIP](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- [llama-bench: режимы pp/tg, context depth, прогрев и output](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md).
- [AMD: архивный пакет llama.cpp b8407 / ROCm 7.2.1](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/advanced/advancedryz/linux/llm/llamacpp.html).
- [Общий практикум](README.md), [паспорт машины](LAB02-hardware.md), [матрица движков](../local-inference-engines.md).
