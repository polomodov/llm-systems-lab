# LAB15 — Pi: исходный SDK-цикл, события и воспроизводимый T002

Сессия: `local-ryzen`

Создано: 2026-10-12T12:24:43.860Z

Статус: **blocked** после сверки учёта 22.10.2026: исходный протокол регистрирует
одну попытку, предварительного плана продолжений `-5` и 15.10 нет. Пилоты выполнены
через local provider (LAB08, Linux/ROCm); облачный минимум не заявляется. Сохранены
два независимых `fail` 12.10 и `pass` 15.10 с новым admission live-хост↔паспорт
(LAB08, L026). Условия bridge различаются: это группы 2+1, а не сопоставимая тройка.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, даты опытов / сверки | opencode (агент) по заданию polomodov; 2026-10-12 и 2026-10-15 / сверка учёта 2026-10-22 |
| Машина, ОС, kernel, режим питания | Ryzen AI Max+ 395 / 128 GB; Ubuntu 24.04.4; kernel 7.0.0-38; balanced |
| Модель/артефакт: revision, shards, SHA-256, quant | `unsloth/Qwen3.5-9B-GGUF` @ `3885219b…`, `Qwen3.5-9B-Q6_K.gguf` (SHA-256 `91898433…`), Q6_K |
| Engine, backend | llama.cpp b8407, ROCm 7.2.1, gfx1151 (local provider, LAB08) |
| Context, KV, slots, sampling, reasoning | 32768; f16/f16; 1 слот; temp 0, seed 1, top_p 1; reasoning auto, thinking on |
| Harness/provider/version, image | Pi `0.73.1` (`mode=sdk`), provider `local`, image `sha256:1bcc87a8…` |
| Предыдущие отчёты / run IDs | LAB08-ryzen-linux-bridge; все три оценённые записи приведены ниже |
| Отличия от задания и причины | Provider local (LAB08) вместо cloud из-за отсутствия `.env`; timeout 1800 s — объявленная группа для медленной локальной модели |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (2026-10-12T12:24:43Z). Гипотеза: при фиксированных модели, образе
и входе стандартных инструментов Pi достаточно для T002. Отдельно проверяется учёт:
`message_end` даёт usage завершённого assistant message, повтор в `turn_end` не
увеличивает токены; поле `model` в событиях Pi не подтверждает модель ответа
(`observed_id=null` для cloud, здесь `lab-model` как local-алиас).

Исходный протокол сохранён без правок. Продолжения `-5` и 15.10 учтены
ретроспективно; дата исходного протокола не подтверждает их предварительную
регистрацию. Основание `blocked` и происхождение дополнений —
[audit-20261022.md](audit-20261022.md).

## Ход выполнения

| Шаг | Действие | Результат |
| --- | --- | --- |
| 1 | Конфигурация, adapter tests, версии | `raw/git-*.txt`, `node-version.txt`, `docker-version.txt`, `harnesses.txt`, `adapter-tests.txt` (pass) |
| 2 | Сборка и offline smoke образа Pi | `raw/build.txt`, `image-id.txt`, `sdk-smoke.txt` (`Pi SDK … no model call`), `sdk-version.txt` (`0.73.1`) |
| 3 | T002 через local provider 12.10 | `…janitor-4`: 31 ход, 956 s; повтор `…janitor-5`: 31 ход, 889 s; оба exit 0 |
| 4 | Сохранённые независимые hidden-check + judge-run | Оба runs 12.10: `completed/fail` |
| 5 | Разбор трассы и учёта | Исторический `raw/comparison.json` только по run `-4`; события Pi |
| 6 | Follow-up 15.10 с admission host↔passport | `2026-10-15-…janitor`: 28 ходов, 851 s, exit 0; сохранённый hidden-check зелёный — `completed/pass` |
| 7 | Сверка manifest и отчёта 22.10 | Все 3 run IDs связаны с реестром; `comparison-20261022.json` разделяет группы 2+1; отсутствие предварительного плана оставлено как blocked |

## Результаты

| Проверка | План | Наблюдение | Evidence |
| --- | --- | --- | --- |
| Пакет/image ID | Pi 0.73.1 / immutable ID | 0.73.1 / `sha256:1bcc87a8…` | `raw/sdk-version.txt`, `raw/image-id.txt` |
| Native smoke | Session + bash без API | `Pi SDK session and native bash initialized offline; no model call` | `raw/sdk-smoke.txt` |
| Identity | Exact request; observed отдельно | `lab-model` (controlled native process, `/props` + offloaded 33/33) | `raw/judge-check-…`, LAB08 |
| Usage | Только завершённые `message_end` | Метрики каждого run приведены отдельно ниже (primary HTTP usage) | Три run records |
| Ограничение | 30 native turns; 1800 s; USD observed | Runs `-4`/`-5`: `max_turns`, счётчик 31; follow-up 15.10: `stop`, 28 ходов; USD `null` | Три run records |

