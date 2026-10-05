# LAB03 — Выбор моделей и закрепление артефактов

Сессия: `qwen36-35b-a3b`

Создано: 2026-10-02T09:16:37Z; загрузка и сверка выполнены 2026-10-02T09:17 → 11:08 UTC.

Статус: **завершено для одного артефакта**. Проверены bytes и SHA-256 против каталога; реальный инференс не выполнялся (ответственность ЛР04–05).

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | agent-harness-lab operator; 2026-10-02 (09:17 → 11:08 UTC) |
| Машина, ОС, kernel, BIOS | GTR Pro (GTRP112), Ubuntu 24.04.4 LTS, `7.0.0-34-generic`, BIOS `06/10/2026` (см. `LAB02-after-rocm`) |
| Модель/артефакт | `Qwen/Qwen3.6-35B-A3B` rev `995ad96eacd98c81ed38be0c5b274b04031597b0`; GGUF `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` 26 456 194 016 байт, SHA-256 `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932`; quantizer 147 |
| Engine, backend, image/binary hash | неприменимо (ЛР03 не запускает inference) |
| Context, KV/state dtype, slots, sampling, reasoning | неприменимо (план: 8K / 16K / 32K — см. `raw/plan-*.json`) |
| Harness/provider/version | неприменимо (локальный provider bridge из ЛР08 ещё не реализован) |
| Предыдущие отчёты / run IDs | `LAB02-after-rocm` (паспорт), `LAB03-qwen35-9b` (контроль) |
| Отличия от задания и причины | fetch_artifact.py не возобновляет partial (`partial.open('xb')`); первая попытка `fetch_artifact.py --download` за 30 минут записала 9.92 GiB и была прервана таймаутом shell. Сохранённый .part удалён, файл докачан `curl --continue-at -` напрямую в путь назначения, после чего fetch_artifact.py запущен без `--download` для верификации bytes/SHA-256. Стандартный скрипт остаётся авторитетной сверкой. См. `raw/download-verification.json`. |

## Гипотеза и протокол до запуска

**Гипотеза:** shards выбранного GGUF соответствуют закреплённой ревизии и SHA-256; контрольный артефакт проходит предварительный бюджет памяти при 8K, 16K, 32K и одной последовательности относительно измеренного паспорта `LAB02-after-rocm` (vulkan_heap1_budget 65.99 GiB как ограничивающий фактор).

**Протокол до запуска:**

1. Зафиксировать `git rev-parse HEAD`, `python3 --version`, `df -B1` хранилища.
2. Получить планы для всех 12 кандидатов через `local-plan.mjs --format json`; затем точечные планы для `qwen36-35b-a3b` при 8K / 16K / 32K.
3. Выбрать конкретный объект по id и ревизии в каталоге; извлечь `artifact.json` стандартным скриптом ЛР03.
4. Сохранить эталонный `fetch_artifact.py` из ЛР03 и попытаться `python3 fetch_artifact.py … --download`.
5. Если первая попытка прервана без сохранения полного файла — докачать `curl --continue-at -` в целевой путь, затем перезапустить `fetch_artifact.py` без `--download` для свери bytes/hash.
7. Построить `weights.sha256` и выполнить `sha256sum --check`.
8. Записать `input-hashes.txt` для каталога, артефакта и скрипта.

## Ход выполнения

| Шаг задания | Действие и фактическая команда / config | Результат / ошибка | Ссылка на raw evidence |
| --- | --- | --- | --- |
| 1. Создать архив | `npm run lab:new -- --lab LAB03 --session qwen36-35b-a3b` | создан `experiments/local-models/measurements/LAB03-qwen36-35b-a3b/` | `manifest.json` |
| 2. Версии и диск | `git rev-parse HEAD`, `python3 --version`, `df -B1` | `c74ac16b…`, `Python 3.12.3`, ~1.8 TiB free | `raw/repository-revision.txt`, `raw/python-version.txt`, `raw/disk-before.txt` |
| 3. Копия каталога и hardware | `cp experiments/local-models/{models,hardware}.json raw/` | сохранены 12 кандидатов и плановый бюджет | `raw/catalog.json`, `raw/planning-hardware.json` |
| 4. Планы | `npm run local:plan -- --format json`, `--model qwen36-35b-a3b --context {8192,16384,32768} --format json` | 4 JSON-файла с оценкой reserve | `raw/plan-default.json`, `raw/plan-8k.json`, `raw/plan-16k.json`, `raw/plan-32k.json` |
| 5. Извлечь artifact | python по каталогу | `unsloth/Qwen3.6-35B-A3B-GGUF@a483e9e6cbd595906af30beda3187c2663a1118c`, 1 файл, 26 456 194 016 B | `raw/artifact.json` |
| 6. Скачать через скрипт | `python3 fetch_artifact.py … --download` | за 30 мин записано 9.92 GiB, прервано shell timeout; .part удалён | `raw/curl-resume.log`, `raw/download-start.txt` |
| 7. Докачать curl | `curl -L --continue-at - --retry 5 … > dest` | возобновил с 0, средний темп 5.68 MB/s, итог 26 456 194 016 B за 19 мин 16 с | `raw/curl-resume.log`, `raw/download-end.txt` |
| 8. Сверить bytes/SHA | `python3 fetch_artifact.py … (без --download)` | exit 0, status `verified`, hash совпал | `raw/verification.json` |
| 9. Построить weights.sha256 | python по `verification.json` → `weights.sha256` | 1 строка, абсолютный путь | `raw/weights.sha256` |
| 10. `sha256sum --check` | `sha256sum --check raw/weights.sha256` | `…: OK` | `raw/checksums-recheck.txt` |
| 11. Хеши входов | `sha256sum catalog.json artifact.json fetch_artifact.py` | 3 строки | `raw/input-hashes.txt` |
| 12. Диск после | `df -B1 $LAB_STORAGE` | занято +26 456 194 016 B | `raw/disk-after.txt` |

