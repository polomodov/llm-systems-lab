# Протокол ЛР03 для qwen36-35b-a3b (записано до загрузки)

**Дата:** 2026-10-02T09:17:00Z

## Цель

Скачать и проверить GGUF `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf` из
`unsloth/Qwen3.6-35B-A3B-GGUF@a483e9e6cbd595906af30beda3187c2663a1118c`
и зафиксировать его для последующих лабораторных ЛР04/ЛР05.

## Изменяемый фактор

- Способ загрузки: первая попытка — `python3 fetch_artifact.py … --download`
  (как предписано шагом 4 ЛР03). Этот путь не возобновляется из-за
  `partial.open('xb')`, поэтому замена — `curl --continue-at -` в целевой путь
  с последующей сверкой тем же `fetch_artifact.py` без `--download`.

## Неизменные условия

- Каталог артефактов: `experiments/local-models/models.json` от 2026-09-20.
- Hardware budget: `LAB02-after-rocm` (vulkan_heap1_budget 65.99 GiB как
  ограничивающий фактор, MemTotal - OS_reserve 108.94 GiB).
- Хранилище весов: `$HOME/local-model-lab-artifacts`.
- Скрипт верификации: `fetch_artifact.py` из ЛР03, без модификаций.

## Минимальное число попыток

- 1 успешная проверка bytes и SHA-256 со status `verified`.

## Порядок запусков

1. Сохранить версии `git rev-parse HEAD`, `python3 --version`, `df -B1`.
2. `local-plan.mjs` для всех 12 кандидатов и точечные планы для
   `qwen36-35b-a3b` при 8K / 16K / 32K.
3. Извлечь `artifact.json` для `qwen36-35b-a3b`.
4. Скачать через `fetch_artifact.py --download`; при прерывании без полного
   файла удалить `.part`, докачать `curl --continue-at -` в целевой путь.
6. Перезапустить `fetch_artifact.py` без `--download` для свери bytes/SHA-256.
7. Сгенерировать `weights.sha256` и выполнить `sha256sum --check`.
8. Сохранить хеши входных файлов.

## Критерий остановки

- `fetch_artifact.py` печатает `status: verified`, exit 0, hash совпадает с
  publisher metadata; `sha256sum --check` печатает `…: OK`.

## Правило принятия решения

- **Поддержана**, если все три условия выше выполнены и плановый pre-flight
  против `LAB02-after-rocm` budget проходит при всех трёх контекстах.