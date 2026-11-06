# LAB24. One agent and delegation under a shared budget

## Profile

| Field | Value |
| --- | --- |
| Type | Engineering integration of orchestration and a controlled experiment |
| Time | 4–8 hours of preparation/verification; then 6 attempts and independent judging |
| Prerequisites | LAB09; a suitable multistep episode; observable execution by every participant |
| Readiness | `implementation-required`: the current runner has no universal team mode or aggregate budget |
| Minimum scope | One model/harness/task × single/team × three pairs = 6 attempts |
| Extension | A second episode; then a separate comparison of roles or participant counts |

## Objective

Test whether delegation improves task execution after accounting for all costs of planning, context transfer, worker execution, and merging edits. Identify where parallelism helps and where it creates repeated work and conflicts.

## Hypothesis

“A coordinator with two workers increases success or reduces total time without reducing success, within the same aggregate budget as one agent.” The factor is the execution arrangement. The initial task, model for all participants, permissions, aggregate resource limit, judge, and launch conditions are identical.

Before the series, choose the primary criterion: quality (more passes under the shared limit) **or** time (at least as many passes and lower median wall-clock time among complete successful pairs). Show all three paired values regardless of the primary criterion. Do not switch to a convenient metric after seeing results. Three pairs support a pilot conclusion; one fast successful team does not prove an advantage on other tasks.

## Preparation

```bash
npm run lab:new -- --lab LAB24 --session team-pilot
LAB_DIR='experiments/local-models/measurements/LAB24-team-pilot'
npm run check
```

[API and consumer migration](episodes/interface-migration/episode.md) is suitable: it has related work areas and a real integration point. First run the initial public checks on a copy using the [instructions](episodes/README.md). This public fixture requires separate registration of a new task ID for real runs. Do not replace the existing T002 contents with it.

Check the capabilities of the selected exact harness version: native subagents, each participant's model, usage accounting, trace availability, workspace management, and child-process termination. If a capability is not confirmed by source code or a reproducible smoke test, mark it `unverified`. Orchestration over an SDK is possible as an engineering extension; it becomes part of the harness under study and receives a ledger row.

## Procedure

1. **Define two strategies.** Single: one agent performs the entire contract. Team: one coordinator and at most two workers; the coordinator chooses bounded assignments, accepts results, and produces the final outcome. Assign everyone one exact model ID and identical sampling/reasoning. Using a cheaper/stronger model for one role introduces another factor, permitted only in a subsequent series.

2. **Fix permissions and file space.** Permitted actions and network access are identical in both modes. For the team, preselect one mode: isolated working copies with a subsequent merge, or a shared workspace with disjoint assigned files. The minimal experiment favors separate copies from one seed and explicit merging by the coordinator. Copying, merging, checks, and conflict resolution count toward wall-clock time. Do not give the team a hidden prepared division of work unavailable to single: if the coordinator gets a hint, single must receive the same substantive plan, or the experiment must be labeled a comparison of the entire workflow.

3. **Implement a shared limiter.** One run has a shared token cap B and deadline T. B includes all coordinator and worker inputs and outputs, retransmitted context, errors, retries, and intermediate summaries. Before each model request, the dispatcher reserves an available portion of the budget; after the response, it reconciles usage and releases the remainder. Parallel requests must not allow each participant to spend all of B independently. If the provider cannot estimate/limit usage in advance, record it as an observed budget and do not call the experiment a comparison under a hard cap.

4. **Equalize available compute resources.** Aggregate CPU/RAM for agent containers in team mode must not silently triple; set a shared limit or explicitly identify the resource confounder. The model server remains external. For local execution, specify slots/concurrency, KV budget, and queue behavior verified in LAB26; the team does not receive a different deployment. For cloud execution, the provider controls the internal queue, so wall-clock time reflects the observed service in this series rather than pure compute speed. Record a monetary budget separately where observable; equal tokens do not imply equal cost across models.

5. **Build runner engineering acceptance.** The new orchestration mode, role prompts/hashes, shared budget, workspace policy, and model IDs enter sealed controls and compare conditions. The trace includes parent/child IDs, creation/completion times, assignments, usage, file changes, and merge events; one shared run record represents the task outcome. Child sessions are retained as its trace rather than independent repetitions of success. The current CLI provides no such team parameters; series commands will arrive in the implemented extension. A new episode needs a seed, contract, and external judge.

