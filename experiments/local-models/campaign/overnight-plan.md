# Ночная кампания: LAB03 + LAB04 + LAB05 для других моделей

Окно: ~12–14 часов (ночной прогон). Стенд: Ryzen AI Max+ 395 / gfx1151 / 124 GiB.
Запуск: `overnight.py` (ветка `overnight-models-20261008`, worktree `/tmp/opencode/overnight-wt-20261008-154949`).

## Правило работы

Каждая модель получает **три preregistered-сессии** (LAB03 → LAB04 → LAB05):
протокол и план коммитятся ДО запусков отдельным коммитом, затем измерения, затем
коммит с результатами. Сбой одной работы не останавливает кампанию: статус пишется в
`overnight-<run>-status.json`, причина — в отчёте соответствующей сессии.

## Очередь (по возрастанию размера, чтобы успеть максимум)

| # | Модель | Quant | Веса | LAB03 | LAB04 | LAB05 |
| --- | --- | --- | ---: | --- | --- | --- |
| 1 | gpt-oss-20b | MXFP4 | 11.3 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 2 | qwen36-27b | Q5_K_M | 18.2 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 3 | gemma4-31b-it | Q5_K_M | 20.2 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 4 | qwen3-coder-30b-a3b | Q5_K_M | 20.3 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 5 | qwen35-35b-a3b | Q5_K_M | 24.5 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 6 | glm-47-flash | Q8_0 | 29.7 GiB | verify | Vulkan/HIP | 8/16/32K+tools |
| 7 | qwen3-coder-next (4 shard) | Q5_K_M | 52.9 GiB | verify | Vulkan/HIP | 8/16/32K+tools |

Суммарно ~177 GiB загрузок (диск: ~1.5 TB свободно). Условные гиганты
(qwen35-122b-a10b, glm-45-air) и LAB06 в эту ночь не входят.

## Оценка времени

- Загрузки: при ~20 MB/s ≈ 2.5 ч на 177 GiB.
- LAB03: ~1 мин после загрузки.
- LAB04: offload-proof + warmup + 3×2 бенча ≈ 10–20 мин на модель.
- LAB05: 3 контекста × (bench-заполнение + сервер + 4×2 HTTP-кейса) ≈ 40–90 мин.
- Итого ≈ 9–13 ч; при отставании модели 6–7 могут не завершиться — это отражено в статусе.

## LAB06

Не входит: требует native BF16 checkpoint и поддержки vLLM/SGLang конкретной архитектуры.
Отдельная кампания после проверки совместимости.

## Ограничения

- Автоматическая кампания использует дефолтный sampling/`--jinja`; model-specific
  reasoning и tool-parser настраиваются вручную в дневных сессиях. Плохой parser —
  не приговор модели.
- GLM-4.7-Flash (MLA), gemma4 (sliding/global) требуют отдельного отчёта runtime о cache.
- Один backend для LAB05 (HIP), как в предыдущих сессиях.

## Мониторинг

```sh
tail -f experiments/local-models/campaign/overnight-<run>.log
cat experiments/local-models/campaign/overnight-<run>-status.json
git -C /tmp/opencode/overnight-wt-<run> log --oneline
du -sh "$HOME/local-model-lab-artifacts"
```

## Утро

Ветка `overnight-models-20261008` пушится автоматически; PR не создаётся —
после просмотра отчётов и `lab:check` оформить один PR на кампанию или по модели.
