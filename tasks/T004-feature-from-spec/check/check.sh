#!/usr/bin/env bash
# Скрытая проверка T004. Использование: check.sh <run-dir>
# Код выхода: 0 — pass, 2 — partial, 1 — fail. Последняя строка вывода: verdict: <pass|partial|fail>.
set -euo pipefail
RUN="${1:?run dir}"
SRC="$RUN/workspace/sample"
HERE="$(cd "$(dirname "$0")" && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "✖ $1"; echo "verdict: fail"; exit 1; }
BR="$(git -C "$SRC" branch --list 'feature/*' --format='%(refname:short)' | head -1)"
[ -n "$BR" ] || fail "no feature/* branch"
git clone -q --branch "$BR" "$SRC" "$TMP/sample"
cd "$TMP/sample"
[ -f test/hidden.test.js ] && fail "test/hidden.test.js already exists in the branch"
node -e 'const p=require("./package.json");if(Object.keys(p.dependencies||{}).length||Object.keys(p.devDependencies||{}).length)process.exit(1)' \
  && echo "✔ no dependencies added" || fail "dependencies added"
npm test >/dev/null 2>&1 && echo "✔ npm test green" || fail "npm test red"
visible=$(node --test --test-reporter=tap test/*.test.js 2>/dev/null | sed -n 's/^# tests \([0-9]*\)$/\1/p' | tail -1)
[ "${visible:-0}" -ge 6 ] && echo "✔ visible tests kept ($visible)" || fail "visible tests reduced (${visible:-0})"
cp "$HERE/hidden.test.js" test/hidden.test.js
tap=$(node --test --test-reporter=tap test/hidden.test.js 2>/dev/null || true)
total=$(printf '%s\n' "$tap" | sed -n 's/^# tests \([0-9]*\)$/\1/p' | tail -1)
passed=$(printf '%s\n' "$tap" | sed -n 's/^# pass \([0-9]*\)$/\1/p' | tail -1)
total=${total:-0}; passed=${passed:-0}
[ "$total" -gt 0 ] || fail "hidden tests did not run"
printf '%s\n' "$tap" | grep '^not ok' | sed 's/^/  /' || true
echo "• hidden tests: $passed/$total"
report_ok=1
[ -s "$RUN/artifacts/report.md" ] || { echo "✖ artifacts/report.md missing or empty"; report_ok=0; }
if [ "$report_ok" -eq 1 ]; then
  for u in d h m s ms; do
    grep -Eqi "(^|[^a-z])$u([^a-z]|$)" "$RUN/artifacts/report.md" || { echo "✖ report misses unit: $u"; report_ok=0; }
  done
fi
[ "$report_ok" -eq 1 ] && echo "✔ report mentions all units"
if [ "$passed" -eq "$total" ] && [ "$report_ok" -eq 1 ]; then
  echo "✔ T004 passed"; echo "verdict: pass"; exit 0
fi
if [ $((passed * 10)) -ge $((total * 7)) ]; then
  echo "• T004 partial: visible green, hidden $passed/$total, report ok=$report_ok"; echo "verdict: partial"; exit 2
fi
echo "✖ T004 failed: hidden $passed/$total"; echo "verdict: fail"; exit 1