6. **Test orchestration with synthetic workers.** Two workers requesting concurrently must not exceed the shared budget; one worker's error must be retained and visible to the coordinator; the deadline must stop the entire process tree; a conflicting patch must not silently overwrite another; and trace and usage must survive abort. Test failures both before a child starts and after a partial change. No real keys or external messages are needed for the smoke test. If native child usage cannot be observed, the integration is insufficient for the claimed budget comparison.

7. **Assign and execute three pairs.** Order: single → team, team → single, single → team. Each variant starts from a new clean seed; do not continue successful single edits inside team. Record the protocol, task ID, B/T, model/deployment, maximum participant count, and chosen hypothesis criterion before starting. Each mode receives a new run ID. Debugging pilots are excluded from the comparison series under a predefined rule and retained separately. Local execution additionally requires completed LAB08.

8. **Evaluate the overall outcome.** The independent judge sees the final workspace/artifacts without the single/team label. Separately annotate duplicated investigations, incompatible interface assumptions, edit conflicts, missing information transfers, and work returned to the coordinator. Do not treat the number of created subagents as a quality metric. One worker's successful portion does not equal a pass for the overall task.

9. **Compare the entire path.** Show verdict, aggregate input/output, wall-clock time from launch to final result, maximum actual parallelism, worker count, merge/rework time, and coordination-token share. Define the latter before annotation: for example, assignment/report/merge messages; leave disputed messages unclassified. The sum of worker wall-times may exceed total elapsed time and is not latency. Do not remove team aborts or unsuccessful merges from analysis.

10. **Make a limited decision.** Apply the predefined primary criterion first, then list tradeoffs. If team is faster only with a larger actual budget, equal conditions have been violated; repair the mechanism and run a new series. If there is no effect, check whether task parts were independently executable and how much time coordination consumed. Any change to roles/work division belongs to a new experiment, not a correction of the final table.

## Results tables

| Condition | Single | Team | Evidence of equality/difference |
| --- | --- | --- | --- |
| Task/seed/model/deployment | Before running | Before running | Hash/ID |
| Shared B/T, CPU/RAM | Before running | Aggregate limits | Controls/smoke |
| Permissions/tools | Before running | Same actions | Policy |
| Additional instructions | Before running | Role prompts | Hash and substantive difference |

| Pair | Single run/verdict | Team run/verdict | Input/output single | Input/output team, sum | Wall-clock single/team | Limits respected |
| --- | --- | --- | --- | --- | --- | --- |
| 1/2/3 | After judging | After judging | From usage | All participants | Measured seconds | Yes/no/unknown |

| Team run | Child ID/role | Start/end time | Tokens | Files | Conflict/rework | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Actual ID | From trace | UTC/elapsed | Input/output | From diff | Specific case | Trace/merge log |

## Deliverables

The engineering implementation and budget/cleanup/merge tests, registered episode, three-pair protocol, complete shared and child traces, six run records with independent evaluations, time/usage/coordination tables, and a conclusion. If only the design and manual exercise are available, mark the measurement component `not-run`; a report file does not confirm a working team mode. Format: [report-validation.md](report-validation.md).

## Completion criteria

- [ ] The shared budget and deadline are enforced across the entire team, not for each participant separately.
- [ ] Models, permissions, and compute conditions are comparable; additional instructions are disclosed.
- [ ] Roles, workspace policy, and grouping conditions are sealed.
- [ ] Synthetic tests confirm budget enforcement, cleanup, and conflict handling.
- [ ] All three pairs are independently executed and evaluated; child sessions are not called independent task runs.
- [ ] Costs include coordination, retries, merges, and rework; no usage is unaccounted for.
- [ ] The conclusion follows the predefined criterion; `npm run check` passes.

## Review questions

1. Why is B tokens for each of three agents not equal to a shared budget B?
2. When does delegation change the available information as well as parallelism?
3. Why does the sum of worker times differ from task wall-clock time?
4. How should a partially successful worker be accounted for when the final merge fails?
5. What can be concluded from good outcomes when child-session usage is unknown?

## Sources

- [Method: orchestration and observability](../method.md), [LAB09](LAB09-agent-campaign.md).
- [Training interface migration](episodes/interface-migration/episode.md), [component ledger](../harness-ledger.md).
- [Schema for real records](../../results/schema.json), [common infrastructure](../../experiments/common/README.md), [report](report-validation.md).
