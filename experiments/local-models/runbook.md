# Runbook: ЛР02–ЛР05 на стенде Ryzen AI Max+ 395

Сводный операторский лист для одной сессии измерений. Собран 21.09.2026 из коммита `b19e7db`.

## Чем это является и чем нет

Это **производный** лист команд: четыре лабораторные работы сведены в один линейный порядок, `my-session` заменён на `ryzen-01`, все `/absolute/path/to/...` выведены из переменных, вложенные heredoc сняты с отступов списка (в исходных документах закрывающий `PY` стоит с отступом и при дословном копировании heredoc не закроется).

**Нормативны исходные лаборатории**, а не этот файл:

- [ЛР02](../../docs/labs/LAB02-hardware.md) · [ЛР03](../../docs/labs/LAB03-artifacts.md) · [ЛР04](../../docs/labs/LAB04-backends.md) · [ЛР05](../../docs/labs/LAB05-context-tools.md)

Соглашение о блоках: команды сбора доказательств идут **отдельными строками**, как в лабораториях, — отказ одной утилиты не должен скрывать вывод остальных. Через `&&` соединены только проверки-ворота, где продолжение при неуспехе бессмысленно.

Здесь нет таблиц результатов, критериев завершения и контрольных вопросов — их заполняют из самих работ. Этот файл не создаёт `run.json`, не выставляет зачёт и не заменяет `report.md`.

Проверка дрейфа источников из корня репозитория:

```sh
sha256sum -c experiments/local-models/runbook.sources.sha256
```

При несовпадении сначала читайте изменившуюся работу, потом пересобирайте runbook.

## 0. Один раз: окружение сессии

Стенд — native Linux на целевой машине. ЛР02 останавливается на `test "$(uname -s)" = Linux`: macOS, WSL и VM паспорт не дают.

Создайте env-файл **вне репозитория** (секретов в нём нет и быть не должно):

```sh
cat > "$HOME/lab-ryzen-01.env" <<'ENV'
export LAB_SESSION=ryzen-01
export LAB_ROOT="$HOME/agent-harnesses-exps"
export LAB_MEASUREMENTS="$LAB_ROOT/experiments/local-models/measurements"
export LAB02_DIR="$LAB_MEASUREMENTS/LAB02-$LAB_SESSION"
export LAB03_DIR="$LAB_MEASUREMENTS/LAB03-$LAB_SESSION"
export LAB04_DIR="$LAB_MEASUREMENTS/LAB04-$LAB_SESSION"
export LAB05_DIR="$LAB_MEASUREMENTS/LAB05-$LAB_SESSION"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
export LLAMA_SOURCE="$HOME/src/llama.cpp-pinned"
export LLAMA_COMMIT=""
ENV
```

Поправьте `LAB_ROOT` под фактический путь клона и `LAB_STORAGE` под диск, свободное место которого измерите в ЛР02. `LLAMA_COMMIT` заполняется в ЛР04, `LOCAL_GGUF` и `LLAMA_BIN` дописываются в файл по ходу работы.

**В каждом терминале этой сессии** (их понадобится до трёх):

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT"
```

Проверка инструментов:

```sh
node --version && git --version && bash --version && python3 --version
```

Нужны Node ≥22 и Python ≥3.11 (`hashlib.file_digest` в ЛР03).

Повтор любого опыта — это новая `--session`, а не перезапись папки: `lab:new` существующий каталог не затирает.

---

# ЛР02. Паспорт машины и бюджет памяти

Только чтение состояния. BIOS, ядро, kernel cmdline, TTM/GTT, драйверы и power profile не меняются. Активные inference-процессы закройте сами, незнакомые пользовательские процессы не трогайте.

До сбора запишите в отчёт: модель компьютера, режим питания, питание от сети, активный рабочий стол, существенные фоновые нагрузки. Серийный номер в архив не нужен.

## 02.1 Архив и проверка ОС

```sh
npm run lab:new -- --lab LAB02 --session "$LAB_SESSION"
```

```sh
export LAB_DIR="$LAB02_DIR" && test "$(uname -s)" = Linux && test -d "$LAB_DIR/raw" && echo ok
```

## 02.2 Сбор сведений

Одна недоступная утилита не прерывает весь сбор — отсутствующие помечаются `unavailable`.

```sh
python3 - <<'PY'
import json, os, pathlib, subprocess, time
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
commands = {
    'time': ['date', '-u', '+%FT%TZ'],
    'kernel': ['uname', '-a'],
    'cpu': ['lscpu'],
    'memory': ['free', '-b'],
    'swap': ['swapon', '--show', '--bytes'],
    'disk': ['df', '-B1', '.'],
    'pci': ['lspci', '-nnk'],
    'vulkan-summary': ['vulkaninfo', '--summary'],
    'vulkan-full': ['vulkaninfo'],
    'rocminfo': ['rocminfo'],
    'hipconfig': ['hipconfig', '--full'],
    'power-profile': ['powerprofilesctl', 'get'],
}
status = {}
for name, argv in commands.items():
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        output = result.stdout + result.stderr
        status[name] = {'command': argv, 'exit_code': result.returncode}
    except (OSError, subprocess.TimeoutExpired) as error:
        output = str(error) + '\n'
        status[name] = {'command': argv, 'exit_code': None, 'reason': str(error)}
    (root / (name + '.txt')).write_text(output)
