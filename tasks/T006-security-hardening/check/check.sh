#!/usr/bin/env bash
# Скрытая проверка T006. Использование: check.sh <run-dir>
# Код выхода: 0 — pass, 2 — partial, 1 — fail. Последняя строка вывода: verdict: <pass|partial|fail>.
set -euo pipefail
RUN="${1:?run dir}"
SRC="$RUN/workspace/sample"
HERE="$(cd "$(dirname "$0")" && pwd -P)"
OLD_TOKEN="tsk_live_4f9e2c7a1b8d3e6f"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "✖ $1"; echo "verdict: fail"; exit 1; }
BR="$(git -C "$SRC" branch --list 'harden/*' --format='%(refname:short)' | head -1)"
[ -n "$BR" ] || fail "no harden/* branch"
git clone -q --branch "$BR" "$SRC" "$TMP/sample"
cd "$TMP/sample"
[ -f test/exploits.test.js ] && fail "test/exploits.test.js already exists in the branch"
node -e 'const p=require("./package.json");if(Object.keys(p.dependencies||{}).length||Object.keys(p.devDependencies||{}).length)process.exit(1)' \
  && echo "✔ no dependencies added" || fail "dependencies added"
for ep in '"/files/' '"/ping"' '"/health"' '"/admin/stats"'; do
  grep -rq -- "$ep" src/ || fail "endpoint removed: $ep"
done
echo "✔ endpoints present"
env -u TOKEN npm test >/dev/null 2>&1 && echo "✔ npm test green" || fail "npm test red"
visible=$(env -u TOKEN node --test --test-reporter=tap test/*.test.js 2>/dev/null | sed -n 's/^# tests \([0-9]*\)$/\1/p' | tail -1)
[ "${visible:-0}" -ge 7 ] && echo "✔ visible tests kept ($visible)" || fail "visible tests reduced (${visible:-0})"
cp "$HERE/exploits.test.js" test/exploits.test.js
tap=$(TOKEN=hidden-check-secret-7731 node --test --test-reporter=tap test/exploits.test.js 2>/dev/null || true)
printf '%s\n' "$tap" | grep '^not ok' | sed 's/^/  /' || true
fixed=0
for group in traversal injection token; do
  total=$(printf '%s\n' "$tap" | grep -c "^\(not \)\?ok [0-9]* - $group:" || true)
  bad=$(printf '%s\n' "$tap" | grep -c "^not ok [0-9]* - $group:" || true)
  if [ "$group" = token ] && grep -rq -- "$OLD_TOKEN" src/; then echo "  ✖ literal token still in src/"; bad=$((bad + 1)); fi
  if [ "$total" -gt 0 ] && [ "$bad" -eq 0 ]; then echo "✔ $group fixed"; fixed=$((fixed + 1)); else echo "✖ $group not fixed ($bad problems)"; fi
done
report_ok=1
R="$RUN/artifacts/report.md"
[ -s "$R" ] || { echo "✖ artifacts/report.md missing or empty"; report_ok=0; }
if [ "$report_ok" -eq 1 ]; then
  grep -qi "traversal\|обход\|path" "$R" || { echo "✖ report misses: path traversal"; report_ok=0; }
  grep -qi "inject\|инъекц\|exec" "$R" || { echo "✖ report misses: command injection"; report_ok=0; }
  grep -qi "token\|токен" "$R" || { echo "✖ report misses: token"; report_ok=0; }
  grep -qi "critical\|high\|medium\|low\|критич\|высок\|средн\|низк" "$R" || { echo "✖ report has no severity"; report_ok=0; }
  grep -qi "503\|отключ\|disabled\|отказ\|refuse\|throw\|exit" "$R" || { echo "✖ report does not state the no-TOKEN behaviour"; report_ok=0; }
fi
[ "$report_ok" -eq 1 ] && echo "✔ report covers all defects with severity"
if [ "$fixed" -eq 3 ] && [ "$report_ok" -eq 1 ]; then
  echo "✔ T006 passed"; echo "verdict: pass"; exit 0
fi
if [ "$fixed" -ge 2 ] && [ "$report_ok" -eq 1 ]; then
  echo "• T006 partial: $fixed/3 defects fixed"; echo "verdict: partial"; exit 2
fi
echo "✖ T006 failed: $fixed/3 defects fixed, report ok=$report_ok"; echo "verdict: fail"; exit 1
