# Runbook: LAB02–LAB05 on Ryzen AI Max+ 395

A consolidated operator worksheet for one measurement session. Assembled on 2026-09-21 from commit `b19e7db`.

## Scope and authority

This is a **derived** command worksheet: four labs are arranged in one linear sequence, `my-session` is replaced with `ryzen-01`, every `/absolute/path/to/...` comes from variables, and nested heredocs are unindented from lists (the original documents indent the closing `PY`, so copying them literally would leave the heredoc open).

The **original lab guides are authoritative**, not this file:

- [LAB02](../../docs/labs/LAB02-hardware.md) · [LAB03](../../docs/labs/LAB03-artifacts.md) · [LAB04](../../docs/labs/LAB04-backends.md) · [LAB05](../../docs/labs/LAB05-context-tools.md)

Block convention: evidence-collection commands occupy **separate lines**, as in the lab guides, so one failed utility cannot hide output from the others. Only gates where proceeding after failure makes no sense are joined with `&&`.

Result tables, completion criteria, and review questions are omitted here; complete them from the lab guides themselves. This file neither creates `run.json` nor awards credit, and it does not replace `report.md`.

Check source drift from the repository root:

```sh
sha256sum -c experiments/local-models/runbook.sources.sha256
```

If hashes differ, read the changed lab guide first, then rebuild the runbook.

## 0. Once per session: environment

The test environment is native Linux on the target machine. LAB02 stops at `test "$(uname -s)" = Linux`: macOS, WSL, and VMs cannot provide the required machine passport.

Create an environment file **outside the repository** (it contains no secrets and must not contain any):

```sh
cat > "$HOME/lab-ryzen-01.env" <<'ENV'
export LAB_SESSION=ryzen-01
export LAB_ROOT="$HOME/llm-systems-lab"
export LAB_MEASUREMENTS="$LAB_ROOT/experiments/local-models/measurements"
export LAB02_DIR="$LAB_MEASUREMENTS/LAB02-$LAB_SESSION"
export LAB03_DIR="$LAB_MEASUREMENTS/LAB03-$LAB_SESSION"
export LAB04_DIR="$LAB_MEASUREMENTS/LAB04-$LAB_SESSION"
export LAB05_DIR="$LAB_MEASUREMENTS/LAB05-$LAB_SESSION"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
export LLAMA_SOURCE="$HOME/src/llama.cpp-pinned"
export LLAMA_COMMIT=""
ENV
```

Adjust `LAB_ROOT` to the actual clone path and `LAB_STORAGE` to the disk whose free space you will measure in LAB02. Fill in `LLAMA_COMMIT` during LAB04; append `LOCAL_GGUF` and `LLAMA_BIN` as the work progresses.

**In every terminal for this session** (up to three are needed):

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT"
```

Check tools:

```sh
node --version && git --version && bash --version && python3 --version
```

Requires Node ≥22 and Python ≥3.11 (`hashlib.file_digest` in LAB03).

Repeating an experiment requires a new `--session`, not overwriting a directory: `lab:new` does not overwrite an existing directory.

---

# LAB02. Machine passport and memory budget

Read system state only. Do not change BIOS, kernel, kernel cmdline, TTM/GTT, drivers, or power profile. Close your own active inference processes; leave unfamiliar user processes alone.

Before collection, record the computer model, power mode, AC power, active desktop, and significant background workloads in the report. The archive does not need a serial number.

## 02.1 Archive and OS check

```sh
npm run lab:new -- --lab LAB02 --session "$LAB_SESSION"
```

```sh
export LAB_DIR="$LAB02_DIR" && test "$(uname -s)" = Linux && test -d "$LAB_DIR/raw" && echo ok
```

## 02.2 Collect system information

One unavailable utility does not interrupt the entire collection; mark missing utilities `unavailable`.

```sh
python3 - <<'PY'
import json, os, pathlib, subprocess, time
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
commands = {
    'time': ['date', '-u', '+%FT%TZ'],
    'kernel': ['uname', '-a'],
    'cpu': ['lscpu'],
    'memory': ['free', '-b'],
    'swap': ['swapon', '--show', '--bytes'],
    'disk': ['df', '-B1', '.'],
    'pci': ['lspci', '-nnk'],
    'vulkan-summary': ['vulkaninfo', '--summary'],
    'vulkan-full': ['vulkaninfo'],
    'rocminfo': ['rocminfo'],
    'hipconfig': ['hipconfig', '--full'],
    'power-profile': ['powerprofilesctl', 'get'],
}
status = {}
for name, argv in commands.items():
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        output = result.stdout + result.stderr
        status[name] = {'command': argv, 'exit_code': result.returncode}
    except (OSError, subprocess.TimeoutExpired) as error:
        output = str(error) + '\n'
        status[name] = {'command': argv, 'exit_code': None, 'reason': str(error)}
    (root / (name + '.txt')).write_text(output)
for name, source in {
    'os-release': '/etc/os-release',
    'meminfo': '/proc/meminfo',
    'vmstat-before': '/proc/vmstat',
    'bios-version': '/sys/class/dmi/id/bios_version',
    'bios-date': '/sys/class/dmi/id/bios_date',
    'product-name': '/sys/class/dmi/id/product_name',
}.items():
    try:
        (root / (name + '.txt')).write_text(pathlib.Path(source).read_text())
    except OSError as error:
        status[name] = {'exit_code': None, 'reason': str(error)}
