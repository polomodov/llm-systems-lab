# HN-O01 measurement, identity and billing procedure

Scope: the frozen first native slot `HN-O01` / `2026-11-07-harbor55-hn-o01`, Codex 0.167.0, requested `gpt-6.1-sol`, medium effort. This procedure supplies observation instrumentation; it does not authorize spending, change model/inference settings, rewrite prepared inputs, or qualify another harness. The immutable agent/verifier images and direct provider route remain in use. Collector, reconciler and local telemetry sink source hashes must be included in the separate exact-run permit and are retained with the Trial.

## Capture before evidence sealing

The coordinator opts into the pinned native SSE response trace and server-reported-model logs with `RUST_LOG`. It configures native OTLP JSON logs to a disposable receiver bound to `127.0.0.1:8769` **inside the agent container**. No additional external host is allowlisted; the sink never forwards data, logs headers, receives a provider key or runs in the verifier. User-prompt export is disabled, native analytics/metrics/trace exporters are disabled. Tool-event logs may contain task data; retain them with the protected raw run evidence. The receiver is removed with the owned agent environment. Existing credential redaction runs before the collection is sealed.

`hn-o01-measurements.json` binds the run, synthetic/live evidence class, collector hash, exact source file hashes, response-ID set and derived values. Finalization recomputes the measurements and rejects changed bytes or operator metric/identity overrides. Only the live class can supply live observations. Offline controls retain synthetic values in this separate report; their run record still has null observed identity, usage and billing and remains inconclusive.

| Field | Source and condition |
| --- | --- |
| Input/output tokens | Sum unique `token_usage_record.response_id` values in the complete root rollout; reconcile with terminal JSON usage and available SSE response usage. Cached input is already included; reasoning output is already included. Never sum cumulative checkpoints. |
| Turns | Completed model responses with unique response IDs, not Codex user turns or failed transport attempts. This is a native observation condition, not cross-harness turn parity. |
| Tool operations | Native function/custom/local-shell call records in the complete rollout. Tool execution and task success are separate observations. |
| Compactions/subagents | Compacted records and child rollouts in the complete collected session tree. Additional sessions, missing ordinals, unsupported record types or incomplete terminal events stop this single-root mapping. |
| Permission requests | User-sourced native `codex.tool_decision` events, only when every eligible nested tool result has a matching decision and all native outer calls have telemetry results. Missing/partial/duplicate/unbound telemetry leaves the counter null. Approval policy alone cannot establish zero. |
| Wall time | Harbor `agent_execution` finish minus start, excluding setup and verifier. |
| Model identity | SSE `response.completed.response.model`, matched to every native response ID, or native server-model metadata events on the complete thread. Config/turn-context/ATIF model labels are never identity. Any observed mismatch is retained as a mismatch. |

SSE payload tracing is exercised with the actual pinned native CLI. Native server-model reporting is based on provider `openai-model` response metadata; the WebSocket timing trace does **not** expose every raw response and is not used as proof. If the live WebSocket route supplies insufficient model metadata, identity remains unknown; do not force HTTP, add a proxy or substitute the requested ID silently. A transport/instrumentation change requires a separately recorded condition.

Pinned source inspection: upstream Codex tag `rust-v0.167.0`, commit `086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a`: `codex-api/src/sse/responses.rs` (SSE trace and `response_model()`), `core/src/session/mod.rs` (`maybe_warn_on_server_model_mismatch`), `otel/src/events/session_telemetry.rs` (tool decisions), and `protocol/src/protocol.rs` (per-response token records), all under `codex-rs/`. Source hashes and the actual native fixture report are retained in the local readiness checkpoint. A native trace is an auditable harness observation, not cryptographic provider attestation.

## Billing scope must be arranged before any authorized attempt

Use an operator-designated OpenAI project/key dedicated to this one run for the **entire UTC cost bucket**, with no other use before, during or after the Trial in that bucket. Bind the project ID and API **key ID** in the exact-run permit, never its secret. The runtime key continues to come only from `.env` through the harness. Do not reuse a busy project/key or attribute a shared daily total proportionally to local tokens. The USD 2 value remains an observed target, not an enforced spend cap.

A billing operator with appropriate account access independently obtains usage and costs outside the agent. No Admin credential is passed to the Trial or read by this tool. Obtain all pages for one complete UTC day covering execution, filtered to the exact project/key. Usage must be grouped by project/key/model, and costs by project/key/line item. Preserve original response bodies; export request metadata is an explicit operator assertion. Record unsuccessful transport/retry activity too. Native/ATIF cost estimates and local price arithmetic are not provider billing.

After the bucket closes, obtain two independent snapshots at distinct recorded times. Reconcile exact usage/model/request counts and token totals with the native evidence; compare complete cost/usage snapshots. A second immediate identical response is not proof of finality: the reviewer must state the provider reporting/finality basis and wait until that basis is satisfied. There is no invented universal settlement delay. Missing data, empty buckets, pagination gaps, changing costs, shared activity, unattributed discounts/credits, crossing midnight, unaccounted retries or count discrepancies stop automated reconciliation. Retain the run in collected-awaiting-finalization and investigate; do not relaunch it or label unknown cost zero. A named reviewer asserts finality, exclusivity and retry coverage; the parser cannot authenticate exports or prove human independence.

`provider-export.example.json` is an inactive shape guide. The real bundle has two `snapshots`, each with original `usage_pages`, `cost_pages`, retrieval time and exact query scope. Bind the bundle to run ID, sealed inputs, collection seal and response-set hashes. `review.status=settled` is a reviewed operational assertion, not an API field. Currency must be USD; explicit provider zero is accepted only with actual matching usage and explicit stable cost rows. Over-target costs are retained and flagged, never clamped; they block the next admission.

Stage the completed non-secret export under the existing private `.cache/operator/` boundary. The command below validates local documents only; it never calls OpenAI:

```sh
mise exec -- python experiments/common/pilot-execution/hn_o01_billing.py \
  --run-id 2026-11-07-harbor55-hn-o01 \
  --export provider-export.json --out reconciled-billing.json
```

After separate execution and completed reconciliation, HN-O01 finalization uses generated provenance without hand-written observation pointers:

```sh
mise exec -- experiments/common/harbor-interop/.venv/bin/python \
  experiments/common/pilot-execution/single_trial.py finalize \
  --run-id 2026-11-07-harbor55-hn-o01 --billing reconciled-billing.json
```

Finalization rechecks export hashes, recomputes the billing receipt and measurement mapping, then preserves all provider/native evidence through the existing importer. It never starts a second slot. A task pass with missing identity or measurements remains inconclusive under the unchanged accounting gate. A failed/incomplete native trace or ambiguous billing requires separate audited reconciliation work; this strict automatic path is not a substitute for investigating it. Finalization is one-shot: inspect an interrupted import rather than overwrite it.

## Offline verification and limits

The unit suite uses invented native/provider documents in temporary directories, including explicit cost zero and overrun, mismatched models/usage, incomplete pagination, changing snapshots, class promotion, altered evidence and forged receipts. Those documents are never accepted as evidence of actual spending. Full Docker controls use only the in-container provider fixture and scratch run catalog; historical runs and prepared live slots remain unchanged.

Current official references, consulted 2026-11-07: [Codex telemetry](https://learn.chatgpt.com/docs/config-file/config-advanced#observability-and-telemetry), [OpenAI usage](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/completions), [OpenAI costs](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs). Costs are bucketed aggregates; the procedure's exclusivity and finality assertions are additional lab requirements. Actual account access, live transport/identity, export availability and settled billing remain unverified until a separately authorized attempt and account-side review.