for name, source in {
    'os-release': '/etc/os-release',
    'meminfo': '/proc/meminfo',
    'vmstat-before': '/proc/vmstat',
    'bios-version': '/sys/class/dmi/id/bios_version',
    'bios-date': '/sys/class/dmi/id/bios_date',
    'product-name': '/sys/class/dmi/id/product_name',
}.items():
    try:
        (root / (name + '.txt')).write_text(pathlib.Path(source).read_text())
    except OSError as error:
        status[name] = {'exit_code': None, 'reason': str(error)}
(root / 'collection-status.json').write_text(json.dumps(status, indent=2))
PY
```

## 02.3 Инвентарь памяти и UMA

```sh
python3 - <<'PY'
import glob, json, os, pathlib, re
result = {'page_size_bytes': os.sysconf('SC_PAGE_SIZE'), 'memory': {}, 'sysfs': {}}
for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
    key, value = line.split(':', 1)
    if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
        count = int(value.split()[0]) * 1024
        result['memory'][key] = {'bytes': count, 'GiB': count / 2**30}
paths = [
    '/sys/module/ttm/parameters/pages_limit',
    '/sys/module/ttm/parameters/page_pool_size',
    '/sys/module/amdgpu/parameters/gtt_size',
]
for card in glob.glob('/sys/class/drm/card*'):
    if re.fullmatch(r'card\d+', pathlib.Path(card).name):
        paths.extend(str(path) for path in pathlib.Path(card, 'device').glob('mem_info_*'))
        paths.extend([card + '/device/vendor', card + '/device/device'])
for source in sorted(set(paths)):
    try:
        result['sysfs'][source] = {'value': pathlib.Path(source).read_text().strip()}
    except OSError as error:
        result['sysfs'][source] = {'value': None, 'reason': str(error)}
