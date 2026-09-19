# Claude Code + Claude Agent SDK

Статус на машине: установлена, 2.1.83 (`claude --version`). Обновить: `brew upgrade claude` или `npm i -g @anthropic-ai/claude-code`.

## Конфигурация
- `settings.example.json` — права и хуки: запрет чтения `tasks/*/check/` через `PreToolUse` (стена, строка L001 реестра), запрет сетевых команд кроме `curl`/`wget` по allow-list, песочница включена.
- `CLAUDE.md` в корне репозитория импортирует `AGENTS.md` (`@AGENTS.md`).
- Навыки и субагенты — не добавлять до первого прогона без них (абляция по методу).

## Запуск A1 на T001 (первый прогон)
```bash
npm run new-run -- --harness claude-code --agent a1-dossier --task T001
RUN=results/runs/<run-id>
bash tasks/T001-dossier-from-sources/setup.sh $RUN/workspace
cp experiments/claude-code/settings.example.json $RUN/workspace/.claude/settings.json 2>/dev/null || (mkdir -p $RUN/workspace/.claude && cp experiments/claude-code/settings.example.json $RUN/workspace/.claude/settings.json)
cd $RUN/workspace
claude -p "$(cat ../../../../agents/a1-dossier/spec.md) --- Задача: $(cat brief.md). Источники в sources.txt. Результаты писать в ../artifacts/." \
  --permission-mode acceptEdits --max-turns 40 --output-format json > ../trace/session.json
```
После прогона: заполнить `run.json` из `session.json` (модель, ходы, стоимость, причина остановки), запустить скрытую проверку `bash tasks/T001-dossier-from-sources/check/check.sh $RUN`, записать вердикт.

Через SDK (для автономного цикла без терминала): `experiments/claude-code/agents/a1-dossier/run.mjs` — заготовка на `@anthropic-ai/claude-agent-sdk` с `maxTurns`, `maxBudgetUsd` и тем же набором хуков; добавить после первого CLI-прогона.

## Что проверить в этой обвязке (ячейки матрицы)
- Сколько запросов на подтверждение видит прогон в `acceptEdits` против `auto`.
- Срабатывает ли хук на `check/` при чтении через `Bash cat`, а не только через `Read`.
- Что происходит при уплотнении на длинном T001: перечитываются ли `brief.md` и `sources.txt`.


## Заметки

См. `NOTES.md` — что пришлось добавить словами, что стенами, что обвязка дала сама, что мешало. Каждая добавленная компонента — строка в `docs/harness-ledger.md`.
