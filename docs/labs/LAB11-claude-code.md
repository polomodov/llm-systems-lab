# LAB11. Claude Code: autonomous fixes, limits, and complete usage

## Profile

| Field | Value |
| --- | --- |
| Harness | `claude-code`, CLI `@anthropic-ai/claude-code@2.1.83` |
| Prerequisite | [LAB01](LAB01-reproducibility.md); Node.js ≥22, Git, Bash, Docker Engine; coordinator running as a regular user |
| Main route | Anthropic API, `ANTHROPIC_API_KEY` from `.env`; no local bridge required |
| Minimum scope | Offline adapter and image verification, one real A2/T002 baseline with independent evaluation |
| Extensions | Three repetitions; T001 discovery/replay; T003; `without-spec`; separate `hard` verification |
| Time | Estimate: 2–3 operator hours, with build and evaluator time separate; one agent execution is limited to 900 s |
| Readiness | Adapter implemented, installation verified on 2026-09-20 on Linux/arm64; results on the learner's machine and the real episode remain `not-run` until execution |

## Objective

Execute a reproducible episode in Claude Code and establish which data support the result: artifacts and external evaluation, observed model ID, complete final usage, and stopping reason. Check the distinction between a turn-count limit, USD policy, and external timeout.

## Hypothesis

Claude Code `2.1.83` with the baseline specification can complete one A2/T002 in the designated environment, and its final `result` allows turns, tokens, and CLI-reported cost to be reconstructed without double-counting cache and `modelUsage`. Task execution and metric completeness are separate outcomes: a task `pass` does not prove complete accounting.

Before execution, record the exact model ID, expected artifacts, stopping rule, and hypothesis-testing rule. One episode's result does not generalize to every task or model.

## Preparation

Run all commands from the repository root. Replace `my-session` if that report already exists; the helper does not overwrite directories. Replace the angle-bracketed values below before execution. After a nonzero exit code, preserve the error and stop dependent steps: an old image tag or file does not confirm that a new command succeeded.

```bash
npm run lab:new -- --lab LAB11 --session my-session
LAB_DIR='experiments/claude-code/measurements/LAB11-my-session'
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
node --version > "$LAB_DIR/raw/node-version.txt"
git rev-parse HEAD > "$LAB_DIR/raw/git-revision.txt"
git status --short > "$LAB_DIR/raw/git-status.txt"
docker version > "$LAB_DIR/raw/docker-version.txt"
npm run check
```

Read the [A2 specification](../../agents/a2-janitor/spec.md), [public T002 contract](../../tasks/T002-repo-janitor/task.md), [profile](../../experiments/claude-code/harness.json), [settings](../../experiments/claude-code/settings.example.json), and [shared evaluation protocol](harness-workflow.md). Do not read `tasks/*/check/` or modify task contracts. Arrange the judge and `hidden-check` method before execution.

Prepare only `ANTHROPIC_API_KEY` in the existing `.env` using an editor. If the file does not exist, create it from `.env.example` without overwriting an existing file. Do not put key values in commands, reports, or logs; the profile passes the credential to container processes but does not mount the host `.env` file. The key is accessible to tools inside that container: this environment limitation is described in the [shared infrastructure](../../experiments/common/README.md).

The profile supports `anthropic` and API domain `api.anthropic.com` but does not guarantee that the account can access a particular model. Select an exact available ID from your API access, without `latest`, `sonnet`, `opus`, or another floating alias. Record the source confirming availability without secrets. Neither a local Claude subscription nor the host CLI version replaces API access or the image's version.

## Procedure

1. **Check the adapter without a model.** Preserve output and exit code; on error, stop preparation and describe the reason.

   ```bash
   node --test experiments/claude-code/adapter.test.mjs > "$LAB_DIR/raw/adapter-tests.txt" 2>&1
   ```

   Explain four cases using the tests: final `modelUsage` is not added again to `usage`; incomplete cache buckets yield unknown input; the ID from the main assistant response differs from a subagent's model; error subtype takes precedence over exit 0. These synthetic cases are not T002 success.

2. **Build and freeze the image.** Installation requires network access; subsequent smoke commands run without network or credentials. Preserve one image ID for the entire series; pinning the CLI does not make a fresh system-package build bit-for-bit identical.

   ```bash
   docker build --build-arg HARNESS_VERSION=2.1.83 \
     -t harness-lab/claude-code:2.1.83 \
     -f experiments/claude-code/Dockerfile experiments/claude-code \
     > "$LAB_DIR/raw/build.txt" 2>&1
   IMAGE_REF=$(docker image inspect --format '{{.Id}}' harness-lab/claude-code:2.1.83)
   docker image inspect "$IMAGE_REF" > "$LAB_DIR/raw/image.json"
   docker run --rm --network none "$IMAGE_REF" claude --version > "$LAB_DIR/raw/cli-version.txt"
   docker run --rm --network none "$IMAGE_REF" claude --help > "$LAB_DIR/raw/cli-help.txt"
   docker pull node:24.13.1-bookworm-slim > "$LAB_DIR/raw/proxy-pull.txt" 2>&1
   PROXY_IMAGE=$(docker image inspect --format '{{.Id}}' node:24.13.1-bookworm-slim)
   docker image inspect "$PROXY_IMAGE" > "$LAB_DIR/raw/proxy-image.json"
   ```

   Verify the actual version `2.1.83`. Find `--max-turns`, `--max-budget-usd`, `--permission-mode`, `--settings`, `--setting-sources`, and `--output-format` in the saved help. Confirm `DISABLE_AUTOUPDATER=1`, `dontAsk` mode, and empty external setting sources in the adapter. Note that `settings.json` allows tools inside the external Docker boundary; the settings file itself does not isolate hidden checks.

