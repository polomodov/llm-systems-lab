# LAB22. How tool interfaces affect agent behavior

## Profile

| Field | Value |
| --- | --- |
| Type | Engineering extension and paired interface comparison |
| Time | 3–6 hours of implementation and verification; then 6 attempts and independent evaluation |
| Prerequisites | LAB09; understanding the selected task's permitted actions |
| Readiness | `implementation-required`: the current runner has no unified shell/structured-tools switch |
| Minimum scope | One task × one harness/model × two interfaces × three pairs = 6 new attempts |
| Extension | Separate series with different schema verbosity or tool result size |

## Objective

Test whether a specialized interface helps an agent select and perform the required operations. Distinguish the interface effect from broader permissions, hidden hints at the solution, and additional returned data.

## Hypothesis

“With the same set of permitted operations, a structured interface reduces invocation errors without reducing task success.” The factor is how an operation is expressed: a command line or a named tool with JSON arguments. Tool behavior, initial files, model, budget, result contents, restrictions, and judge are identical.

Pilot rule: the pass count does not decrease, and the total count of predefined invocation errors is lower; boundary violations are prohibited in both variants. Three pairs do not establish a universal advantage. Fewer calls alone are not an improvement if the outcome is worse.

## Preparation

```bash
npm run lab:new -- --lab LAB22 --session tools-pilot
LAB_DIR='experiments/local-models/measurements/LAB22-tools-pilot'
npm run lab:practice -- --scenario tool-success --session tools-pilot
npm run check
```

Analyze the [synthetic trace](practice.md): tool call ID, name, arguments, result, and model continuation. This is a ready-to-use learning exercise without an API; it does not test a real agent's ability to choose a tool. Save a link to its synthetic manifest in the report; do not create `run_ids` for it.

The primary episode is [API migration](episodes/interface-migration/episode.md) or the existing T002. The public migration first requires registration of a new task ID. T002 retains its contract, seed, and external judge. Verify the selected harness's native tools and ability to remove duplicate tools for the exact version; do not assume that all nine harnesses have identical hooks/MCP/tool registries.

## Procedure

1. **Define identical permissions.** Before implementation, list the operations the episode needs: read a file, search text, apply an edit to an allowed file, run an allowed check. Path, input size, subprocess, and network restrictions must match. Comparing an unrestricted shell with four strictly restricted tools changes both the interface and capabilities; it cannot be presented as the minimal experiment.

2. **Implement two representations of one execution function.** In the command variant, the agent invokes a small CLI with explicit subcommands; in the structured variant, it uses `read_file`, `search_text`, `apply_edit`, and `run_check` tools. These are interfaces to design, not existing repository commands. Both paths call the same testable implementation and receive identical errors and results. Tool names must not reveal the finished patch or fault location. The contract specifies permitted actions, not the solution sequence.

3. **Prepare engineering acceptance in one harness.** Register the tools/command facade, disable bypass through an equivalent native capability, or explicitly acknowledge that the experiment is observational. Record schemas, help text, handler hashes, output limits, and mode in sealed controls and run identity. Retain the native adapter before/after and an assumption entry in the ledger. `--variant without-spec` is unsuitable for this; new parameters must first be implemented and tested.

4. **Prove operation equivalence offline.** For each permitted action, submit identical inputs through both paths and compare workspace changes, exit/result, and response content. Include a missing file, an incorrect field type, a path outside the workspace, a patch conflict, and output beyond the limit. The limit and truncation rule must be identical; truncation itself must be reported. The handler/boundary enforces a prohibited operation, rather than a textual request to the model. Do not weaken the current Docker/network walls.

5. **Define error categories and the stopping rule.** Before the series, specify categories: unknown tool, invalid schema/CLI syntax, prohibited path, execution error on a valid request, and valid invocation with the wrong objective. Keep these cases separate. Count a model error only with a complete trace; a missing tool result is an observability problem. Stop at verdict-ready, overall timeout, budget exhaustion, or a boundary violation. The last condition stops the series until the mechanism is repaired.

