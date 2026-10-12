# LAB15 — Pi: исходный SDK-цикл, события и воспроизводимый T002

Сессия: `local-ryzen`

Создано: 2026-10-12T12:24:43.860Z

Статус: **завершено**. Пилот выполнен через local provider (LAB08, Linux/ROCm), а не
через облачный anthropic/openai: `.env` отсутствовал. Это расширение маршрута ЛР15;
облачный минимум не заявляется. Независимый verdict — `fail`.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата начала/окончания | opencode (агент) по заданию polomodov; 2026-10-12 |
| Машина, ОС, kernel, режим питания | Ryzen AI Max+ 395 / 128 GB; Ubuntu 24.04.4; kernel 7.0.0-38; balanced |
| Модель/артефакт: revision, shards, SHA-256, quant | `unsloth/Qwen3.5-9B-GGUF` @ `3885219b…`, `Qwen3.5-9B-Q6_K.gguf` (SHA-256 `91898433…`), Q6_K |
| Engine, backend | llama.cpp b8407, ROCm 7.2.1, gfx1151 (local provider, LAB08) |
| Context, KV, slots, sampling, reasoning | 32768; f16/f16; 1 слот; temp 0, seed 1, top_p 1; reasoning auto, thinking on |
| Harness/provider/version, image | Pi `0.73.1` (`mode=sdk`), provider `local`, image `sha256:1bcc87a8…` |
| Предыдущие отчёты / run IDs | LAB08-ryzen-linux-bridge; run `2026-10-12-pi-a2-janitor-t002-repo-janitor-4` |
| Отличия от задания и причины | Provider local (LAB08) вместо cloud из-за отсутствия `.env`; timeout 1800 s — объявленная группа для медленной локальной модели |

## Гипотеза и протокол до запуска

См. `raw/protocol.md` (2026-10-12T12:24:43Z). Гипотеза: при фиксированных модели, образе
и входе стандартных инструментов Pi достаточно для T002. Отдельно проверяется учёт:
`message_end` даёт usage завершённого assistant message, повтор в `turn_end` не
увеличивает токены; поле `model` в событиях Pi не подтверждает модель ответа
(`observed_id=null` для cloud, здесь `lab-model` как local-алиас).

## Ход выполнения

| Шаг | Действие | Результат |
| --- | --- | --- |
| 1 | Конфигурация, adapter tests, версии | `raw/git-*.txt`, `node-version.txt`, `docker-version.txt`, `harnesses.txt`, `adapter-tests.txt` (pass) |
| 2 | Сборка и offline smoke образа Pi | `raw/build.txt`, `image-id.txt`, `sdk-smoke.txt` (`Pi SDK … no model call`), `sdk-version.txt` (`0.73.1`) |
| 3 | T002 через local provider | `…janitor-4`: 31 ход, 956 s, exit 0, `awaiting_review` |
| 4 | Независимый hidden-check + judge-run | `completed/fail` |
| 5 | Разбор трассы и учёта | `raw/comparison.json`, события Pi |

## Результаты

| Проверка | План | Наблюдение | Evidence |
| --- | --- | --- | --- |
| Пакет/image ID | Pi 0.73.1 / immutable ID | 0.73.1 / `sha256:1bcc87a8…` | `raw/sdk-version.txt`, `raw/image-id.txt` |
| Native smoke | Session + bash без API | `Pi SDK session and native bash initialized offline; no model call` | `raw/sdk-smoke.txt` |
| Identity | Exact request; observed отдельно | `lab-model` (controlled native process, `/props` + offloaded 33/33) | `raw/judge-check-…`, LAB08 |
| Usage | Только завершённые `message_end` | 196 202 in / 5 680 out (primary HTTP usage) | run record |
| Ограничение | 30 native turns; 1800 s; USD observed | останов на границе 30 ходов (`max_turns`); USD `null` | run record |

| Слот | Run ID | Native turns | Tokens in / out | USD | Wall-clock s | Lifecycle / verdict |
| --- | --- | --- | --- | --- | --- | --- |
| T002 baseline, local 32K | `2026-10-12-pi-a2-janitor-t002-repo-janitor-4` | 31 | 196202 / 5680 | null (local) | 956 | completed / **fail** |
| T002 baseline repeat, local 32K | `2026-10-12-pi-a2-janitor-t002-repo-janitor-5` | 31 | — | null (local) | 889 | completed / **fail** |

Учёт: входные токены — сумма `input` завершённых `message_end`; `turn_end` не добавляет
вторую копию usage. `observed_id=lab-model` подтверждён controlled native process, а не
полем `model` сообщения. Стоимость `null` с причиной (local, SDK-цены не биллинг).

## Ошибки и ограничения

- Вердикты `fail` (run `-4` и repeat `-5`): агент редактировал `src/slugify.js` и
  `package.json`, но не закоммитил изменения к native cap 30 ходов (в `-4` — `git stash`,
  в `-5` — незакоммиченные правки); clean clone `npm test` красный. Это поведение модели,
  а не отказ SDK; повтор воспроизвёл исход.
- Cloud-маршрут (anthropic/openai) не выполнялся: нет `.env`.
- Два `fail` с одинаковой причиной усиливают, но не доказывают устойчивость поведения.
- Более ранние aborted попытки сохранены в отчёте LAB08 (не переписаны).

## Вывод по гипотезе

**Не поддержана в этой попытке.** Исходной конфигурации Pi 0.73.1 оказалось недостаточно
для T002 в пределах 30 native ходов: попытка завершилась независимым `fail`. Исходный
SDK-цикл и учёт подтверждены (сохранённые события, один `lab_pi_result`), но `fail`
опровергает достаточность конфигурации в этой попытке.

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
- [x] Offline-подготовка и одна реальная T002 с независимым `fail`.
- [x] Разобран учёт `message_end`; объяснён `observed_id` (local).
- [x] Отчёт, raw evidence и run record согласованы; `npm run check` проходит.

Решение проверяющего: **не проверено**.
