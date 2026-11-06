# Observations · Google Antigravity CLI

## Infrastructure check, 2026-09-20

No real runs yet. The official Linux/arm64 archive of `agy` 1.2.7 was installed after SHA-512 verification; image ID: `sha256:cba424c657846ca32c9975ac27ad8f72b55f0de4cbee593d0e2f9bd129fa9bc6`. Base: `node:24.13.1-bookworm-slim`.

`agy --version` returned `1.2.7`; `agy --help` exited with code 0 under UID/GID 1000 with a read-only rootfs, tmpfs `/tmp`, and `--network none`. The runtime read `modelProvider: gemini` from the prepared settings and exited with code 1 and the expected missing-`GEMINI_API_KEY` error. Neither keys nor network access were supplied. [Raw results](smoke/2026-09-20.json) are retained separately from episode records.

A material difference between documentation and the measured interface: the headless page described a default 5-minute timeout, whereas `agy --help` 1.2.7 reports `0s`. The adapter explicitly uses 0 and relies on an externally enforced timeout. The download-page snapshot named 1.2.0, while the official installer manifest already contained 1.2.7; the actual retrieved version and hash are pinned, not a floating installer.

Unit tests confirm final-aggregate handling, no double counting, unknown metrics, unsupported-limit rejection, and distinction between errors and truncation. Selected-model availability, input/cache accounting, subagent metric completeness, and Gemini API operation through the gateway require a real recorded episode. The x64 manifest is retained, but an image for that architecture has not been checked locally.