target = pathlib.Path(os.environ['LAB_DIR']) / 'raw' / 'memory-inventory.json'
target.write_text(json.dumps(result, indent=2))
print(json.dumps(result['memory'], indent=2))
PY
```

`pages_limit × page_size_bytes` — предел страниц TTM, **не** свободная память GPU. Не складывайте его с `MemTotal`, VRAM или GTT: shared UMA, carve-out и API heap могут описывать одну и ту же физическую память.

## 02.4 Три уровня обнаружения GPU

Сопоставьте вручную по собранным файлам:

| Уровень | Файл | Что искать |
| --- | --- | --- |
| PCI / драйвер | `raw/pci.txt` | активный `amdgpu` |
| Vulkan | `raw/vulkan-full.txt` | Radeon 8060S, ICD, версии API/драйвера, heap sizes и budgets |
| HSA / ROCm | `raw/rocminfo.txt` | `gfx1151` |

Программный Vulkan renderer за GPU не считается. При нескольких устройствах зафиксируйте выбранное и его render node; `/dev/dri/renderD128` не предполагается.

## 02.5 Ядро против требований KFD

Сверьте ядро и ROCm с **версией** документации AMD. Для gfx1151 перечислены: Ubuntu HWE от `6.17.0-19.19~24.04.2`, OEM от `6.14.0-1018`, остальные дистрибутивы от `6.18.4` для указанной таблицы prebuilt. Проверьте backports своего релиза. Запишите URL, дату доступа и вывод: `documented`, `conditional` или `unverified`. Команды смены ядра в этой работе не выполняются.

## 02.6 Бюджет первой серии

Резерв ОС — 16 GiB, если в ЛР01 не объявлен другой. Оценка должна удовлетворять **обоим** ограничениям:

```text
weights + runtime + KV/state <= measured_RAM - OS_reserve
allocations_on_GPU           <= measured_available_GPU_budget
```

Если budget API его не сообщает — оставьте неизвестным. 96 GB из рекламы вместо наблюдения не подставляются.

Через минуту простоя:

```sh
free -b > "$LAB_DIR/raw/memory-after-idle.txt"
```

Заметное расхождение с первым замером требует описания фоновых нагрузок.

## 02.7 Отчёт

Заполните `report.md`, `measurements.tsv`, `manifest.json`: ссылку на архив ЛР01, пути к raw evidence, допуск или конкретный blocker **для каждой ветви** (Vulkan и HIP/ROCm отдельно). Паспорт не превращается в `run.json` и не получает verdict агентской задачи.

## Ворота на выход

- Целевая машина и native Linux подтверждены.
- Для каждой ветви есть допуск либо конкретный blocker.
- RAM, TTM/GTT и GPU budget не сложены как независимые банки.

Сдача с blocker одной ветви — корректный результат диагностики, а не допуск к её измерениям.

> **Если `vulkaninfo`, `rocminfo` или `hipconfig` недоступны:** пометьте `unavailable` и сдайте паспорт как есть. Установка стека и build-зависимостей (`cmake`, компилятор, Vulkan headers и shader compiler, HIP SDK) — **отдельная работа**, после которой паспорт снимается заново новой сессией, например `ryzen-02`. ЛР04 зависимости на лету не ставит.

---

# ЛР03. Артефакты и контрольный GGUF

Предпосылка: сданы ЛР01 и ЛР02. Минимум — решение по всем 12 кандидатам и **один** проверенный контрольный GGUF `qwen35-9b` Q6_K (≈7,0 GiB). Второй контроль `gpt-oss-20b` MXFP4 (11,3 GiB) и остальные загрузки — расширение. Все 12 артефактов вместе — около 406,7 GiB, качать их для зачёта не нужно.

## 03.1 Архив и входы

```sh
npm run lab:new -- --lab LAB03 --session "$LAB_SESSION"
```

```sh
export LAB_DIR="$LAB03_DIR"
mkdir -p "$LAB_STORAGE"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-before.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
cp experiments/local-models/models.json "$LAB_DIR/raw/catalog.json"
cp experiments/local-models/hardware.json "$LAB_DIR/raw/planning-hardware.json"
```

Ссылка на паспорт ЛР02 и его измеренные `MemTotal`, `MemAvailable`, GPU heap/GTT и swap в `manifest.json` обязательна.

## 03.2 План до загрузки

Общий план и план контрольной модели:

```sh
node scripts/local-plan.mjs --format json > "$LAB_DIR/raw/plan-default.json"
```

```sh
node scripts/local-plan.mjs --model qwen35-9b --context 8192 --format json > "$LAB_DIR/raw/control-plan.json"
```

Планировщик по умолчанию использует **гипотезы** 119,2 GiB RAM, 89,4 GiB GPU budget, 16 GiB ОС, 6 GiB runtime и 4/8/16 GiB для 8K/16K/32K. Подставьте измеренное в ЛР02 и сохраните отдельным файлом вместе с точной командой:

```sh
node scripts/local-plan.mjs --memory-gib ЧИСЛО --gpu-budget-gib ЧИСЛО --format json > "$LAB_DIR/raw/plan-measured.json"
```

Для каждой из 12 моделей запишите решение «первый запуск / позднее / не проходит выбранный бюджет» и условие пересмотра. У MoE загружаются все эксперты, активные параметры описывают только вычисления на токен. Hybrid attention считает cache/state отдельно.

## 03.3 Экспорт точного артефакта

```sh
python3 - "$LAB_DIR" qwen35-9b <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1]) / "raw"
catalog = json.loads((out / "catalog.json").read_text())
model = next(m for m in catalog["models"] if m["id"] == sys.argv[2])
(out / "artifact.json").write_text(json.dumps(model, indent=2) + "\n")
print(json.dumps(model["artifact"], indent=2))
PY
```

Проверьте `model_id`/`model_revision`, репозиторий квантизатора, `artifact.revision`, имена и число файлов, `bytes`, `sha256`, точность и лицензию: ревизии основной модели и GGUF различаются. Недоступный файл или изменившаяся лицензия — статус `no-artifact` и остановка этой конфигурации.

## 03.4 Скрипт загрузки

```sh
cat > "$LAB_DIR/raw/fetch_artifact.py" <<'PY'
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
PY
```

Скрипт не возобновляет оборванную загрузку и не заменяет молча неверный существующий файл. Сверьте запас диска с `artifact.total_bytes`, временными файлами и будущими копиями сервисов.

## 03.5 Загрузка и повторная offline-проверка

```sh
python3 --version > "$LAB_DIR/raw/python-version.txt"
python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/download-verification.json"
```

```sh
python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/verification.json"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-after.txt"
```

При ошибке сохраните stderr и ненулевой exit code. Для split GGUF нужны **все** оригинальные shards в исходной структуре; серверу дальше передаётся первый shard. Shards не склеивают и не переименовывают. Vision projector, speculative draft или иной quant — новый manifest.

## 03.6 Передача артефакта дальше

Checksum-файл для `sha256sum --check` в ЛР04–07 (JSON для этого не подходит):

```sh
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
```

```sh
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/checksums-recheck.txt"
```

```sh
sha256sum "$LAB_DIR/raw/catalog.json" "$LAB_DIR/raw/artifact.json" "$LAB_DIR/raw/fetch_artifact.py" > "$LAB_DIR/raw/input-hashes.txt"
```

Закрепите путь весов в env-файле сессии (для split GGUF убедитесь, что это **первый** shard):

```sh
python3 -c "import json,os,pathlib;d=json.loads(pathlib.Path(os.environ['LAB03_DIR']+'/raw/verification.json').read_text());print('export LOCAL_GGUF=\"'+next(f['path'] for f in d['files'] if f['path'].endswith('.gguf'))+'\"')" | tee -a "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && test -f "$LOCAL_GGUF" && echo "$LOCAL_GGUF"
```

## Ворота на выход

- Для 12 кандидатов есть решение с условиями памяти и очередью.
- Для контрольного GGUF проверены все bytes и SHA-256 либо документирован `no-artifact`/`fail` с причиной.
- Model revision, quantizer revision, quantization и shards различимы в manifest.
- Отсутствующим запускам оставлен `not-run`; оценка не названа замером. Веса в Git не добавляются.

---

# ЛР04. llama.cpp: Vulkan против HIP/ROCm

Предпосылки: ЛР02 и ЛР03 сданы; `cmake`, компилятор, Vulkan headers и shader compiler, HIP SDK **уже установлены**. При ошибке сборки зависимости на лету не ставятся.

Обе ветви обязательны. Отсутствие одной — blocker, а не победа второй.

## 04.1 Закрепление commit

Выберите один commit llama.cpp по поддержке архитектуры и quant вашей модели, запишите полный 40-символьный SHA и дату выбора. `master` и номер релиза идентификатором сборки не являются.

```sh
npm run lab:new -- --lab LAB04 --session "$LAB_SESSION"
```

Впишите SHA в env-файл, затем перечитайте его:

```sh
"${EDITOR:-nano}" "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && export LAB_DIR="$LAB04_DIR" && python3 -c "import os,re,sys; sys.exit(0 if re.fullmatch(r'[0-9a-f]{40}', os.environ['LLAMA_COMMIT']) else 'set full lowercase commit SHA')"
```

Если отдельного checkout ещё нет (`LLAMA_SOURCE` должен быть новым, не занятым каталогом):

```sh
git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE" && git -C "$LLAMA_SOURCE" checkout --detach "$LLAMA_COMMIT"
```

## 04.2 Входы и проверка весов

```sh
test "$(uname -s)" = Linux && test -f "$LOCAL_GGUF" && test "$(git -C "$LLAMA_SOURCE" rev-parse HEAD)" = "$LLAMA_COMMIT" && echo ok
```

```sh
git -C "$LLAMA_SOURCE" rev-parse HEAD > "$LAB_DIR/raw/llama-commit.txt"
git -C "$LLAMA_SOURCE" status --porcelain > "$LAB_DIR/raw/llama-status.txt"
cmake --version > "$LAB_DIR/raw/cmake-version.txt"
hipconfig --full > "$LAB_DIR/raw/hipconfig.txt" 2>&1
vulkaninfo --summary > "$LAB_DIR/raw/vulkan-summary.txt" 2>&1
```

`git status --porcelain` должен быть пустым. При локальных patch сохраните diff и примените его одинаково к обеим сборкам — это отдельный вариант относительно чистого pin.

```sh
cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/verification-before.txt"
```

При ненулевом exit code остановитесь. Хеширование читает веса целиком и прогревает filesystem cache — учтите это в описании состояния кеша.

## 04.3 Две сборки из одного checkout

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

`HSA_OVERRIDE_GFX_VERSION` в baseline не добавляется, target на другую архитектуру ради прохождения не подменяется. Ошибку сохраняйте целиком.

## 04.4 Инвентарь бинарников

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

Проверьте в pinned `--help` наличие `-fa on`, `-ctk/-ctv`, `-d`, `-r`, `-o json`. При другом синтаксисе адаптируйте команды по документации выбранного commit и сохраните их. Автовыбор устройства допустим только после подтверждения Radeon 8060S в обеих ветвях.

## 04.5 Прогрев

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

В логах найдите фактическое число GPU layers, backend и allocations: `-ngl 999` — это запрос, а не доказательство full offload. CPU tokenizer и sampling допустимы; уход слоёв модели на CPU — отдельная конфигурация. При OOM, GPU reset, невалидных данных или выходе за бюджет остановите ветвь. KV precision, контекст и offload незаметно не уменьшаются.

## 04.6 Телеметрия — терминал B, запустить до серии

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB04_DIR" && vmstat -w 1 > "$LAB_DIR/raw/vmstat-series.txt"
```

