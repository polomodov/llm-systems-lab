# LAB03 — Выбор моделей и закрепление артефактов: Qwen3.5-9B (Q6_K)

Сессия: `qwen35-9b`

Дата: 2026-10-01

Статус: **blocked** — результаты выбора и проверки файла сохранены, но исходный предварительный протокол не подтверждён. Контрольный артефакт
`Qwen3.5-9B-Q6_K.gguf` загружен с Hugging Face, SHA-256 сверен с
publisher metadata и с локальным файлом. В этой сессии inference не выполнялся; аппаратные проверки относятся к отдельным лабораторным.

Связанные сессии:

- `experiments/local-models/measurements/LAB02-after-rocm/` — паспорт машины
  с актуальными бюджетами (Vulkan heap1 budget 65.99 GiB — лимитирующий
  фактор).
- `experiments/local-models/measurements/LAB02-first-pass/` — первый паспорт
  без Vulkan/ROCm runtime.
- `docs/labs/LAB03-artifacts.md` — протокол ЛР03.
- `experiments/local-models/models.json` — каталог 12 кандидатов.
- `experiments/local-models/hardware.json` — аппаратные резервы.

## Сверка учёта 2026-10-22

Исходный отдельный файл протокола, сохранённый до работы, не найден. Текст плана в старом manifest и дата без такого файла не доказывают предварительную регистрацию. Реестр восстановлен 2026-10-22 по сохранённым материалам и не является предрегистрацией. Исходные `manifest.json`, `report.md` и `measurements.tsv` сохранены побайтно в `raw/backup/before-reconciliation-*`; SHA-256 и преобразования перечислены в `raw/backup/reconciliation.json`. Строковые результаты и плановые резервы сохранены там отдельно от численных замеров. Неизвестные значения в TSV пусты с причиной; пропущенные команды и inference остаются в реестре. Исходные raw-файлы не изменены, новых измерений не выполнялось. `reviewer_decision` остаётся `null`; комплектность blocked-отчёта не означает завершение лабораторной.

## Паспорт выполнения

Исполнитель: agent-harness-lab operator; дата исходной работы — 2026-10-01. Машина: Ryzen AI Max+ 395, Ubuntu 24.04.4, kernel 7.0.0-34-generic (снимок LAB02-after-rocm). Обвязка и inference runtime в этой сессии не запускались; `run_ids` пуст. Ревизия репозитория и версия Python сохранены в `raw/repository-revision.txt` и `raw/python-version.txt`.

### Аппаратный бюджет (из ЛР02-after-rocm)

| Параметр | Значение | Источник |
| --- | --- | --- |
| MemTotal | 124.94 GiB (134 153 334 784 bytes) | `LAB02-after-rocm/raw/memory-inventory.json` |
| MemAvailable (до простоя) | 116.65 GiB | `LAB02-after-rocm/raw/memory-inventory.json` |
| OS reserve (default ЛР02) | 16.00 GiB | `LAB02-after-rocm/raw/backup/reconciliation.json` |
| Доступная RAM для модели | 108.94 GiB | `MemTotal − OS_reserve` |
| Vulkan heap1 (DEVICE_LOCAL) size | 67.00 GiB | `LAB02-after-rocm/raw/vulkan-full.txt` |
| **Vulkan heap1 budget** (лимит) | **65.99 GiB** | `LAB02-after-rocm/raw/vulkan-full.txt` |
| ROCm GPU COARSE GRAINED pool | 100.00 GiB | `LAB02-after-rocm/raw/rocminfo.txt` |
| TTM pages_limit × page_size | 100.00 GiB | `LAB02-after-rocm/raw/memory-inventory.json` |
| Лимитирующий фактор | **65.99 GiB** | Vulkan heap1 budget (ICD reserve) |

