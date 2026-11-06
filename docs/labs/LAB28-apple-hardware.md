# LAB28. Apple M5 Max hardware profile and unified memory

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Hardware measurement / `target-machine` |
| Time | 1–2 hours |
| Prerequisites | LAB01; the M5 Max / 128 GB machine, native macOS |
| Minimum | Hardware profile, two memory snapshots 60 seconds apart, planned budget and admission decision |

## Objective

Distinguish physical RAM, macOS memory state and Metal recommendations from the memory budget actually available to the model.

## Hypothesis

The machine matches its stated configuration and is suitable for an initial single-model smoke test with a 16 GiB OS reserve. An unknown GPU budget does not confirm that the model fits.

## Preparation

Read the [shared Apple protocol](../../experiments/local-models/apple/README.md). Create a session and complete the protocol before collecting data:

```sh
npm run lab:new -- --lab LAB28 --session apple-first
export LAB_DIR='experiments/local-models/measurements/LAB28-apple-first'
```

Do not change memory limits, macOS, Xcode or the power mode during collection. Serial numbers, UUIDs and a full application list are not required.

## Procedure

1. Save a minimal hardware profile. A command failure stays in its output file and status registry; do not replace it with zero:

   ```sh
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, subprocess, sys
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   commands = {
       'os': ['sw_vers'], 'arch': ['uname', '-m'],
       'cpu': ['sysctl', 'machdep.cpu.brand_string', 'hw.ncpu', 'hw.memsize'],
       'gpu': ['system_profiler', 'SPDisplaysDataType'],
       'developer-path': ['xcode-select', '-p'], 'compiler': ['xcrun', 'clang', '--version'],
       'sdk': ['xcrun', '--show-sdk-version'], 'power': ['pmset', '-g', 'custom'],
       'memory-before': ['vm_stat'], 'swap-before': ['sysctl', 'vm.swapusage'],
       'pressure-before': ['memory_pressure', '-Q'],
   }
   status = {}
   for name, command in commands.items():
       try:
           p = subprocess.run(command, capture_output=True, text=True, timeout=60)
           body, code = p.stdout + p.stderr, p.returncode
       except (OSError, subprocess.TimeoutExpired) as e:
           body, code = str(e), None
       (raw / (name + '.txt')).write_text(body)
       status[name] = {'command': command, 'exit_code': code}
   (raw / 'collection-status.json').write_text(json.dumps(status, indent=2))
   PY
   ```

2. Check `arm64`, the SoC name, CPU/GPU cores, macOS version/build and SDK. `hw.memsize / 2**30` is physical RAM in GiB; do not divide it again as if it were decimal 128 GB. Preserve `xcrun` errors as build blockers; do not silently install an SDK during the experiment.

3. If Command Line Tools are ready, obtain the Metal recommendation with a short program. It does not allocate memory for a model:

   ```sh
   cat > "$LAB_DIR/raw/metal-device.swift" <<'SWIFT'
   import Metal
   import Foundation
   guard let device = MTLCreateSystemDefaultDevice() else {
       fputs("Metal device unavailable\n", stderr)
       exit(1)
   }
   let data: [String: Any] = [
       "name": device.name,
       "has_unified_memory": device.hasUnifiedMemory,
       "recommended_max_working_set_bytes": device.recommendedMaxWorkingSetSize,
       "max_buffer_length_bytes": device.maxBufferLength
   ]
   let encoded = try JSONSerialization.data(withJSONObject: data, options: [.prettyPrinted, .sortedKeys])
   print(String(decoding: encoded, as: UTF8.self))
   SWIFT
   xcrun swift "$LAB_DIR/raw/metal-device.swift" \
     > "$LAB_DIR/raw/metal-device.json" 2> "$LAB_DIR/raw/metal-device-errors.txt"
   printf '%s\n' "$?" > "$LAB_DIR/raw/metal-device-exit.txt"
   ```

   The working-set recommendation and maximum buffer length mean different things; neither is a free GPU budget. On failure, record `null` with a reason.

4. After 60 seconds of normal idle time, repeat `vm_stat`, `sysctl vm.swapusage`, `memory_pressure -Q` into `raw/*-after-idle.txt`. Record AC/battery power and background workloads. Do not add compressed, resident and GPU memory as independent banks.

5. Record `gpu_budget_gib=null` until you choose a justified safe working budget and run the LAB30/31 smoke test. For the first small model, describe the tentative ceiling and reserve separately; do not call it a measured allocation limit. The command must show an unknown final budget:

   ```sh
   npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --format json \
     > "$LAB_DIR/raw/initial-plan.json"
   ```

6. Decide which next steps the machine may proceed to: build, artifact preparation, initial smoke test. Save the profile in `raw/hardware-snapshot.json` with units, source-file paths and an explicitly unknown GPU budget; reference it in `conditions.hardware_snapshot`.

## Results tables

| Metric | Value | Unit | Evidence / reason unknown |
| --- | --- | --- | --- |
| SoC / CPU cores / GPU cores | | | |
| macOS build / SDK / arm64 | | | |
| hw.memsize | | bytes / GiB | |
| Metal recommended working set / max buffer | | bytes | |
| Swap before / after; memory pressure | | bytes / raw output | |
| OS reserve / working GPU budget | | GiB | |
| Admission to LAB30 / LAB31 | | | |

## Deliverables

Report, TSV, manifest v2; `collection-status.json`, hardware profile, system-command and Metal-probe output, plan and protocol. For unavailable commands, include the exit code and reason. `run.json` is not required.

## Completion criteria

- [ ] Machine, OS, architecture and physical memory confirmed.
- [ ] Two snapshots and power conditions saved.
- [ ] Metal recommendation is not presented as free memory.
- [ ] Reserve, unknown fields and admission/blocker for each branch identified.
- [ ] `lab:check --mode submission` run according to the shared protocol.

## Review questions

1. Why should 128 GB in a product name and 128 GiB in sysctl not automatically be treated as equivalent on another machine?
2. How does the recommended working set differ from the free GPU budget?
3. Why can adding RSS and Metal allocations overestimate usage?
4. What does the hardware profile establish, and what can only loading a model show?

## Sources

- [MTLDevice.recommendedMaxWorkingSetSize](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize).
- [Apple M5 Pro and M5 Max: vendor claims](https://www.apple.com/newsroom/2026/03/apple-debuts-m5-pro-and-m5-max-to-supercharge-the-most-demanding-pro-workflows/).
- Local `man vm_stat`, `man memory_pressure`, `man time`; attach versions and raw output.
