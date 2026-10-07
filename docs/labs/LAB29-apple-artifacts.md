# ЛР29. Закрепление GGUF и MLX-артефактов

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Подготовка артефактов / `target-machine` |
| Время | 1–3 часа плюс загрузка |
| Предпосылки | LAB28 и общий Apple-протокол |
| Минимум | Одна исходная модель, один GGUF и один MLX-вариант либо документированный blocker MLX |

## Цель

Получить проверяемые manifests весов и входного протокола, пригодные для повторного запуска на Mac и сравнения с Ryzen.

## Проверяемая гипотеза

Для выбранной исходной модели доступны воспроизводимые артефакты обоих движков. Одинаковый model name не гарантирует одинаковые weights, tokenizer, quantization или template.

## Подготовка

```sh
npm run lab:new -- --lab LAB29 --session apple-artifacts
export LAB_DIR='experiments/local-models/measurements/LAB29-apple-artifacts'
npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --engine all --format json \
  > "$LAB_DIR/raw/candidates.json"
```

Следуйте [общему протоколу](../../experiments/local-models/apple/README.md). Выберите небольшой candidate для первого smoke и задайте предел SSD/памяти до загрузки. `artifact-required` — необходимость найти MLX-веса, не запрет модели. Каталог общий, его включение не доказывает поддержку архитектуры Metal или MLX.

## Порядок выполнения

1. Выберите исходный repository и **полный immutable commit**, затем отдельные repositories/revisions для GGUF и MLX. Сохраните model card/config, лицензию, список файлов и сведения о происхождении conversion. Для GGUF сравнения с Ryzen используйте в точности уже закреплённые файлы и hashes; нельзя подменять их другой сборкой с тем же названием quant.

2. Загрузите только выбранные revisions штатным клиентом хранилища; запишите команду и версию клиента в `raw/acquisition.txt`. Секреты не сохраняйте. Если веса уже есть, сохраните происхождение локальной копии. Модели храните вне Git/evidence. В `MODEL_DIR` укажите отдельный каталог **одного** варианта: все shards, config/tokenizer/template, без других моделей. `ARTIFACT_NAME` — `gguf` или `mlx`:

   ```sh
   export MODEL_DIR='/absolute/path/to/pinned-model'
   export ARTIFACT_NAME='gguf'
   python3 - "$MODEL_DIR" "$LAB_DIR/raw/$ARTIFACT_NAME-files.json" <<'PY'
   import hashlib, json, pathlib, sys
   root = pathlib.Path(sys.argv[1]).resolve()
   if not root.is_dir():
       raise SystemExit('MODEL_DIR must exist')
   rows = []
   for path in sorted(root.rglob('*')):
       if not path.is_file():
           continue
       relative = path.relative_to(root).as_posix()
       if any(p.startswith('.') for p in pathlib.PurePosixPath(relative).parts):
           continue  # exclude client metadata and hidden files, never include credentials
       digest = hashlib.sha256()
       with path.open('rb') as source:
           for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
               digest.update(block)
       rows.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()})
   if not rows:
       raise SystemExit('No artifact files')
   with pathlib.Path(sys.argv[2]).open('x') as out:
       json.dump({'files': rows, 'total_bytes': sum(r['bytes'] for r in rows)}, out, indent=2)
   PY
   ```

   Повторите для MLX с новым именем. Все ожидаемые shards должны присутствовать; hashing неполного каталога не доказывает комплектность. Сравните SHA с метаданными издателя, если опубликованы. Локальные hashes подтверждают повторяемость этих bytes, не автоматически происхождение.

3. Запишите `raw/artifact-manifest.json`: исходные model/revision, для каждого варианта repository/revision, format, quantization (для MLX также bits/group_size и исключения), список файлов/hash evidence, tokenizer/template hashes, лицензия, conversion command/version или причина неизвестности. Embedded GGUF tokenizer/template извлеките средствами pinned runtime и сохраните отдельно; hash GGUF фиксирует bytes, но не заменяет описание template override.

4. Сопоставьте chat template, special tokens, thinking/reasoning, EOS и output cap. Изменение template — отдельная конфигурация. Если исходный revision MLX не установлен, сравнение по одному фактору невозможно: отметьте deployment comparison либо blocker; не придумывайте provenance.

5. Сверьте объём на SSD и грубый план памяти. Файловый размер MLX не равен peak memory, размер GGUF не переносится на MLX. GPU budget остаётся неизвестным до smoke. Повторные хеши должны совпасть; повреждённый shard исключает допуск.

## Таблицы результатов

| Вариант | Source revision | Artifact revision | Quant / group size | Файлы / bytes / SHA evidence | Template hash | Допуск |
| --- | --- | --- | --- | --- | --- | --- |
| GGUF | | | | | | |
| MLX | | | | | | |

## Что сдать

Отчёт, TSV, manifest v2, acquisition commands, карточки/config, списки hashes и `artifact-manifest.json`. Веса в отчёт не включаются. `conditions.model_artifact_manifest` ссылается на manifest; пропуски подтверждены причиной.

## Критерии завершения

- [ ] Revisions immutable, все shards учтены и проверены.
- [ ] GGUF и MLX имеют отдельные format/quant/size сведения.
- [ ] Tokenizer/template и исходное происхождение установлены либо явно неизвестны.
- [ ] Нет утверждения о вместимости без аппаратного smoke.
- [ ] Комплект проверен `lab:check --mode submission`.

## Контрольные вопросы

1. Почему GGUF Q4 и MLX 4-bit могут иметь разное качество и память?
2. Что подтверждает SHA и чего он не подтверждает?
3. Как template override меняет условия сравнения?
4. Почему MoE active parameters не определяют полный объём весов?

## Источники

- [Общий каталог моделей](../local-model-candidates.md).
- [MLX-LM: модели и conversion](https://github.com/ml-explore/mlx-lm).
- [Hugging Face: pinned download](https://huggingface.co/docs/huggingface_hub/guides/download).
- Model cards и revision URLs выбранных вариантов прилагаются исполнителем.
