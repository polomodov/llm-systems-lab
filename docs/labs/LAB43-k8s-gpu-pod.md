# ЛР43. GPU в pod: k3s и AMD device plugin на gfx1151

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылка | [ЛР02](LAB02-hardware.md) (паспорт Ryzen, `gfx1151` виден ROCm) и [ЛР05](LAB05-context-tools.md) (рабочий llama.cpp server, контрольный GGUF и HTTP-драйвер) |
| Стенд | A: Ryzen AI Max+ 395 / 128 GB / Linux, одноузловой k3s |
| Минимум | Установка k3s, AMD device plugin, `amd.com/gpu` в `allocatable` (или задокументированный отказ), pod с `rocminfo`, llama.cpp server как Deployment, сравнение скорости с запуском вне Kubernetes |
| Расширения | AMD GPU Operator вместо отдельного device plugin; Node Feature Discovery и метки узла; Vulkan-сборка llama.cpp в pod |
| Время | Ориентир 3–5 часов |
| Готовность | `target-machine`; поддержка APU `gfx1151` в AMD device plugin `unverified` |
| Начальное состояние | Учебный manifest — `not-started` |

## Цель

Пройти всю цепочку, по которой GPU попадает в контейнер под Kubernetes: kernel driver `amdgpu` → ROCm в user space → container runtime → device plugin → extended resource → планировщик → pod. Убедиться, что Kubernetes не добавляет накладных расходов к инференсу, и записать, что пришлось добавить к обычному Deployment.

## Проверяемая гипотеза

AMD device plugin регистрирует на узле ровно один `amd.com/gpu`, pod с запросом `amd.com/gpu: 1` видит `gfx1151` без `privileged: true`, а llama.cpp server в pod показывает prompt processing и token generation в пределах ±5% от baseline ЛР05 на том же GGUF, backend и параметрах.

Опровержение — плагин не находит устройство, pod видит GPU только в привилегированном режиме, либо скорость отличается больше чем на 5% при повторах. Порог фиксируется в протоколе до замера.

## Подготовка

- Прочитайте: документацию k3s по установке и containerd, [AMD GPU Device Plugin for Kubernetes](https://instinct.docs.amd.com/projects/k8s-device-plugin/en/latest/), раздел про device plugins и extended resources в документации Kubernetes.
- Документация AMD требует «ROCm-capable AMD GPU» и ориентирована на Instinct. Работа с APU — предмет проверки, а не известный факт.
- Не совмещайте с сериями ЛР04–07 и с развёрнутым SPACE (ЛР36): k3s и Kind конкурируют за память, iptables/nft и GPU.
- Закрепите версии k3s, device plugin и образа llama.cpp по digest. Образ llama.cpp собирается из того же commit и с той же backend, что baseline ЛР05.

```bash
npm run lab:new -- --lab LAB43 --session ryzen-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB43-ryzen-01'
```

## Порядок выполнения

1. **Состояние хоста.** Сохраните в `raw/` `uname -r`, `rocminfo`, `ls -l /dev/kfd /dev/dri`, группы пользователя. Сверьте с паспортом ЛР02: если что-то изменилось, сначала обновите паспорт.
2. **k3s.** Установите закреплённую версию, сохраните `kubectl version`, `kubectl get nodes -o wide`, конфигурацию containerd. Манифесты кладите в `experiments/k8s-gpu/manifests/LAB43/`.
3. **Device plugin.** Разверните AMD device plugin DaemonSet. Сохраните его логи и `kubectl get node -o jsonpath='{.status.allocatable}'`. Если `amd.com/gpu` не появился, найдите причину по логам (не видит `/dev/kfd`, не распознаёт ASIC, нет прав) и запишите её; затем переходите к запасному пути из шага 5.
4. **Проба в pod.** Pod с запросом `amd.com/gpu: 1` и образом ROCm запускает `rocminfo` и маленький HIP-тест или `python -c` с `torch.cuda.get_device_properties(0)`. В выводе должен быть `gfx1151`. Сохраните manifest, вывод и `kubectl describe pod`.
5. **Запасной путь.** Только если шаг 3 провалился: pod с `hostPath` на `/dev/kfd` и `/dev/dri` и минимально необходимыми правами. Запишите, какие права понадобились, и почему это хуже device plugin (планировщик не знает о GPU, нет учёта).
6. **Сервер инференса.** Deployment с llama.cpp server, контрольным GGUF через `hostPath` read-only (хэш сверяется с ЛР03), Service типа ClusterIP, readiness probe на `/health`. Проверка тем же HTTP-драйвером ЛР05.
7. **Сравнение скорости.** Не меньше 5 повторов `llama-bench` или серверного прогона ЛР05 внутри pod и столько же на хосте в том же сеансе, порядок чередуется. Пиши PP и TG в `measurements.tsv`, одна строка — одна попытка.
8. **Teardown.** `k3s-uninstall.sh`, проверка, что сервисы k3s остановлены и правила iptables/nft очищены. Запишите, что осталось на диске.

## Таблицы результатов

| Слой | Что проверили | Результат | Evidence |
| --- | --- | --- | --- |
| Driver / ROCm на хосте | | | |
| Device plugin: `amd.com/gpu` в allocatable | | | |
| Pod видит `gfx1151` без privileged | | | |
| Запасной путь (если понадобился) | | | |
| llama.cpp server: health и HTTP-драйвер | | | |

| Среда | N | PP медиана, tok/s | TG медиана, tok/s | Разброс | Отличие от хоста |
| --- | --- | --- | --- | --- | --- |
| Хост | | | | | — |
| Pod | | | | | |

| Что добавлено к обычному Deployment | Зачем | Можно ли убрать |
| --- | --- | --- |
| | | |

## Что сдать

- Отчёт, манифесты в `experiments/k8s-gpu/manifests/LAB43/`, логи device plugin, вывод проб из pod, сырые замеры обеих сред.
- Версии k3s, device plugin, образов по digest; хэш GGUF.

## Критерии завершения

- Цепочка от драйвера до pod пройдена либо точно указан слой, на котором она оборвалась, с логом.
- Гипотеза о накладных расходах принята или отвергнута по сырым замерам не меньше чем 5 повторов в каждой среде.
- Кластер удалён, остатки на хосте перечислены.

## Контрольные вопросы

1. Чем extended resource `amd.com/gpu` отличается от CPU и памяти с точки зрения планировщика? Почему его нельзя запросить дробно?
2. Нода показывает GPU, а pod его не видит. По каким слоям вы пройдёте и какие команды выполните на каждом?
3. Что теряется, если отдать GPU в pod через `hostPath` вместо device plugin?
4. Почему для unified memory APU `allocatable` ничего не говорит о доступной модели памяти и где это ограничение живёт на самом деле?

## Источники

- [AMD GPU Device Plugin for Kubernetes](https://instinct.docs.amd.com/projects/k8s-device-plugin/en/latest/), репозиторий `ROCm/k8s-device-plugin`.
- Документация Kubernetes: Device Plugins, Extended Resources; документация k3s.
- Этот репозиторий: [ЛР02](LAB02-hardware.md), [ЛР05](LAB05-context-tools.md), [протокол](../method.md).