Остановить Ctrl-C после серии. Отсутствующие sensors отмечайте `null`. RSS процесса, GPU allocation и page cache не складываются без анализа пересечения UMA.

## 04.7 Три парных повтора — терминал A

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

Ветви не запускаются одновременно. `/usr/bin/time` — GNU time, а не shell keyword; при его отсутствии сохраните blocker process-метрик. Успешный exit code всё равно требует проверки логов на offload и allocations; частичный JSON не идёт в отчёт как успешный замер.

## 04.8 Разбор

Состояние кеша описывается отдельно: каждый `llama-bench` — новый процесс, но это не холодный filesystem cache. Пишите «process cold / filesystem warm или unknown». Встроенный прогрев исключён из t/s, а `/usr/bin/time` включает весь процесс — process wall time не называется временем загрузки модели.

Перенесите три индивидуальных результата в `measurements.tsv`, посчитайте median/min/max и отношение `median_HIP / median_Vulkan` для каждого режима. При разных quant, FA или offload отношение как чистый эффект backend не интерпретируется. По `pswpin`/`pswpout` до и после оцените подкачку. В конце повторите проверки SHA весов и commit.

## Ворота на выход

- Обе ветви собраны из одного commit и используют одни SHA весов.
- Подтверждены Radeon 8060S, фактический offload и одинаковые настройки.
- Есть прогрев и три парных повтора либо конкретный blocker.
- Проверены swap и бюджеты, скрытого fallback не было.

