#!/usr/bin/env bash
# Creates the T004 initial state in $1/sample.
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
  "name": "duration-sample",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "test": "node --test test/*.test.js"
  }
}
EOF
cat > "$DEST/src/duration.js" <<'EOF'
// Duration parsing and formatting. The specification is in brief.md.

/**
 * Parses a string such as "1h 30m" into an integer number of milliseconds.
 * @param {string} text
 * @returns {number}
 */
export function parseDuration(text) {
  throw new Error("not implemented");
}

/**
 * Formats an integer number of milliseconds as a string such as "1h 30m".
 * @param {number} ms
 * @returns {string}
 */
export function formatDuration(ms) {
  throw new Error("not implemented");
}
EOF
cat > "$DEST/test/duration.test.js" <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseDuration, formatDuration } from "../src/duration.js";

test("parses hours and minutes without spaces", () => assert.equal(parseDuration("1h30m"), 5400000));
test("parses seconds", () => assert.equal(parseDuration("45s"), 45000));
test("parses days", () => assert.equal(parseDuration("2d"), 172800000));
test("parses zero", () => assert.equal(parseDuration("0ms"), 0));
test("formats hours and minutes", () => assert.equal(formatDuration(5400000), "1h 30m"));
test("round trip keeps the value", () => assert.equal(parseDuration(formatDuration(93784005)), 93784005));
EOF
cat > "$DEST/brief.md" <<'EOF'
# Durations for duration-sample

Check: `npm test` in sample/. Implement `parseDuration` and `formatDuration` in `src/duration.js`
according to the specification below. Visible tests in `test/` cover only basic cases; the hidden check covers the full specification.
Forbidden: removing or weakening tests, changing exported names or signatures, adding dependencies.
Initial branch: main; working branch: feature/<run-id>.
Report: ../artifacts/report.md relative to sample/ (artifacts/report.md at the workspace root): what was implemented,
decisions on ambiguous cases, and tests added.

## Specification

### `parseDuration(text) -> number`
1. Input is a string; any other type (number, `null`, `undefined`, object) raises `TypeError`.
2. The string consists of one or more `<number><unit>` components. Units: `d` (day, 86 400 000 ms),
   `h` (hour, 3 600 000 ms), `m` (minute, 60 000 ms), `s` (second, 1 000 ms), `ms` (millisecond).
3. Units are case-insensitive: `1H 30M` and `2MS` are valid.
4. Whitespace (including tabs) is allowed at the beginning, end, and between components: `"1h 30m"`, `" 90m "`, and `"1h30m"` are equivalent.
   Whitespace between a number and its unit (`"1 h"`) is forbidden and raises `TypeError`.
5. A number is a nonnegative integer written with decimal digits. A minus sign (`"-5s"`), plus sign, fractional part (`"1.5h"`, `"1,5h"`),
   or exponent raises `TypeError`. Leading zeros are allowed (`"007s"` = 7000).
6. Each unit appears at most once: `"1h1h"` raises `TypeError`. Components may appear in any order: `"30m 1h"` = 5 400 000.
7. An empty string, whitespace-only string, number without a unit (`"90"`), unknown unit (`"3w"`, `"5 sec"`),
   or any extraneous text raises `TypeError`.
8. The result is the sum of components in milliseconds, as an integer. Overflow is out of scope: input does not exceed 2^53 - 1 ms.

### `formatDuration(ms) -> string`
1. Input is a finite nonnegative integer (`Number.isInteger`). Negative or fractional values, `NaN`, `Infinity`,
   strings, and `bigint` raise `TypeError`.
2. Decompose the value greedily into units in order: `d`, `h`, `m`, `s`, `ms`.
3. Omit zero components; separate components with one space; the order is always `d h m s ms`.
   Examples: `5400000` → `"1h 30m"`, `86400000` → `"1d"`, `1500` → `"1s 500ms"`, `93784005` → `"1d 2h 3m 4s 5ms"`.
4. Emit `ms` only when the millisecond remainder is nonzero.
5. Format zero as `"0ms"`.
6. For any valid `ms`, `parseDuration(formatDuration(ms)) === ms` holds.
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
  git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm "T004 start state"
)
echo "[T004] workspace ready in $DEST"
