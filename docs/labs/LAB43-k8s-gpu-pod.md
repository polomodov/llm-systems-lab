# LAB43. GPU in a pod: k3s and AMD device plugin on gfx1151

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the Kubernetes and GPU branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | [LAB02](LAB02-hardware.md) (Ryzen profile, ROCm sees `gfx1151`) and [LAB05](LAB05-context-tools.md) (working llama.cpp server, reference GGUF and HTTP driver) |
| Machine | A: Ryzen AI Max+ 395 / 128 GB / Linux, single-node k3s |
| Minimum | k3s installation, AMD device plugin, `amd.com/gpu` in `allocatable` (or documented failure), pod with `rocminfo`, llama.cpp server as a Deployment, speed comparison with execution outside Kubernetes |
| Extensions | AMD GPU Operator instead of a standalone device plugin; Node Feature Discovery and node labels; Vulkan llama.cpp build in a pod |
| Time | Allow 3–5 hours |
| Readiness | `target-machine`; AMD device plugin support for the `gfx1151` APU is `unverified` |
| Initial state | Educational manifest: `not-started` |

## Objective

Trace the entire chain that exposes a GPU to a Kubernetes container: kernel `amdgpu` driver → user-space ROCm → container runtime → device plugin → extended resource → scheduler → pod. Verify whether Kubernetes adds inference overhead and record additions to a standard Deployment.

## Hypothesis

The AMD device plugin registers exactly one `amd.com/gpu` on the node, a pod requesting `amd.com/gpu: 1` sees `gfx1151` without `privileged: true`, and llama.cpp server in the pod achieves prompt processing and token generation within ±5% of the LAB05 baseline with the same GGUF, backend and parameters.

The hypothesis is falsified if the plugin finds no device, the pod sees the GPU only in privileged mode, or repeated speed measurements differ by more than 5%. Fix the threshold in the protocol before measurement.

## Preparation

- Read: k3s installation and containerd documentation, [AMD GPU Device Plugin for Kubernetes](https://instinct.docs.amd.com/projects/k8s-device-plugin/en/latest/), and Kubernetes documentation on device plugins and extended resources.
- AMD documentation requires a “ROCm-capable AMD GPU” and focuses on Instinct. APU compatibility is the subject of this check, not an established fact.
- Do not combine this with LAB04–07 series or a running SPACE deployment (LAB36): k3s and Kind compete for memory, iptables/nft and the GPU.
- Pin k3s and device-plugin versions and the llama.cpp image digest. Build the llama.cpp image from the same commit and backend as the LAB05 baseline.

```bash
npm run lab:new -- --lab LAB43 --session ryzen-01
LAB_DIR='experiments/k8s-gpu/measurements/LAB43-ryzen-01'
```

## Procedure

1. **Host state.** Save `uname -r`, `rocminfo`, `ls -l /dev/kfd /dev/dri` and user groups in `raw/`. Compare with the LAB02 profile; if anything changed, update the profile first.
2. **k3s.** Install the pinned version; save `kubectl version`, `kubectl get nodes -o wide` and containerd configuration. Put manifests in `experiments/k8s-gpu/manifests/LAB43/`.
3. **Device plugin.** Deploy the AMD device plugin DaemonSet. Save its logs and `kubectl get node -o jsonpath='{.status.allocatable}'`. If `amd.com/gpu` does not appear, identify and record the cause from logs (cannot see `/dev/kfd`, unrecognized ASIC, missing permissions); then take the fallback in step 5.
4. **Pod probe.** A ROCm-image pod requesting `amd.com/gpu: 1` runs `rocminfo` and a small HIP test or `python -c` with `torch.cuda.get_device_properties(0)`. Output must include `gfx1151`. Save the manifest, output and `kubectl describe pod`.
5. **Fallback.** Only if step 3 failed: a pod with `hostPath` for `/dev/kfd` and `/dev/dri` and the minimum necessary permissions. Record required permissions and why this is inferior to a device plugin (the scheduler is unaware of the GPU; no accounting).
6. **Inference server.** A llama.cpp server Deployment with the reference GGUF via read-only `hostPath` (hash checked against LAB03), a ClusterIP Service and a `/health` readiness probe. Check with the same LAB05 HTTP driver.
7. **Speed comparison.** At least 5 repetitions of `llama-bench` or the LAB05 server run inside the pod and as many on the host in the same session, alternating order. Write PP and TG to `measurements.tsv`, one row per attempt.
8. **Teardown.** `k3s-uninstall.sh`; verify k3s services stopped and iptables/nft rules removed. Record what remains on disk.

## Results tables

| Layer | Check performed | Result | Evidence |
| --- | --- | --- | --- |
| Host driver / ROCm | | | |
| Device plugin: `amd.com/gpu` in allocatable | | | |
| Pod sees `gfx1151` without privileged | | | |
| Fallback (if needed) | | | |
| llama.cpp server: health and HTTP driver | | | |

| Environment | N | PP median, tok/s | TG median, tok/s | Spread | Difference from host |
| --- | --- | --- | --- | --- | --- |
| Host | | | | | — |
| Pod | | | | | |

| Addition to standard Deployment | Purpose | Can it be removed? |
| --- | --- | --- |
| | | |

## Deliverables

- Report, manifests in `experiments/k8s-gpu/manifests/LAB43/`, device-plugin logs, pod-probe output, raw measurements for both environments.
- k3s and device-plugin versions, image digests; GGUF hash.

## Completion criteria

- Driver-to-pod chain completed, or the exact failing layer identified with a log.
- Overhead hypothesis accepted or rejected from raw measurements with at least 5 repetitions per environment.
- Cluster removed; host remnants listed.

## Review questions

1. How does the `amd.com/gpu` extended resource differ from CPU and memory from the scheduler's perspective? Why cannot it be requested fractionally?
2. The node shows a GPU, but the pod cannot see it. Which layers would you inspect, and which commands would you run at each?
3. What is lost by exposing the GPU to a pod through `hostPath` instead of a device plugin?
4. Why does `allocatable` say nothing about memory available to a model on a unified-memory APU, and where does that limit actually reside?

## Sources

- [AMD GPU Device Plugin for Kubernetes](https://instinct.docs.amd.com/projects/k8s-device-plugin/en/latest/), `ROCm/k8s-device-plugin` repository.
- Kubernetes documentation: Device Plugins, Extended Resources; k3s documentation.
- This repository: [LAB02](LAB02-hardware.md), [LAB05](LAB05-context-tools.md), [protocol](../method.md).
