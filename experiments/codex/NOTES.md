# Observations · OpenAI Codex CLI

## Infrastructure check, 2026-09-20

No real runs yet. Installed `@openai/codex@0.155.1` on `node:24.13.1-bookworm-slim`, Linux/arm64. Image ID: `sha256:a8ee8340e5eba49390da3fe9cd7a58b468e9083f8bb8e27c43301725415ad736`.

The build succeeded. `codex --version` returned `codex-cli 0.155.1`; `codex exec --help` exited with code 0 under UID/GID 1000, with a read-only rootfs and tmpfs `/tmp`, without network access or keys. The CLI warns that PATH aliases are unavailable in HOME under `/tmp`; this did not prevent interface verification. File tools still need a real episode check.

Checking the complete argv without a key under `--network none` started JSONL and repeated failed DNS requests; the test terminated the container after a 20-second timeout. This confirms configuration loading, not API operation or correct authentication handling. No request could leave the container. In the [raw report](smoke/2026-09-20.json), `error=ETIMEDOUT` takes precedence over the Docker client process status.

Parser tests use synthetic events and check literal argv, unsupported mandatory-limit rejection, cache accounting, absence of invented zeros, errors, and truncated JSONL. Next: a recorded episode with an exact selected model ID, proxy transport and tool verification, and an independent verdict.