Планировщик `scripts/local-plan.mjs` по умолчанию использует гипотезы
119.2 GiB RAM и 89.4 GiB GPU — это резервы, **не** измеренные значения.
Для нашей машины фактический GPU budget ниже (65.99 GiB); это учитывается
в колонке «fit_vs_vulkan_heap1_budget» ниже.

## Гипотеза и протокол до запуска

**Гипотеза:** выбранный GGUF совпадает с закреплёнными revision/bytes/SHA-256; плановая оценка памяти допускает последующую проверку загрузки при 8K и одной последовательности.

Отдельный исходный протокол до работы не найден. Текст в старом manifest не подтверждает предварительную регистрацию; `protocol_before_run` и `protocol_recorded_at` оставлены `null`. Список действий ниже восстановлен по сохранённым файлам 2026-10-22 и не считается предрегистрацией.

## Ход выполнения

### Подготовка

```sh
npm run lab:new -- --lab LAB03 --session qwen35-9b
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB03-qwen35-9b"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
mkdir -p "$LAB_STORAGE"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-before.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
cp experiments/local-models/models.json "$LAB_DIR/raw/catalog.json"
cp experiments/local-models/hardware.json "$LAB_DIR/raw/planning-hardware.json"
python3 --version > "$LAB_DIR/raw/python-version.txt"
```

- Git revision: см. `raw/repository-revision.txt` (`84b40b3` — `Merge pull
  request #6 from polomodov/lab02-after-rocm`).
- Python: 3.12.3 (≥ 3.11 — поддерживает `hashlib.file_digest`).
- Свободно на диске до: 1 832 540 762 112 bytes (1.83 TB).

## Результаты

### 1. План по 12 кандидатам (из `raw/plan-default.json`)

| Кандидат | Контекст | Веса, GiB (est) | Total, GiB | Headroom vs 65.99 GiB | Решение / условие |
| --- | ---: | ---: | ---: | ---: | --- |
| `qwen35-9b` (Q6_K) | 8K | 7.0 | 17.0 | 48.99 | **P1, контроль, выполнено** |
| `qwen35-9b` | 16K | 7.0 | 21.0 | 44.99 | P1 (плановый rerun, не нужен для зачёта) |
| `qwen35-9b` | 32K | 7.0 | 29.0 | 36.99 | P1 (после LAB05) |
| `gpt-oss-20b` (MXFP4) | 8K | 11.3 | 21.3 | 44.69 | P1, второй контроль (позднее) |
| `qwen36-27b` (Q5_K_M) | 8K | 18.2 | 28.2 | 37.79 | P1 |
| `qwen36-35b-a3b` (UD-Q5_K_M) | 8K | 24.7 | 34.7 | 31.29 | P1, MoE (все эксперты загружены, не только active 3B) |
| `glm-47-flash` (Q8_0) | 8K | 29.7 | 39.7 | 26.29 | P1 |
| `qwen3-coder-next` (Q5_K_M) | 8K | 52.9 | 62.9 | 3.09 | P1, требует увеличения KV при большом контексте |
| `gemma4-31b-it` (Q5_K_M) | 8K | 20.2 | 30.2 | 35.79 | P2 |
| `qwen3-coder-30b-a3b` (Q5_K_M) | 8K | 20.3 | 30.3 | 35.69 | P2 |
| `gpt-oss-120b` (MXFP4) | 8K | 59.1 | 69.1 | **−3.11** | P2, условно: не проходит 65.99 GiB budget; 16K+ — тоже |
| `qwen35-122b-a10b` (Q4_K_M) | 8K | 71.3 | 81.3 | **−15.31** | P2, условно: не проходит; нужно снижение quant или контекста |
| `qwen35-35b-a3b` (Q5_K_M) | 8K | 24.5 | 34.5 | 31.49 | P3 |
| `glm-45-air` (Q4_K_M) | 8K | 68.0 | 78.0 | **−12.01** | P3, условно: не проходит |

