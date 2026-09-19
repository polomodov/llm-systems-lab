#!/usr/bin/env bash
# Воспроизводит стартовое состояние T001 в каталоге $1 (по умолчанию — текущий).
set -euo pipefail
DEST="${1:-.}"
mkdir -p "$DEST"
cat > "$DEST/brief.md" <<'EOF'
# Досье: как источники 2026 года определяют обвязку агента

Дата среза: сегодня. Ответить на три вопроса:
1. Как каждый источник определяет обвязку (harness) и чем она отличается от лесов (scaffold) и фреймворка?
2. Какие числа об эффекте обвязки при фиксированной модели есть в источниках и при каких условиях они получены?
3. Что в источниках противоречит друг другу?
EOF
cat > "$DEST/sources.txt" <<'EOF'
https://code.claude.com/docs/en/glossary  # определение вендора
https://www.langchain.com/blog/the-anatomy-of-an-agent-harness  # Agent = Model + Harness
https://martinfowler.com/articles/harness-engineering.html  # guides vs sensors
https://www.anthropic.com/engineering/harness-design-long-running-apps  # предположения о модели
https://metr.org/notes/2026-02-13-measuring-time-horizon-using-claude-code-and-codex/  # контрсвидетельство
https://modelcontextprotocol.io/specification/2026-07-28/changelog  # stateless MCP
EOF
echo "[T001] workspace ready in $DEST"
