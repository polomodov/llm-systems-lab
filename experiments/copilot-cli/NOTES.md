# Notes · GitHub Copilot CLI

No experimental runs yet.

2026-09-20 — infrastructure without API calls or keys: Docker Engine 29.5.2 / Linux arm64, package `@github/copilot@1.0.86`, Node base `24.13.1-bookworm-slim`. Build with `--ignore-scripts` succeeded. Offline version/help and adapter argv invocation were checked; the expected authentication rejection occurred without a key. The read-only container requires a separate executable tmpfs for native cache; shared `/tmp` was not expanded.

The installed official package’s JSONL formatter in `app.js` was checked: the CLI terminator contains `exitCode`, while SDK events `assistant.usage` / `session.shutdown` are filtered. Tests use this format. Real token totals, USD cost, and observed model ID remain unverified. Sources and commands: [README](README.md). The first episode must check provider egress, turn-event completeness, and auxiliary-model effects; record the run ID here and in `results/runs/`.

Native-cache limit recheck: the version check passes with `/tmp:rw,nosuid,noexec,size=512m,mode=1777`, `/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777`, 2 GiB memory, and UID 1000. The smallest tested successful native tmpfs size is 256 MiB; the absolute minimum was not measured. Cache after `--version`: 161284 KiB. With 256 MiB, cgroup `memory.current=169492480`, `memory.peak=400183296` bytes. 128 MiB is insufficient; the working configuration uses 512 MiB for headroom. Values apply only to CLI 1.0.86 / Linux arm64 / offline smoke, not an agent run.
