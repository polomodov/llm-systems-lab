# Tasks — replayable episodes

Each task contains `task.md` (initial state, contract, and the visible portion of evaluation), `setup.sh` (reproduces the initial state in `results/runs/<run-id>/workspace/`), and `check/` (hidden evaluation; never show it to the agent).

| ID | Task | Agent | Evaluation type |
| --- | --- | --- | --- |
| T001 | Dossier from six sources about harnesses | A1 | script + rubric |
| T002 | Janitor: failing `npm test` in a small project | A2 | script |
| T003 | Audit this repository’s harness | A3 | rubric |
| T004 | Implement a specification: duration parsing and formatting | A4 | script |
| T005 | Data normalization: three dirty order exports | A5 | script |
| T006 | Security hardening: three defects in a small HTTP server | A6 | script |

Method rule: the harness must prevent agent access to `tasks/*/check/`. A run in which the agent looks there is marked `fail` regardless of its result.
