# Subscription normalization pilot

This separate infrastructure condition uses native Codex CLI and ChatGPT subscription authentication. It does not replace a campaign slot or the API-funded HN-O01 condition. The public input and independent normalization oracle retain their existing bytes. The new public instruction changes only the network-boundary sentence.

## Limits

One attempt only, with no automatic retry or continuation. Agent execution has a 180-second external timeout; independent verification has a 60-second timeout. Eight completed model responses are an observed target, not a native hard turn cap. Per-run USD cost is unavailable, not zero; the subscription fee is not allocated to this attempt using API token prices.

Proposed quota admission requires fresh observations for all reported buckets and both quota windows, at least 20 percent remaining, backend ordinary-usage permission, and explicit absence of credit-backed usage. The proposed observed delta target is 5 percentage points per window. These thresholds are unapproved heuristics and cannot enforce a hard quota ceiling; in-flight work can overshoot. A missing, stale, reset, changed-account or credit-ambiguous observation stops admission/reconciliation. No purchase, reset redemption, API fallback or automatic second attempt is permitted.

## Isolation and evidence

Use a fresh private HOME and CODEX_HOME, file credential storage and forced ChatGPT login. Do not reuse host authentication, keyring, configuration, agents, hooks or an API key. The agent's selected credential remains accessible to that same native process/user; this is scope isolation, not credential secrecy from the agent. The verifier receives only a bounded regular result artifact and its immutable oracle, with no credentials, account session, host HOME, source checkout or Docker socket.

Retain native terminal/response logs, exact image/version, input/output hashes, separate verifier report, private-runtime boundary metadata and native full quota RPC snapshots. Preserve reset times, bucket IDs, account binding and retrieval times. Quota observations are rounded and shared with other account activity; exact run consumption remains null even if the displayed delta is zero. Missing permission measurements remain unknown, as in the reviewed HN-O01 collector. Model reroutes cannot be replaced with the requested model ID.

No real execution is implemented or authorized in this preparation. A later attempt needs an explicit scope-bound authorization, separate user login, verified live network/refresh policy, real model access and approved quota conditions. Stop after the attempt and reconcile evidence; never infer campaign admission from a synthetic pass.
