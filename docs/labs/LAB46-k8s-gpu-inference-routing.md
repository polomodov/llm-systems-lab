# LAB46. Inference-aware routing and replica cold start

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the Kubernetes and GPU branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB44](LAB44-k8s-gpu-scheduling.md) (Kind on machine B) and [LAB45](LAB45-k8s-gpu-vllm-capacity.md) (vLLM in k3s on machine A) |
| Machines | B: routing on a simulator; A: one real vLLM replica and cold start |
| Minimum | Part A (round-robin versus Gateway API Inference Extension on 4 simulator replicas), part C (real-replica cold-start breakdown) |
| Extensions | Part B (real vLLM replica in an InferencePool on machine A); node weight cache or image volume; multi-LoRA on the simulator |
| Time | Allow 1 day |
| Readiness | `target-machine`; compatibility of pinned simulator and endpoint-picker versions is `unverified` |
| Initial state | Educational manifest: `not-started` |

## Objective

Understand how LLM request routing differs from ordinary HTTP load balancing and what it gains, and break down replica cold start into stages. These two factors determine serving-platform latency and cost during autoscaling.

## Hypothesis

1. On a workload with shared prefixes and uneven request lengths, inference-aware routing (Gateway API Inference Extension endpoint picker) reduces TTFT p95 by at least X% versus round-robin at the same total load.
2. Weight loading and engine preparation account for more than half of real vLLM replica cold-start time, rather than pod scheduling and image download.

Fix X in the protocol before measurement.

## Preparation

- Read: [Introducing Gateway API Inference Extension](https://kubernetes.io/blog/2025/06/05/introducing-gateway-api-inference-extension/), `kubernetes-sigs/gateway-api-inference-extension` documentation (InferencePool, endpoint picker), `llm-d/llm-d` (well-lit paths, KV-cache-aware routing, prefill/decode disaggregation), `llm-d/llm-d-inference-sim`.
- The simulator mimics an OpenAI-compatible vLLM server and its metrics without a GPU. Its delays are a model, not measurements of a real engine; part A conclusions concern the routing algorithm.
- Pin Gateway API CRD, Gateway implementation, Inference Extension and simulator versions.
- Use the same workload as LAB45 set B plus a mix of short and long requests; generator in `experiments/k8s-gpu/bench/`.

```bash
npm run lab:new -- --lab LAB46 --session honor-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB46-honor-01'
```

For parts B and C on machine A, create a separate `ryzen-01` session of this lab.

## Procedure

1. **Part A: simulator.** Kind on machine B, Gateway API and a chosen Gateway implementation, 4 `llm-d-inference-sim` replicas with identical delay parameters.
   - Run A1: HTTPRoute to the replica Service with explicitly configured per-request round-robin balancing in the chosen Gateway implementation. An ordinary kube-proxy Service is unsuitable: it picks a pod randomly once per connection, so keep-alive accumulates requests on one replica. Verify even request distribution from replica logs or metrics; otherwise the run does not count.
   - Run A2: InferencePool with endpoint picker.
   Three runs per variant, alternating order, identical load. Save configuration, endpoint-picker logs and replica metrics.
2. **Part B (extension): real replica.** On machine A, add LAB45 vLLM to an InferencePool alongside simulator replicas. Verify from endpoint-picker logs that it reads real-replica metrics, and record traffic distribution.
3. **Part C: cold start.** On machine A, delete the vLLM pod with an empty page cache (record how it was cleared) and with a warm cache. Record timestamps: pod created → assigned to node → image ready → container started → weights loaded (from vLLM logs) → readiness → first response. Three repetitions per mode.
4. **Extension: weight cache.** Repeat part C with weights from an image volume or local node cache and record the difference.
5. **Teardown.** Delete machine B's Kind cluster; on machine A, restore the LAB45 state or remove k3s.

## Results tables

| Variant (part A) | Run | TTFT median / p95, ms | Request share on busiest replica, % | Errors |
| --- | --- | --- | --- | --- |
| Round-robin | 1–3 | | | |
| Endpoint picker | 1–3 | | | |

| Cold-start stage (part C) | Cold cache, s | Warm cache, s | Weight cache (extension), s |
| --- | --- | --- | --- |
| Pod scheduling | | | |
| Image ready | | | |
| Container startup | | | |
| Weight loading | | | |
| Engine preparation to readiness | | | |
| First response | | | |
| Total | | | |

## Deliverables

- Reports for both sessions, Gateway and InferencePool manifests, load generator, raw results, timestamped endpoint-picker and vLLM logs.
- All component versions; description of the simulator's delay model.

## Completion criteria

- A1 and A2 each run 3 times on the same load; hypothesis 1 accepted or rejected.
- Cold start broken down by stage in both cache modes; hypothesis 2 accepted or rejected.
- Limits of simulator-derived conclusions explicitly listed.

## Review questions

1. Which signals does the endpoint picker use that ordinary load balancers lack, and why do they matter for LLMs?
2. What is prefill/decode disaggregation, and under which workload profile does it pay off?
3. Design serving for dozens of differently sized models with different SLOs. What is shared, what is per-model, where does routing live, and how are GPUs divided?
4. Which cold-start stages can be removed or parallelized, and at what cost?

## Sources

- [Introducing Gateway API Inference Extension](https://kubernetes.io/blog/2025/06/05/introducing-gateway-api-inference-extension/); `kubernetes-sigs/gateway-api-inference-extension`.
- [llm-d](https://github.com/llm-d/llm-d), `llm-d/llm-d-inference-sim`.
- Kubernetes image-volumes documentation; vLLM model-loading documentation.
- This repository: [LAB45](LAB45-k8s-gpu-vllm-capacity.md), [protocol](../method.md).