---

# ЛР05. Контекст 8/16/32K, streaming и инструменты

Ключевая работа маршрута: именно она делает сервер пригодным для агентов и открывает ЛР08.

Порядок контекстов строго по возрастанию: **8192 → 16384 → 32768**, каждый следующий только при соблюдённых бюджетах предыдущего. Три сервера одновременно не поднимаются. Агентский baseline — 16K; 32K остаётся отдельным вариантом.

Ниже один backend. Для второго работа повторяется в **новом архиве** (например `--session ryzen-01-vulkan`), а не дописывается в этот.

## 05.1 Архив, backend и fixtures

```sh
npm run lab:new -- --lab LAB05 --session "$LAB_SESSION"
```

Выберите прошедший ЛР04 backend и закрепите путь к бинарникам в env-файле (здесь HIP; для Vulkan — `build-vulkan`):

```sh
echo "export LLAMA_BIN=\"$LAB04_DIR/build-hip/bin\"" | tee -a "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && export LAB_DIR="$LAB05_DIR" && test -x "$LLAMA_BIN/llama-server" && test -f "$LOCAL_GGUF" && echo ok
```

```sh
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
sha256sum "$LAB_DIR/raw/chat-request.json" "$LAB_DIR/raw/tool-request.json" > "$LAB_DIR/raw/fixtures.sha256"
```

Поле `model` в обеих fixtures — `lab-model`; оно совпадает с `--alias lab-model` сервера ниже. При другом alias fixtures правятся до серии, и правка получает свой SHA.

```sh
"$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
"$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
sha256sum "$LLAMA_BIN/llama-server" "$LLAMA_BIN/llama-bench" > "$LAB_DIR/raw/binaries.sha256"
```

Проверьте наличие `--alias`, `--no-context-shift`, `-np`, `-fa`, `-d` в pinned help. Зафиксируйте sampling и reasoning из карточки модели в `raw/model-settings.txt` и в manifest; применяйте их одинаково во всех трёх контекстах. Изменённый template получает свой SHA и отдельный вариант.

## 05.2 Проба заполнения памяти без HTTP

Терминал B, до пробы:

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB05_DIR" CTX=8192 && vmstat -w 1 > "$LAB_DIR/raw/context-$CTX-vmstat-series.txt"
```

Терминал A:

```sh
export CTX=8192
DEPTH=$((CTX - 128))
free -b > "$LAB_DIR/raw/context-$CTX-memory-before.txt"
cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-before.txt"
if /usr/bin/time -v -o "$LAB_DIR/raw/context-$CTX-process.txt" \
  "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 0 -n 128 -d "$DEPTH" -r 3 -o json \
  > "$LAB_DIR/raw/context-$CTX-bench.json" \
  2> "$LAB_DIR/raw/context-$CTX-bench.log"; then
  bench_status=0
else
  bench_status=$?
fi
printf '%s\n' "$bench_status" > "$LAB_DIR/raw/context-$CTX-exit.txt"
free -b > "$LAB_DIR/raw/context-$CTX-memory-after.txt"
cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-after.txt"
test "$bench_status" -eq 0
```

Глубины по контекстам — 8064, 16256 и 32640 токенов перед 128 generated. Встроенный прогрев в три измеряемых повтора не входит. Сохранённый exit code проверяется до перехода дальше. При OOM, GPU reset, постоянной подкачке, fallback или выходе за бюджет конфигурация останавливается; более длинный контекст автоматически не запускается. Изменение KV или FA ради вместимости — новый вариант, а не исправление результата.

## 05.3 Сервер этого контекста — терминал C

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB05_DIR" CTX=8192 && "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" --host 127.0.0.1 --port 8080 --alias lab-model -ngl 999 -c "$CTX" -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on --jinja --no-context-shift > "$LAB_DIR/raw/server-$CTX.log" 2>&1
```

Добавьте сюда записанные model-specific sampling/reasoning flags. Сервер остаётся только на loopback. Терминал A, после health response:

