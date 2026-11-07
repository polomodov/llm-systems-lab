# Native Codex subscription normalization preparation

`SN-C01` is a separate, unstarted subscription-funded condition using Codex 0.167.0 and requested `gpt-6.1-sol` at medium effort. It reuses the immutable native agent and verifier images and public normalization input/oracle. It has its own [contract](contract.md), [plan](plan.json), [record schema](schema.json) and inactive [authorization example](authorization.example.json). Existing API campaigns, HN-O01, budgets, model/image pins and historical results remain unchanged. The separate records stay in this experiment; the root campaign catalog is not extended or relabeled.

The available commands are `plan` and `offline`. There is **no real execution, login or authorization command** in this preparation. The prepared slot record has no start time, verdict or observed live model. An offline task pass is infrastructure evidence, never subscription access, consumed allowance or live-model qualification.

## Authorization isolation

A later separately authorized attempt would require a dedicated, user-performed ChatGPT login in a private profile outside the public checkout. Do not mount or reuse the desktop/host `~/.codex`, keyring, full HOME, repository, `.env`, SSH agent or Docker socket. The runtime receives one fresh scoped copy of that profile through an explicit secret channel; it must be writable for native refresh and discarded after teardown. Do not copy refresh updates back into a shared desktop login. A future persistence change requires a recorded protocol revision. Keep account/operator approval and actual account ID separate from the secret; the account alias is an audit assertion, not proof of identity.

Enforce `forced_login_method="chatgpt"`, file-only credential storage, fresh HOME/CODEX_HOME, disabled app/plugin discovery, and no API environment variables. Verify native login mode and account binding before any model request. The runtime and verifier run as UID1000, with read-only roots, bounded writable temporary directories, dropped capabilities and no host mounts. The selected subscription credential is accessible to the agent process; scope isolation cannot hide it from that same user. Export only declared public result/evidence paths, never `auth.json`, a profile directory or token-bearing diagnostics. The verifier gets no profile or credentials.

The offline test uses invented JWT/refresh values created only inside the disposable container. A separate API-auth fixture is rejected by the native subscription-only profile before any backend request. No host auth file or credential store is read. Dummy credentials and a self-signed loopback certificate cannot authenticate to OpenAI. The TLS private key is removed from the host scratch directory after upload; fake auth remains in the container's private tmpfs and disappears during teardown.

The selected subscription backend differs from the API-only allowlist. Real networking/refresh routing is **not configured or qualified** here. A later launch needs a reviewed scoped allowlist for the native ChatGPT backend and login/refresh destinations, without adding generic task network access. No real account-side check is performed now.

## Quota accounting

Native `account/rateLimits/read` responses are collected before and after execution through an ephemeral stdio app-server in the same private profile. No thread/turn is started by the quota reader. `account/read` confirms the native auth type; the full quota response binds the backend account ID. Native `ordinaryUsageAllowed` must be true: displayed percentages alone do not establish admission. Check every reported bucket, both windows, reset times, plan type and credit metadata. Missing data remains unknown. Full snapshots are used; sparse notifications cannot establish an empty quota bucket or a complete zero.

Proposed thresholds are 20 percent minimum remaining and a 5 percentage-point observed delta target, subject to later explicit approval. They are heuristics, not hard caps. Unknown/credit-backed allowance, account mismatch, insufficient allowance or snapshots older than 60 seconds block readiness. A positive readiness result still has `execution_authorized=false`.

Reconciliation preserves shared-account percentage-point deltas and raw snapshots. Reset/window/bucket/account/plan changes and decreasing usage invalidate deltas. Concurrent activity and rounded displays prevent exact per-run attribution; a displayed zero delta is not zero consumption. `exact_run_quota_consumption` and `cost_usd` stay null. Do not convert percentages or token counts into API bills, allocate subscription fees arbitrarily, claim free/unlimited usage or transfer the API pilot budget. There are no credit purchases, reset redemptions, API fallbacks or automatic retries.

The new subscription condition does not weaken the API-funded accounting gate. Missing nested permission coverage remains explicit and cannot establish full harness qualification. Actual subscription/model availability, live identity/transport, quota behavior, refresh, shared activity and any risk of consuming existing paid credits need account-side verification only after authorization.

## Offline checks

```sh
mise exec -- python3 experiments/codex/subscription-pilot/offline.py plan
mise exec -- python3 -m unittest discover -s experiments/common/pilot-execution -p test_subscription.py -v
mise exec -- python3 experiments/codex/subscription-pilot/offline.py offline \
  --docker-host unix:///Users/apolomodov/.colima/default/docker.sock
mise exec -- python3 experiments/codex/subscription-pilot/check.py
mise exec -- npm run check
```

The actual pinned native CLI signs into the **invented** ChatGPT profile, reads account/quota snapshots, runs the normalization tool loop against a local fixture, and sends only its bounded regular artifact to the frozen verifier. Docker network is `none`; the local TLS endpoint uses certificate validation with a dedicated fixture CA. Offline endpoint overrides use an explicitly named custom provider with native OpenAI authentication; the pinned CLI rejects overriding its reserved built-in provider. This tests the native subscription credential and quota interfaces, not the real hosted endpoint, workspace policy or refresh service. No HTTP proxy, package download or real provider is involved in the control. Raw evidence and failed-control records remain locally under ignored `.cache/`; a clean checkout must reproduce them.

`preservation.json` protects the prior 1,673-file result/preparation inventory plus the original pilot-execution sources/checkpoints and Codex profile. The global ledger gains the new component row only. Prior checkpoints retain their historical source hashes; the standalone subscription checker validates preservation and this new source revision without rewriting them. No old record is reclassified as a subscription result.

Official sources checked 2026-11-07: [authentication](https://learn.chatgpt.com/docs/auth), [native account/rate-limit interface](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt), [non-interactive use](https://learn.chatgpt.com/docs/non-interactive-mode). The docs support scoped credential storage and native quota observations; isolation thresholds, proposed quota targets and preservation requirements are this lab's protocol. Subscription authorization caches must never enter public CI. No real sign-in or run has been performed.

The original `offline-evidence.json` retains the initial preparation checkpoint. `pr-evidence.json` records verification after integration with the current main branch, including generated status freshness and the pinned `mise run verify` checks. Both checkpoints and the original raw controls remain retained.
