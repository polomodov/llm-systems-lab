ARG BASE_IMAGE=node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=0.167.0
# Pin matches experiments/codex/harness.json; npm run check compares both files.
RUN test "$HARNESS_VERSION" = "0.167.0"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install --global --ignore-scripts "@openai/codex@${HARNESS_VERSION}" && codex --version