```sh
curl --fail --max-time 10 http://127.0.0.1:8080/health > "$LAB_DIR/raw/health-$CTX.json"
curl --fail --max-time 10 http://127.0.0.1:8080/props > "$LAB_DIR/raw/props-$CTX.json"
curl --fail --max-time 10 http://127.0.0.1:8080/v1/models > "$LAB_DIR/raw/models-$CTX.json"
```

Подтвердите alias `lab-model`, GPU offload, effective context и slots, template. `--reasoning-format` описывает разбор результата, а не режим thinking: thinking не объявляется отключённым только потому, что reasoning не виден в `content`.

## 05.4 HTTP/SSE измеритель

```sh
cat > "$LAB_DIR/raw/http_probe.py" <<'PY'
import argparse, json, pathlib, time, urllib.error, urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url')
parser.add_argument('--request')
parser.add_argument('--out', required=True)
parser.add_argument('--follow-tool', action='store_true')
parser.add_argument('--validate-tool-message')
args = parser.parse_args()
def save(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def validate_tool(message):
    calls = message.get('tool_calls', [])
    if len(calls) != 1:
        raise ValueError('expected exactly one tool call')
    tool = calls[0]
    function = tool['function']
    arguments = json.loads(function['arguments'])
    if tool.get('type') != 'function':
        raise ValueError('only function tools allowed')
    if function['name'] != 'lookup_lab_value' or arguments != {'key': 'alpha'}:
        raise ValueError('tool/arguments rejected by allowlist')
    if not tool.get('id'):
        raise ValueError('missing tool call id')
    return tool

if args.validate_tool_message:
    try:
        validate_tool(json.loads(pathlib.Path(args.validate_tool_message).read_text()))
        save(args.out + '.tool-validation.json', {'accepted': True})
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise SystemExit(1)
    raise SystemExit(0)
if not args.url or not args.request:
    parser.error('--url and --request are required for HTTP probes')

def call(payload, prefix):
    save(prefix + '.request.json', payload)
    metrics = {'ttft_content_s': None, 'ttft_reasoning_s': None, 'usage': None}
    start = time.perf_counter()
    request = urllib.request.Request(args.url.rstrip('/') + '/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            metrics['http_status'] = response.status
            if not payload.get('stream'):
                value = json.load(response)
                save(prefix + '.response.json', value)
                message = value['choices'][0]['message']
                metrics['finish_reason'] = value['choices'][0].get('finish_reason')
                metrics['usage'] = value.get('usage')
            else:
                message = {'role': 'assistant', 'content': ''}
                tools, reasoning, done = {}, '', False
                with open(prefix + '.sse', 'wb') as raw:
                    for line in response:
                        raw.write(line)
                        raw.flush()
                        if not line.startswith(b'data:'):
                            continue
                        data = line[5:].strip()
                        if data == b'[DONE]':
                            done = True
                            break
                        if not data:
                            continue
                        event = json.loads(data)
                        if event.get('error'):
                            raise ValueError(str(event['error']))
                        if event.get('usage') is not None:
                            metrics['usage'] = event['usage']
                        for choice in event.get('choices', []):
                            delta = choice.get('delta', {})
                            content = delta.get('content') or ''
                            thought = delta.get('reasoning_content') or ''
                            if content and metrics['ttft_content_s'] is None:
                                metrics['ttft_content_s'] = time.perf_counter() - start
                            if thought and metrics['ttft_reasoning_s'] is None:
                                metrics['ttft_reasoning_s'] = time.perf_counter() - start
                            message['content'] += content
                            reasoning += thought
                            for piece in delta.get('tool_calls', []):
                                item = tools.setdefault(piece['index'], {'id': '',
                                    'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                if piece.get('id'):
                                    item['id'] = piece['id']
                                function = piece.get('function', {})
                                item['function']['name'] += function.get('name') or ''
                                item['function']['arguments'] += function.get('arguments') or ''
                            if choice.get('finish_reason') is not None:
                                metrics['finish_reason'] = choice['finish_reason']
                if tools:
                    message['tool_calls'] = [tools[index] for index in sorted(tools)]
                if reasoning:
                    message['reasoning_content'] = reasoning
                metrics['stream_done'] = done
                save(prefix + '.assembled.json', message)
                if not done:
                    raise ValueError('SSE ended without [DONE]')
            metrics['duration_s'] = time.perf_counter() - start
            save(prefix + '.metrics.json', metrics)
            return message
    except Exception as error:
        if isinstance(error, urllib.error.HTTPError):
            metrics['http_status'] = error.code
            pathlib.Path(prefix + '.http-error.txt').write_bytes(error.read())
        metrics.update(error=str(error), duration_s=time.perf_counter() - start)
        save(prefix + '.metrics.json', metrics)
        raise

payload = json.loads(pathlib.Path(args.request).read_text())
message = call(payload, args.out)
if args.follow_tool:
    try:
        tool = validate_tool(message)
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise
    followup = dict(payload)
    followup['messages'] = payload['messages'] + [message, {
        'role': 'tool', 'tool_call_id': tool['id'], 'content': 'LAB_VALUE_42'}]
    message = call(followup, args.out + '.followup')
save(args.out + '.final.json', {'content': message.get('content'),
    'tool_calls': message.get('tool_calls'), 'reasoning_content': message.get('reasoning_content')})
PY
```

