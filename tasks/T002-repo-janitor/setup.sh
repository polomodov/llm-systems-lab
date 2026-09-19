#!/usr/bin/env bash
# Создаёт стартовое состояние T002 в каталоге $1/sample.
set -euo pipefail
DEST="${1:-.}/sample"
rm -rf "$DEST"; mkdir -p "$DEST/src" "$DEST/test"
cat > "$DEST/package.json" <<'EOF'
{
  "name": "janitor-sample",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "lint": "node scripts/lint.mjs",
    "test": "npm run lint && node --test test/"
  },
  "dependencies": {
    "lodash": "4.17.15"
  }
}
EOF
mkdir -p "$DEST/scripts"
cat > "$DEST/scripts/lint.mjs" <<'EOF'
// Крошечный линтер: запрещает console.log в src/ и незакрытые TODO без номера.
import { readdirSync, readFileSync } from "node:fs";
let bad = 0;
for (const f of readdirSync("src")) {
  const s = readFileSync(`src/${f}`, "utf8");
  if (/console\.log/.test(s)) { console.error(`lint: console.log in src/${f}`); bad++; }
  if (/TODO(?!\(#\d+\))/.test(s)) { console.error(`lint: TODO without issue in src/${f}`); bad++; }
}
process.exit(bad ? 1 : 0);
EOF
cat > "$DEST/src/slugify.js" <<'EOF'
// TODO make it faster
export function slugify(title) {
  console.log("slugify", title);
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/, "");
}
EOF
cat > "$DEST/test/slugify.test.js" <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { slugify } from "../src/slugify.js";

test("basic words", () => assert.equal(slugify("Hello World"), "hello-world"));
test("trims dashes on both ends", () => assert.equal(slugify("--Agent Harness--"), "agent-harness"));
test("collapses punctuation", () => assert.equal(slugify("a, b; c"), "a-b-c"));
EOF
cat > "$DEST/brief.md" <<'EOF'
# Дворник для janitor-sample
Проверка: `npm test` в каталоге sample/. Запрещено: удалять или ослаблять тесты, менять сигнатуру slugify.
Известная уязвимость: lodash 4.17.15 (обновить в пределах 4.x).
EOF
( cd "$DEST" && git init -q && git add -A && git -c user.name=setup -c user.email=setup@example.com commit -qm "T002 start state" )
echo "[T002] workspace ready in $DEST"
