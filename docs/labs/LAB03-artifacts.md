# ЛР03. Выбор моделей и закрепление артефактов

## Паспорт

- Время: 1–2 часа работы плюс загрузка выбранных весов.
- Предпосылки: сданы [ЛР01](LAB01-reproducibility.md) и [ЛР02](LAB02-hardware.md); доступны Python 3.11+, Node.js и место на диске целевой Linux-машины.
- Готовность: расчёт и подготовку manifest можно выполнить сейчас; загрузка и проверка файлов выполняются участником лабораторной. В репозитории нет скачанных весов или аппаратных результатов.
- Минимум: оценить память всех 12 кандидатов, скачать и проверить **один** контрольный GGUF `qwen35-9b`. Второй контроль `gpt-oss-20b` и остальные загрузки — расширение.

## Цель

Получить проверенный локальный артефакт, который можно передать нескольким движкам без незаметной смены весов, и обосновать очередь остальных моделей по реальному бюджету памяти из ЛР02.

## Проверяемая гипотеза

«Выбранные shards соответствуют закреплённой ревизии и SHA-256, а контрольный GGUF проходит предварительный бюджет памяти при 8192 токенах и одной последовательности». Первая часть проверяется здесь; размещение при реальном инференсе проверяется в ЛР04–05. Положительный расчёт сам по себе не подтверждает GPU residency.

## Подготовка

Работайте из корня репозитория в Bash. Создайте отчёт и задайте отдельный каталог весов, желательно на том диске, свободное место которого измерено в ЛР02:

```bash
npm run lab:new -- --lab LAB03 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
mkdir -p "$LAB_STORAGE"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-before.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
cp experiments/local-models/models.json "$LAB_DIR/raw/catalog.json"
cp experiments/local-models/hardware.json "$LAB_DIR/raw/planning-hardware.json"
```

Ссылка на паспорт ЛР02 и его измеренные `MemTotal`, `MemAvailable`, GPU heap/GTT и swap обязательна в `manifest.json`. Не складывайте CPU RAM и GPU budget: это одна UMA-память. По умолчанию planner использует **гипотезы** 119,2 GiB RAM, 89,4 GiB GPU budget, 16 GiB для ОС, 6 GiB runtime и 4/8/16 GiB для контекстов 8K/16K/32K. Это резервы, а не расчёт KV cache конкретной архитектуры.

## Порядок выполнения

1. **Зафиксируйте отбор до загрузки.** Сохраните общий план:

   ```bash
   node scripts/local-plan.mjs --format json > "$LAB_DIR/raw/plan-default.json"
   node scripts/local-plan.mjs --model qwen35-9b --context 8192 --format json > "$LAB_DIR/raw/control-plan.json"
   ```

   Если бюджет из ЛР02 отличается, повторите команду с `--memory-gib ЧИСЛО --gpu-budget-gib ЧИСЛО`, сохранив отдельный JSON и точную команду. Числа берутся из отчёта машины; переменные доступной памяти и общий объём — разные величины. Для каждой из 12 моделей заполните решение «первый запуск / позднее / не проходит выбранный бюджет» и условие пересмотра.

   | Кандидат | Закреплённый GGUF | Веса, GiB, оценка вверх | Очередь |
   | --- | --- | ---: | --- |
   | `qwen35-9b` | Q6_K | 7,0 | P1, контроль |
   | `qwen36-35b-a3b` | UD-Q5_K_M | 24,7 | P1 |
   | `qwen36-27b` | Q5_K_M | 18,2 | P1 |
   | `qwen3-coder-next` | Q5_K_M | 52,9 | P1 |
   | `gpt-oss-20b` | MXFP4 | 11,3 | P1, второй контроль |
   | `glm-47-flash` | Q8_0 | 29,7 | P1 |
   | `qwen3-coder-30b-a3b` | Q5_K_M | 20,3 | P2 |
   | `gpt-oss-120b` | MXFP4 | 59,1 | P2, условно |
   | `qwen35-122b-a10b` | Q4_K_M | 71,3 | P2, условно |
   | `gemma4-31b-it` | Q5_K_M | 20,2 | P2 |
   | `qwen35-35b-a3b` | Q5_K_M | 24,5 | P3 |
   | `glm-45-air` | Q4_K_M | 68,0 | P3, условно |

   Таблица описывает файлы каталога на 20.09.2026; это не измеренный пик RAM. Все 12 артефактов вместе занимают около 406,7 GiB диска до дополнительных копий. Скачивать их все для зачёта не нужно. У MoE активные параметры характеризуют вычисления на токен, но загружаются все эксперты. Hybrid attention требует собственного расчёта cache/state. KV, scratch, graph buffers, tokenizer, mmap/page cache и другие процессы учитывать отдельно.

