# LAB 02. Ryzen AI Max+ 395 profile and available Linux memory

## Profile

| Field | Value |
| --- | --- |
| Estimated time | 45–90 minutes with diagnostic utilities available |
| Prerequisites | LAB 01 completed; working directly on the target Ryzen under Linux; Node.js and Python 3 available |
| Readiness status | Instructions ready; machine parameters and hardware smoke tests remain `unverified` |
| Outcome | CPU/GPU/OS profile, initial RAM and GPU budgets, decision on admission to subsequent labs |

Run commands from the lab repository root on the target Linux machine. This lab reads system state and creates an observation archive. It does not install packages or change the BIOS, kernel, TTM/GTT, drivers, or power profile.

## Objective

Establish the actual Ryzen AI Max+ 395 configuration and the memory that can safely be budgeted for one local model, reserving capacity for the OS and harness.

## Hypothesis

A Radeon 8060S / `gfx1151` is available on the machine and visible to Vulkan and ROCm, and measured shared-memory and GPU budgets allow memory to be allocated for the model without double-counting UMA. “128 GB” in the computer's description does not by itself confirm this hypothesis.

## Preparation

- Close active inference processes yourself; do not terminate unfamiliar user processes.
- Record the computer model, power mode, whether it is on AC power, active desktop environment, and significant background workloads. Do not publish the serial number.
- Choose a new `session-id`. The example uses `my-session`; a repeated lab gets a different name.
- Mark missing `vulkaninfo`, `rocminfo`, or `hipconfig` as `unavailable`. Installing a missing stack is a separate task, after which the profile must be collected again.

## Procedure

1. Create the lab archive and verify the target OS:

   ```sh
   npm run lab:new -- --lab LAB02 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB02-my-session'
   test "$(uname -s)" = Linux
   test -d "$LAB_DIR/raw"
   ```

   If this is macOS, WSL, or another machine, stop and record the reason in the report. This series requires native Linux on Ryzen; someone else's result or a virtual machine does not replace the owner's machine profile.

2. Collect available information, preserving errors and missing utilities. The script does not abort the entire collection if one sensor is unavailable:

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

3. Read only available UMA sysfs parameters and convert the units. The script saves both original bytes and GiB; TTM parameters remain separate from RAM capacity:

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

   `pages_limit × page_size_bytes` is the TTM page limit, not guaranteed free GPU memory. Do not add it to `MemTotal`, VRAM, or GTT. Shared UMA, a dedicated carve-out, and an API heap may describe overlapping physical memory.

4. Compare three detection levels: PCI/driver, Vulkan device, and HSA/ROCm device. Find Radeon 8060S in `vulkan-full.txt`, `gfx1151` in `rocminfo.txt`, and an active `amdgpu` in `pci.txt`. A software Vulkan renderer does not count as a GPU. Save ICD names, API/driver versions, heap sizes, and budgets where available. If there are multiple devices, identify the selected device and its render node; do not assume it is always `/dev/dri/renderD128`.

5. Compare the kernel and ROCm against a **version** of the AMD documentation. For gfx1151, AMD describes required KFD fixes; the cited prebuilt table lists Ubuntu HWE from `6.17.0-19.19~24.04.2`, OEM from `6.14.0-1018`, and other distributions from `6.18.4`. Check backports and limitations of your release. Record the URL, access date, and conclusion: `documented`, `conditional`, or `unverified`. Do not execute any kernel-changing commands from external instructions during this lab.

6. Record the first series' budget in the report: actual RAM, OS/harness reserve, separately available GPU budget, and the source of every number. The initial OS reserve is 16 GiB unless another was declared in LAB 01. The preliminary model estimate must satisfy both constraints:

   ```text
   weights + runtime + KV/state <= measured_RAM - OS_reserve
   allocations_on_GPU <= measured_available_GPU_budget
   ```

   If the API does not provide a budget, leave it unknown: a subsequent load test is needed for confirmation. Do not substitute the advertised 96 GB for an observation. After one minute of normal idle time, repeat the measurement; a significant change requires describing background workloads:

   ```sh
   free -b > "$LAB_DIR/raw/memory-after-idle.txt"
   ```

7. Complete `report.md`, `measurements.tsv`, and the draft `manifest.json` created by the helper. Reference the LAB 01 archive dependencies and raw evidence paths. Do not convert the profile into `run.json` or assign it an agent-task verdict.

## Results tables

Fill empty cells after execution. Represent unknown values as `null`, with a reason in the report.

| Metric | Observed value | Unit | Evidence file |
| --- | --- | --- | --- |
| CPU / OEM | | | |
| Linux / kernel / BIOS | | | |
| MemTotal / MemAvailable | | bytes and GiB | |
| OS reserve | | GiB | |
| TTM pages limit / page size | | pages / bytes | |
| Vulkan device / ICD / driver | | | |
| Vulkan heap / available budget | | bytes and GiB | |
| ROCm version / HSA target | | | |
| Swap / power mode | | | |

| Branch | Device detected | Stack matches documentation | Admission / blocker reason |
| --- | --- | --- | --- |
| Vulkan | | | |
| HIP/ROCm | | | |

## Deliverables

- `report.md`: profile, reserve calculation, admission decision, and answers to questions.
- `measurements.tsv`: measured numeric fields with units.
- `manifest.json`: session identifier and evidence references; this is a lab draft.
- `raw/collection-status.json`, `raw/memory-inventory.json`, `raw/meminfo.txt`, `raw/kernel.txt`, `raw/os-release.txt`, `raw/pci.txt`, `raw/vulkan-full.txt`, `raw/rocminfo.txt`, `raw/hipconfig.txt`, `raw/memory-after-idle.txt`; for unavailable data, preserve the reason.

## Completion criteria

- [ ] The target machine and native Linux are confirmed.
- [ ] CPU/GPU/OS/BIOS information and diagnostic utility statuses are collected.
- [ ] RAM, TTM/GTT, and GPU budgets are not added as independent memory banks.
- [ ] Each branch has an admission decision or a specific blocker, including unknowns.
- [ ] The OS reserve is justified; tables are supported by raw files.
- [ ] BIOS, kernel, memory, and power profile were not changed during collection.

You may submit the lab with one backend blocked: this is a valid diagnostic result, not successful admission to measurements on that backend.

## Review questions

1. Why does a 128 GB label not establish a 128 GiB memory budget for the model?
2. How do `MemAvailable`, the TTM page limit, and the Vulkan memory budget differ?
3. Why does `torch.cuda.is_available()` or the presence of `gfx1151` not yet prove full GPU offload of the model?
4. Which machine changes require a new profile?

## Sources

- [AMD Ryzen AI Max+ 395: specification](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
- [AMD VGM FAQ: 96 GB claim and shared memory](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html).
- [AMD ROCm 7.14.1: RDNA3.5, TTM, and KFD requirements](https://rocm.docs.amd.com/en/docs-7.14.1/reference/system-optimization/rdna3-5.html).
- [Versioned ROCm 7.14.1 compatibility matrix](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html).
- [Lab course](README.md), [report template](templates/report.md), [local-model plan](../local-models.md).
