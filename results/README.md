# Записи прогонов

Одна папка на прогон: `results/runs/<YYYY-MM-DD>-<harness>-<agent>-<task>[-<n>]/`.

- `run.json` — запись по `results/schema.json`. Обязательна.
- `workspace/` — рабочий каталог агента (в `.gitignore`).
- `trace/` — журнал сессии, который отдаёт обвязка, если отдаёт.
- `artifacts/` — то, что агент произвёл по контракту задачи (досье, патч, реестр).

`npm run new-run -- --harness <name> --agent <code> --task <id>` создаёт папку и заготовку `run.json`. `npm run check` проверяет все записи по схеме и сверяет ссылки на строки реестра.
