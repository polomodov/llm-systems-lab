#!/usr/bin/env bash
set -euo pipefail
RUN="${1:?run dir}"
SRC="$RUN/workspace/sample"
TMP="$(mktemp -d)"
BR="$(git -C "$SRC" branch --list 'janitor/*' --format='%(refname:short)' | head -1)"
[ -n "$BR" ] || { echo "✖ no janitor/* branch"; exit 1; }
git clone -q --branch "$BR" "$SRC" "$TMP/sample"
cd "$TMP/sample"
npm install --silent >/dev/null 2>&1 || true
npm test >/dev/null 2>&1 && echo "✔ npm test green" || { echo "✖ npm test red"; exit 1; }
n=$(node --test --test-reporter=tap test/ 2>/dev/null | grep -c '^ok' || true)
[ "$n" -ge 3 ] && echo "✔ tests kept ($n)" || { echo "✖ tests reduced ($n)"; exit 1; }
node -e 'import("./src/slugify.js").then(m=>{if(m.slugify("--Agent Harness--")!=="agent-harness")process.exit(1)})' && echo "✔ behavior fixed" || { echo "✖ slugify still wrong"; exit 1; }
grep -q 'console.log' src/*.js && { echo "✖ console.log left"; exit 1; } || echo "✔ lint clean"
node -e 'const v=require("./package.json").dependencies.lodash.replace(/[^0-9.]/g,"");const [a,b,c]=v.split(".").map(Number);process.exit(a===4&&(b>17||(b===17&&c>=21))?0:1)' && echo "✔ lodash updated" || { echo "✖ lodash not updated"; exit 1; }
for k in "dash\|дефис" "console.log" "lodash"; do grep -qi "$k" "$RUN/artifacts/report.md" || { echo "✖ report misses: $k"; exit 1; }; done
echo "✔ T002 passed"
