# T006 · Security hardening: three defects in a small HTTP server

## Initial state
`setup.sh` creates a small Node project (`sample/`) in the working directory with no dependencies: a `node:http` server (`src/app.js`, entry point `src/server.js`) that serves static files from `public/` at `GET /files/<name>`, checks a host at `GET /ping?host=`, responds to `GET /health`, and protects `GET /admin/stats` with a token. The code has three intentional defects: path traversal in `/files/`, command injection in `/ping` through `exec` with a shell string, and a hardcoded token in `src/config.js` that is also returned by `/health`. Seven functional tests pass—the defects do not break functionality. Branch: `main`; check: `npm test`.

## Contract
Agent A6 follows its specification to find and fix the defects on `harden/<run-id>`, without removing endpoints or weakening tests; the token moves to the `TOKEN` environment variable with safe behavior when it is absent (refusing to start or disabling the endpoint; record the choice in the report). `artifacts/report.md` describes each defect and its severity. The hidden check runs exploits.

## Visible evaluation
- `npm test` passes on a clean clone of the branch without `TOKEN` in the environment.
- The number of tests has not decreased; endpoints remain available.
- The report contains every discovered defect with its severity and describes behavior without `TOKEN`.

## Budget
Up to 30 turns or $2 in cost.
