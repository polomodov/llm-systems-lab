# Notes · Amp

No experimental runs yet.

2026-09-20 — infrastructure without API calls or keys: Docker Engine 29.5.2 / Linux arm64, package `@ampcode/cli@0.0.1789920039-gafe14b`, Node base `24.13.1-bookworm-slim`. Normal npm postinstall is required to place the native binary. Offline version/help confirm `low`, `medium`, `high`, `ultra`, `--executor local`, stream JSON, proxy, and settings-file. Old `smart` / `rush` examples are not used.

A read-only container with noexec `/tmp` could not load the native addon; a separate executable tmpfs at `/tmp/harness-native` and `TMPDIR` resolve the error. Without `AMP_API_KEY`, even execute mode starts interactive authentication; the infrastructure check stopped without login, with networking disabled. The shared coordinator checks for the key before launch.

The parser preserves unknown model ID, USD, and absent usage. The first real episode must check egress, server-side routing, workspace/account settings, and aggregate-usage completeness. Record the run ID here; sources are in [README](README.md).

Recheck under the coordinator’s exact limits: `--version` passes with `/tmp:rw,nosuid,noexec,size=512m,mode=1777`, `/tmp/harness-native:rw,nosuid,exec,size=512m,mode=1777`, 2 GiB memory, and UID 1000. Cache: 2672 KiB; cgroup `memory.current=4698112`, `memory.peak=161296384` bytes. Values apply only to this version / Linux arm64 / offline smoke test; actual model workload has not been measured.
