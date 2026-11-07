# Controlled pilot execution and independent evaluation

This change closes the offline orchestration/procedure gaps identified after PR4. It does not authorize model requests or change the frozen campaigns, native pilot plans, budgets, images or existing run records. Historical inputs/checks remain untouched. All experiments in this directory use invented responses/checkers in separate scratch catalogs.

## One Harbor Trial

`single_trial.py` uses pinned Harbor's real `Trial.create()` / `Trial.run()`, the original native adapter and the frozen separate verifier. It never creates a Job, schedules a batch, retries an attempt or advances to the next slot.

- `plan` reads non-secret metadata only. `offline` creates a new isolated lab catalog under `.cache/`, copies the already materialized networkless HN-O01 package and runs native Codex against the in-container loopback fixture. No existing prepared record is reused. The copied package is explicitly an offline condition, not the later provider-allowlisted task.
- Future `execute` requires an operator-owned, non-group/world-writable exact-run authorization file. It binds run/slot, input/plan hashes, runner/common/accounting source hashes, one Trial, the USD 2 target, expiry, operator and billing project. The example is deliberately inactive. A global exclusive coordinator lock and the existing ordered admission gate reject concurrent execution, skipped attempts, failed qualifications and unsettled prior billing.
- Harbor checkout identity/cleanliness, sealed record/package integrity and exact image/version are checked before any credential read. Only the selected literal key is read from root `.env` after authorization/admission; host auth/HOME and unrelated environment variables are not reused. Credentials enter `agent.env`, not the environment/verifier configuration. Logs/configuration are redacted before sealing. No authorization is embedded in or retroactively added to an old plan.
- An exclusive execution claim and start receipt precede the Trial. The coordinator records native logs/ATIF, independent verifier/artifact output, source snapshots, image/mount observations, task digests, lifecycle hooks and teardown. A collection seal catches later evidence modification. The agent and verifier retain their native phase policies and UID1000. Harbor's DNS/ICMP allowance remains a known limit; this is not lab-gateway parity.
- Trial agent/verifier limits remain 180/60 seconds from the sealed contract. A separate 480 second outer coordinator watchdog covers setup/teardown too; it does not enlarge the agent's 180 seconds. Setup failure, timeout and cleanup problems preserve evidence and block admission. A host/daemon crash can leave an exclusive lock/claim and a `running` record; inspect owned resources and receipts manually before recovery, never delete the claim or rerun that ID silently.
- `execute` stops after collection. A record remains `running` with a separate `collected-awaiting-finalization` receipt while independent billing is pending; it does not mean an agent is still running. Do not use the ordinary lab coordinator's reconciliation command on this separate native lifecycle. No second slot can pass admission in that state.
- Future `finalize` requires settled billing attributed to this run/provider/authorized project, a hashed provider export and an explicit attribution method. Native estimates and fixture usage are insufficient. Explicit raw evidence pointers supply only available response identity/usage; missing fields stay null. Valid task output can be `completed/pass` with **inconclusive qualification**. No next-slot admission follows automatically.

The full offline Trial demonstrates this last distinction: independent task reward 1 and valid ATIF, but unknown observed live-model identity and cost, so qualification remains inconclusive. It is synthetic infrastructure evidence, never a new campaign outcome.

From repository root, with pinned Node and Harbor Python:

```sh
mise exec -- experiments/common/harbor-interop/.venv/bin/python experiments/common/pilot-execution/single_trial.py plan
mise exec -- experiments/common/harbor-interop/.venv/bin/python experiments/common/pilot-execution/single_trial.py offline \
  --docker-host unix:///Users/apolomodov/.colima/default/docker.sock \
  --docker-plugin-dir experiments/common/harbor-interop/.cache/docker-plugins
```

The future production interface is `execute --run-id <prepared-id> --authorization <operator-file>` followed separately by `finalize --run-id <id> --billing <receipt> --observations <raw-provenance-pointers>`. Authorization, billing, observations and the referenced billing export must be flat filenames inside `experiments/common/pilot-execution/.cache/operator/`. Stage operator-owned regular files there only after the relevant approval; symlinks, hard links, traversal, group/world writable files and files over 2 MB are rejected. Both commands refer only to this repository's frozen prepared records. These commands were **not executed** against a real provider. No active authorization file is supplied. A model-access test is a separately accounted real attempt, not an extra unbudgeted preflight.

