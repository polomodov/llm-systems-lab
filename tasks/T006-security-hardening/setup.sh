#!/usr/bin/env bash
# Создаёт стартовое состояние T006 в каталоге $1/sample.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo 'usage: setup.sh <dest>' >&2
  exit 64
fi
WORKSPACE=$(node --input-type=module - "$1" <<'JS'
import { lstatSync, mkdirSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
const destination = process.argv[2];
if (!destination.trim()) throw new Error('Нужен явный непустой путь рабочего каталога.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Отказ перезаписывать непустой каталог, файл или ссылку: ${dest}`);
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
// Настройки сервера. Токен используется для /admin/stats.
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

// Выполняет команду оболочки и возвращает её вывод.
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
 * Создаёт HTTP-сервер (без listen).
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
<body><h1>tools-server</h1><p>Статические файлы: /files/&lt;name&gt;. Инструменты: /ping?host=, /health, /admin/stats.</p></body>
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
# Укрепление tools-server-sample

Проверка: `npm test` в каталоге sample/ — должна оставаться зелёной. Сервер (`src/app.js`, точка входа `src/server.js`)
отдаёт статические файлы из `public/` по `GET /files/<name>`, проверяет доступность узла по `GET /ping?host=`,
отвечает на `GET /health` и отдаёт статистику по `GET /admin/stats` с заголовком `Authorization: Bearer <token>`.
В коде есть дефекты безопасности. Найти их, устранить и описать.

Запрещено: удалять конечные точки или менять их успешные ответы, удалять или ослаблять тесты, добавлять зависимости,
менять сигнатуру `createServer({ runner, token, publicDir })` (тесты внедряют `runner` и `token` через неё).
Разрешено и ожидается: добавлять тесты, менять форму вызова `runner` (например, `runner(file, args)` вместо строки
оболочки) при условии, что внедрённый тестами `runner` продолжает работать.

Требования к результату:
- Любой запрос к файлам вне `public/` отклоняется кодом 400, 403 или 404 без содержимого файла.
- Значение `host` проверяется до любого выполнения команды: допустимы только имена узлов и IP-адреса;
  при недопустимом значении — 400 и `runner` не вызывается. Команда не собирается строкой оболочки.
- Токен не хранится в исходниках: по умолчанию читается из переменной окружения `TOKEN` при старте;
  поведение без `TOKEN` безопасно — либо сервер отказывается стартовать, либо `/admin/stats` отключён (503).
  Какой вариант выбран — записать в отчёте. Токен не возвращается ни в одном ответе.

Ветка исходного состояния: main; рабочая ветка: harden/<run-id>.
Отчёт: ../artifacts/report.md относительно sample/ (artifacts/report.md в корне workspace): каждый дефект —
где, как эксплуатируется, серьёзность (критическая / высокая / средняя / низкая), что сделано.
EOF
(
  cd "$DEST"
  # Не наследовать шаблоны, hooks, подписи и настройки окончания строк оператора.
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