6. **Fix three pairs and all constants.** Order: CLI → structured, structured → CLI, CLI → structured. Use one exact model ID, harness image, task/seed, permitted operations, token/time budget, sampling, and initial prompt content. Help/schema differ as part of the intervention and are hashed. Their tokens count: a verbose schema is not free. A protocol debugging pilot is excluded from these six attempts.

7. **Execute only after acceptance.** Create real records using the current lifecycle and the actually accepted interface of the new variant. Save commands in the report. Without the engineering extension, only the offline exercise and mechanism design are available; mark the agent series `not-run`. A local model additionally requires a working LAB08 setup, confirmed tools, and deployment identity.

8. **Evaluate the outcome and invocations.** An independent judge checks artifacts without knowing the variant. A trace analyst labels all tool calls using the predefined categories, with repeated calls marked separately. When uncertain, a second analyst reviews the disputed row. Metrics: verdict, errors of each type, correction of an error by the next call, call count, total input/output tokens, and wall-clock time. Tool JSON response size in bytes can be measured directly; do not call it model tokens.

9. **Compare pairs and decide what to test next.** Show all outcomes and errors, including aborted attempts. Improvement on one simple episode supports another experiment, not universal removal of shell access. To study schema verbosity or `tool result` sizes of 2/8/32 KB, run a **new series with one new factor**, an unchanged interface, and identical useful content. Do not change schema, output cap, and toolset simultaneously in the minimal experiment.

## Results tables

| Operation | CLI representation | Structured representation | Identical permissions | Identical result | Test evidence |
| --- | --- | --- | --- | --- | --- |
| read/search/edit/check, one row each | After implementation | Schema/hash | Paths/limits | Content/error | Synthetic test |

| Pair | Order | CLI run ID | Structured run ID | Different controls fields | Other conditions |
| --- | --- | --- | --- | --- | --- |
| 1/2/3 | Before running | After creation | After creation | Only the interface and its description | Comparable/not comparable |

| Run | Verdict | Invalid tool/schema/syntax | Prohibited path | Execution error | Wrong objective | Calls | Tokens / time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Actual ID | Judge | Separate counts | Separately | Separately | Based on evidence | Total | Measured values/unknown |

## Deliverables

The protocol, equivalent-operation map, schemas/help/handler hashes, offline equivalence test results, ledger row, all six run IDs and evaluations, trace annotations, paired analysis, and limitations. The training trace from `lab:practice` is stored as synthetic evidence, separately from experimental results. Completeness checks: [report-validation.md](report-validation.md).

## Completion criteria

- [ ] The minimal series changes the interface while preserving permissions and operation implementation.
- [ ] Bypass through a second toolset is excluded, or the work is honestly labeled as a different, incomparable design.
- [ ] Schemas and the intervention are versioned; conditions are reflected in controls/record/compare.
- [ ] Three pairs and error categories are defined before execution.
- [ ] All attempts, independent verdicts, and complete invocation annotations are retained.
- [ ] Tool description and correction costs are included; unknown metrics are not replaced by zeros.
- [ ] Unfinished engineering work is not called a measurement; `npm run check` passes.

## Review questions

1. Why do an unrestricted shell and four permitted tools change more than one factor?
2. Where should path validation be enforced: in the tool description or the handler?
3. How does an incorrect argument type differ from a valid request for a nonexistent file?
4. Can a shorter tool result count as an improvement if it hides necessary evidence?
5. Why must tool descriptions be included in the budget?

## Sources

- [Method: tools and trust boundaries](../method.md), [common infrastructure](../../experiments/common/README.md).
- [Public migration episode](episodes/interface-migration/episode.md), [offline practice](practice.md).
- [LAB09](LAB09-agent-campaign.md), [component ledger](../harness-ledger.md), [record schema](../../results/schema.json).
