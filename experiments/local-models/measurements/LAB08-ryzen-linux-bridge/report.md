# LAB08 — Изолированное подключение локального сервера (Ryzen/Linux)

Сессия: `ryzen-linux-bridge`

Создано: 2026-10-12T12:36:28.029Z

Статус: **blocked** после сверки учёта 22.10.2026: в исходном протоколе нет
предварительной регистрации повтора `-5` и follow-up 15.10. Linux-ветвь local bridge
реализована; сохранены шесть записей T002 — три `aborted`, два `completed/fail` и
один `completed/pass`. Два `fail` и `pass` относятся к разным условиям bridge, а не
к одной сопоставимой тройке. Допущены только Pi и T002; остальные обвязки — pending.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, даты опытов / сверки | opencode (агент) по заданию polomodov; 2026-10-12 и 2026-10-15 / сверка учёта 2026-10-22 |
| Машина, ОС, kernel, режим питания | Ryzen AI Max+ 395 / 128 GB; Ubuntu 24.04.4; kernel 7.0.0-38-generic; power profile balanced; power_mode 0 |
| Модель/артефакт: revision, shards, SHA-256, quant | `unsloth/Qwen3.5-9B-GGUF` @ `3885219b…`; один shard `Qwen3.5-9B-Q6_K.gguf` 7 458 301 152 B, SHA-256 `91898433…`; Q6_K (mixed Q6_K/Q8_0/F32) |
| Engine, backend, image/binary hash | llama.cpp `b8407` (commit `312cf033…`), backend ROCm 7.2.1, gfx1151; executable + 50 lib-файлов запечатаны в deployment |
| Context, KV/state dtype, slots, sampling, reasoning | 8192 / 16384 / 32768; KV f16/f16; slots 1; temp 0, seed 1, top_p 1; reasoning auto, thinking on; batch 512, ubatch 256, threads 8, offload 999 |
| Harness/provider/version | Pi `0.73.1` (`mode=sdk`), provider `local`, alias `lab-model`; image `sha256:1bcc87a8…` |
| Предыдущие отчёты / run IDs | Apple-ветвь: LAB08-apple-provider-bridge-20261009; Linux и run IDs — ниже |
| Отличия от задания и причины | Linux-ветвь добавлена как реализация недостающего adapter'а; Apple-часть не менялась |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (записан 2026-10-12T12:36:28Z, до первого запуска). Гипотеза:
Linux/ROCm-ветвь того же изолированного bridge применима к Ryzen, identity весов,
template и backend подтверждается до/после старта, а существенные смены условий
различаются fingerprint. Критерий опровержения: доступ к другому адресу/порту/admin/
cloud, потерянный tool-result, две конфигурации в одной группе, absent usage = 0.

Протокол сохранён без правок. Он перечисляет runs до `-4`; повтор `-5` и follow-up
15.10 внесены в реестр исполнения ретроспективно. `protocol_recorded_at` не
подтверждает предварительную регистрацию этих продолжений. Основание статуса
`blocked` и происхождение дополнений — [audit-20261022.md](audit-20261022.md).

## Ход выполнения

| Шаг | Действие | Результат |
| --- | --- | --- |
| 1 | Реализована Linux-ветвь `startNative` в `experiments/common/local-runtime.mjs` | Платформенный выбор macos/linux; для Linux — сэмплер `/proc`,`/sys`, `LD_LIBRARY_PATH`, offload/device proof |
| 2 | Генератор `experiments/local-models/build-local-deployment.mjs` | Валидные deployment v1, fingerprint посчитан |
| 3 | `npm test`, `npm run check` | 172 pass / 2 skip; check проходит |
| 4 | Попытки T002 12.10 через `run --provider local` | 5 записей: 3 aborted, 2 completed/fail; одна aborted до старта агента |
| 5 | Сохранённые независимые hidden-check и `judge-run` | runs `-4` и `-5`: completed/fail |
| 6 | Follow-up 15.10 с admission host↔passport | `2026-10-15-…janitor`: completed/pass, 28 ходов, 851 s |
| 7 | Сверка manifest и отчёта 22.10 | Все 6 run IDs связаны с реестром; отсутствие предварительного плана продолжений сохранено как blocked |

## Результаты

| Обвязка | Engine/backend | Artifact/template fingerprint | B01–B10 | Реальный pilot run ID | Verdict | Готовность |
| --- | --- | --- | --- | --- | --- | --- |
| Pi 0.73.1, bridge 12.10 | llama.cpp b8407 / ROCm | deployment fp `d333cabc…` (32K), local_bridge `0148edab…` | B01–B10 + B11 (`raw/test-run.txt`) | `2026-10-12-pi-a2-janitor-t002-repo-janitor-4`, `…janitor-5` | fail, fail | Условия 12.10; полная native-матрица не выполнена |
| Pi 0.73.1, bridge 15.10 | llama.cpp b8407 / ROCm | deployment fp `d333cabc…` (32K), local_bridge `9e3a6abe…` | Существующий follow-up подтверждает admission host↔passport | `2026-10-15-pi-a2-janitor-t002-repo-janitor` | pass | Отдельные условия; предварительный план не найден |

Run IDs:

