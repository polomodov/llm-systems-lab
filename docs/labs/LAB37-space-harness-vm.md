# ЛР37. Pi и OpenHands в микро-VM SPACE

> **Заморожено 05.11.2026.** Методичка сохранена как есть, но новые сессии `lab:new` для неё не создаются: ветка SPACE не имеет измерений и реализации и выделяется в отдельный учебный репозиторий. Снятие заморозки требует отдельного решения и записи в [статусе практикума](README.md#заморозка-инфраструктурных-веток).

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылки | [ЛР36](LAB36-space-deploy-smoke.md) на выбранном стенде; [ЛР15](LAB15-pi.md) и [ЛР17](LAB17-openhands.md) хотя бы до offline smoke и одного Docker-пилота T002 |
| Обвязки | `pi` (`@mariozechner/pi-coding-agent@0.73.1`), `openhands` (`openhands-sdk==1.49.2`); образы этого репозитория |
| Изоляция | Firecracker microVM SPACE вместо Docker-контейнера раннера; `sandbox.kind = "vm"` в `run.json` |
| Минимум | Шаблоны SPACE из обоих образов, offline `--smoke` обеих обвязок внутри VM, backend раннера для SPACE, по одной T002 на обвязку с независимым судьёй |
| Расширения | Три повтора на обвязку; T001 replay; агент в VM с локальной моделью на стенде A через мост [ЛР08](LAB08-local-bridge.md) |
| Время | Ориентир 1–2 дня инженерной работы плюс прогоны; agent execution ≤900 s на попытку |
| Готовность | `implementation-required`: в `scripts/run.mjs` сейчас есть только Docker-backend |
| Начальное состояние | Эксперимент `not-run`; учебный manifest — `not-started` |

## Цель

Выполнить тот же эпизод A2/T002, что в ЛР15 и ЛР17, но с изоляцией Firecracker-VM, и записать, какие компоненты пришлось добавить в обвязку и раннер. Сам агент остаётся тем же: шаблон SPACE собирается из того же OCI-образа, который раннер использует в Docker.

## Проверяемая гипотеза

1. Обе обвязки проходят собственный `--smoke` внутри VM SPACE без изменений `experiments/pi/run.mjs` и `experiments/openhands/run.py`.
2. Для реального эпизода достаточно трёх новых компонентов раннера: загрузки запечатанных входов в VM, egress к API выбранного провайдера и выгрузки трассы/workspace. Каждый получает строку в [реестре](../harness-ledger.md).
3. Verdict T002 в VM совпадает с Docker-пилотом той же обвязки и модели; разница wall-clock объясняется временем старта среды.

Пункт 3 на одной попытке не доказывается: это наблюдение, а не сравнение. Сравнение требует повторов (расширение) и правил [ЛР09](LAB09-agent-campaign.md).

## Подготовка

- Стенд с принятой ЛР36 и работающим кластером SPACE. Commit SPACE тот же, что в отчёте ЛР36, или новый с повторённым baseline smoke.
- Собранные образы `harness-lab/pi:0.73.1` и `harness-lab/openhands:1.49.2` и их image ID из ЛР15/ЛР17.
- Прочитайте в SPACE: `docs/native-template-runtime.md`, `templates/firecracker/recipes/oci-python-smoke.toml` (шаблон поверх seed из OCI-образа), `docs/using-api.md`, `docs/egress-profiles.md`, пример LLM-агента `examples/llm_agent.py` (черновой PR polomodov/SPACE#1) как образец command session + SSE.
- Прочитайте здесь: `scripts/run.mjs` (как Docker-backend монтирует `/control`, задаёт сеть, лимиты и собирает трассу), [метод](../method.md), [порядок оценки](harness-workflow.md).

```bash
npm run lab:new -- --lab LAB37 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB37-ryzen-01'
```

Секреты провайдера по-прежнему читаются только из `.env` раннером. Ключ, попавший внутрь VM, — известная граница этой работы; её закрывает [ЛР41](LAB41-space-network-secrets.md).

## Порядок выполнения

1. **Доставка образа в SPACE.** Установите, откуда сборщик шаблонов SPACE берёт OCI-образ в вашей установке (публичный registry, registry на loopback, загрузка в узел Kind). Это `unverified`: запишите проверенный способ и команды. Образ доставляется по digest, а не по тегу.

2. **Рецепты шаблонов.** Создайте `experiments/space/recipes/pi.toml` и `openhands.toml` по образцу `oci-python-smoke.toml`: `from = "oci-image"`, `base = "seed"`, `image = <ref@digest>`, явные `vcpu`, `memory_mib`, `disk_size_mb`. Шаг `run` проверяет версию пакета так же, как `harness.json` (`node -p` для Pi, `importlib.metadata` для OpenHands). Учтите, что OCI `CMD`/`ENTRYPOINT` шаблоном игнорируются. Соберите, опубликуйте, запишите content hash шаблона.

3. **Offline smoke в VM.** Создайте песочницу из каждого шаблона без egress, загрузите `experiments/<harness>/` в `/control` и выполните command session:

   - Pi: `node /control/run.mjs --smoke`
   - OpenHands: `python /control/run.py --smoke`

   Сохраните stdout/stderr и код выхода. Отличия от Docker-smoke (`/tmp noexec`, read-only rootfs, uid 1000 против пользователя `user` uid 2000 в seed) запишите в отчёт: какие из них SPACE воспроизводит, какие нет.

4. **Backend раннера.** Добавьте в `scripts/run.mjs` выбор `--sandbox space` (по умолчанию остаётся Docker). Минимальный контракт:
   - создать песочницу из шаблона, привязанного к image ID профиля; content hash шаблона — в `run.json`;
   - залить запечатанные входы и `/control`, запустить точку входа профиля с теми же аргументами, что в Docker;
   - стримить stdout в `trace/stdout.jsonl`, соблюдать timeout и turn limit из контракта задачи;
   - забрать workspace для судьи, удалить песочницу в `finally`;
   - скрытая проверка выполняется на хосте после выгрузки, в VM не попадает;
   - `sandbox.kind = "vm"`, `sandbox.network` — фактическая политика.

   Добавьте offline-тесты на фейковом SPACE API (как `scripts/tests/test_llm_agent_example.py` в PR SPACE). Каждый компонент — строка ledger в том же изменении.

5. **Egress.** Для реального эпизода VM нужен доступ к API провайдера. Минимум — разрешить только домен провайдера (см. `docs/egress-profiles.md`); если профили не поддержаны в вашей установке, зафиксируйте фактическую сеть VM и отметьте это как ограничение. Полная проверка — ЛР41.

6. **Реальные T002.** По одной попытке на обвязку, тот же provider/model, что в Docker-пилоте:

   ```bash
   npm run new-run -- --harness pi --harness-version 0.73.1 --agent a2-janitor --task T002 \
     --provider anthropic --model "$MODEL_ID"
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   npm run run -- --run "$RUN_ID" --sandbox space --template "$PI_TEMPLATE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   Флаги `--sandbox`/`--template` появляются после шага 4; точный интерфейс фиксируйте по реализации. Затем независимая оценка по [harness-workflow](harness-workflow.md). Аналогично для OpenHands.

7. **Сравнение с Docker-пилотом.** Заполните таблицу: verdict, ходы, токены, cost, wall-clock, время до первой команды агента, время создания/удаления среды.

## Таблицы результатов

**Шаблоны**

| Обвязка | Image ID | Ref@digest | Template content hash | vCPU / MiB / диск | Сборка, s | Код |
| --- | --- | --- | --- | --- | --- | --- |
| pi | | | | | | |
| openhands | | | | | | |

**Offline smoke**

| Обвязка | Среда | Код | Ключевой вывод | Отличия от Docker |
| --- | --- | --- | --- | --- |
| pi | Docker (ЛР15) | | | — |
| pi | SPACE VM | | | |
| openhands | Docker (ЛР17) | | | — |
| openhands | SPACE VM | | | |

**Эпизоды T002**

| Run ID | Обвязка | Среда | Verdict судьи | Ходы | Токены in/out | USD | Wall-clock, s | Старт среды, s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | pi | Docker | | | | | | |
| | pi | SPACE | | | | | | |
| | openhands | Docker | | | | | | |
| | openhands | SPACE | | | | | | |

**Добавленные компоненты** — ссылки на строки ledger.

## Что сдать

- Отчёт, рецепты шаблонов в `experiments/space/recipes/`, изменения раннера с тестами, строки ledger.
- Raw: сборка шаблонов, smoke-логи из VM, `run.json` и трассы обоих эпизодов, verdict судьи.
- Описание способа доставки образа в SPACE с проверенными командами.

## Критерии завершения

- Оба offline smoke в VM имеют сохранённый код выхода и вывод.
- `npm test` и `npm run check` проходят; Docker-backend без флага `--sandbox` работает как раньше.
- Для каждой обвязки есть `run.json` с `sandbox.kind = "vm"` и независимым verdict (любой: pass, fail или partial).
- Скрытые проверки не попадали в VM; это видно из кода backend и трассы.
- Каждый добавленный компонент есть в ledger с условием повторной проверки.

## Контрольные вопросы

1. Какие допущения Docker-backend (`--network none`, `--read-only`, `/tmp noexec`, uid) не переносятся в VM напрямую и что вы сделали с каждым?
2. По каким полям трассы отличить сбой SPACE от сбоя агента?
3. Что теряется, если шаблон собран из тега, а не из digest?
4. Где граница доверия к ключу провайдера в этой схеме и что изменит ЛР41?
5. Какой компонент кажется лишним после прогона и что покажет его удаление?

## Источники

- Этот репозиторий: [ЛР15](LAB15-pi.md), [ЛР17](LAB17-openhands.md), `experiments/pi/README.md`, `experiments/openhands/README.md`, `scripts/run.mjs`, [ledger](../harness-ledger.md).
- SPACE: `docs/native-template-runtime.md`, `templates/firecracker/recipes/oci-python-smoke.toml`, `docs/using-api.md`, `docs/egress-profiles.md`, `examples/first_sandbox.py`.
- SPACE PR #1 (`polomodov/SPACE`): `examples/llm_agent.py` и его офлайн-тесты.
