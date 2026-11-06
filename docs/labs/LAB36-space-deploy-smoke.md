# LAB36. SPACE: host profile, Kind deployment and smoke tests

> **Frozen 2026-11-05.** The manual is preserved, but `lab:new` does not create new sessions for it: the SPACE branch has no measurements or implementation and is being moved to a separate educational repository. Unfreezing requires a separate decision and an entry in the [lab status](README.md#infrastructure-branch-freeze).

## Profile

| Field | Value |
| --- | --- |
| Prerequisite | Completed [LAB01](LAB01-reproducibility.md); sudo access to the target machine |
| Machines | A: Ryzen AI Max+ 395 / 128 GB / Linux (same as [LAB02](LAB02-hardware.md)); B: HONOR MagicBook X16, Ryzen 7 PRO 8845HS / 32 GB / Ubuntu |
| Platform | `polomodov/SPACE` (fork of `perplexityai/SPACE`), pinned commit; E0 profile: Linux x86_64 + KVM + Firecracker 1.15.1 |
| Minimum | Host profile, full installation, `first_sandbox.py`, baseline `smoke-kind-e2e.sh`, typed `native` smoke, teardown — a separate session on **each** machine |
| Extensions | `smoke-kind-typed.sh ecw` and `all` (sharded on B), `smoke-spaced-rest.sh`, bring-up timeline |
| Time | Allow 3–6 operator hours per machine; the first Rust workspace build accounts for most of it |
| Readiness | `target-machine`; the “machine + SPACE commit” combination is `unverified` until the first session |
| Initial state | Educational manifest: `not-started` |

Name sessions after the machine: `ryzen-01`, `honor-01`. A repeat on the same machine is a new session (`ryzen-02`), not an overwrite.

## Objective

Bring up local SPACE (Kind + Firecracker) on each machine without platform code changes, obtain reproducible smoke-suite verdicts and measure deployment time, memory and disk cost. The outcome is machine admission to LAB37–42.

## Hypothesis

On both machines, installation following `docs/installation.md` succeeds without SPACE code changes, `examples/first_sandbox.py` prints `Hello from SPACE`, and `smoke-kind-e2e.sh` and `smoke-kind-typed.sh native` exit with code `0`. On machine B, limiting Tilt parallelism (`SPACE_TILT_MAX_PARALLEL_UPDATES=1`) is sufficient.

OOM, Kind apiserver timeout, preflight rejection or a nonzero smoke exit under these settings falsifies the hypothesis. Typed smoke code `42` means an environment-related skip, not a pass; it does not confirm the hypothesis.

## Preparation

- Read in the SPACE repository: `docs/installation.md`, `docs/first-sandbox.md`, `infra/space/kind/README.md` (Smoke test and Kind apiserver timeouts sections), `docs/troubleshooting.md#local-installation`. Project notes contain a Russian summary, but the repository is authoritative if they disagree.
- The installer installs packages with sudo, starts privileged containers and creates loop devices and nft rules. On machine A, do not run LAB04–07 series concurrently, and stop inference servers: Kind and the build share the same memory.
- On machine A, record the GPU UMA allocation from the LAB02 profile: it determines how much RAM Linux sees.
- On machine B, connect AC power and disable sleep during the build.
- Do not publish serial numbers, external addresses, the console password or bearer tokens in the report.

Create a report and pin the SPACE version:

```bash
npm run lab:new -- --lab LAB36 --session ryzen-01
LAB_DIR="$PWD/experiments/space/measurements/LAB36-ryzen-01"
git clone https://github.com/polomodov/SPACE.git ~/src/SPACE
git -C ~/src/SPACE rev-parse HEAD > "$LAB_DIR/raw/space-revision.txt"
```

Run all SPACE commands below from `~/src/SPACE` in one bash session (inside `tmux` over SSH).

## Procedure

1. **Host profile (read-only).**

   ```bash
   { uname -a; cat /etc/os-release; nproc; grep -m1 'model name' /proc/cpuinfo;
     grep -c -w svm /proc/cpuinfo; grep -E 'MemTotal|SwapTotal' /proc/meminfo;
     ls -l /dev/kvm /dev/net/tun; grep -w btrfs /proc/filesystems; losetup -f;
     docker info --format '{{.ServerVersion}} {{.DockerRootDir}} {{.CgroupVersion}}';
     df -h "$(docker info --format '{{.DockerRootDir}}')" "$HOME"; } > "$LAB_DIR/raw/host.txt" 2>&1
   ```

   If `/dev/kvm` or the `svm` flag is absent, check whether BIOS virtualization is enabled and stop with a blocker. A VM requires nested virtualization; this lab expects bare metal.

2. **Protocol before execution.** Save `raw/protocol.md`: SPACE commit, machine, `SPACE_TILT_MAX_PARALLEL_UPDATES`, step order, mandatory smoke tests and stop rule (first phase error).

3. **Tools and Firecracker.** Record time and peak memory for each phase:

   ```bash
   set +eu; set -o pipefail
   export PATH="$HOME/.local/bin:$PATH" INSTALL_DIR="$HOME/.local/bin"; mkdir -p "$INSTALL_DIR"
   unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN DD_API_KEY EPPO_SDK_KEY
   export SPACE_VENDOR_ROOT="$HOME/.local/share/space/vendor" SPACE_KIND_CLUSTER=space-local
   /usr/bin/time -v bash infra/space/kind/scripts/install-prereqs.sh > "$LAB_DIR/raw/prereqs.txt" 2>&1
   /usr/bin/time -v bash infra/space/kind/scripts/install-fc-vendor.sh > "$LAB_DIR/raw/fc-vendor.txt" 2>&1
   ```

4. **Cluster bring-up.** Collect background memory observations and a timeline in parallel:

   ```bash
   vmstat -t 5 > "$LAB_DIR/raw/vmstat-bootstrap.txt" & VMSTAT=$!
   python3 scripts/benchmarks/kind-bringup-timeline.py watch "$LAB_DIR/raw/timeline" & TIMELINE=$!
   # On machine B: export SPACE_TILT_MAX_PARALLEL_UPDATES=1
   /usr/bin/time -v bash infra/space/kind/scripts/bootstrap.sh > "$LAB_DIR/raw/bootstrap.txt" 2>&1
   kill $VMSTAT $TIMELINE
   ```

   Record failures at this step with the last 200 log lines and pod state (`kubectl --context kind-space-local -n space get pods -o wide`). A retry after an environment fix is a new entry in `planned_attempts`.

5. **Readiness and first sandbox.**

   ```bash
   export SPACE_API_URL=http://127.0.0.1:8080 SPACE_DATA_PLANE_URL=http://127.0.0.1:8090
   kubectl --context kind-space-local -n space wait --for=condition=complete job/space-seed-publish --timeout=300s
   for ds in $(bash infra/space/kind/lib/node-services.sh daemonsets); do
     kubectl --context kind-space-local -n space rollout status "ds/$ds" --timeout=300s; done
   curl --noproxy '*' -fsS "$SPACE_API_URL/openapi-m1.json" | jq -e '.openapi and .paths' >/dev/null && echo "API ok"
   export SPACE_API_TOKEN="$(jq -nc '{email:"root@local",password:"password"}' |
     curl --noproxy '*' -fsS -H 'Content-Type: application/json' --data-binary @- \
     "$SPACE_API_URL/auth/v1/sessions" | jq -er .token)"
   python3 examples/first_sandbox.py 2>&1 | tee "$LAB_DIR/raw/first-sandbox.txt"
   ```

   Success means the lines `Hello from SPACE` and `Command completed successfully`. Answer `y` to the deletion prompt. The token must not enter logs; check with `grep -rlF -- "$SPACE_API_TOKEN" "$LAB_DIR/raw" || echo clean` (expect `clean`).

6. **Staged smoke tests.** Each stage is a separate table row with its exit code.

   ```bash
   SKIP_BOOTSTRAP=1 bash scripts/tests/smoke-kind-e2e.sh > "$LAB_DIR/raw/smoke-e2e.txt" 2>&1; echo "e2e=$?" >> "$LAB_DIR/raw/exit-codes.txt"
   SKIP_BOOTSTRAP=1 bash scripts/tests/smoke-kind-typed.sh native > "$LAB_DIR/raw/smoke-native.txt" 2>&1; echo "native=$?" >> "$LAB_DIR/raw/exit-codes.txt"
   ```

   Extension: `smoke-kind-typed.sh ecw`, then `all`. On machine B, run the full `all` sequentially as shards `all 1/2` and `all 2/2`; never run shards against the same cluster simultaneously. Run `smoke-spaced-rest.sh` using the command in the Smoke test section of `infra/space/kind/README.md`.

7. **Resources after the run.** Save `docker system df`, `du -sh "$SPACE_VENDOR_ROOT"`, `df -h` to `raw/disk-after.txt`.

8. **Teardown.**

   ```bash
   SPACE_KIND_CLUSTER=space-local bash infra/space/kind/scripts/teardown.sh > "$LAB_DIR/raw/teardown.txt" 2>&1
   kind get clusters >> "$LAB_DIR/raw/teardown.txt"
   ```

   Image caches and Firecracker artifacts remain; record their size. This lab does not require deleting shared Docker caches.

## Results tables

**Host profile**

| Field | Machine A | Machine B |
| --- | --- | --- |
| CPU, cores/threads, `svm` | | |
| MemTotal / swap / UMA | | |
| Kernel, distribution | | |
| Docker, cgroup, data root, free space | | |
| `/dev/kvm`, `/dev/net/tun`, btrfs, loop | | |
| Commit SPACE | | |

**Installation phases**

| Phase | Machine | Wall-clock, s | Max RSS, KiB | Peak used RAM from vmstat, MiB | Disk before/after, GiB | Exit code |
| --- | --- | --- | --- | --- | --- | --- |
| install-prereqs | | | | | | |
| install-fc-vendor | | | | | | |
| bootstrap | | | | | | |

**Smoke**

| Stage | Machine | Code (0/42/1) | Passed | Skipped | Failed | First error |
| --- | --- | --- | --- | --- | --- | --- |
| first_sandbox.py | | | | | | |
| smoke-kind-e2e | | | | | | |
| typed native | | | | | | |
| typed ecw (ext.) | | | | | | |
| typed all / shards (ext.) | | | | | | |

## Deliverables

- One report per machine (`LAB36-ryzen-NN`, `LAB36-honor-NN`) with completed tables and `raw/protocol.md`.
- Raw: `host.txt`, phase logs, `vmstat`, timeline, `first-sandbox.txt`, smoke logs, `exit-codes.txt`, `teardown.txt`.
- List of failed scenarios with the first error line and a log link.
- A “Machine differences” section in the second session report: what changed on B relative to A, and why.

## Completion criteria

- Minimum completed on the machine: successful `first_sandbox.py`, `smoke-kind-e2e` and `typed native` exit `0`, teardown confirmed.
- Each stage has an exit code and log; `42` is not counted as pass.
- Peak memory and bootstrap time measured rather than estimated.
- Raw evidence contains no tokens, password or private addresses.
- If the machine did not pass, the report is `blocked` with an exact reason; it is not admitted to LAB37–42.

## Review questions

1. Which phase determines peak memory, and which machine has the least headroom?
2. How does an environment skip (`42`) differ from a pass, and why does CI treat them differently?
3. Why must typed-smoke shards not run concurrently against one cluster?
4. Which host-profile details explain bootstrap-time differences between machines?
5. Which resources remain on disk after teardown, and how can they be safely removed separately?

## Sources

- SPACE: `docs/installation.md`, `docs/first-sandbox.md`, `docs/troubleshooting.md`, `docs/execution-environments.md`.
- SPACE: `infra/space/kind/README.md`, `scripts/tests/smoke-kind-e2e.sh`, `scripts/tests/smoke-kind-typed.sh`, `scripts/benchmarks/kind-bringup-timeline.py`.
- This repository: [LAB02](LAB02-hardware.md) (machine A profile), [protocol](../method.md), [report validation](report-validation.md).
