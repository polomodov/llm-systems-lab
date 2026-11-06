# LAB45. vLLM in Kubernetes: TTFT/ITL curves, prefix caching and replica capacity

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the Kubernetes and GPU branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB43](LAB43-k8s-gpu-pod.md) (GPU available in a pod) and [LAB06](LAB06-engines.md) (vLLM ROCm image and checkpoint passed `gfx1151` validation) |
| Machine | A: Ryzen AI Max+ 395 / 128 GB / Linux, k3s from LAB43 |
| Minimum | vLLM Deployment with pinned image and LAB06 checkpoint, concurrency grid 1/4/16/64, two prefix-caching modes on shared-prefix load, replica capacity established under an SLO |
| Extensions | A second checkpoint of another size; quantized variant; chunked prefill on/off; comparison with LAB43 llama.cpp server on the same load |
| Time | Allow 4–6 hours |
| Readiness | `target-machine` |
| Initial state | Educational manifest: `not-started` |

## Objective

Measure how one inference-engine replica behaves under load and obtain the starting point for capacity planning: how many concurrent requests it handles without violating a time-to-first-token SLO. Separately test the benefit of prefix caching on requests sharing a long prefix, as in a “search + answer” product.

## Hypothesis

1. TTFT p95 grows monotonically with concurrency, while median ITL grows substantially more slowly than TTFT until saturation.
2. For a workload with a shared prefix of at least 2048 tokens, prefix caching lowers median TTFT by at least 30% with unchanged ITL.
3. There is a concurrency level beyond which TTFT p95 exceeds the SLO. This determines replica capacity.

Fix the TTFT p95 SLO (default 2 s), improvement threshold and input/output lengths in the protocol before measurement.

## Preparation

- Read: the PagedAttention paper (Kwon et al., 2023), vLLM documentation on continuous batching, automatic prefix caching, chunked prefill and Prometheus metrics; `vllm bench serve` or `vllm-project/guidellm` documentation.
- Use the same vLLM image digest that passed LAB06. Do not upgrade Torch/Triton on top of the image.
- Interpret the vLLM memory-fraction parameter on unified memory as cautiously as in LAB06: first check the LAB02 budget.
- Load requests are synthetic, generated deterministically by a script in `experiments/k8s-gpu/bench/`: set A without a shared prefix; set B with a shared prefix and different suffixes.

```bash
npm run lab:new -- --lab LAB45 --session ryzen-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB45-ryzen-01'
```

## Procedure

1. **Deployment.** A vLLM Deployment requesting `amd.com/gpu: 1` (or the LAB43 fallback), checkpoint via a read-only volume, readiness probe, Service. Save the manifest, full server arguments, `GET /v1/models` and `/metrics` after startup.
2. **Warmup.** Several requests excluded from measurement.
3. **Concurrency grid.** At each level 1/4/16/64, send a fixed number of set A requests from a load generator in a separate pod in the same cluster. Capture TTFT, ITL, end-to-end latency, throughput, and queue/KV-cache metrics from `/metrics`.
4. **Prefix caching.** At a middle-grid concurrency level, run set B with prefix caching disabled and enabled, two runs per mode, alternating order. Each mode switch restarts the pod; record restart time separately.
5. **Capacity.** Refine the grid around the point where TTFT p95 crosses the SLO, and find the maximum concurrency satisfying the SLO in all repetitions.
6. **Resource observation.** During runs, capture host and GPU memory using LAB02 tools and node CPU load.

## Results tables

| Concurrency | Requests | TTFT median / p95, ms | ITL median / p95, ms | Throughput, tok/s | Max queue | Max KV cache, % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |
| 4 | | | | | | |
| 16 | | | | | | |
| 64 | | | | | | |

| Set B, prefix caching | Run | TTFT median / p95, ms | ITL median, ms | Prefix cache hit rate |
| --- | --- | --- | --- | --- |
| off | 1 | | | — |
| off | 2 | | | — |
| on | 1 | | | |
| on | 2 | | | |

| Outcome | Value |
| --- | --- |
| SLO TTFT p95 | |
| Replica capacity, concurrency | |
| Throughput at this capacity, tok/s | |

## Deliverables

- Report, manifests, request generator and load-generator configuration in `experiments/k8s-gpu/bench/`, raw load-generator results and `/metrics` snapshots.
- Image digest, checkpoint revision, full vLLM arguments.

## Completion criteria

- Full concurrency grid run; saturation found or explicitly not reached at 64.
- Prefix-caching hypothesis accepted or rejected from two runs per mode.
- Replica capacity under the fixed SLO recorded with conditions.

## Review questions

1. Why is prefill compute-bound while decode is memory-bandwidth-bound? How is this visible in your TTFT and ITL curves?
2. Why is CPU utilization unsuitable for scaling inference, and which metric would you choose for autoscaling?
3. How does one replica's capacity become a GPU procurement plan for a given peak traffic level?
4. How would your figures change on a discrete card with HBM instead of unified memory?

## Sources

- Kwon et al., *Efficient Memory Management for Large Language Model Serving with PagedAttention*, 2023.
- vLLM documentation: automatic prefix caching, metrics, `vllm bench serve`; `vllm-project/guidellm`.
- This repository: [LAB06](LAB06-engines.md), [LAB26](LAB26-concurrent-load.md) as an example concurrent-load report, [protocol](../method.md).
