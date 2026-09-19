#!/usr/bin/env bash
# Использование: setup.sh <dest> <harness>
set -euo pipefail
DEST="${1:?dest}"; H="${2:?harness}"
mkdir -p "$DEST"
cp -R "$(dirname "$0")/../../experiments/$H/." "$DEST/"
cp "$(dirname "$0")/../../docs/harness-ledger.md" "$DEST/ledger-template.md"
printf '# Аудит обвязки %s\nМодель: указать в run.json. Форма реестра — ledger-template.md.\n' "$H" > "$DEST/brief.md"
echo "[T003] workspace ready in $DEST for $H"