TTFT измеряется только для streaming: задержка получения полного JSON не является TTFT. `ttft_content_s` отделён от первого reasoning-токена.

## 05.5 Четыре protocol case по два раза

```sh
python3 - <<'PY'
import json, os, pathlib
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
for kind in ('chat', 'tool'):
    value = json.loads((root / (kind + '-request.json')).read_text())
    value['stream'] = True
    (root / (kind + '-stream-request.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
PY
```

```sh
for repeat in 1 2; do
  for kind in chat chat-stream; do
    python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
      --request "$LAB_DIR/raw/$kind-request.json" \
      --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat"
  done
  for kind in tool tool-stream; do
    python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
      --request "$LAB_DIR/raw/$kind-request.json" \
      --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat" --follow-tool
  done
done
```

Ожидаемые final: `LAB_READY` для чата, `LAB_VALUE_42` для tool round trip. Проверяйте совпадение `call_id`, валидный JSON arguments, завершающее событие и finish reason. Первый и повторный запрос обозначайте отдельно: второй может использовать prefix cache. Отсутствующий usage записывается `null`, токены из длины текста не вычисляются. Незавершённый round trip — не pass даже при HTTP 200.

## 05.6 Отказ диспетчера неизвестному инструменту

Endpoint не вызывается; проверяется граница клиента.

```sh
python3 - <<'PY'
import copy, json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
valid = {'role': 'assistant', 'content': None, 'tool_calls': [{
    'id': 'offline-case-1', 'type': 'function',
    'function': {'name': 'lookup_lab_value', 'arguments': '{"key":"alpha"}'}}]}
cases = {'valid': valid}
for name, field, value in [('unknown-name', 'name', 'unexpected_tool'),
                          ('wrong-arguments', 'arguments', '{"key":"beta"}')]:
    message = copy.deepcopy(valid)
    message['tool_calls'][0]['function'][field] = value
    cases[name] = message
message = copy.deepcopy(valid)
del message['tool_calls'][0]['id']
cases['missing-id'] = message
results = {}
for name, message in cases.items():
    prefix = root / ('offline-tool-' + name)
    source = pathlib.Path(str(prefix) + '-message.json')
    source.write_text(json.dumps(message, indent=2))
    result = subprocess.run([sys.executable, str(root / 'http_probe.py'),
        '--validate-tool-message', str(source), '--out', str(prefix)], check=False)
    expected = 0 if name == 'valid' else 1
    results[name] = {'exit_code': result.returncode, 'expected_exit_code': expected}
(root / 'offline-tool-checks.json').write_text(json.dumps(results, indent=2))
assert all(row['exit_code'] == row['expected_exit_code'] for row in results.values())
PY
```

В `offline-tool-*.tool-rejected.json` подтвердите конкретные причины `tool/arguments rejected by allowlist` и `missing tool call id`, а не произвольную Python-ошибку; для valid ожидается `accepted: true`.

## 05.7 Длинный вход с учётом шаблона

Генератор использует `/apply-template` и `/tokenize`, inference не выполняет. Если pinned server этих endpoints не поддерживает — фиксируйте blocker методики и считайте длину его tokenizer отдельно.

```sh
python3 - <<'PY'
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = int(os.environ['CTX'])
budget = context - 4096
def post(route, value):
    request = urllib.request.Request('http://127.0.0.1:8080' + route,
        data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)
def candidate(rows):
    text = 'Контрольное значение: LAB_SENTINEL_42.\n'
    text += ''.join(f'Строка {i}: нейтральные данные измерения.\n' for i in range(rows))
    text += 'Верни только контрольное значение из первой строки.'
    messages = [{'role': 'user', 'content': text}]
    prompt = post('/apply-template', {'messages': messages})['prompt']
    tokens = post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens']
    return messages, prompt, len(tokens)
low, high, best = 0, context, None
while low <= high:
    middle = (low + high) // 2
    messages, prompt, count = candidate(middle)
    if count <= budget:
        best = (messages, prompt, count)
        low = middle + 1
    else:
        high = middle - 1
if best is None:
    raise RuntimeError('template exceeds input budget')
messages, prompt, count = best
payload = {'model': 'lab-model', 'messages': messages, 'max_tokens': 4096, 'stream': True}
prefix = root / ('ctx' + str(context) + '-long')
pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
pathlib.Path(str(prefix) + '-prompt.txt').write_text(prompt)
pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({
    'context': context, 'input_tokens': count, 'output_reserve': 4096, 'input_budget': budget}, indent=2))
PY
```

