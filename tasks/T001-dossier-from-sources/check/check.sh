#!/usr/bin/env bash
# Детерминированная часть скрытой проверки T001. Использование: check.sh <run-dir>
set -euo pipefail
RUN="${1:?run dir}"
A="$RUN/artifacts"
fail=0
for u in code.claude.com/docs/en/glossary langchain.com/blog/the-anatomy-of-an-agent-harness martinfowler.com/articles/harness-engineering.html anthropic.com/engineering/harness-design-long-running-apps metr.org/notes/2026-02-13 modelcontextprotocol.io/specification/2026-07-28; do
  grep -q "$u" "$A/sources.json" || { echo "✖ missing source: $u"; fail=1; }
done
grep -qi "противореч\|contradict" "$A/dossier.md" || { echo "✖ no contradictions section"; fail=1; }
python3 - "$A" <<'PY' || fail=1
import json,re,sys
a=sys.argv[1]
src=json.load(open(f"{a}/sources.json"))
fetched=" ".join(json.dumps(s,ensure_ascii=False) for s in src if s.get("fetched"))
doss=open(f"{a}/dossier.md",encoding="utf-8").read()
nums=set(re.findall(r"\d+(?:[.,]\d+)?",doss))
missing=[n for n in nums if n not in fetched and len(n)>1 and not re.match(r"^(19|20)\d\d$",n)]
if missing: print("✖ numbers without a fetched source:",missing[:20]); sys.exit(1)
print("✔ numbers backed by fetched sources")
PY
[ $fail -eq 0 ] && echo "✔ T001 deterministic checks passed" || { echo "✖ T001 deterministic checks failed"; exit 1; }
