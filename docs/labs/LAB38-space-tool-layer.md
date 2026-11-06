# LAB38. Tool layer: SPACE as an executor for any harness

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisites | [LAB36](LAB36-space-deploy-smoke.md) on the machine; the dedicated lab for each chosen harness (e.g. [LAB11](LAB11-claude-code.md), [LAB17](LAB17-openhands.md)) through a Docker T002 pilot |
| Design | The harness runs in the runner's regular container; agent commands and file operations execute in a SPACE sandbox through a narrow tool interface |
| Minimum | Tool server in `experiments/space/tools/` with offline tests, integration with two harnesses, one T002 per harness with built-in shell/file tools disabled |
| Extensions | The same client through ECW and E2B SDK (`docs/ecw.md`), accounting for 501 responses; per-call overhead measurement |
| Time | Allow 1–2 engineering days plus runs |
| Readiness | `implementation-required` |
| Initial state | Experiment `not-run`; educational manifest `not-started` |

## Objective

Build the first layer over the platform: a tool server through which any harness executes code in SPACE, and test whether this narrow interface suffices for a real task. This reverses [LAB37](LAB37-space-harness-vm.md): there the agent lives in the VM; here only its actions go to the VM.

## Hypothesis

Four tools — `run_command`, `read_file`, `write_file`, `list_dir` — over the native SPACE API suffice for both chosen harnesses to solve T002 with the same verdict as their Docker pilots, without built-in shell/file tools. Median SPACE overhead per `run_command` (create session → `process_exited` for `true`) does not exceed a threshold fixed in the protocol before measurement.

## Preparation

- Example client: `examples/llm_agent.py` from draft PR polomodov/SPACE#1: command session, `events_url` validation, SSE, base64 frames, `process_exited`, sandbox deletion in `finally`.
- Harness transport: MCP where the pinned version supports it (Claude Code; OpenHands SDK—check 1.49.2 documentation), or native SDK custom tools (Pi—check `docs/sdk.md` at tag v0.73.1). Support not confirmed by pinned-version documentation is `unverified`.
- Record the two selected harnesses and overhead threshold in `raw/protocol.md` before the first run.

```bash
npm run lab:new -- --lab LAB38 --session ryzen-01
LAB_DIR='experiments/space/measurements/LAB38-ryzen-01'
```

## Procedure

1. **Tool contract.** Describe each tool's schema in `experiments/space/tools/README.md`: inputs, limits (command timeout, output size, middle truncation), error format and persistence between calls (files yes, shell state no). One sandbox per episode; only the server sees its ID.

2. **Implementation.** The server creates a sandbox at episode start and deletes it at completion, logging every call (tool, duration, exit code, output size) as JSONL. The runner's environment supplies the SPACE token to the server; it never enters agent context.

3. **Offline tests.** Fake control/data plane (as in SPACE PR tests): a nonzero code is a result, not an error; SSE termination without `process_exited` is an error; a foreign `events_url` receives no token; sandbox deletion after failure.

4. **Harness integration.** For each chosen harness, create a profile variant with built-in shell/file tools disabled and the server connected. A profile change gets a ledger row.

5. **Overhead measurement.** 30 `run_command('true')` calls and 30 `write_file`+`read_file` calls on 4 KiB; raw durations in `measurements.tsv`.

6. **T002 episodes.** One attempt per harness through the full `new-run → prepare-run → run → judge-run` cycle. Compare with that harness's Docker pilot.

7. **Extension: ECW.** The same scenario through `e2b-code-interpreter` using the SPACE ECW address. Record SDK methods that return 501 or behave differently.

## Results tables

**Overhead**

| Operation | N | Median, ms | p90, ms | min / max, ms | Protocol threshold |
| --- | --- | --- | --- | --- | --- |
| run_command(true) | | | | | |
| write_file + read_file 4 KiB | | | | | |

**Episodes**

| Run ID | Harness | Tools | Verdict | Tool calls | Turns | USD | Wall-clock, s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | built-in (Docker pilot) | | | | | |
| | | SPACE tools | | | | | |

**ECW extension**

| E2B SDK method | Expected | Actual (code/response) |
| --- | --- | --- |

## Deliverables

- Server code and tests in `experiments/space/tools/`, profile variants, ledger rows.
- Report with protocol, tables and tool-call JSONL.
- `run.json` and verdicts for both episodes.

## Completion criteria

- Server offline tests pass in `npm test`; `npm run check` passes.
- Both harnesses executed T002 with built-in tools disabled; verdicts are independent.
- Overhead measured from raw data; threshold hypothesis accepted or rejected.
- SPACE token absent from agent traces.

## Review questions

1. Which built-in tool capabilities did the agent miss, and how does the trace show it?
2. Why does the lack of shell state between calls change agent behavior?
3. How does this layer's trust boundary differ from the LAB37 design?
4. Which ECW responses prevent using existing E2B agents unchanged?

## Sources

- SPACE: `docs/using-api.md`, `docs/ecw.md`, `examples/first_sandbox.py`; PR polomodov/SPACE#1 (`examples/llm_agent.py`).
- This repository: profiles and READMEs of the chosen harnesses, [harness-workflow](harness-workflow.md), [ledger](../harness-ledger.md).
- Pi SDK v0.73.1: `packages/coding-agent/docs/sdk.md`; OpenHands SDK 1.49.2 MCP documentation (verify against the tag).
