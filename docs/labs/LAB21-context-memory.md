# LAB21. Agent memory and history compaction

## Profile

| Field | Value |
| --- | --- |
| Type | Engineering extension and controlled experiment |
| Time | 3–6 hours to design and verify the adapter; then 6 attempts plus judging |
| Prerequisites | LAB09; LAB20 calibration is useful before evaluating a dossier |
| Readiness | `implementation-required`: the runner currently has no memory switches or registration for the training episodes |
| Minimum scope | One episode × one model/harness × two modes × three pairs = 6 new attempts after engineering acceptance |
| Extension | Third mode: a structured checkpoint; a second multistep episode |

## Objective

Measure which requirements and intermediate decisions are lost when history is compacted and whether the reduction in subsequent input tokens pays off. Unlike LAB05, this tests the continuation of multistep work, rather than just fitting a long prompt into the context.

## Hypothesis

“After one predefined checkpoint, a short summary preserves solution quality on the selected episode while reducing total input token usage.” The factor is the history transfer mode after the checkpoint: `full-history` or `summary-only`. The second mode includes both the cost and time of creating the summary.

The model, exact harness version, initial seed, available files and tools, permissions, limits, judge, checkpoint timing, and total budget are identical. Three pairs are a pilot: a lack of differences does not prove equivalence. The rule for pilot support of the hypothesis is: at least as many passes with summary, no new violation of a mandatory requirement, and lower total input in every pair with measured usage. With incomplete metrics, the conclusion about savings is “insufficient data.”

## Preparation

```bash
npm run lab:new -- --lab LAB21 --session memory-pilot
LAB_DIR='experiments/local-models/measurements/LAB21-memory-pilot'
npm run check
```

Choose [a bug fix across multiple modules](episodes/multi-file-bug/episode.md) or [a dossier on conflicting sources](episodes/conflicting-sources/episode.md). Before connecting the model, complete the manual exercise on a copy using the [episode instructions](episodes/README.md). This helps clarify mandatory requirements but does not count as an agent run. A person who knows the finished patch must not hint at it in the next attempt's prompt.

Read the selected adapter's implementation and its individual LAB11–19 manual. Native compaction, session resume, threshold settings, and a complete transcript are not assumed: confirm each capability in the code/exact version or record `unverified`. If hidden automatic compaction cannot be disabled or observed, this harness is unsuitable for a causal comparison of these modes.

## Procedure

1. **First establish engineering acceptance.** Register a new task ID in a separate change with an immutable contract, seed, permitted actions, isolated preparation, and an external judge. Public fixtures in `docs/` do not become runner tasks by themselves. Do not edit existing `tasks/*/task.md` or read hidden checks. Registration checks must prove that the initial seed is identical and that the judge is inaccessible to the agent container.

2. **Implement an observable checkpoint.** The adapter must be able to stop after a completed tool result and before the next model request, save the transcript and workspace, and resume with the assigned form of history. Do not split an active tool call or leave a tool response without its corresponding call. Record the snapshot format, strategy ID, summary prompt/hash, summary limit, its author's model ID, and recovery policy. New condition fields must be retained in sealed controls and comparison grouping; the existing `--variant without-spec` does not mean compaction.

3. **Verify the mechanisms without a model.** On a synthetic transcript, confirm exact preservation of the current assignment, boundaries, and latest matched tool call/result; absence of a future verdict in the summary; accounting for summary usage; and an unchanged workspace. Full-history and summary continuations must start from the same seed and protocol. Record native automatic compaction as an additional intervention; otherwise stop the series. A real series is allowed only after these checks. Do not use invented memory flags in the current CLI.

4. **Specify the timing and format of the intervention.** For the dossier, use the point after the conditions matrix is created and before writing the conclusion; for the bug fix, use the point after initial diagnosis and recording a plan, before the first file edit. The adapter must confirm this event through a trace rather than infer it from wall-clock time. The minimum summary contains the objective, mandatory requirements, verified observations, file state, decisions made, and next work; set its limit, for example 800 tokens, before the pilot and keep it identical throughout the series. If the summary cannot be measured with a native tokenizer, use a fixed character limit and label it accordingly.