3. **Register the minimum: one new T002.** Record `baseline`, `observed`, timeout 900, and image IDs in the report manifest beforehand. The main route selects a shared budget policy for comparisons with other harnesses: the USD cap is not applied here, while native max-turns remains. Limits come from the contract and are not edited in the task.

   ```bash
   MODEL_ID='<exact available Anthropic model ID>'
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a2-janitor --task T002 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<ID printed by new-run>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Copy the actual ID into the report's `manifest.json`. Check `results/runs/$RUN_ID/inputs/manifest.json`: harness, provider, variant, seed commit, and files. The agent snapshot must not contain hidden checks or `.env`. Do not manually change the snapshot/workspace after prepare.

4. **Execute the cloud episode.** This command calls the selected account's paid API; `observed` does not cap the USD bill.

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode observed
   ```

   Check `run.json`, `trace/harness-version.txt`, `trace/stdout.jsonl`, `trace/stderr.txt`, `trace/change.patch`, and `artifacts/report.md`. Do not fix the result manually. `awaiting_review` means ready for evaluation; preserve `aborted` with its reason. A retry after an error gets a new ID; the previous attempt remains in the report.

5. **Audit the trace for this harness.** In the main `result`, find `num_turns`, `total_cost_usd`, `usage`/`modelUsage`, `session_id`, and stopping reason. Compare them with `run.json`. For input, use either a complete `modelUsage` breakdown or complete `usage`: input + cache creation + cache read. Do not add two representations of the same work. Separately compare requested `model.id` with `model.observed_id` from the main `assistant.message.model`. If no observation exists, preserve the unknown; on model drift, the current runner should abort the attempt.

   Preserve the explanation for every unknown field in `metrics_unavailable`. CLI USD is harness-reported cost, not a billing reconciliation; compaction/subagent counts are unknown without a complete counter. Do not publish an entire raw trace without checking for sensitive task content.

6. **Obtain an independent evaluation.** Generate JSON only for `awaiting_review`:

   ```bash
   (
     set -o noclobber
     npm run --silent evaluation-template -- --run "$RUN_ID" > "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   )
   ```

   The external evaluator checks T002 using the [procedure](harness-workflow.md), fills in `result`, `evaluator`, `check_output`, and optionally `human_notes`, preserving generated hashes. The agent container receives neither the check, its answer, nor an opportunity to fix the result after evaluation. Import only the completed evaluation:

   ```bash
   npm run judge-run -- --run "$RUN_ID" --evaluation "$LAB_DIR/raw/evaluation-$RUN_ID.json"
   npm run check
   ```

   `fail` and `partial` are valid scientific results of completed work. Without an independent judge, the run remains `awaiting_review`, and the minimum lab is incomplete. Do not judge `aborted`; preserve the error and create a new pilot if a completed episode is needed.

7. **Extension: three repetitions and ablation.** Before execution, assign three baseline slots, three `without-spec` slots, alternating order, and fixed conditions. Create each slot using step 3 with a new ID; for ablation, use the following instead of baseline preparation:

   ```bash
   npm run prepare-run -- --run "$RUN_ID" --variant without-spec --provider anthropic
   ```

   This is alternative preparation of a new record, not re-preparing an existing one. Perform steps 4–6 for every slot. The minimum T002 serves as a pilot and admission to LAB09; comparison baseline/without-spec triples always contain new attempts. Preserve started failures and do not select only successful IDs. Compare the assigned IDs:

   ```bash
   SERIES_RUN_IDS='<all assigned run IDs separated by commas>'
   npm run --silent compare -- --runs "$SERIES_RUN_IDS" > "$LAB_DIR/raw/compare.json"
   ```

   `without-spec` removes only the specification text from the prompt. Docker, gateway, and independent judge remain. See [LAB10](LAB10-ablation.md) for paired-outcome interpretation and the ledger; do not label unfinished groups `pass^3`.