See [authorization.example.json](authorization.example.json), [billing.example.json](billing.example.json) and [observations.example.json](observations.example.json). Authorization placeholders must be replaced only after separate explicit spending approval. The program target remains USD 12, with USD 6 per provider and USD 2 per attempt; these are observed targets and may overshoot through in-flight requests/native retries. The campaign's separate USD 12 allocation cannot fund this pilot implicitly.

## Independent T002/T004 evaluation

Follow [EVALUATION.md](EVALUATION.md). `evaluation.mjs` exports only sealed public contracts/descriptors plus copies of final workspace/artifacts. An independent evaluator receives the `submission/` directory, not the private run/actor binding, provider configuration, `.env`, hidden lab sources or historical traces. Opaque contents/branch names can reveal harness identity; this is metadata minimization, not guaranteed blinding.

The separate evaluator uses `evaluator_container.py` with a trusted checker package obtained independently at the agreed revision. The container has network none, no keys/socket, UID1000, read-only root and exactly two read-only input mounts. Checks run against a writable disposable copy; original result bytes are never edited. The existing immutable lab Codex image is reused only for Node/git tooling; no Codex process is launched. The wrapper records logs, exit status, image/check-package hashes and unchanged inputs, but leaves result/evaluator/interpretation blank.

The evaluator supplies the actual judgment. The coordinator validates separate actor identity, exact submission/check revision, artifact/workspace hashes and log hashes, rejects infrastructure errors, then uses the existing `judge-run` importer. No result is inferred from exit0. No real hidden check was read or executed during preparation. Actual evaluator assignment, pinned checker revision/calibration and live billing/access are still prerequisites for later real execution.

## Offline checks and evidence

```sh
mise exec -- node --test experiments/common/pilot-execution/evaluation.test.mjs
mise exec -- python -m unittest discover -s experiments/common/pilot-execution -p 'test_*.py' -v
mise exec -- experiments/common/harbor-interop/.venv/bin/python experiments/common/pilot-execution/offline_evaluation_smoke.py \
  unix:///Users/apolomodov/.colima/default/docker.sock
mise exec -- experiments/common/harbor-interop/.venv/bin/python experiments/common/pilot-execution/check_offline.py
mise exec -- npm run check
```

Unit tests exercise synthetic T002/T004 handoffs, independently supplied fail verdicts, existing judge import, altered input/log/check revisions, solver-as-judge rejection, exact authorization, concurrency, missing billing and modified collection evidence. CI runs only these unit tests; no Docker Trial or model request is started by default.

[offline-evidence.json](offline-evidence.json) binds the accepted full native Trial, two separate evaluator-container probes with invented checks, test logs and current sources. Raw scratch records, Trials and evaluator logs remain local under ignored `.cache/`; the read-only validator requires those bytes. A clean checkout must repeat/rematerialize the offline probes. [preservation.json](preservation.json) protects existing result/preparation evidence. No old result is rewritten to claim this new orchestration was tested previously.

## PR5 review checkpoint

`offline-evidence.json` retains the initial preparation checkpoint from commit `210ec37`. `review-evidence.json` records fresh validation after review fixes; `check_offline.py` validates the newest available checkpoint and the unchanged 1,673-file preservation inventory. Old raw Trial/evaluator evidence and historical results are retained.

## HN-O01 observations and billing

[HN-O01.md](HN-O01.md) documents the added native measurement collector, response-level model confirmation, loopback-only tool-decision telemetry and strict operator-export reconciliation. HN-O01 provenance is now generated/recomputed from the sealed collection; `finalize` needs its reconciled billing receipt and no manual `--observations` file. Other slots retain their existing interface. New permits must additionally bind collector, reconciler and telemetry-sink hashes. `hn-o01-evidence.json` retains the initial checkpoint; `hn-o01-review-evidence.json` is the current review checkpoint. It retains a fresh full native Trial and pinned source inspection, with nested-exec permissions explicitly unavailable rather than inferred zero. Full qualification remains blocked by that missing counter under the unchanged accounting gate. These sources add observation only; all historical checkpoints and frozen campaign/native inputs are preserved.
