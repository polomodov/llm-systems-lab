# LAB08 — Изолированное подключение локального сервера (Ryzen/Linux)

Сессия: `ryzen-linux-bridge`

Создано: 2026-10-12T12:36:28.029Z

Статус: **завершено** для выбранного среза Pi/T002/Linux/ROCm. Реализована Linux-ветвь
того же local bridge, что и Apple-вариант; выполнен один реальный T002 с независимой
оценкой (`completed/fail`). Допущены только Pi и T002; остальные обвязки — pending.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | opencode (агент) по заданию polomodov; 2026-10-12 |
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

## Ход выполнения

| Шаг | Действие | Результат |
| --- | --- | --- |
| 1 | Реализована Linux-ветвь `startNative` в `experiments/common/local-runtime.mjs` | Платформенный выбор macos/linux; для Linux — сэмплер `/proc`,`/sys`, `LD_LIBRARY_PATH`, offload/device proof |
| 2 | Генератор `experiments/local-models/build-local-deployment.mjs` | Валидные deployment v1, fingerprint посчитан |
| 3 | `npm test`, `npm run check` | 172 pass / 2 skip; check проходит |
| 4 | Реальные T002 через `run --provider local` | 4 попытки: 3 aborted, 1 completed/fail |
| 5 | Независимый hidden-check и `judge-run` | run `-4`: completed/fail |

## Результаты

| Обвязка | Engine/backend | Artifact/template fingerprint | B01–B10 | Реальный pilot run ID | Verdict | Готовность |
| --- | --- | --- | --- | --- | --- | --- |
| Pi 0.73.1 | llama.cpp b8407 / ROCm | deployment v1 fp `e8f458ae…` (8K), `b9089bbc…` (16K), `…` (32K) | B01–B10 + B11 (`raw/test-run.txt`) | `2026-10-12-pi-a2-janitor-t002-repo-janitor-4` | fail | Pi ready; остальные pending |

Run IDs:

| Слот | Context/timeout | Run ID | Статус | Verdict |
| --- | --- | --- | --- | --- |
| pilot | 8192 / 900 s | `…janitor` | aborted | — (8195>8192) |
| pilot | 16384 / 900 s | `…janitor-2` | aborted | — (EADDRINUSE до старта) |
| pilot | 16384 / 900 s | `…janitor-3` | aborted | — (timeout) |
| pilot (группа 1800 s) | 32768 / 1800 s | `…janitor-4` | completed | **fail** |
| pilot repeat (группа 1800 s) | 32768 / 1800 s | `…janitor-5` | completed | **fail** (31 ход, 889 s) |

Native identity: `/props` совпал с sealed deployment (`model_alias=lab-model`, `n_ctx`,
`build_info=b8407-312cf0332`, chat template SHA `7f0e5290…`), лог `offloaded 33/33 layers
to GPU`, device `ROCm0`. Tokens: 196 202 in / 5 680 out (из primary HTTP usage). USD
`null` (local; SDK-цены не биллинг).

## Ошибки и ограничения

- 8192 оказалось мало: агент превысил контекст на 3 токена; 16384 замедлил prefill и не
  уложилось в 900 s; группа 32768/1800 s дошла до native cap 30 ходов.
- run `-2` израсходован технической ошибкой (остаток native-порта прошлого прогона,
  `EADDRINUSE` до старта агента) — не переписан.
- В run `-4` модель сделала `git stash` и не закоммитила изменения до лимита ходов,
  поэтому clean clone `npm test` красный (hidden-check: `✖ npm test red`) — это
  поведение модели, а не отказ bridge.
- B01–B10 покрыты существующими broker-тестами; для Linux-ветви добавлен B11 на
  сэмплер, но отдельная native-матрица B01–B10 на Linux как серия не выполнялась.
- Apple/Metal код не менялся и не перепроверялся в этой сессии.

## Вывод по гипотезе

**Поддержана.** Linux/ROCm-ветвь local bridge работает end-to-end: изоляция сохранена,
identity подтверждена controlled native process, агент Pi выполнил штатный цикл
инструментов. Один реальный T002 получил независимый `fail`; вклад bridge в качество
агента не заявляется (для этого нужны серии до/после).

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
- [x] `planned_attempts` включают все 4 попытки (failed/not-run/completed).
- [x] Сохранены deployment, protocol, test-run, judge-check, evaluation, comparison.
- [x] Указаны run IDs; записи в `results/runs/`.
- [x] Вывод, ограничения и ответы на вопросы заполнены.
- [x] `lab:check --mode submission` и `npm run check` проходят.

Решение проверяющего: **не проверено**.