**Лимитирующий фактор** — Vulkan heap1 budget **65.99 GiB**, не TTM cap
100 GiB и не `MemTotal − OS_reserve` 108.94 GiB. Это объясняет, почему
`gpt-oss-120b` и `qwen35-122b-a10b`/`glm-45-air` не проходят наш
бюджет — даже при 8K.

Контрольный план для выбранного `qwen35-9b` сохранён в
`raw/control-plan.json` (engine не выбран — это задел для ЛР04).

### 2. Выбранный артефакт

`raw/artifact.json`:

```json
{
  "repository": "unsloth/Qwen3.5-9B-GGUF",
  "revision": "3885219b6810b007914f3a7950a8d1b469d598a5",
  "files": [
    {
      "path": "Qwen3.5-9B-Q6_K.gguf",
      "bytes": 7458301152,
      "sha256": "91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59"
    }
  ],
  "total_bytes": 7458301152,
  "checksum_status": "publisher_metadata_not_download_verified"
}
```

- **Ревизия основной модели**: `Qwen/Qwen3.5-9B` (см. каталог).
- **Ревизия GGUF (издатель unsloth)**: `3885219b6810b007914f3a7950a8d1b469d598a5`.
- **Quantization**: `Q6_K` (k-quant, 6 бит).
- **Лицензия**: Apache-2.0 (наследуется от Qwen3.5-9B).
- **Число shards**: 1 (split GGUF не используется).
- **Дополнительные компоненты**: vision projector / speculative draft —
  отсутствуют (это текстовая модель).

### 3. Скрипт загрузки

`raw/fetch_artifact.py` — копия шаблона из ЛР03-artifacts.md с
проверкой:

- `repository` соответствует `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`.
- `revision` — 40 hex.
- `path` — относительный, без `..`.
- `dest.resolve().is_relative_to(root)` — защита от path traversal.
- `urllib.request.urlopen` без автоматического возобновления (`.part`
  сохраняется при ошибке для диагностики).
- Проверка SHA-256 и размера **после** полной загрузки (до `os.replace`).
- Exit 0 только если все файлы `verified`.

### 4. Загрузка и offline-проверка

```sh
# download
python3 raw/fetch_artifact.py raw/artifact.json "$LAB_STORAGE" --download \
  > raw/download-verification.json
# offline re-verify
python3 raw/fetch_artifact.py raw/artifact.json "$LAB_STORAGE" \
  > raw/verification.json
sha256sum --check raw/weights.sha256 > raw/checksums-recheck.txt 2>&1
sha256sum raw/catalog.json raw/artifact.json raw/fetch_artifact.py \
  > raw/input-hashes.txt
```

| Шаг | Длительность | Результат |
| --- | --- | --- |
| Загрузка (7.46 GB / 6.95 GiB) | `unavailable`: старое заявление 1360 с без сырого отсчёта | `verified` |
| Offline re-verify | `unavailable`: старое заявление ~80 с без сырого отсчёта | `verified` |
| `sha256sum --check` | `unavailable`: длительность не сохранена | `OK` |

| Наблюдение | Значение | Условия | Evidence |
| --- | --- | --- | --- |
| Свободный диск до | 1 832 540 762 112 bytes | `df -B1` до загрузки | `raw/disk-before.txt` |
| Свободный диск после | 1 825 077 895 168 bytes | `df -B1` после | `raw/disk-after.txt` |
| Уменьшение свободного диска | 7 462 866 944 bytes | разность `df`; вклад загрузки и фоновых процессов отдельно не измерен | оба `df`, `raw/backup/reconciliation.json` |
| Время загрузки | `unavailable` | старый отчёт заявляет 1360 s; начальный/конечный отсчёт не сохранён | `raw/backup/before-reconciliation-report.md` |

### 5. Контрольные артефакты