| Слот | Context/timeout | Run ID | Статус | Verdict |
| --- | --- | --- | --- | --- |
| pilot | 8192 / 900 s | `…janitor` | aborted | — (8195>8192) |
| pilot | 16384 / 900 s | `…janitor-2` | aborted | — (EADDRINUSE до старта) |
| pilot | 16384 / 900 s | `…janitor-3` | aborted | — (timeout) |
| pilot (группа 1800 s) | 32768 / 1800 s | `…janitor-4` | completed | **fail** |
| pilot repeat (группа 1800 s) | 32768 / 1800 s | `…janitor-5` | completed | **fail** (31 ход, 889 s) |
| follow-up (отдельная группа bridge, host↔passport gate) | 32768 / 1800 s | `2026-10-15-pi-a2-janitor-t002-repo-janitor` | completed | **pass** (28 ходов, 851 s, `report.md` сдан) |

`comparison-20261022.json` разделяет оценённые runs на группы 2+1 по `local_bridge`;
в обеих `triples=[]`. Исторический `raw/comparison.json` содержит только run `-4`
и оставлен без изменений. Реестр из шести записей не является серией шести
сопоставимых выполненных запусков: одна попытка прервана до исполнения.

Admission Linux host↔passport: run `2026-10-15-…janitor` прошёл новый gate — `startNative` сверил
живой хост с запечатанным паспортом и записал `host_identity` в trace: kernel `7.0.0-38-generic`,
OS `Ubuntu 24.04.4 LTS`, CPU `AMD RYZEN AI MAX+ 395 w/ Radeon 8060S`, MemTotal 134153789440 B
(≈ паспорт, расхождение 0.0003%), устройства `/dev/kfd` и `/dev/dri/renderD128` присутствуют.
Этот же run — первый `completed/pass` Pi/T002 на локальном провайдере (clean clone `npm test`
зелёный, отчёт сдан).

Native identity: `/props` совпал с sealed deployment (`model_alias=lab-model`, `n_ctx`,
`build_info=b8407-312cf0332`, chat template SHA `7f0e5290…`), лог `offloaded 33/33 layers
to GPU`, device `ROCm0`. Tokens из primary HTTP usage: run `-4` — 196 202 in / 5 680
out; run `-5` — 197 350 / 4 006; follow-up 15.10 — 172 863 / 5 225. USD у всех трёх
`null` (local; SDK-цены не биллинг).

## Ошибки и ограничения

- 8192 оказалось мало: агент превысил контекст на 3 токена; 16384 замедлил prefill и не
  уложилось в 900 s; два runs 12.10 с 32768/1800 s дошли до native cap 30 ходов.
- run `-2` израсходован технической ошибкой (остаток native-порта прошлого прогона,
  `EADDRINUSE` до старта агента) — не переписан.
- В run `-4` модель сделала `git stash` и не закоммитила изменения до лимита ходов,
  поэтому clean clone `npm test` красный (hidden-check: `✖ npm test red`) — это
  поведение модели, а не отказ bridge.
- B01–B10 покрыты существующими broker-тестами; для Linux-ветви добавлен B11 на
  сэмплер, но отдельная native-матрица B01–B10 на Linux как серия не выполнялась.
- Apple/Metal код не менялся и не перепроверялся в этой сессии.
- Отсутствие предварительного плана продолжений `-5` и 15.10 нельзя исправить
  задним числом. Комплект оформлен как `blocked`; состоявшиеся оценки сохранены.

## Вывод по гипотезе

**Наблюдения поддерживают работоспособность узкого маршрута Pi/T002/Linux/ROCm.**
Сохранены два независимых `fail` 12.10 и `pass` 15.10; в последнем агент завершил
задачу за 28 ходов и 851 s. Изменение bridge делит результаты на группы 2+1, поэтому
они не доказывают ни устойчивость успеха, ни вклад admission gate в качество агента.
Методическое завершение комплекта заблокировано отсутствием предварительной
регистрации продолжений; полный допуск остальных обвязок и native-матрица Linux
не заявляются.

## Ответы на контрольные вопросы

1. **Почему разрешить `192.168.0.0/16` недостаточно?** Брокер всё равно позволил бы
   выбирать target/LAN/admin; безопасность даёт единственный закреплённый endpoint, а
   не широкий CIDR.
2. **Чем alias отличается от весов/template?** `/models` с тем же alias не доказывает
   веса; identity доказывают sealed deployment и pre/post-проверка процесса.
3. **Почему серверу нельзя 2 GiB лимит контейнера?** Он держит веса и KV вне task
   container; 2 GiB относятся только к agent, иначе OOM/подмена условий.
4. **Что разделяет группы при Vulkan→ROCm?** Поля `engine.backend`/fingerprint в условиях
   compare.
5. **Что доказывает synthetic tool round-trip?** Сохранение tool-call→result→final; не
   доказывает качество решения задачи.
6. **Когда inference fee = 0?** Только при подтверждённом local-only пути без внешнего
   API; электричество и амортизация считаются отдельно (здесь USD `null`).

## Комплект сдачи

- [x] `manifest.json` заполнен; пропуски снабжены причинами.
- [x] `planned_attempts` включает все 6 run records (failed/not-run/completed) и инженерное упражнение; ретроспективные дополнения обозначены.
- [x] Сохранены deployment, исходный protocol, test-run, judge-check, evaluation и исторический comparison; актуальная сводка — `comparison-20261022.json`.
- [x] Указаны run IDs; записи в `results/runs/`.
- [x] Вывод, ограничения и ответы на вопросы заполнены.
- [x] `lab:check --mode submission` проходит для оформленного `blocked`; это проверка комплектности, а не зачёт.
- [ ] Полный предварительный план продолжений отсутствует; восстановление задним числом запрещено.

Решение проверяющего: **не проверено**.