2. **Выберите точный объект, а не поисковый alias.** Экспортируйте профиль из сохранённого каталога:

   ```bash
   python3 - "$LAB_DIR" qwen35-9b <<'PY'
   import json, pathlib, sys
   out = pathlib.Path(sys.argv[1]) / "raw"
   catalog = json.loads((out / "catalog.json").read_text())
   model = next(m for m in catalog["models"] if m["id"] == sys.argv[2])
   (out / "artifact.json").write_text(json.dumps(model, indent=2) + "\n")
   print(json.dumps(model["artifact"], indent=2))
   PY
   ```

   Проверьте `model_id/model_revision`, репозиторий квантизатора, `artifact.revision`, имена и число файлов, `bytes`, `sha256`, точность и лицензию. Ревизии основной модели и GGUF различаются. SHA в каталоге получены из metadata издателя; локальная проверка ещё не выполнена. При недоступном файле или изменении лицензии остановите эту конфигурацию со статусом `no-artifact`; выбор замены оформите новым manifest.

3. **Подготовьте воспроизводимую загрузку.** Сохраните следующий открытый учебный скрипт в `$LAB_DIR/raw/fetch_artifact.py`. Он работает также с manifest native checkpoint из ЛР06. Без `--download` скрипт только проверяет существующие файлы; при несовпадении завершится ошибкой. Существующий неверный файл не заменяется автоматически.

   ```python
   import argparse, hashlib, json, os, pathlib, re, urllib.parse, urllib.request

   p = argparse.ArgumentParser()
   p.add_argument("manifest")
   p.add_argument("storage")
   p.add_argument("--download", action="store_true")
   a = p.parse_args()
   model = json.loads(pathlib.Path(a.manifest).read_text())
   artifact = model["artifact"]
   repo, rev = artifact["repository"], artifact["revision"]
   assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
   assert re.fullmatch(r"[0-9a-f]{40}", rev)
   root = (pathlib.Path(a.storage).expanduser() / repo / rev).resolve()
   results = []
   for item in artifact["files"]:
       rel = pathlib.PurePosixPath(item["path"])
       assert not rel.is_absolute() and ".." not in rel.parts
       dest = root.joinpath(*rel.parts)
       assert dest.resolve().is_relative_to(root)
       url = "https://huggingface.co/" + repo + "/resolve/" + rev + "/"
       url += urllib.parse.quote(str(rel), safe="/")
       if not dest.exists() and a.download:
           dest.parent.mkdir(parents=True, exist_ok=True)
           partial = dest.with_name(dest.name + ".part")
           # Не используйте одновременно две копии этого скрипта для одного файла.
           try:
               with urllib.request.urlopen(url, timeout=120) as src, partial.open("xb") as out:
                   while chunk := src.read(8 * 1024 * 1024):
                       out.write(chunk)
               with partial.open("rb") as src:
                   digest = hashlib.file_digest(src, "sha256").hexdigest()
               assert partial.stat().st_size == item["bytes"], "size mismatch"
               assert not item.get("sha256") or digest == item["sha256"], "hash mismatch"
               os.replace(partial, dest)
           except BaseException:
               # .part сохраняется для диагностики; удалять только после разбора ошибки.
               raise
       if not dest.is_file():
           results.append({"path": str(dest), "status": "no-artifact"})
           continue
       with dest.open("rb") as src:
           digest = hashlib.file_digest(src, "sha256").hexdigest()
       size_ok = dest.stat().st_size == item["bytes"]
       hash_ok = not item.get("sha256") or digest == item["sha256"]
       results.append({"path": str(dest), "bytes": dest.stat().st_size,
                       "sha256": digest,
                       "publisher_hash_present": bool(item.get("sha256")),
                       "status": "verified" if size_ok and hash_ok else "fail"})
   print(json.dumps({"repository": repo, "revision": rev,
                     "files": results}, indent=2))
   raise SystemExit(0 if all(x["status"] == "verified" for x in results) else 1)
   ```

   Нужен Python **3.11+** для `hashlib.file_digest`; версия попадает в отчёт. Скрипт не возобновляет оборванную загрузку, чтобы не скрывать непроверенный partial. Сверьте запас диска с суммой `artifact.total_bytes`, временными файлами и будущими копиями сервисов. Проверка файлов — последовательное чтение всего объёма.

4. **Загрузите только выбранный артефакт, затем повторно проверьте offline.** Эти команды выполняет участник лабораторной на целевой машине после шага 3:

   ```bash
   python3 --version > "$LAB_DIR/raw/python-version.txt"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/download-verification.json"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/verification.json"
   df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-after.txt"
   ```

   При ошибке сохраните stderr и ненулевой exit code в отчёте. Для split GGUF нужны **все оригинальные shards** в исходной структуре; серверу далее передаётся первый shard. Не склеивайте и не переименовывайте shards. Не добавляйте vision projector, speculative draft или иной quant без нового manifest. Для защищённого репозитория используйте документированный клиент HF и доступ из `.env`; данный публичный контроль не требует токена.