```sh
for repeat in 1 2; do
  python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
    --request "$LAB_DIR/raw/ctx$CTX-long-request.json" \
    --out "$LAB_DIR/raw/ctx$CTX-long-r$repeat"
done
```

Сравните server `usage.prompt_tokens` с предварительным count: расхождение означает другой effective template или tokenization и требует объяснения. Ожидаемый final — `LAB_SENTINEL_42`, и только при отсутствии truncation и context shift.

## 05.8 Переполнение, отмена, восстановление

```sh
python3 - <<'PY'
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = int(os.environ['CTX'])
source = root / ('ctx' + str(context) + '-long-request.json')
payload = json.loads(source.read_text())
text = payload['messages'][0]['content']
for attempt in range(8):
    text = text + '\n' + text
    payload['messages'][0]['content'] = text
    def post(route, value):
        request = urllib.request.Request('http://127.0.0.1:8080' + route,
            data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    prompt = post('/apply-template', {'messages': payload['messages']})['prompt']
    count = len(post('/tokenize', {'content': prompt,
        'add_special': False, 'parse_special': True})['tokens'])
    if count > context:
        break
else:
    raise RuntimeError('could not construct overflow within bounded attempts')
payload['max_tokens'] = 128
prefix = root / ('ctx' + str(context) + '-overflow')
pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False))
pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({'input_tokens': count, 'context': context}))
PY
```

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/ctx$CTX-overflow-request.json" --out "$LAB_DIR/raw/ctx$CTX-overflow"
```

Recovery запускается **отдельной командой**, даже если ожидаемая HTTP-ошибка завершила probe ненулевым кодом:

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-overflow-recovery"
```

Ожидается явный отказ либо документированное ограничение; тихое обрезание с baseline несовместимо.

```sh
if curl --no-buffer --max-time 1 -H 'Content-Type: application/json' \
  --data-binary @"$LAB_DIR/raw/ctx$CTX-long-request.json" \
  http://127.0.0.1:8080/v1/chat/completions \
  > "$LAB_DIR/raw/ctx$CTX-cancel.sse" 2> "$LAB_DIR/raw/ctx$CTX-cancel.log"; then
  printf '0\n' > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
else
  printf '%s\n' "$?" > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
fi
```

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-cancel-recovery"
```

Timeout клиента не доказывает, что сервер отменил вычисление: проверьте server log, slot и время восстановления. Если запрос успел закончиться за секунду — это не проверка отмены, повторите с более длительным запросом.

## 05.9 Следующий контекст

Остановите сервер Ctrl-C в терминале C, убедитесь, что процесс завершился и память освобождена. Затем повторите 05.2–05.8 с `CTX=16384`, после него — с `CTX=32768`, только если предыдущие бюджеты соблюдены. В manifest сохраните одинаковые settings и отдельно context каждого запуска.

## Ворота на выход

- Для каждого контекста выполнена проба заполнения либо сохранён blocker.
- Есть два повтора chat, streaming, tools и streaming tools для допущенных контекстов.
- Tool round trip проверен через allowlist, без исполнения произвольного кода.
- Длинный вход посчитан tokenizer и проверен на тихое обрезание.
- Reasoning и final, output cap и finish reason описаны раздельно.
- Проверены обработка ошибки, отмена и восстановление slot.

Работа с честно зафиксированным потолком 16K считается выполненной. Это не означает, что модель прошла 32K или готова к любому агентному протоколу.

---

# Гигиена доказательств

Корневой `.gitignore` исключает `*.log`, а `experiments/local-models/.gitignore` — `measurements/*/build-vulkan/`, `measurements/*/build-hip/`, `measurements/*/raw/sglang-src/`, `measurements/*/raw/ollama-models/`. Обычный commit **не перенесёт весь комплект raw evidence**: архивируйте `raw/` отдельно и указывайте архив в `manifest.json`.

Неудачные попытки не удаляются. `null` или пусто — неизвестное с причиной; `0` — только измеренный ноль. Число без единиц, контекста и условий в сравнение не идёт.

В конце каждой работы:

```sh
npm run check
```

Он проверяет структуру заданий, каталоги и run records — **зачёт за отчёт он не выставляет**.

# Что дальше

| Куда | Что даёт | Предпосылка |
| --- | --- | --- |
| [ЛР07](../../docs/labs/LAB07-serving.md) | Два сервиса из Ollama / LM Studio / Lemonade на том же GGUF | ЛР05 |
| [ЛР06](../../docs/labs/LAB06-engines.md) | vLLM, SGLang, Transformers на ROCm; нужен отдельный native BF16 checkpoint, GGUF не переиспользуется | ЛР03 и ЛР05 |
| [ЛР08](../../docs/labs/LAB08-local-bridge.md) | Local provider bridge — единственный путь к локальным ЛР09–10 | ЛР01 и ЛР05 |

Проектную часть ЛР08 (контракт endpoint, граница сети, поля схемы под fingerprint инференса) можно писать параллельно, пока идут сборки ЛР04.
