#!/usr/bin/env bash
set -euo pipefail
RUN="$(cd -- "${1:?run dir}" && pwd)" || exit 2
SRC="$RUN/workspace/sample"
BR="janitor/${RUN##*/}"
TEST_FILE="test/slugify.test.js"

check_error() { echo "✖ T002 check error: $*" >&2; exit 2; }
fail() { echo "✖ T002 fail: $*" >&2; exit 1; }

for tool in git node npm; do
  command -v "$tool" >/dev/null || check_error "$tool is unavailable"
done
NODE_VERSION="$(node --version)" || check_error "Node could not start"
NPM_VERSION="$(npm --version)" || check_error "npm could not start"
echo "T002 check: Node $NODE_VERSION, npm $NPM_VERSION, branch $BR"
[ -d "$SRC/.git" ] || check_error "workspace/sample Git repository is missing"
git -C "$SRC" show-ref --verify --quiet "refs/heads/$BR" || fail "missing branch $BR"

TMP="$(mktemp -d)" || check_error "could not create a temporary directory"
trap 'rm -r -- "$TMP"' EXIT
git -c core.autocrlf=false -c core.hooksPath=/dev/null -c init.templateDir= \
  clone -q --no-local --branch "$BR" -- "$SRC" "$TMP/sample" || check_error "could not clone $BR"
cd "$TMP/sample" || check_error "could not enter the clean clone"

# Compare against the coordinator's snapshot, outside the agent's workspace.
EXPECTED="$(node - "$RUN" "$TEST_FILE" <<'JS'
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const [, , run, testFile] = process.argv;
const record = JSON.parse(readFileSync(join(run, 'run.json'), 'utf8'));
const manifestBytes = readFileSync(join(run, 'inputs/manifest.json'));
if (createHash('sha256').update(manifestBytes).digest('hex') !== record.inputs?.manifest_sha256) {
  throw new Error('input manifest SHA-256 mismatch');
}
const manifest = JSON.parse(manifestBytes);
const expected = manifest.workspace.find(row => row.path === `sample/${testFile}`)?.sha256;
if (typeof expected !== 'string' || !/^[0-9a-f]{64}$/.test(expected)) {
  throw new Error(`missing original test checksum for ${testFile}`);
}
console.log(expected);
JS
)" || check_error "could not read the original test checksum"
[ ! -L test ] && [ -f "$TEST_FILE" ] && [ ! -L "$TEST_FILE" ] ||
  fail "original test file is missing or replaced: $TEST_FILE"
ACTUAL="$(node -e 'const {createHash}=require("node:crypto"); const {readFileSync}=require("node:fs"); console.log(createHash("sha256").update(readFileSync(process.argv[1])).digest("hex"))' "$TEST_FILE")" ||
  check_error "could not hash $TEST_FILE"
[ "$ACTUAL" = "$EXPECTED" ] || fail "original tests changed: $TEST_FILE"
echo "✔ original tests unchanged"

# Run the original tests even if the submitted package script skips them.
node --test "$TEST_FILE" || fail "original tests failed"
npm test || fail "npm test failed"
echo "✔ npm test green"
node -e 'import("./src/slugify.js").then(m=>{if(m.slugify("--Agent Harness--")!=="agent-harness")process.exit(1)})' && echo "✔ behavior fixed" || { echo "✖ slugify still wrong"; exit 1; }
grep -q 'console.log' src/*.js && { echo "✖ console.log left"; exit 1; } || echo "✔ lint clean"
node -e 'const v=require("./package.json").dependencies.lodash.replace(/[^0-9.]/g,"");const [a,b,c]=v.split(".").map(Number);process.exit(a===4&&(b>17||(b===17&&c>=21))?0:1)' && echo "✔ lodash updated" || { echo "✖ lodash not updated"; exit 1; }
for k in "dash\|дефис" "console.log" "lodash"; do grep -qi "$k" "$RUN/artifacts/report.md" || { echo "✖ report misses: $k"; exit 1; }; done
echo "✔ T002 passed"
