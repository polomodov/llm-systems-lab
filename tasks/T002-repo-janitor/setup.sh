#!/usr/bin/env bash
# Creates the T002 initial state in $1/sample.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo 'usage: setup.sh <dest>' >&2
  exit 64
fi
WORKSPACE=$(node --input-type=module - "$1" <<'JS'
import { lstatSync, mkdirSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
const destination = process.argv[2];
if (!destination.trim()) throw new Error('An explicit nonempty workspace path is required.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Refusing to overwrite a nonempty directory, file, or symlink: ${dest}`);
}
mkdirSync(join(dest, 'artifacts'), { recursive: true });
console.log(dest);
JS
)
DEST="$WORKSPACE/sample"
umask 022
mkdir -p "$DEST/src" "$DEST/test"
cat > "$DEST/package.json" <<'EOF'
{
  "name": "janitor-sample",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "lint": "node scripts/lint.mjs",
    "test": "npm run lint && node --test test/*.test.js"
  },
  "dependencies": {
    "lodash": "4.17.15"
  }
}
EOF
mkdir -p "$DEST/scripts"
cat > "$DEST/scripts/lint.mjs" <<'EOF'
// Tiny linter: forbids console.log in src/ and unresolved TODOs without a number.
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
# Janitor for janitor-sample
Check: `npm test` in sample/. Forbidden: removing or weakening tests, changing the slugify signature.
Known vulnerability: lodash 4.17.15 (upgrade within 4.x).
Fix the implementation mismatch with existing tests while preserving the public signature.
Initial branch: main; working branch: janitor/<run-id>.
Report: ../artifacts/report.md relative to sample/ (artifacts/report.md at the workspace root).
EOF
(
  cd "$DEST"
  # Do not inherit the operator’s templates, hooks, signatures, or line-ending settings.
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
  export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=0
  export GIT_AUTHOR_DATE=2026-09-19T00:00:00Z GIT_COMMITTER_DATE=2026-09-19T00:00:00Z
  export GIT_AUTHOR_NAME=setup GIT_AUTHOR_EMAIL=setup@example.com
  export GIT_COMMITTER_NAME=setup GIT_COMMITTER_EMAIL=setup@example.com
  git -c init.templateDir= init -q --initial-branch=main
  git -c core.autocrlf=false add -A
  git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm "T002 start state"
)
echo "[T002] workspace ready in $DEST"