5. **Передайте артефакт в следующую работу.** Из `verification.json` возьмите абсолютный путь контрольного GGUF и запишите его как `GGUF` в своём отчёте; runtime получит этот файл. Создайте стандартный checksum-файл всех shards для `sha256sum --check` в ЛР04–07. JSON не является форматом checksum-файла:

   ```bash
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / "raw"
   verification = json.loads((raw / "verification.json").read_text())
   assert verification["files"]
   lines = []
   for item in verification["files"]:
       assert item["status"] == "verified" and item["publisher_hash_present"]
       path = pathlib.Path(item["path"])
       assert path.is_absolute() and "\n" not in str(path) and "\\" not in str(path)
       lines.append(item["sha256"] + "  " + str(path) + "\n")
   (raw / "weights.sha256").write_text("".join(lines))
   PY
   sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/checksums-recheck.txt"
   ```

   Пути абсолютные и относятся к этой машине; при переносе обновляется путь в отдельной копии checksum-файла, а hashes остаются прежними. Приложите hashes входного каталога, экспортированного manifest и скрипта:

   ```bash
   sha256sum "$LAB_DIR/raw/catalog.json" "$LAB_DIR/raw/artifact.json" "$LAB_DIR/raw/fetch_artifact.py" > "$LAB_DIR/raw/input-hashes.txt"
   ```

   Заполните `report.md`, `measurements.tsv`, `manifest.json`. Статус `verified` относится к bytes/hash, `candidate` — к расчёту памяти, `not-run` — к отсутствующему инференсу. Ошибка доступа/хеша — отдельное наблюдение, а не скорость 0 tokens/s. Позднее обновление модели или квантизатора создаёт новую конфигурацию.

## Таблицы результатов

Заполните первую таблицу для всех 12 кандидатов; строки можно копировать. Ячейки с фактическими измерениями изначально пусты.

| Model slug | Контекст | Веса, GiB | Runtime/cache reserve, GiB | Бюджет/источник | Планируемый запас | Решение и причина |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| | | | | | | |

| Model / artifact revision | Shards: ожидается / получено | Bytes: ожидается / измерено | SHA-256 verdict | Путь verification | Статус / причина |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

| Наблюдение | Значение | Единица | Условия | Evidence |
| --- | ---: | --- | --- | --- |
| Свободный диск до / после | | bytes | | |
| Время загрузки / проверки | | s | | |

## Что сдать

Каталог отчёта с заполненными тремя файлами helper, копией исходного каталога, 12 решениями по памяти, выбранным `artifact.json`, скриптом загрузки, результатом повторной проверки, источником аппаратных бюджетов и абсолютным путём весов. **Сами веса в Git не добавляются.** В выводе отдельно указать, что будет проверяться при реальной загрузке модели в ЛР04–05.

## Критерии завершения

- [ ] Для 12 кандидатов есть решение с условиями памяти и очередью.
- [ ] Для одного контрольного GGUF проверены все bytes/SHA-256 либо документирован `no-artifact`/`fail` с причиной и шагом исправления.
- [ ] Model revision, quantizer revision, quantization и shards различимы в manifest.
- [ ] Диск, RAM, GPU budget, веса и KV/state не смешаны в одну величину.
- [ ] Отсутствующим аппаратным запускам оставлен `not-run`; оценка не названа замером.
- [ ] Отчёт позволяет другому участнику воспроизвести выбор и проверку без поиска alias.

## Контрольные вопросы

1. Почему 3B active у MoE не означает, что на диске или в RAM нужно хранить только 3B параметров?
2. Почему GGUF Q5 и UD-Q5 одного семейства не дают чистую абляцию поколения?
3. Что доказывает SHA-256, и чего он не говорит о качестве квантизации и корректности inference kernels?
4. Почему сохранённый hash metadata издателя ещё не равен проверке локального файла?
5. Какие расходы памяти могут превратить положительную оценку 32K в OOM?

## Источники

- [Каталог с закреплёнными revisions, shards и hashes](../../experiments/local-models/models.json), [разбор кандидатов и ограничений](../local-model-candidates.md).
- [План памяти и порядок аппаратной кампании](../local-models.md), [Linux runbook](../local-model-runtime.md).
- [Hugging Face: версии и загрузка файлов](https://huggingface.co/docs/huggingface_hub/guides/download).
- [Официальная модель Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B), [GGUF издателя](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF).
- [Python hashlib.file_digest](https://docs.python.org/3/library/hashlib.html#hashlib.file_digest).