(root / 'collection-status.json').write_text(json.dumps(status, indent=2))
PY
```

## 02.3 Memory inventory and UMA

```sh
python3 - <<'PY'
import glob, json, os, pathlib, re
result = {'page_size_bytes': os.sysconf('SC_PAGE_SIZE'), 'memory': {}, 'sysfs': {}}
for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
    key, value = line.split(':', 1)
    if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
        count = int(value.split()[0]) * 1024
        result['memory'][key] = {'bytes': count, 'GiB': count / 2**30}
paths = [
    '/sys/module/ttm/parameters/pages_limit',
    '/sys/module/ttm/parameters/page_pool_size',
    '/sys/module/amdgpu/parameters/gtt_size',
]
for card in glob.glob('/sys/class/drm/card*'):
    if re.fullmatch(r'card\d+', pathlib.Path(card).name):
        paths.extend(str(path) for path in pathlib.Path(card, 'device').glob('mem_info_*'))
        paths.extend([card + '/device/vendor', card + '/device/device'])
for source in sorted(set(paths)):
    try:
        result['sysfs'][source] = {'value': pathlib.Path(source).read_text().strip()}
    except OSError as error:
        result['sysfs'][source] = {'value': None, 'reason': str(error)}
target = pathlib.Path(os.environ['LAB_DIR']) / 'raw' / 'memory-inventory.json'
target.write_text(json.dumps(result, indent=2))
print(json.dumps(result['memory'], indent=2))
PY
```

`pages_limit × page_size_bytes` is the TTM page limit, **not** free GPU memory. Do not add it to `MemTotal`, VRAM, or GTT: shared UMA, carve-outs, and API heaps may describe the same physical memory.

## 02.4 Three levels of GPU detection

Manually compare the collected files:

| Level | File | What to look for |
| --- | --- | --- |
| PCI / driver | `raw/pci.txt` | active `amdgpu` |
| Vulkan | `raw/vulkan-full.txt` | Radeon 8060S, ICD, API/driver versions, heap sizes and budgets |
| HSA / ROCm | `raw/rocminfo.txt` | `gfx1151` |

A software Vulkan renderer does not count as a GPU. With multiple devices, record the selected device and its render node; do not assume `/dev/dri/renderD128`.

## 02.5 Kernel versus KFD requirements

Check the kernel and ROCm against a specific **version** of AMD documentation. The cited prebuilt table lists gfx1151 requirements: Ubuntu HWE from `6.17.0-19.19~24.04.2`, OEM from `6.14.0-1018`, and other distributions from `6.18.4`. Check backports for your release. Record the URL, access date, and conclusion: `documented`, `conditional`, or `unverified`. Do not execute kernel-change commands in this lab.

## 02.6 First-series budget

Reserve 16 GiB for the OS unless LAB01 declares another value. The estimate must satisfy **both** limits:

```text
weights + runtime + KV/state <= measured_RAM - OS_reserve
allocations_on_GPU           <= measured_available_GPU_budget
```

If the budget API does not report it, leave it unknown. Do not substitute the advertised 96 GB for an observation.

After one minute idle:

```sh
free -b > "$LAB_DIR/raw/memory-after-idle.txt"
```

A substantial difference from the first measurement requires a description of background workloads.

## 02.7 Report

Fill in `report.md`, `measurements.tsv`, and `manifest.json`: link the LAB01 archive, give raw-evidence paths, and record admission or a concrete blocker **for each track** (Vulkan and HIP/ROCm separately). A passport does not become `run.json` or receive an agent-task verdict.

## Exit gates

- Target machine and native Linux confirmed.
- Each track has admission or a concrete blocker.
- RAM, TTM/GTT, and GPU budget are not summed as independent banks.

A submission with a blocker for one track is a valid diagnostic result, not admission to that track’s measurements.

> **If `vulkaninfo`, `rocminfo`, or `hipconfig` is unavailable:** mark it `unavailable` and submit the passport as it stands. Installing the stack and build dependencies (`cmake`, compiler, Vulkan headers and shader compiler, HIP SDK) is **separate work**, after which a new session, such as `ryzen-02`, collects a fresh passport. LAB04 does not install dependencies on the fly.

---

# LAB03. Artifacts and control GGUF

Prerequisite: LAB01 and LAB02 submitted. The minimum is a decision for all 12 candidates and **one** verified control GGUF, `qwen35-9b` Q6_K (≈7.0 GiB). A second control, `gpt-oss-20b` MXFP4 (11.3 GiB), and other downloads are extensions. All 12 artifacts total about 406.7 GiB; downloading all of them is not required for credit.

## 03.1 Archive and inputs

```sh
npm run lab:new -- --lab LAB03 --session "$LAB_SESSION"
```

```sh
export LAB_DIR="$LAB03_DIR"
mkdir -p "$LAB_STORAGE"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-before.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
cp experiments/local-models/models.json "$LAB_DIR/raw/catalog.json"
cp experiments/local-models/hardware.json "$LAB_DIR/raw/planning-hardware.json"
```

`manifest.json` must link the LAB02 passport and its measured `MemTotal`, `MemAvailable`, GPU heap/GTT, and swap.

## 03.2 Plan before downloading

Overall plan and control-model plan:

```sh
node scripts/local-plan.mjs --format json > "$LAB_DIR/raw/plan-default.json"
```

```sh
node scripts/local-plan.mjs --model qwen35-9b --context 8192 --format json > "$LAB_DIR/raw/control-plan.json"
```

The planner defaults to **hypotheses** of 119.2 GiB RAM, 89.4 GiB GPU budget, 16 GiB OS, 6 GiB runtime, and 4/8/16 GiB for 8K/16K/32K. Substitute LAB02 measurements and save a separate file with the exact command:

```sh
node scripts/local-plan.mjs --memory-gib NUMBER --gpu-budget-gib NUMBER --format json > "$LAB_DIR/raw/plan-measured.json"
```

For each of the 12 models, record “first run / later / exceeds selected budget” and a reconsideration condition. MoE loads all experts; active parameters describe only per-token computation. Hybrid attention accounts for cache/state separately.

## 03.3 Export an exact artifact

```sh
python3 - "$LAB_DIR" qwen35-9b <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1]) / "raw"
catalog = json.loads((out / "catalog.json").read_text())
model = next(m for m in catalog["models"] if m["id"] == sys.argv[2])
(out / "artifact.json").write_text(json.dumps(model, indent=2) + "\n")
print(json.dumps(model["artifact"], indent=2))
PY
```

Check `model_id`/`model_revision`, quantizer repository, `artifact.revision`, filenames and file count, `bytes`, `sha256`, precision, and license: base-model and GGUF revisions differ. An unavailable file or changed license gives `no-artifact` and stops this configuration.

## 03.4 Download script

```sh
cat > "$LAB_DIR/raw/fetch_artifact.py" <<'PY'
import argparse, hashlib, json, os, pathlib, re, urllib.parse, urllib.request

