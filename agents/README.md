# Agents

An agent specification is independent of its harness: mission, inputs, outputs, boundaries, stop condition, and evaluation. Harness-specific implementations live in `experiments/<harness>/agents/<code>/` and can range from an instruction file to SDK code.

| Code | Agent | Tasks |
| --- | --- | --- |
| `a1-dossier` | Source dossier writer | T001 |
| `a2-janitor` | Repository janitor | T002 |
| `a3-ledger-auditor` | Harness auditor | T003 |
| `a4-implementer` | Specification implementer | T004 |
| `a5-data-wrangler` | Data normalizer | T005 |
| `a6-hardener` | Security hardener | T006 |

Rule: start with a minimal implementation (the specification alone as instructions), then add components, each with a ledger row.