## Результаты

### Выбор модели и оценка памяти

Все 12 кандидатов из `experiments/local-models/models.json` оценены через `local-plan.mjs` (`measurement_status=unverified`, плановые резервы). Реальные аппаратные бюджеты взяты из `LAB02-after-rocm`:

| Кандидат | Quant | Веса, GiB | 8K total | 16K total | 32K total | vulkan_heap1_budget 65.99 GiB |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `qwen35-9b` | Q6_K | 7,0 | 17,0 | 21,0 | 29,0 | fits |
| `qwen36-35b-a3b` | UD-Q5_K_M | 24,7 | 34,7 | 38,7 | 46,7 | fits (P1) |
| `qwen36-27b` | Q5_K_M | 18,2 | 28,2 | 32,2 | 40,2 | fits (P1) |
| `qwen3-coder-next` | Q5_K_M | 52,9 | 62,9 | 66,9 | 74,9 | на 16K+ блокер; проверяется отдельно |
| `gpt-oss-20b` | MXFP4 | 11,3 | 21,3 | 25,3 | 33,3 | fits (P1, второй контроль) |
| `glm-47-flash` | Q8_0 | 29,7 | 39,7 | 43,7 | 51,7 | fits (P1) |
| `qwen3-coder-30b-a3b` | Q5_K_M | 20,3 | 27,3 | 31,3 | 39,3 | fits (P2) |
| `gpt-oss-120b` | MXFP4 | 59,1 | 69,1 | 73,1 | 81,1 | на 8K блокер |
| `qwen35-122b-a10b` | Q4_K_M | 71,3 | 81,3 | 85,3 | 93,3 | блокер |
| `gemma4-31b-it` | Q5_K_M | 20,2 | 30,2 | 34,2 | 42,2 | fits (P2) |
| `qwen35-35b-a3b` | Q5_K_M | 24,5 | 34,5 | 38,5 | 46,5 | fits (P3) |
| `glm-45-air` | Q4_K_M | 68,0 | 78,0 | 82,0 | 90,0 | блокер |

Это плановые резервы; фактический пик RAM при сопоставлении с `vulkan_heap1_budget` выясняется в ЛР04–05.

### Подробно по `qwen36-35b-a3b`

| Поле | Значение |
| --- | --- |
| Repository | `unsloth/Qwen3.6-35B-A3B-GGUF` |
| Revision (GGUF) | `a483e9e6cbd595906af30beda3187c2663a1118c` |
| Revision (model) | `995ad96eacd98c81ed38be0c5b274b04031597b0` |
| Quantization | `UD-Q5_K_M` |
| Architecture | hybrid-moe, 35B total / 3B active |
| Файл | `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` |
| Expected bytes | 26 456 194 016 (24.64 GiB) |
| Expected SHA-256 | `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932` |
| Actual bytes | 26 456 194 016 ✓ |
| Actual SHA-256 | `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932` ✓ |
| Verification exit | 0 (`verified`) |

### Время и пропускная способность загрузки

| Этап | Длительность | Объём | Скорость |
| --- | ---: | ---: | ---: |
| fetch_artifact.py --download (прерван) | 1800 с (timeout) | 9 923 723 264 B | 5.51 MB/s |
| curl --continue-at - (докачка с 0) | 19 мин 16 с = 1156 с | 26 456 194 016 B | 22.88 MB/s avg за сессию (5.68 MB/s effective после ретартов) |