p = argparse.ArgumentParser()
p.add_argument("manifest")
p.add_argument("storage")
p.add_argument("--download", action="store_true")
a = p.parse_args()
model = json.loads(pathlib.Path(a.manifest).read_text())
artifact = model["artifact"]
repo, rev = artifact["repository"], artifact["revision"]
assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
assert re.fullmatch(r"[0-9a-f]{40}", rev)
root = (pathlib.Path(a.storage).expanduser() / repo / rev).resolve()
results = []
for item in artifact["files"]:
    rel = pathlib.PurePosixPath(item["path"])
    assert not rel.is_absolute() and ".." not in rel.parts
    dest = root.joinpath(*rel.parts)
    assert dest.resolve().is_relative_to(root)
    url = "https://huggingface.co/" + repo + "/resolve/" + rev + "/"
    url += urllib.parse.quote(str(rel), safe="/")
    if not dest.exists() and a.download:
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        # Do not run two copies of this script concurrently for one file.
        try:
            with urllib.request.urlopen(url, timeout=120) as src, partial.open("xb") as out:
                while chunk := src.read(8 * 1024 * 1024):
                    out.write(chunk)
            with partial.open("rb") as src:
                digest = hashlib.file_digest(src, "sha256").hexdigest()
            assert partial.stat().st_size == item["bytes"], "size mismatch"
            assert not item.get("sha256") or digest == item["sha256"], "hash mismatch"
            os.replace(partial, dest)
        except BaseException:
            # Retain .part for diagnosis; remove it only after investigating the error.
            raise
    if not dest.is_file():
        results.append({"path": str(dest), "status": "no-artifact"})
        continue
    with dest.open("rb") as src:
        digest = hashlib.file_digest(src, "sha256").hexdigest()
    size_ok = dest.stat().st_size == item["bytes"]
    hash_ok = not item.get("sha256") or digest == item["sha256"]
    results.append({"path": str(dest), "bytes": dest.stat().st_size,
                    "sha256": digest,
                    "publisher_hash_present": bool(item.get("sha256")),
                    "status": "verified" if size_ok and hash_ok else "fail"})
print(json.dumps({"repository": repo, "revision": rev,
                  "files": results}, indent=2))
raise SystemExit(0 if all(x["status"] == "verified" for x in results) else 1)
PY
```

The script does not resume interrupted downloads or silently replace an invalid existing file. Check disk headroom against `artifact.total_bytes`, temporary files, and future service copies.

## 03.5 Download and repeat offline verification

```sh
python3 --version > "$LAB_DIR/raw/python-version.txt"
python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/download-verification.json"
```

```sh
python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/verification.json"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-after.txt"
```

On error, retain stderr and the nonzero exit code. Split GGUF requires **all** original shards in their original structure; pass the first shard to the server afterward. Do not concatenate or rename shards. A vision projector, speculative draft, or different quantization requires a new manifest.

## 03.6 Pass the artifact downstream

Checksum file for `sha256sum --check` in LAB04–07 (JSON is not suitable):

```sh
python3 - "$LAB_DIR" <<'PY'
import json, pathlib, sys
raw = pathlib.Path(sys.argv[1]) / "raw"
verification = json.loads((raw / "verification.json").read_text())
assert verification["files"]
lines = []
for item in verification["files"]:
    assert item["status"] == "verified" and item["publisher_hash_present"]
    path = pathlib.Path(item["path"])
    assert path.is_absolute() and "\n" not in str(path) and "\\" not in str(path)
    lines.append(item["sha256"] + "  " + str(path) + "\n")
