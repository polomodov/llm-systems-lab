# T001 · Досье из шести источников об обвязках

## Стартовое состояние
`setup.sh` кладёт в рабочий каталог `brief.md` и `sources.txt` с шестью ссылками: документация Claude Code (глоссарий), пост LangChain «The Anatomy of an Agent Harness», статья Böckeler на martinfowler.com, пост Anthropic «Harness design for long-running application development», заметка METR «Measuring time horizon using Claude Code and Codex», changelog MCP 2026-07-28.

## Контракт
Агент A1 по своей спецификации создаёт `artifacts/dossier.md` и `artifacts/sources.json`. Досье отвечает на три вопроса из `brief.md`: как источники определяют обвязку; какие числа об эффекте обвязки в них есть и с какими условиями; что в них противоречит друг другу.

## Видимая часть проверки
- `sources.json` покрывает все шесть ссылок.
- В досье нет числа без источника с `fetched: true`.
- Есть раздел «Противоречия» хотя бы с одним пунктом.

## Бюджет
До 40 ходов или $3 стоимости, что раньше. Один прогон на первый заход; три — при повторе.