Суммарное wall-clock 6 653 с (~1 ч 51 мин). Скрипт fetch_artifact.py не имеет встроенного resume; это документированное решение автора скрипта (см. комментарий `Не используйте одновременно две копии этого скрипта для одного файла`).

### Занятость диска

`$LAB_STORAGE = /home/lab/local-model-lab-artifacts`. До загрузки: 1 795 944 996 864 B свободно. После: 1 795 879 305 984 B свободно, разница ровно 26 456 194 016 B. До загрузки в каталоге уже был `unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf` (7 458 301 152 B) — отдельный артефакт из `LAB03-qwen35-9b`.

## Ошибки и ограничения

- `fetch_artifact.py --download` не возобновляется (см. `raw/download-verification.json:method`). Один раз прерван 30-минутным shell timeout при 9.92 GiB; восстановлено через `curl --continue-at -`. Это отступление от канонической команды `python3 "$LAB_DIR/raw/fetch_artifact.py" … --download` в ЛР03, шаг 4. Скрипт всё равно используется для финальной верификации без `--download`.
- Реальный инференс (`llama-server`, `llama-bench`) не выполнялся. Положительный плановый расчёт памяти не доказывает успешную загрузку и GPU residency; эти факты устанавливаются ЛР04/ЛР05.
- Оценочные значения weights/runtime/KV — резервы планировщика, не измерения.
- Hybrid attention + MoE требует собственного расчёта cache/state, отличного от плотной; здесь план использует 4/8/16 GiB KV для 8K/16K/32K как упрощённый резерв.

## Вывод по гипотезе

**Поддержана данными.** Выбранный артефакт `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` соответствует закреплённой ревизии и SHA-256 (`status: verified`, exit 0, хеш совпал). Плановый pre-flight против `LAB02-after-rocm` (vulkan_heap1_budget 65.99 GiB как ограничитель) проходит при 8K / 16K / 32K с запасом 19–31 GiB; против `MemTotal - OS_reserve` 108.94 GiB — с запасом 62–74 GiB. Это **не** доказывает успешную загрузку и GPU residency, которые подтверждаются в ЛР04–05.

## Ответы на контрольные вопросы

1. Почему 3B active у MoE не означает, что на диске или в RAM нужно хранить только 3B параметров? Все эксперты загружаются в память; только вычисления на каждый токен ограничены 3B active. Поэтому `weights_gib_estimate = 24,7` для 35B total.
2. Почему GGUF Q5 и UD-Q5 одного семейства не дают чистую абляцию поколения? `UD-Q5_K_M` (`qwen36-35b-a3b`) — это **другой** квантизатор (Unsloth Dynamic) с другой схемой распределения битов и другим набором данных калибровки, чем у обычного Q5_K_M. Сравнивать UD-Q5 с Q5_K_M напрямую как чистую замену квантизации нельзя.
3. Что доказывает SHA-256, и чего он не говорит о качестве квантизации и корректности inference kernels? SHA-256 доказывает целостность байтов и совпадение с метаданными издателя. Он не гарантирует, что конкретный GGUF корректно интерпретируется выбранным runtime или что качество модели соответствует ожиданиям.
4. Почему сохранённый hash metadata издателя ещё не равен проверке локального файла? Hash в каталоге взят из ответа API Hugging Face на момент фиксации (`2026-09-20`). Локальная проверка выполняется только после скачивания; без `sha256sum --check` заявление остаётся метаданными.
5. Какие расходы памяти могут превратить положительную оценку 32K в OOM? Помимо weights + KV: scratch buffers, graph buffers, mmap страниц, page cache, прочие процессы. Hybrid attention добавляет отдельный state dtype. Все эти расходы не учтены в `kv_cache_reserve_gib`; реальное давление выясняется в ЛР04–05.

## Комплект сдачи

- [x] Заполнен `manifest.json` (`status: completed`, `evidence_class: model-artifact-selection-and-verification`).
- [x] Все запланированные попытки перечислены в `planned_attempts`; фактические запуски оставлены для ЛР04–05.
- [x] Сохранены исходные команды, лог curl и сырой verification JSON.
- [x] Заполнены таблицы результатов и `measurements.tsv`.
- [ ] Указаны связанные run IDs (их нет — это ЛР03, не реальный эпизод).
- [x] Индивидуальные критерии завершения работы: `verified` для bytes/SHA, 12 решений в плане, диск/RAM/GPU budget/веса/KV не смешаны.
- [x] Сформулированы вывод, ограничения и ответы на вопросы.
- [ ] `lab:check --mode submission` (содержательное решение остаётся за проверяющим).

Решение проверяющего: **не проверено**.