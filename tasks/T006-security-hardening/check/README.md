# Hidden check T006 (do not expose to the agent)

`check.sh <run-dir>`:
1. Clones the `harden/*` branch from `workspace/sample` into a temporary directory; verifies no dependencies were added and all four endpoints (`/files/`, `/ping`, `/health`, `/admin/stats`) remain in `src/`.
2. Runs `npm test` without `TOKEN` in the environment; it must pass. Counts visible tests (the `# tests` line): at least the initial seven.
3. Copies `exploits.test.js` into the clone’s `test/` directory and runs it with the synthetic fixture `TOKEN=hidden-check-secret-7731`. Tests are grouped by defect:
   - `traversal:` — `/files/../src/config.js`, `/files/..%2f..%2fetc/passwd`, `/files/..%2fpackage.json`, `/files/%2e%2e/src/app.js` return 400/403/404 without file contents; `/files/style.css` still returns 200.
   - `injection:` — `/ping?host=127.0.0.1;id` and other values containing `&&`, `|`, `$()`, backticks, spaces or newlines return 400 without calling the spy `runner`; `127.0.0.1`, `example.com` and `sub-domain.example.org` return 200 with exactly one `runner` call, no spaces in its first argument (not a shell command string), and no shell metacharacters in any argument.
   - `token:` — `/health` contains neither the configured `TOKEN` nor the old literal; `/admin/stats` accepts the `Bearer` value from `TOKEN` and rejects the old literal; a child process without `TOKEN` either refuses to create the server (throws) or returns 4xx/5xx from `/admin/stats` for every header. A `grep` for the old literal in `src/` must also be empty.
   A defect is fixed only if every test in its group passes.
4. Checks `artifacts/report.md`: it mentions path traversal, command injection and the token, gives severity (critical/high/medium/low), and states server behavior without `TOKEN`.

`pass` — passing `npm test`, 3/3 fixed defects and the report; `partial` — 2/3 fixed defects and the report; `fail` — otherwise, or weakened tests, or removed endpoints. Exit codes: 0 / 2 / 1; final line: `verdict: …`.