(raw / "weights.sha256").write_text("".join(lines))
PY
```

```sh
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/checksums-recheck.txt"
```

```sh
sha256sum "$LAB_DIR/raw/catalog.json" "$LAB_DIR/raw/artifact.json" "$LAB_DIR/raw/fetch_artifact.py" > "$LAB_DIR/raw/input-hashes.txt"
```

Pin the weights path in the session environment file (for split GGUF, ensure this is the **first** shard):

```sh
python3 -c "import json,os,pathlib;d=json.loads(pathlib.Path(os.environ['LAB03_DIR']+'/raw/verification.json').read_text());print('export LOCAL_GGUF=\"'+next(f['path'] for f in d['files'] if f['path'].endswith('.gguf'))+'\"')" | tee -a "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && test -f "$LOCAL_GGUF" && echo "$LOCAL_GGUF"
```

## Exit gates

- All 12 candidates have a decision with memory conditions and queue position.
- All bytes and SHA-256 values for the control GGUF are verified, or `no-artifact`/`fail` is documented with a reason.
- The manifest distinguishes model revision, quantizer revision, quantization, and shards.
- Unexecuted runs remain `not-run`; estimates are not called measurements. Weights are not added to Git.

---

# LAB04. llama.cpp: Vulkan versus HIP/ROCm

Prerequisites: LAB02 and LAB03 submitted; `cmake`, compiler, Vulkan headers and shader compiler, and HIP SDK are **already installed**. Build failures do not justify installing dependencies on the fly.

Both tracks are mandatory. One being absent is a blocker, not a victory for the other.

## 04.1 Pin the commit

Choose one llama.cpp commit based on support for your model architecture and quantization; record the full 40-character SHA and selection date. Neither `master` nor a release number identifies a build.

```sh
npm run lab:new -- --lab LAB04 --session "$LAB_SESSION"
```

Enter the SHA in the environment file, then reload it:

```sh
"${EDITOR:-nano}" "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && export LAB_DIR="$LAB04_DIR" && python3 -c "import os,re,sys; sys.exit(0 if re.fullmatch(r'[0-9a-f]{40}', os.environ['LLAMA_COMMIT']) else 'set full lowercase commit SHA')"
```

If no separate checkout exists (`LLAMA_SOURCE` must be a new, unoccupied directory):

```sh
git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE" && git -C "$LLAMA_SOURCE" checkout --detach "$LLAMA_COMMIT"
```

## 04.2 Inputs and weights verification

```sh
test "$(uname -s)" = Linux && test -f "$LOCAL_GGUF" && test "$(git -C "$LLAMA_SOURCE" rev-parse HEAD)" = "$LLAMA_COMMIT" && echo ok
```

```sh
git -C "$LLAMA_SOURCE" rev-parse HEAD > "$LAB_DIR/raw/llama-commit.txt"
git -C "$LLAMA_SOURCE" status --porcelain > "$LAB_DIR/raw/llama-status.txt"
cmake --version > "$LAB_DIR/raw/cmake-version.txt"
hipconfig --full > "$LAB_DIR/raw/hipconfig.txt" 2>&1
vulkaninfo --summary > "$LAB_DIR/raw/vulkan-summary.txt" 2>&1
```

`git status --porcelain` must be empty. If local patches exist, retain the diff and apply it identically to both builds; this is a separate variant from the clean pin.

```sh
cp "$LAB03_DIR/raw/artifact.json" "$LAB_DIR/raw/artifact.json"
cp "$LAB03_DIR/raw/weights.sha256" "$LAB_DIR/raw/weights.sha256"
sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/verification-before.txt"
```

Stop on a nonzero exit code. Hashing reads all weights and warms the filesystem cache; account for this when describing cache state.

## 04.3 Two builds from one checkout

```sh
(
set -eu
cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-vulkan" \
  -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release \
  > "$LAB_DIR/raw/configure-vulkan.log" 2>&1
cmake --build "$LAB_DIR/build-vulkan" --config Release -j 8 \
  > "$LAB_DIR/raw/build-vulkan.log" 2>&1

HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -S "$LLAMA_SOURCE" -B "$LAB_DIR/build-hip" \
  -DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_BUILD_TYPE=Release \
  > "$LAB_DIR/raw/configure-hip.log" 2>&1
cmake --build "$LAB_DIR/build-hip" --config Release -j 8 \
  > "$LAB_DIR/raw/build-hip.log" 2>&1
)
```

Do not add `HSA_OVERRIDE_GFX_VERSION` to the baseline or substitute another architecture target just to pass. Preserve the entire error.

## 04.4 Binary inventory

```sh
for backend in vulkan hip; do
  binary="$LAB_DIR/build-$backend/bin/llama-bench"
  "$binary" --help > "$LAB_DIR/raw/$backend-bench-help.txt" 2>&1
  "$binary" --list-devices > "$LAB_DIR/raw/$backend-devices.txt" 2>&1
  "$LAB_DIR/build-$backend/bin/llama-server" --version \
    > "$LAB_DIR/raw/$backend-version.txt" 2>&1
  sha256sum "$binary" "$LAB_DIR/build-$backend/bin/llama-server" \
    > "$LAB_DIR/raw/$backend-binaries.sha256"
  cp "$LAB_DIR/build-$backend/CMakeCache.txt" "$LAB_DIR/raw/$backend-CMakeCache.txt"