| Файл | SHA-256 | Назначение |
| --- | --- | --- |
| `raw/catalog.json` | `923c9e1a6c6573952ba9485b4dc824d708045768b008df881df09f464c42395b` | вход: каталог 12 моделей |
| `raw/artifact.json` | `7288738d81a635854d1300a1e9a35378a99b456abf3af68e76b7a80142c4b242` | вход: выбранный артефакт |
| `raw/fetch_artifact.py` | `08646ba2b488d4cd84bddb42acc18e3beceba5b82b3f812f7e5a3265e2c2bffb` | вход: скрипт загрузки |
| `raw/weights.sha256` | одна строка: `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59  /home/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf` | контрольный файл для `sha256sum --check` |

### 6. Путь для следующих лабораторных

Абсолютный путь весов:

```
/home/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf
```

Этот путь передаётся в ЛР04 (Vulkan) и ЛР05 (HIP/ROCm) как `GGUF`.

## Что будет проверяться при реальной загрузке (ЛР04–05)

- `llama-bench -m <GGUF> -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on
  -p 512,2048,8192 -n 0 -r 3 -o json` — pp при 8K.
- То же `-n 128 -d 0,8192` — tg при 8K (вместимость должна быть не меньше
  `8192 + 128`).
- Проверка выбранного backend: Vulkan → `RADV GFX1151`, HIP/ROCm →
  `rocminfo` показывает GPU agent; **CPU fallback не считается успехом
  ветки**.
- Telemetry: MemAvailable, GTT used, `/sys/class/drm/card1/device/mem_info_*`,
  RSS процесса.

## Ошибки и ограничения

- **Inference не выполнялся.** `real_inference_qwen35_9b` помечен
  `not-run` в `measurements.tsv`; planner fit — это только нижняя
  оценка, не доказательство GPU residency. Только ЛР04–05 это подтвердят.
- **Disk used — разность свободного диска**, а не отдельное измерение загрузки. Два `df` не показывают наличие временных `.part` и вклад фоновых процессов. Старое численное значение исправлено по исходным `df`; оригинал сохранён в backup.
- **Версия GGUF (3885219b...)** привязана к репозиторию `unsloth/Qwen3.5-9B-GGUF`.
  Любое изменение upstream требует нового manifest и повторной проверки.
- **`hipconfig` unavailable** не влияет на ЛР03 — для паспорта артефакта
  достаточно `sha256sum` + `df`.

## Ответы на контрольные вопросы

1. **Почему 3B active у MoE не означает, что на диске/в RAM нужно только
   3B параметров?**
   У MoE при inference активны только `active` параметры, но **все**
   эксперты должны быть загружены в память (иначе нечего активировать).
   Например, `qwen36-35b-a3b` имеет 35B суммарно и 3B active — на диске
   24.7 GiB (Q5_K_M), и **все** эти 24.7 GiB нужны в RAM/GTT, не 2-3
   GiB. То же для `qwen35-122b-a10b` (122B/10B active ≈ 71.3 GiB на диске,
   все 71.3 нужны).

2. **Почему Q5 и UD-Q5 одного семейства — не чистая абляция поколения?**
   UD-Q5_K_M (`qwen36-35b-a3b`) — это **другой** квантизатор
   (`Unsloth Dynamic`), другой метод и часто другая сетка per-layer.
   Сравнение Q5 vs UD-Q5 смешивает поколение модели и метод квантизации;
   чистое сравнение требует одинакового квантизатора (например, Q5_K от
   одного автора).

3. **Что доказывает SHA-256, и чего не говорит о качестве квантизации и
   корректности inference kernels?**
   SHA-256 подтверждает: (а) файл точно соответствует тому, что опубликовал
   издатель (бит-в-бит); (б) файл не повреждён при передаче и хранении.
   SHA-256 **не** говорит: (а) правильно ли выбран метод квантизации для
   архитектуры; (б) пройдёт ли модель inference на конкретном движке без
   NaN/мусора; (в) не содержит ли файл вредоносного кода (формат GGUF
   хранит код для тензорных операций, но исполнение идёт в движке).