5. **Predefine three pairs.** Pair 1 order is full → summary, pair 2 is summary → full, and pair 3 is full → summary. Each variant makes an independent attempt from the initial seed; this tests the complete strategy, rather than six continuations of one successful checkpoint. All initial stages and summaries count toward the total budget. Keep temperature/reasoning/context/output and external time/token limits identical; do not replace unknown seed support with a promise of determinism.

6. **Run the series through the accepted extension interface.** Use the `new-run → prepare-run → run → judge-run` lifecycle and the new fields/parameters actually implemented in the engineering change. Include exact commands in the report. The published runner currently has baseline/without-spec; before acceptance, you may submit the mechanism design and manual exercise, but the measurement component remains `not-run`. Local execution additionally requires a working LAB08 bridge.

7. **Evaluate the outcome and requirement retention.** Give the independent judge only the final artifacts and contract. A second trace analysis identifies every forgotten requirement, repeated read/fix, contradiction of the checkpoint, and overwrite of a correct result. Build the requirements register from the contract before running; do not add criteria only for the unsuccessful variant. The judge must not reveal the reference answer to the agent during continuation.

8. **Calculate costs for the entire path.** Show input/output separately before the checkpoint, for the summary, and afterward; total is the sum of all stages and errors. Add full execution wall-clock time, summary size, repeated tool call count, and verdict. If the API does not report cache tokens or compaction count, leave them unknown and identify the observation source; text file size is not a substitute for token usage. Calculate paired differences only for comparable measured values.

9. **Form a limited conclusion.** A new violation of a mandatory requirement means the pilot does not support the hypothesis, even at a lower price. With identical outcomes and incomplete usage, there is insufficient evidence of savings. Identify summary fields to reconsider, but do not repair the mechanism midway through the series. A new version requires a new series and a corresponding assumption/evidence entry in the ledger.

## Results tables

| Pair | Order | Full run ID | Summary run ID | Identical seed/model/limits | Checkpoint evidence |
| --- | --- | --- | --- | --- | --- |
| 1/2/3 | Predefined | After acceptance | After acceptance | Yes/no and reason | Trace event/hash |

| Run | Mode | Verdict | Input before / summary / after | Total output | Wall-clock, s | Repeated tool calls | Lost requirements |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Actual ID | Assigned | After judging | From usage or unknown | From usage | Measure | Define before the series | ID and evidence |

| Contract requirement | Present before checkpoint | Included in summary | Met in result | Evidence | Compaction error or another cause |
| --- | --- | --- | --- | --- | --- |
| Predefined ID | Yes/no | Yes/no/not required | Yes/no | Trace/artifact | Justify |

## Deliverables

A report, acceptance design/implementation with tests, the exact strategy protocol, checkpoint and summary hashes, all six run IDs, independent verdicts, the requirements table, and complete cost accounting. Before implementation, submission of the **engineering component** with explicit `not-run` status is allowed; this does not complete the experimental component. Completeness checks are described in [report-validation.md](report-validation.md).

## Completion criteria

- [ ] The new episode is registered; strategies are sealed and distinguished in compare conditions.
- [ ] The checkpoint is observable; tool call/result pairs match; hidden compaction is excluded or the experiment is declared incomparable.
- [ ] Three pairs were planned before execution and all attempts are retained.
- [ ] Summary costs are included in the total budget.
- [ ] All final artifacts are independently evaluated; errors are linked to requirements and evidence.
- [ ] The conclusion is not generalized to other context lengths, models, or episodes.
- [ ] `npm run check` passes; incomplete engineering work is not called a completed experiment.

## Review questions

1. Why does a shorter history in characters not yet imply a lower total cost?
2. How does copying one checkpoint for two continuations differ from independent execution of a strategy?
3. What data must not be removed between a tool call and its tool result?
4. Why is poor initial diagnosis not necessarily a compaction error?
5. Can native auto-compaction be compared with a manual summary without an observable compaction point?

## Sources

- [Method: context and memory](../method.md), [LAB05: context capacity and tools](LAB05-context-tools.md).
- [Public training episodes](episodes/README.md), [LAB09](LAB09-agent-campaign.md), [LAB20](LAB20-judge-calibration.md).
- [Preparing controls](../../scripts/prepare-run.mjs), [schema for real records](../../results/schema.json), [component ledger](../harness-ledger.md).
