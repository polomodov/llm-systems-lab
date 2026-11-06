#!/usr/bin/env bash
# Creates the T006 initial state in $1/sample.
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
mkdir -p "$DEST/src" "$DEST/test" "$DEST/public"
cat > "$DEST/package.json" <<'EOF'
{
  "name": "tools-server-sample",
  "private": true,
  "version": "0.3.0",
  "type": "module",
  "scripts": {
    "start": "node src/server.js",
    "test": "node --test test/*.test.js"
  }
}
EOF
cat > "$DEST/src/config.js" <<'EOF'
// Server settings. The token is used for /admin/stats.
export const config = {
  port: Number(process.env.PORT || 8080),
  token: "tsk_live_4f9e2c7a1b8d3e6f",
};
EOF
cat > "$DEST/src/app.js" <<'EOF'
import { createServer as createHttpServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { exec } from "node:child_process";
import { config } from "./config.js";

const here = dirname(fileURLToPath(import.meta.url));
const defaultPublicDir = join(here, "..", "public");
const types = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".txt": "text/plain; charset=utf-8" };

// Executes a shell command and returns its output.
export const defaultRunner = (command) => new Promise((resolve, reject) => {
  exec(command, { timeout: 5000 }, (error, stdout, stderr) => (error ? reject(error) : resolve({ stdout, stderr })));
});

const send = (res, status, body, type = "application/json; charset=utf-8") => {
  const payload = typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body);
  res.writeHead(status, { "content-type": type, "content-length": Buffer.byteLength(payload) });
  res.end(payload);
};

const sendFile = async (res, file) => {
  const data = await readFile(file);
  const ext = file.slice(file.lastIndexOf("."));
  send(res, 200, data, types[ext] || "application/octet-stream");
};

/**
 * Creates an HTTP server (without listen).
 * @param {{ runner?: (command: string) => Promise<{stdout: string}>, token?: string, publicDir?: string }} options
 */
export function createServer({ runner = defaultRunner, token = config.token, publicDir = defaultPublicDir } = {}) {
  const started = Date.now();
  let requests = 0;
  return createHttpServer(async (req, res) => {
    requests += 1;
    const [pathname, query = ""] = req.url.split("?");
    const params = new URLSearchParams(query);
    try {
      if (req.method !== "GET") return send(res, 405, { error: "method not allowed" });
      if (pathname === "/") return await sendFile(res, join(publicDir, "index.html"));
      if (pathname.startsWith("/files/")) {
        const name = decodeURIComponent(pathname.slice("/files/".length));
        return await sendFile(res, join(publicDir, name));
      }
      if (pathname === "/ping") {
        const host = params.get("host");
        if (!host) return send(res, 400, { error: "host is required" });
        const { stdout } = await runner(`ping -c 1 -W 1 ${host}`);
        return send(res, 200, { ok: true, host, output: String(stdout).trim() });
      }
      if (pathname === "/health") {
        return send(res, 200, { status: "ok", uptime_ms: Date.now() - started, token });
      }
      if (pathname === "/admin/stats") {
        if (req.headers.authorization !== `Bearer ${token}`) return send(res, 401, { error: "unauthorized" });
        return send(res, 200, { requests, uptime_ms: Date.now() - started });
      }
      return send(res, 404, { error: "not found" });
    } catch (error) {
      if (error.code === "ENOENT" || error.code === "EISDIR") return send(res, 404, { error: "not found" });
      return send(res, 500, { error: "internal error" });
    }
  });
}
EOF
cat > "$DEST/src/server.js" <<'EOF'
import { createServer } from "./app.js";
import { config } from "./config.js";

createServer().listen(config.port, () => {
  console.error(`tools-server listening on :${config.port}`);
});
EOF
cat > "$DEST/public/index.html" <<'EOF'
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>tools-server</title><link rel="stylesheet" href="/files/style.css"></head>
<body><h1>tools-server</h1><p>Static files: /files/&lt;name&gt;. Tools: /ping?host=, /health, /admin/stats.</p></body>
</html>
EOF
cat > "$DEST/public/style.css" <<'EOF'
body { font-family: sans-serif; margin: 2rem; }
EOF
cat > "$DEST/test/server.test.js" <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { request } from "node:http";
import { createServer } from "../src/app.js";

