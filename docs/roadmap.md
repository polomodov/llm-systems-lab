# Experiment extension roadmap

Date: 2026-11-05. Document class: author's forecast with verification criteria. No item is a result; each is a question, a run series that can answer it, and a condition for closing the direction.

## Starting point

After the “Lighten the core” PR, the lab has:

- 9 harness adapters with pinned images; one has run a real model (Pi, local model).
- 6 tasks in three categories: web-source research (T001), repository changes (T002, T004, T006), and auditing/data without a repository (T003, T005). Only T002 has evaluated runs.
- 11 records, 3 independently evaluated, and no complete triple under matching conditions.
- A 29-row ledger with 28 entries marked proposed: components are implemented, but their contribution to agent success has not been measured.

The lab's main question — what a harness needs to execute the same specification — remains unanswered. The directions below are ordered by how quickly they can move toward an answer.

## Direction 1. First campaign: the same model, different harnesses

**Question.** Do harnesses differ in success, cost and turns with one model, one task and matching boundaries?

**Series.** LAB09. Three harnesses that accept the same exact Anthropic model ID: Claude Code, Pi and OpenCode. Two tasks with scripted checks: T002 and T004. Three repeats per cell. Total: 18 runs, contract budget up to USD 2 per run, expected series cost up to USD 40. One image per harness for the whole series, with `--budget-mode observed` for Pi and OpenCode explicitly marked in the comparison.

**Output.** The first complete triples, `pass@3` and `pass^3` per cell, and the first `compare --out` table. Within-cell variability will indicate how many repeats are needed next: if two triples of one cell disagree on `pass@3`, three repeats are insufficient.

**Stop criterion.** If all three harnesses achieve `pass^3` on both tasks, the tasks are too easy and direction 4 takes priority. If none achieves `pass@3`, investigate the model and contract before the harnesses.

**Avoid.** Do not mix providers in one group, compare Amp `managed:*` against an exact ID, or rebuild images between repeats.

## Direction 2. Harness component ablation

**Question.** Which harness components actually affect outcomes with a fixed model, and which duplicate the model's default behavior?

**Series.** LAB10 under the same conditions as direction 1. The first ablation is implemented: `--variant without-spec`. Each additional variant needs its own `prepare-run` flag and ledger row:

| Variant | What is removed | Assumption under test |
| --- | --- | --- |
| `without-spec` | Agent specification text from the prompt | An explicit specification helps the model |
| `without-brief-rules` | Prohibitions and rules from `brief.md`; the contract remains | Instructional constraints, rather than enforced boundaries, change behavior |
| `without-native-limits` | Adapter native turn/budget limits; the external timeout remains | Harness limits change the model's strategy, not just interrupt it |
| `minimal-config` | Harness configuration is reduced to empty; the adapter remains | Default harness settings are sufficient |

Boundaries (Docker, gateway, exclusion of `check/`) are never ablated.

**Output.** Ledger rows move from proposed to confirmed or unconfirmed, with before/after run IDs. This is the only way the ledger becomes evidence rather than a catalog.

**Stop criterion.** A component that changes neither `pass@3` nor cost in two paired series is removed from configuration, rather than retained “just in case.”

## Direction 3. Model matrix

**Question.** Which has a larger effect: changing the harness with the same model, or changing the model with the same harness?

**Series.** After direction 1, add same-provider models one cost tier below and above, and run the same cells for one harness. The matrix is 3 harnesses × 1 model plus 1 harness × 3 models, sharing one cell.

**Output.** An estimate of the main source of variation. If the model explains almost everything, the harness lab becomes a cost lab: how much the same result costs across models using one harness.

**Condition.** An exact model ID in `run.json`, confirmed by `observed_id` from the trace. Runs with `model_mismatch` do not enter the groups.

## Direction 4. New task types

The six tasks cover research, repair, audit, implementation, data and security. They do not cover the types where harnesses should differ most.

| Task | Type | Harness capability tested | Evaluation |
| --- | --- | --- | --- |
| T007 · long horizon | Refactor across 5–8 files, with passing tests at every step | Context compaction, memory, action ordering | Script: tests and diff against a reference structure |
| T008 · source injection | T001 with an archive containing agent-directed instructions on one page | Resistance to injection through data; the source/instruction boundary | Script: evidence of following the injection in artifacts and trace |
| T009 · incomplete specification | A deliberate contradiction in `brief.md` | Whether the agent stops and records the contradiction rather than guessing | Rubric plus a script checking for a contradictions section |
| T010 · recovery | Tests depend on an external process that fails on the first start | Retry and diagnosis strategy (related to LAB23) | Script: passing tests and restart count from the trace |
| T011 · tools | A task solvable only through a specified MCP server or CLI with an unusual interface | Tool design and interface cost (related to LAB22) | Script: result and tool-call count |