8. **Extension: T001 replay and T003.** For a separate discovery T001, create a new record and prepare it without an archive:

   ```bash
   AS_OF_DATE='<fixed YYYY-MM-DD date>'
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a1-dossier --task T001 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<new discovery ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic --as-of "$AS_OF_DATE"
   ```

   Perform steps 4–6; T001 uses `rubric`, and the evaluator also uses its designated source check. Preserve the `trace/sources.jsonl` archive with response bodies and statuses. Then create another T001 using `new-run` above, assign its new ID, and use alternative preparation:

   ```bash
   SOURCE_ARCHIVE='<path to discovery run trace/sources.jsonl>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic \
     --as-of "$AS_OF_DATE" --source-archive "$SOURCE_ARCHIVE"
   ```

   Repeat execution and independent judging. A controlled T001 series uses one archive and date; live discovery is excluded. For T003:

   ```bash
   npm run new-run -- --harness claude-code --harness-version 2.1.83 \
     --agent a3-ledger-auditor --task T003 --provider anthropic --model "$MODEL_ID"
   RUN_ID='<new T003 ID>'
   npm run prepare-run -- --run "$RUN_ID" --variant baseline --provider anthropic
   ```

   Perform steps 4–6 using `rubric`; submit `ledger.md` and `ablation-plan.md`. T003 configurations differ across harnesses, so this audits a specific Claude deployment.

9. **Claude extension: `hard`.** Create and prepare a separate baseline T002 with step 3 commands, then run:

   ```bash
   npm run run -- --run "$RUN_ID" --image "$IMAGE_REF" --proxy-image "$PROXY_IMAGE" \
     --model "$MODEL_ID" --provider anthropic --timeout 900 --budget-mode hard
   ```

   Preserve launch limits, actual stopping reason, and reported cost. Staying within budget in one short episode does not prove behavior when the limit is exhausted; if not reached, record “limit enforcement was not observed”. Do not change the task contract to reach the limit. Obtain evaluation according to run state. `hard` and `observed` remain separate comparison groups.

10. **State the conclusion and record observations.** Add actual IDs, conditions, and shortcomings to `experiments/claude-code/NOTES.md`; a new component requires a new [ledger](../harness-ledger.md) row, while the existing adapter is L008. Put infrastructure smoke tests and experiments in separate report rows.

## Results tables

| Environment check | Observed result | Exit code | Evidence |
| --- | --- | --- | --- |
| CLI version, image ID/architecture, proxy ID, parser tests | Fill in after execution | Fill in | Relative path in `raw/` |

| Slot before execution | Task/variant/budget | Run ID | Status | Evaluator verdict | Stop reason | Wall-clock, s |
| --- | --- | --- | --- | --- | --- | --- |
| Fill in | T002/baseline/observed | After new-run | After run | After judge | From record | From record |

| Metric | Value or `null` | Unit/definition | Evidence | Reason for absence |
| --- | --- | --- | --- | --- |
| Requested/observed model; turns; input/cache/output; cost | Fill in | Do not mix buckets | Run ID + field/event | Fill in for `null` |

| Additional series | Preassigned IDs | Outcomes | What changed | Permitted conclusion |
| --- | --- | --- | --- | --- |
| Repetitions/ablation/replay/hard | Fill in if executed | All outcomes | One condition | With limitations |

## Deliverables

- `report.md`, manifest with the pre-run hypothesis, `run_ids`, and evidence references; completed tables.
- Adapter-test output, build/version/help, immutable IDs, and image architectures.
- At least one real T002 with artifacts, original trace, patch, and external evaluation linked to manifests; include all failed attempts alongside it in the ID list.
- Usage and model-identity audit, review-question answers, and NOTES entry; extension results only if executed.

## Completion criteria

- [ ] Exact version and image confirmed on your machine; parser tests pass.
- [ ] One T002 completed the lifecycle to `completed` with an independent `pass`, `fail`, or `partial`; installation error or `awaiting_review` is recorded as incomplete.
- [ ] Main `observed` budget and timeout 900 explicitly recorded; optional hard is not mixed into the main group.
- [ ] `result`/`modelUsage` is not double-counted; unknown metrics are not replaced with zeros.
- [ ] Requested and observed models are distinguished, as are the task and smoke test.
- [ ] The report contains no credentials, hidden checks, or manually corrected results; `npm run check` passes.

## Review questions

1. How does `modelUsage` differ from `usage`, and why must they not be added?
2. How does `observed` change Claude's launch, and which limit remains enforced?
3. Why do `dontAsk` and an allowed `Bash` tool not give the agent the host workspace?
4. Why is the main `assistant.message.model` more useful than `init.model` for identity verification?
5. How should `error_max_turns` be interpreted with exit 0 and an existing `report.md`?
6. What observation would actually confirm USD-cap enforcement?
7. What remains unchanged in `without-spec`, and why is that required?

## Sources

- [Claude Code README](../../experiments/claude-code/README.md), [profile](../../experiments/claude-code/harness.json), [adapter](../../experiments/claude-code/adapter.mjs), [tests](../../experiments/claude-code/adapter.test.mjs), [Dockerfile](../../experiments/claude-code/Dockerfile).
- [Protocol](../method.md), [shared infrastructure](../../experiments/common/README.md), [independent evaluation](harness-workflow.md), [LAB10](LAB10-ablation.md).
- This lab's commands and interpretations are pinned to the current repository sources and CLI `2.1.83`; verify version and actual API access during execution rather than inferring them from the document date.
