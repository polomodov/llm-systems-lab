# OpenCode

Статус на машине: установлена, 1.18.29 (`opencode --version`). Обновить: `brew upgrade opencode`.

## Конфигурация
- `opencode.json` — провайдер и модель (та же, что в прогоне Claude Code, ради правила одной модели), права: запрет чтения `tasks/*/check/` (строка L002), запрет деструктивных команд.
- Читает `AGENTS.md` из корня.

## Запуск A1 на T001
```bash
npm run new-run -- --harness opencode --agent a1-dossier --task T001
RUN=results/runs/<run-id>
bash tasks/T001-dossier-from-sources/setup.sh $RUN/workspace
cp experiments/opencode/opencode.json $RUN/workspace/
cd $RUN/workspace
opencode run --model <provider/model> "$(cat ../../../../agents/a1-dossier/spec.md) --- Задача: $(cat brief.md). Источники в sources.txt. Результаты писать в ../artifacts/."
```
Экспорт сессии: `opencode session export` (проверить точное имя команды в `opencode --help`), положить в `trace/`.

## Что проверить
- Реализуется ли запрет `check/` правами или только инструкцией (если только инструкцией — это слово, а не стена; записать в реестр как «не подтверждена»).
- Совпадает ли результат с Claude Code при одной модели — первая точка для схемы «эффект обвязки против силы модели».


## Заметки

См. `NOTES.md` — что пришлось добавить словами, что стенами, что обвязка дала сама, что мешало. Каждая добавленная компонента — строка в `docs/harness-ledger.md`.
