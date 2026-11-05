#!/usr/bin/env bash
# Скрытая проверка T005. Использование: check.sh <run-dir>
# Код выхода: 0 — pass, 2 — partial, 1 — fail. Последняя строка вывода: verdict: <pass|partial|fail>.
set -euo pipefail
RUN="${1:?run dir}"
HERE="$(cd "$(dirname "$0")" && pwd -P)"
DATA="$RUN/workspace/data"
A="$RUN/artifacts"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "✖ $1"; echo "verdict: fail"; exit 1; }
[ -d "$DATA" ] || fail "no workspace/data"
# Исходные данные не должны быть изменены агентом.
for f in orders_a.csv orders_b.tsv orders_c.json; do
  bash "$HERE/../setup.sh" "$TMP/pristine" >/dev/null 2>&1 || true
  cmp -s "$DATA/$f" "$TMP/pristine/data/$f" || fail "data/$f was modified"
done
echo "✔ data untouched"
node "$HERE/reference.mjs" "$DATA" > "$TMP/expected.json" || fail "reference failed"
[ -s "$A/normalized.json" ] || fail "artifacts/normalized.json missing or empty"
result=$(node "$HERE/compare.mjs" "$TMP/expected.json" "$A/normalized.json")
echo "• $result"
records_ok=0; rejected_ok=0
[[ "$result" == *"records=ok"* ]] && records_ok=1
[[ "$result" == *"rejected=ok"* ]] && rejected_ok=1
report_ok=1
[ -s "$A/report.md" ] || { echo "✖ artifacts/report.md missing or empty"; report_ok=0; }
if [ "$report_ok" -eq 1 ]; then
  for id in $(node -e 'console.log(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).rejected.map(r=>r.id).join(" "))' "$TMP/expected.json"); do
    grep -q "$id" "$A/report.md" || { echo "✖ report misses rejected id: $id"; report_ok=0; }
  done
  for f in orders_a orders_b orders_c; do
    grep -q "$f" "$A/report.md" || { echo "✖ report misses per-file section: $f"; report_ok=0; }
  done
fi
[ "$report_ok" -eq 1 ] && echo "✔ report lists all rejections and files"
if [ "$records_ok" -eq 1 ] && [ "$rejected_ok" -eq 1 ] && [ "$report_ok" -eq 1 ]; then
  echo "✔ T005 passed"; echo "verdict: pass"; exit 0
fi
if [ "$records_ok" -eq 1 ]; then
  echo "• T005 partial: records ok, rejected ok=$rejected_ok, report ok=$report_ok"; echo "verdict: partial"; exit 2
fi
echo "✖ T005 failed: records differ"; echo "verdict: fail"; exit 1