done
```

Check pinned `--help` for `-fa on`, `-ctk/-ctv`, `-d`, `-r`, and `-o json`. If syntax differs, adapt and retain commands using documentation for the selected commit. Automatic device selection is allowed only after confirming Radeon 8060S in both tracks.

## 04.5 Warmup

```sh
(
set -eu
for backend in vulkan hip; do
  "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
    -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
    -p 512 -n 128 -r 1 -o json \
    > "$LAB_DIR/raw/$backend-warmup.json" \
    2> "$LAB_DIR/raw/$backend-warmup.log"
done
)
```

Find the actual GPU-layer count, backend, and allocations in logs: `-ngl 999` is a request, not proof of full offload. CPU tokenization and sampling are allowed; model layers on CPU constitute a separate configuration. Stop the track on OOM, GPU reset, invalid data, or exceeded budget. Do not silently reduce KV precision, context, or offload.

## 04.6 Telemetry — terminal B, start before the series

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB04_DIR" && vmstat -w 1 > "$LAB_DIR/raw/vmstat-series.txt"
```

Stop with Ctrl-C after the series. Mark missing sensors `null`. Do not add process RSS, GPU allocation, and page cache without analyzing UMA overlap.

## 04.7 Three paired repeats — terminal A

```sh
(
set -eu
test -x /usr/bin/time
for repeat in 1 2 3; do
  if [ "$repeat" = 2 ]; then set -- hip vulkan; else set -- vulkan hip; fi
  for backend do
    prefix="$LAB_DIR/raw/$backend-r$repeat"
    free -b > "$prefix-memory-before.txt"
    cat /proc/vmstat > "$prefix-vmstat-before.txt"
    /usr/bin/time -v -o "$prefix-pp-process.txt" \
      "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
      -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
      -p 2048 -n 0 -r 1 -o json \
      > "$prefix-pp.json" 2> "$prefix-pp.log"
    /usr/bin/time -v -o "$prefix-tg-process.txt" \
      "$LAB_DIR/build-$backend/bin/llama-bench" -m "$LOCAL_GGUF" \
      -ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
      -p 0 -n 128 -d 4096 -r 1 -o json \
      > "$prefix-tg.json" 2> "$prefix-tg.log"
    cat /proc/vmstat > "$prefix-vmstat-after.txt"
    free -b > "$prefix-memory-after.txt"
  done
done
)
```

Do not run both tracks concurrently. `/usr/bin/time` is GNU time, not a shell keyword; if absent, record a blocker for process metrics. A successful exit code still requires checking logs for offload and allocations; do not report partial JSON as a successful measurement.

## 04.8 Analysis

Describe cache state separately: each `llama-bench` is a new process, but the filesystem cache is not cold. Write “process cold / filesystem warm or unknown”. Built-in warmup is excluded from t/s, whereas `/usr/bin/time` includes the entire process; do not label process wall time as model-load time.

Transfer the three individual results to `measurements.tsv`; calculate median/min/max and the `median_HIP / median_Vulkan` ratio for each mode. If quantization, FA, or offload differs, do not interpret the ratio as a pure backend effect. Assess swap activity from before/after `pswpin`/`pswpout`. Finish by repeating weights-SHA and commit checks.

## Exit gates

- Both tracks are built from one commit and use identical weights SHAs.
- Radeon 8060S, actual offload, and identical settings are confirmed.
- Warmup and three paired repeats exist, or a concrete blocker is recorded.
- Swap and budgets are checked; no hidden fallback occurred.

---

# LAB05. Context 8/16/32K, streaming, and tools

The key lab in this track: it makes the server suitable for agents and opens LAB08.

Contexts increase strictly in order: **8192 → 16384 → 32768**, proceeding only after the previous context meets its budgets. Do not launch three servers concurrently. The agent baseline is 16K; 32K remains a separate variant.

One backend is shown below. Repeat for the second backend in a **new archive** (for example, `--session ryzen-01-vulkan`), rather than appending to this one.

## 05.1 Archive, backend, and fixtures

```sh
npm run lab:new -- --lab LAB05 --session "$LAB_SESSION"
```

Select a backend that passed LAB04 and pin its binary path in the environment file (HIP here; use `build-vulkan` for Vulkan):

```sh
echo "export LLAMA_BIN=\"$LAB04_DIR/build-hip/bin\"" | tee -a "$HOME/lab-ryzen-01.env"
```

```sh
source "$HOME/lab-ryzen-01.env" && export LAB_DIR="$LAB05_DIR" && test -x "$LLAMA_BIN/llama-server" && test -f "$LOCAL_GGUF" && echo ok
```

```sh
cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
sha256sum "$LAB_DIR/raw/chat-request.json" "$LAB_DIR/raw/tool-request.json" > "$LAB_DIR/raw/fixtures.sha256"
```

The `model` field in both fixtures is `lab-model`, matching the server’s `--alias lab-model` below. For another alias, modify fixtures before the series and give the change its own SHA.

```sh
"$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
"$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
sha256sum "$LLAMA_BIN/llama-server" "$LLAMA_BIN/llama-bench" > "$LAB_DIR/raw/binaries.sha256"
```

Check pinned help for `--alias`, `--no-context-shift`, `-np`, `-fa`, and `-d`. Record sampling and reasoning from the model card in `raw/model-settings.txt` and the manifest; apply them identically in all three contexts. A modified template gets its own SHA and separate variant.

## 05.2 Memory-fill probe without HTTP