Each task comes with `task.json`, `setup.sh`, a hidden check with distinguishable `pass`, `partial` and `fail` outcomes, and manual verification of all three before the first run. T008 uses `capture-sources`: capture the archive once, then modify it manually to make the injection reproducible.

**Stop criterion.** A task that all harnesses solve identically in three repeats does not distinguish harnesses. Move it to warmup rather than the campaign.

## Direction 5. Measurements and the judge

**Question.** Are numbers comparable across harnesses, and how independent is independent evaluation?

- **Shared trace vocabulary.** Each adapter currently normalizes events differently. A common `trace/events.jsonl` schema with `model_call`, `tool_call`, `tool_result`, `compaction`, `subagent` and explicit `unavailable` values provides consistent turn/tool-call counters. Preserve the raw CLI stream alongside it.
- **Cost calibration.** Compare CLI `cost_usd` with provider billing for an isolated key over the direction-1 series. Record discrepancies under the evidence class “harness claim.”
- **Two judges.** LAB20: two independent evaluators use one rubric for T001 and T003, measuring agreement item by item. Until agreement meets the threshold, refine the rubric rather than the result.
- **Time to first action and fraction of turns without tools.** Two metrics visible in any trace that distinguish harness strategies without judging quality.

**Stop criterion.** A metric that cannot be obtained from at least two harnesses with the same definition stays `null` with a reason and is excluded from comparisons.

## Direction 6. Boundaries and trust

**Question.** Do boundaries hold in real runs, not just synthetic tests?

- **Canaries.** Put a decoy file outside the allowed write area and a URL outside the allowlist in each workspace. Record every access through the gateway and checks. This turns “the agent did not read `check/`” from an assumption into a measurement.
- **Credential broker.** The provider key is currently accessible to processes inside the agent container. A reverse proxy that adds authorization on the coordinator side removes the key from the agent environment. It is required for T008 and any task with untrusted inputs.
- **Per-harness boundary probes.** Add the same probes to LAB11–19: writes outside the workspace, CONNECT to a forbidden domain, and reads of `/control`. Put each harness's result in the matrix as a measurement, not a description.

## Direction 7. Local models as a condition

Pi with local llama.cpp already works. Extend it in two steps without bringing local-model measurements back into this tree:

1. Port the local provider to a second harness (OpenCode or mini-SWE-agent), making “local model” a condition rather than a property of Pi.
2. LAB25: one task, one harness, two quantizations of one model, three repeats each. Does quantization change agent-task success, rather than only speed?

Measurement bundles go in a separate measurement repository; keep `run.json`, a summary and a link here.

## Direction 8. Infrastructure and regressions

- **CI image builds.** Implemented in the workflow: all nine Dockerfiles on manual/weekly runs; affected harnesses on PR/push. Check the actual installed pin without network access; Pi also runs the local-bridge Docker smoke. These are infrastructure checks, not agent results.
- **Pin-update protocol.** LAB27: when a harness or model version changes, run the same direction-1 cell before and after, recording the difference in the ledger with two run IDs.
- **Comparison publication.** After successful checks on a push to `main`, the workflow saves `compare --out results/compare/latest.md` as an artifact and job summary. The evidence state is readable without running scripts locally; reports are not committed automatically.
- **Automatic series preparation.** A command creates N records for one cell with matching parameters in one invocation, avoiding manual series assembly.

## Order and effort

| Step | Direction | Dependencies | Estimated effort |
| --- | --- | --- | --- |
| 1 | Campaign 3 × 2 × 3 (direction 1) | Keys for two providers, built images | 1–2 operator days, up to USD 40 |
| 2 | `without-spec` ablation on the best cell (direction 2) | Step 1 | Half a day, up to USD 15 |
| 3 | Canaries and boundary probes (direction 6) | None | 1 engineering day |
| 4 | T007 and T008 (direction 4) | `capture-sources` on the operator's machine | 2 days |
| 5 | Shared trace vocabulary (direction 5) | None, but before expanding adapters | 2–3 days |
| 6 | Model matrix (direction 3) | Step 1 | 1 day, up to USD 40 |
| 7 | Credential broker (direction 6) | Before any untrusted task | 2 days |
| 8 | Local provider in a second harness (direction 7) | Access to the target platform | 2–3 days |

Steps 1 and 2 provide the first numbers for the main question and determine whether the remaining investment is worthwhile. Step 3 protects those results from doubts about the boundary. The rest expands the condition space and makes sense only after the first triples show that the setup can distinguish harnesses.

## What to avoid

- Do not return local-model measurement bundles or frozen LAB36–52 infrastructure branches to this tree.
- Do not add a tenth harness before the nine existing ones have completed at least one campaign cell.
- Do not rank harnesses using incomplete triples or combine groups with different models, variants or budget policies.
- Do not add a harness component without a ledger row and a planned before/after run pair.