| Слот | Run ID | Native turns | Tokens in / out | USD | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, local 32K | `2026-10-12-pi-a2-janitor-t002-repo-janitor-4` | 31 | 196202 / 5680 | null (local) | 956 | completed / **fail** |
| T002 baseline repeat, local 32K | `2026-10-12-pi-a2-janitor-t002-repo-janitor-5` | 31 | 197350 / 4006 | null (local) | 889 | completed / **fail** |
| T002 baseline, local 32K, host↔passport gate | `2026-10-15-pi-a2-janitor-t002-repo-janitor` | 28 | 172863 / 5225 | null (local) | 851 | completed / **pass** |

Учёт: входные токены — сумма `input` завершённых `message_end`; `turn_end` не добавляет
вторую копию usage. `observed_id=lab-model` подтверждён controlled native process, а не
полем `model` сообщения. Стоимость `null` с причиной (local, SDK-цены не биллинг).

В `comparison-20261022.json` два runs 12.10 имеют `local_bridge=0148edab…`, follow-up
15.10 — `local_bridge=9e3a6abe…`. В обеих группах `triples=[]`; общий pass@3/pass^3
по этим трём записям не вычисляется.

## Ошибки и ограничения

- Вердикты `fail` (run `-4` и repeat `-5`): агент редактировал `src/slugify.js` и
  `package.json`, но не закоммитил изменения к native cap 30 ходов (в `-4` — `git stash`,
  в `-5` — незакоммиченные правки); clean clone `npm test` красный. Это поведение модели,
  а не отказ SDK; повтор воспроизвёл исход.
- Cloud-маршрут (anthropic/openai) не выполнялся: нет `.env`.
- Два `fail` с одинаковой причиной усиливают, но не доказывают устойчивость поведения.
- Более ранние aborted попытки сохранены в отчёте LAB08 (не переписаны).
- Отдельный предварительный план продолжений `-5` и 15.10 отсутствует. Добавление
  выполненных runs в manifest устраняет неполноту учёта, но не снимает эту блокировку.

## Вывод по гипотезе

**Одна успешная попытка подтверждает возможность решения T002 этим локальным
маршрутом.** Pi 0.73.1 дал `fail` дважды 12.10 и `pass` 15.10 (28 ходов, 851 s,
172 863 входных / 5 225 выходных токенов; clean clone `npm test` зелёный, отчёт сдан).
В follow-up добавлен admission native-стека Linux, сверяющий живой хост с паспортом.
Изменение `local_bridge` разделяет попытки на группы 2+1; устойчивость результата и
эффект admission gate по ним не установлены. Offline-подготовка выполнена, облачный
минимум не заявляется. Комплект остаётся `blocked` из-за отсутствия предварительной
регистрации продолжений; ретроспективная сверка не исправляет методический пробел.

## Ответы на контрольные вопросы

1. **`message_end` vs `turn_end`:** `message_end` — завершённый assistant message с usage;
   `turn_end` повторяет сообщение, не создавая второй оплаченный ответ.
2. **Что ограничивает `agent.abort()`:** abort на границе хода; turns разных систем — не
   одна универсальная метрика.
3. **Почему поля `model` мало:** оно заполняется из конфигурации запроса и не доказывает
   ответ провайдера; для local identity нужен controlled process.
4. **Отключённая compaction:** длинная серия не уплотняется, растёт контекст — что и
   вызвало overflow на 8K.
5. **Почему image ID, а не версия пакета:** транзитивные зависимости фиксирует image ID.
6. **Independent fail vs aborted:** fail — законченный исполненный эпизод с оценкой;
   aborted — прерванное исполнение без вердикта.

## Комплект сдачи

- [x] `manifest.json` заполнен; пропуски снабжены причинами.
- [x] Offline-подготовка и три реальные T002 с независимыми `fail`, `fail`, `pass`; продолжения отмечены как ретроспективные записи.
- [x] Разобран учёт `message_end`; объяснён `observed_id` (local).
- [x] Отчёт, manifest и сохранённые оценки согласованы; актуальная сводка групп — `comparison-20261022.json`.
- [x] `lab:check --mode submission` проходит для оформленного `blocked`; это проверка комплектности, а не зачёт.
- [ ] Полный предварительный план продолжений отсутствует; восстановление задним числом запрещено.

Решение проверяющего: **не проверено**.