Terminal B, before the probe:

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB05_DIR" CTX=8192 && vmstat -w 1 > "$LAB_DIR/raw/context-$CTX-vmstat-series.txt"
```

Terminal A:

```sh
export CTX=8192
DEPTH=$((CTX - 128))
free -b > "$LAB_DIR/raw/context-$CTX-memory-before.txt"
cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-before.txt"
if /usr/bin/time -v -o "$LAB_DIR/raw/context-$CTX-process.txt" \
  "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
  -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
  -p 0 -n 128 -d "$DEPTH" -r 3 -o json \
  > "$LAB_DIR/raw/context-$CTX-bench.json" \
  2> "$LAB_DIR/raw/context-$CTX-bench.log"; then
  bench_status=0
else
  bench_status=$?
fi
printf '%s\n' "$bench_status" > "$LAB_DIR/raw/context-$CTX-exit.txt"
free -b > "$LAB_DIR/raw/context-$CTX-memory-after.txt"
cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-after.txt"
test "$bench_status" -eq 0
```

Depths are 8064, 16256, and 32640 tokens before 128 generated tokens. Built-in warmup is excluded from the three measured repeats. Check the recorded exit code before proceeding. Stop the configuration on OOM, GPU reset, sustained swap, fallback, or exceeded budget; do not automatically launch a longer context. Changing KV or FA to fit is a new variant, not a correction of the result.

## 05.3 Server for this context — terminal C

```sh
source "$HOME/lab-ryzen-01.env" && cd "$LAB_ROOT" && export LAB_DIR="$LAB05_DIR" CTX=8192 && "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" --host 127.0.0.1 --port 8080 --alias lab-model -ngl 999 -c "$CTX" -np 1 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa on --jinja --no-context-shift > "$LAB_DIR/raw/server-$CTX.log" 2>&1
```

Add the recorded model-specific sampling/reasoning flags here. Keep the server on loopback only. Terminal A, after the health response:

```sh
curl --fail --max-time 10 http://127.0.0.1:8080/health > "$LAB_DIR/raw/health-$CTX.json"
curl --fail --max-time 10 http://127.0.0.1:8080/props > "$LAB_DIR/raw/props-$CTX.json"
curl --fail --max-time 10 http://127.0.0.1:8080/v1/models > "$LAB_DIR/raw/models-$CTX.json"
```

Confirm alias `lab-model`, GPU offload, effective context and slots, and template. `--reasoning-format` describes result parsing, not thinking mode: do not claim thinking is disabled merely because reasoning is absent from `content`.

## 05.4 HTTP/SSE measurement tool

```sh
cat > "$LAB_DIR/raw/http_probe.py" <<'PY'
import argparse, json, pathlib, time, urllib.error, urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url')
parser.add_argument('--request')
parser.add_argument('--out', required=True)
parser.add_argument('--follow-tool', action='store_true')
parser.add_argument('--validate-tool-message')
args = parser.parse_args()
def save(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def validate_tool(message):
    calls = message.get('tool_calls', [])
    if len(calls) != 1:
        raise ValueError('expected exactly one tool call')
    tool = calls[0]
    function = tool['function']
    arguments = json.loads(function['arguments'])
    if tool.get('type') != 'function':
        raise ValueError('only function tools allowed')
    if function['name'] != 'lookup_lab_value' or arguments != {'key': 'alpha'}:
        raise ValueError('tool/arguments rejected by allowlist')
    if not tool.get('id'):
        raise ValueError('missing tool call id')
    return tool

if args.validate_tool_message:
    try:
        validate_tool(json.loads(pathlib.Path(args.validate_tool_message).read_text()))
        save(args.out + '.tool-validation.json', {'accepted': True})
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise SystemExit(1)
    raise SystemExit(0)
if not args.url or not args.request:
    parser.error('--url and --request are required for HTTP probes')

def call(payload, prefix):
    save(prefix + '.request.json', payload)
    metrics = {'ttft_content_s': None, 'ttft_reasoning_s': None, 'usage': None}
    start = time.perf_counter()
    request = urllib.request.Request(args.url.rstrip('/') + '/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            metrics['http_status'] = response.status
            if not payload.get('stream'):
                value = json.load(response)
                save(prefix + '.response.json', value)
                message = value['choices'][0]['message']
                metrics['finish_reason'] = value['choices'][0].get('finish_reason')
                metrics['usage'] = value.get('usage')
            else:
                message = {'role': 'assistant', 'content': ''}
                tools, reasoning, done = {}, '', False
                with open(prefix + '.sse', 'wb') as raw:
                    for line in response:
                        raw.write(line)
                        raw.flush()
                        if not line.startswith(b'data:'):
                            continue
                        data = line[5:].strip()
                        if data == b'[DONE]':
                            done = True
                            break
                        if not data:
                            continue
                        event = json.loads(data)
                        if event.get('error'):
                            raise ValueError(str(event['error']))
                        if event.get('usage') is not None:
                            metrics['usage'] = event['usage']
                        for choice in event.get('choices', []):
                            delta = choice.get('delta', {})
                            content = delta.get('content') or ''
                            thought = delta.get('reasoning_content') or ''
                            if content and metrics['ttft_content_s'] is None:
                                metrics['ttft_content_s'] = time.perf_counter() - start
                            if thought and metrics['ttft_reasoning_s'] is None:
                                metrics['ttft_reasoning_s'] = time.perf_counter() - start
                            message['content'] += content
                            reasoning += thought
                            for piece in delta.get('tool_calls', []):
                                item = tools.setdefault(piece['index'], {'id': '',
                                    'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                if piece.get('id'):
                                    item['id'] = piece['id']
                                function = piece.get('function', {})
                                item['function']['name'] += function.get('name') or ''
                                item['function']['arguments'] += function.get('arguments') or ''
                            if choice.get('finish_reason') is not None:
                                metrics['finish_reason'] = choice['finish_reason']
                if tools:
                    message['tool_calls'] = [tools[index] for index in sorted(tools)]
                if reasoning:
                    message['reasoning_content'] = reasoning
                metrics['stream_done'] = done
                save(prefix + '.assembled.json', message)
                if not done:
                    raise ValueError('SSE ended without [DONE]')
            metrics['duration_s'] = time.perf_counter() - start
            save(prefix + '.metrics.json', metrics)
            return message
    except Exception as error:
        if isinstance(error, urllib.error.HTTPError):
            metrics['http_status'] = error.code
            pathlib.Path(prefix + '.http-error.txt').write_bytes(error.read())
        metrics.update(error=str(error), duration_s=time.perf_counter() - start)
        save(prefix + '.metrics.json', metrics)
        raise

payload = json.loads(pathlib.Path(args.request).read_text())
message = call(payload, args.out)
if args.follow_tool:
    try:
        tool = validate_tool(message)
    except Exception as error:
        save(args.out + '.tool-rejected.json', {'reason': str(error)})
        raise
    followup = dict(payload)
    followup['messages'] = payload['messages'] + [message, {
        'role': 'tool', 'tool_call_id': tool['id'], 'content': 'LAB_VALUE_42'}]
    message = call(followup, args.out + '.followup')
save(args.out + '.final.json', {'content': message.get('content'),
    'tool_calls': message.get('tool_calls'), 'reasoning_content': message.get('reasoning_content')})
PY
```

Measure TTFT only for streaming: latency to a complete JSON response is not TTFT. `ttft_content_s` is distinct from time to the first reasoning token.

## 05.5 Four protocol cases, twice each

```sh
python3 - <<'PY'
import json, os, pathlib
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
for kind in ('chat', 'tool'):
    value = json.loads((root / (kind + '-request.json')).read_text())
    value['stream'] = True
    (root / (kind + '-stream-request.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
PY
```

```sh
for repeat in 1 2; do
  for kind in chat chat-stream; do
    python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
      --request "$LAB_DIR/raw/$kind-request.json" \
      --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat"
  done
  for kind in tool tool-stream; do
    python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
      --request "$LAB_DIR/raw/$kind-request.json" \
      --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat" --follow-tool
  done
done
```

Expected final values: `LAB_READY` for chat and `LAB_VALUE_42` for the tool round-trip. Check matching `call_id`, valid JSON arguments, terminal event, and finish reason. Label initial and repeated requests separately: the second may use prefix cache. Record missing usage as `null`; do not infer tokens from text length. An incomplete round-trip is not a pass even with HTTP 200.

## 05.6 Dispatcher rejects an unknown tool

No endpoint is called; this checks the client boundary.

```sh
python3 - <<'PY'
import copy, json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
valid = {'role': 'assistant', 'content': None, 'tool_calls': [{
    'id': 'offline-case-1', 'type': 'function',
    'function': {'name': 'lookup_lab_value', 'arguments': '{"key":"alpha"}'}}]}
cases = {'valid': valid}
for name, field, value in [('unknown-name', 'name', 'unexpected_tool'),
                          ('wrong-arguments', 'arguments', '{"key":"beta"}')]:
    message = copy.deepcopy(valid)
    message['tool_calls'][0]['function'][field] = value
    cases[name] = message
message = copy.deepcopy(valid)
del message['tool_calls'][0]['id']
cases['missing-id'] = message
results = {}
for name, message in cases.items():
    prefix = root / ('offline-tool-' + name)
    source = pathlib.Path(str(prefix) + '-message.json')
    source.write_text(json.dumps(message, indent=2))
    result = subprocess.run([sys.executable, str(root / 'http_probe.py'),
        '--validate-tool-message', str(source), '--out', str(prefix)], check=False)
    expected = 0 if name == 'valid' else 1
    results[name] = {'exit_code': result.returncode, 'expected_exit_code': expected}
(root / 'offline-tool-checks.json').write_text(json.dumps(results, indent=2))
assert all(row['exit_code'] == row['expected_exit_code'] for row in results.values())
PY
```

In `offline-tool-*.tool-rejected.json`, confirm the specific reasons `tool/arguments rejected by allowlist` and `missing tool call id`, not an arbitrary Python error; the valid case must report `accepted: true`.

## 05.7 Long input accounting for the template

The generator uses `/apply-template` and `/tokenize`, without inference. If the pinned server lacks these endpoints, record a methodology blocker and count length separately with its tokenizer.

```sh
python3 - <<'PY'
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = int(os.environ['CTX'])
budget = context - 4096
def post(route, value):
    request = urllib.request.Request('http://127.0.0.1:8080' + route,
        data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)
def candidate(rows):
    text = 'Control value: LAB_SENTINEL_42.\n'
    text += ''.join(f'Row {i}: neutral measurement data.\n' for i in range(rows))
    text += 'Return only the control value from the first row.'
    messages = [{'role': 'user', 'content': text}]
    prompt = post('/apply-template', {'messages': messages})['prompt']
    tokens = post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens']
    return messages, prompt, len(tokens)
low, high, best = 0, context, None
while low <= high:
    middle = (low + high) // 2
    messages, prompt, count = candidate(middle)
    if count <= budget:
        best = (messages, prompt, count)
        low = middle + 1
    else:
        high = middle - 1
if best is None:
    raise RuntimeError('template exceeds input budget')
messages, prompt, count = best
payload = {'model': 'lab-model', 'messages': messages, 'max_tokens': 4096, 'stream': True}
prefix = root / ('ctx' + str(context) + '-long')
pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
pathlib.Path(str(prefix) + '-prompt.txt').write_text(prompt)
pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({
    'context': context, 'input_tokens': count, 'output_reserve': 4096, 'input_budget': budget}, indent=2))
PY
```

```sh
for repeat in 1 2; do
  python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
    --request "$LAB_DIR/raw/ctx$CTX-long-request.json" \
    --out "$LAB_DIR/raw/ctx$CTX-long-r$repeat"
done
```

Compare server `usage.prompt_tokens` with the preliminary count: a discrepancy indicates a different effective template or tokenization and needs explanation. Expected final value: `LAB_SENTINEL_42`, and only without truncation or context shift.

## 05.8 Overflow, cancellation, and recovery

```sh
python3 - <<'PY'
import json, os, pathlib, urllib.request
root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
context = int(os.environ['CTX'])
source = root / ('ctx' + str(context) + '-long-request.json')
payload = json.loads(source.read_text())
text = payload['messages'][0]['content']
for attempt in range(8):
    text = text + '\n' + text
    payload['messages'][0]['content'] = text
    def post(route, value):
        request = urllib.request.Request('http://127.0.0.1:8080' + route,
            data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    prompt = post('/apply-template', {'messages': payload['messages']})['prompt']
    count = len(post('/tokenize', {'content': prompt,
        'add_special': False, 'parse_special': True})['tokens'])
    if count > context:
        break
else:
    raise RuntimeError('could not construct overflow within bounded attempts')
payload['max_tokens'] = 128
prefix = root / ('ctx' + str(context) + '-overflow')
pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False))
pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({'input_tokens': count, 'context': context}))
PY
```

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/ctx$CTX-overflow-request.json" --out "$LAB_DIR/raw/ctx$CTX-overflow"
```

Run recovery as a **separate command**, even if an expected HTTP error made the probe exit nonzero:

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-overflow-recovery"
```

Expect explicit rejection or a documented limit; silent truncation is incompatible with the baseline.

```sh
if curl --no-buffer --max-time 1 -H 'Content-Type: application/json' \
  --data-binary @"$LAB_DIR/raw/ctx$CTX-long-request.json" \
  http://127.0.0.1:8080/v1/chat/completions \
  > "$LAB_DIR/raw/ctx$CTX-cancel.sse" 2> "$LAB_DIR/raw/ctx$CTX-cancel.log"; then
  printf '0\n' > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
else
  printf '%s\n' "$?" > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
fi
```

```sh
python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-cancel-recovery"
```

A client timeout does not prove that the server cancelled computation: check the server log, slot, and recovery time. If the request finished within a second, this did not test cancellation; repeat with a longer request.

## 05.9 Next context

Stop the server with Ctrl-C in terminal C and verify process exit and memory release. Then repeat 05.2–05.8 with `CTX=16384`, followed by `CTX=32768`, only if the previous budgets were respected. Record identical settings and each run’s context separately in the manifest.

## Exit gates

- Each context has a memory-fill probe or a recorded blocker.
- Admitted contexts have two repeats of chat, streaming, tools, and streaming tools.
- Tool round-trip is checked through an allowlist without arbitrary code execution.
- Long input is tokenizer-counted and checked for silent truncation.
- Reasoning and final content, output cap, and finish reason are described separately.
- Error handling, cancellation, and slot recovery are checked.

A lab with an honestly recorded 16K ceiling counts as complete. This does not mean the model passed 32K or is ready for every agent protocol.

---

# Evidence hygiene

The root `.gitignore` excludes `*.log`; `experiments/local-models/.gitignore` excludes `measurements/*/build-vulkan/`, `measurements/*/build-hip/`, `measurements/*/raw/sglang-src/`, and `measurements/*/raw/ollama-models/`. A normal commit **does not transfer the entire raw-evidence set**: archive `raw/` separately and reference the archive in `manifest.json`.

Never delete failed attempts. `null` or empty means unknown with a reason; `0` means a measured zero only. A number without units, context, and conditions is excluded from comparison.

At the end of each lab:

```sh
npm run check
```

This checks assignment structure, catalogs, and run records; it **does not award credit for the report**.

# Next steps

| Destination | What it provides | Prerequisite |
| --- | --- | --- |
| [LAB07](../../docs/labs/LAB07-serving.md) | Two services from Ollama / LM Studio / Lemonade on the same GGUF | LAB05 |
| [LAB06](../../docs/labs/LAB06-engines.md) | vLLM, SGLang, Transformers on ROCm; requires a separate native BF16 checkpoint, without reusing GGUF | LAB03 and LAB05 |
| [LAB08](../../docs/labs/LAB08-local-bridge.md) | Local provider bridge: the only path to local LAB09–10 | LAB01 and LAB05 |

The LAB08 design work (endpoint contract, network boundary, schema fields for the inference fingerprint) can proceed in parallel while LAB04 builds run.