4. **Почему сохранённый hash metadata издателя ещё не равен проверке
   локального файла?**
   Hash в `models.json` получен из Hugging Face API на 2026-09-20. Это
   «publisher metadata»: декларация издателя о содержимом файла. Локальная
   проверка (`hashlib.file_digest`) сравнивает байты реально скачанного
   файла с этой декларацией. Совпадение доказывает, что файл пришёл
   от издателя без изменений. До проверки статус `checksum_status` в
   catalog — `publisher_metadata_not_download_verified`.

5. **Какие расходы памяти могут превратить положительную оценку 32K в
   OOM?**
   (а) Реальный KV cache для конкретной архитектуры (для dense не совпадает
   с плановой оценкой `kv_cache_reserve_gib`); для MoE + hybrid attention
   формула совсем другая. (б) Компиляция графа / `compile` / `cudaGraph`
   может потребовать дополнительные буферы. (в) `mmap` страниц
   поверх page cache. (г) Одновременные процессы (desktop, IDE, браузер).
   (д) Фрагментация TTM heap. Планировщик даёт нижнюю границу; реальная
   загрузка может потребовать на 5–15 GiB больше.

## Вывод по гипотезе

Сохранённые отчёты загрузки и offline-проверки подтверждают размер и SHA-256 контрольного файла. Плановые резервы памяти и вывод `candidate` не являются измерением GPU residency. Исходный протокол и сырые отсчёты длительности отсутствуют; учёт исправлен со статусом `blocked`, без новых запусков и без назначения зачёта.

## Комплект сдачи

- [x] `report.md` с таблицами 12 кандидатов + выбранный артефакт +
  наблюдения диска/времени.
- [x] `manifest.json` со всеми evidence_files.
- [x] `measurements.tsv` (7 числовых/недоступных наблюдений; строковые результаты и плановые значения сохранены в `raw/backup/reconciliation.json`).
- [x] `raw/catalog.json`, `raw/artifact.json`, `raw/fetch_artifact.py`,
  `raw/verification.json`, `raw/weights.sha256`, `raw/checksums-recheck.txt`,
  `raw/input-hashes.txt`, `raw/disk-{before,after}.txt`,
  `raw/repository-revision.txt`, `raw/python-version.txt`.
- [x] Реальный inference — `not-run` (план по памяти не равен замеру).
- [x] Связь с ЛР02-after-rocm (бюджеты).
- [x] Контрольные вопросы заполнены.
- [x] Веса в Git **не** добавлены (только путь).

### Индивидуальные критерии завершения ЛР03

- [x] Для 12 кандидатов есть решение с условиями памяти и очередью.
- [x] Для одного контрольного GGUF проверены все bytes/SHA-256 — `verified`.
- [x] Model revision, quantizer revision, quantization и shards различимы
  в manifest.
- [x] Диск, RAM, GPU budget, веса и KV/state не смешаны в одну величину.
- [x] Отсутствующим аппаратным запускам оставлен `not-run`; оценка не
  названа замером.
- [x] Отчёт позволяет другому участнику воспроизвести выбор и проверку
  без поиска alias (см. `raw/artifact.json`).

## Источники

- [Каталог 12 кандидатов](../../models.json), [разбор кандидатов](../../../../docs/local-model-candidates.md).
- [План памяти и порядок кампании](../../../../docs/local-models.md), [Linux runbook](../../../../docs/local-model-runtime.md).
- [Hugging Face: версии и загрузка](https://huggingface.co/docs/huggingface_hub/guides/download).
- [Qwen3.5-9B (официальная модель)](https://huggingface.co/Qwen/Qwen3.5-9B),
  [GGUF от unsloth](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF).
- [Python hashlib.file_digest](https://docs.python.org/3/library/hashlib.html#hashlib.file_digest).
- Паспорт машины: `../LAB02-after-rocm/report.md`.