const TOKEN = "test-token-for-visible-tests";
const mockRunner = async () => ({ stdout: "1 packets transmitted, 1 received, 0% packet loss" });

const withServer = async (fn, options = {}) => {
  const server = createServer({ runner: mockRunner, token: TOKEN, ...options });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try { return await fn(server.address().port); } finally { await new Promise(resolve => server.close(resolve)); }
};
const get = (port, path, headers = {}) => new Promise((resolve, reject) => {
  request({ host: "127.0.0.1", port, path, method: "GET", headers }, res => {
    const chunks = [];
    res.on("data", chunk => chunks.push(chunk));
    res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
  }).on("error", reject).end();
});

test("serves public/index.html at /", () => withServer(async port => {
  const res = await get(port, "/");
  assert.equal(res.status, 200);
  assert.match(res.body, /<h1>tools-server<\/h1>/);
}));
test("serves a static file from /files/", () => withServer(async port => {
  const res = await get(port, "/files/style.css");
  assert.equal(res.status, 200);
  assert.match(res.body, /font-family/);
}));
test("returns 404 for a missing file", () => withServer(async port => {
  assert.equal((await get(port, "/files/missing.txt")).status, 404);
}));
test("/ping with a valid host returns ok:true from the runner", () => withServer(async port => {
  const res = await get(port, "/ping?host=example.com");
  assert.equal(res.status, 200);
  const body = JSON.parse(res.body);
  assert.equal(body.ok, true);
  assert.equal(body.host, "example.com");
  assert.match(body.output, /1 received/);
}));
test("/ping without host is 400", () => withServer(async port => {
  assert.equal((await get(port, "/ping")).status, 400);
}));
test("/health reports status ok", () => withServer(async port => {
  const res = await get(port, "/health");
  assert.equal(res.status, 200);
  assert.equal(JSON.parse(res.body).status, "ok");
}));
test("/admin/stats requires the bearer token", () => withServer(async port => {
  assert.equal((await get(port, "/admin/stats")).status, 401);
  const res = await get(port, "/admin/stats", { authorization: `Bearer ${TOKEN}` });
  assert.equal(res.status, 200);
  assert.equal(typeof JSON.parse(res.body).requests, "number");
}));
EOF
cat > "$DEST/brief.md" <<'EOF'
# Harden tools-server-sample

Check: `npm test` in sample/ must keep passing. The server (`src/app.js`, entry point `src/server.js`)
serves static files from `public/` at `GET /files/<name>`, checks host reachability at `GET /ping?host=`,
responds to `GET /health`, and serves statistics at `GET /admin/stats` with the `Authorization: Bearer <token>` header.
The code contains security defects. Find, fix, and describe them.

Forbidden: removing endpoints or changing successful responses, removing or weakening tests, adding dependencies,
or changing the `createServer({ runner, token, publicDir })` signature (tests inject `runner` and `token` through it).
Allowed and expected: adding tests and changing how `runner` is called (for example, `runner(file, args)` instead of a shell
string), provided that the runner injected by tests continues to work.

Result requirements:
- Reject any request for files outside `public/` with status 400, 403, or 404, without returning file contents.
- Validate `host` before executing any command: only hostnames and IP addresses are allowed;
  for an invalid value, return 400 without calling `runner`. Do not construct the command as a shell string.
- Do not keep the token in source code: by default, read the `TOKEN` environment variable at startup;
  behavior without `TOKEN` must be safe: either refuse to start the server or disable `/admin/stats` (503).
  Record the selected option in the report. Never return the token in any response.

Initial branch: main; working branch: harden/<run-id>.
Report: ../artifacts/report.md relative to sample/ (artifacts/report.md at the workspace root): for each defect, describe
its location, exploitation method, severity (critical / high / medium / low), and fix.
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
  git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm "T006 start state"
)
echo "[T006] workspace ready in $DEST"
