ARG BASE_IMAGE=node:24.13.1-bookworm-slim
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION
RUN test -n "$HARNESS_VERSION"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install --global --ignore-scripts "@anthropic-ai/claude-code@${HARNESS_VERSION}" && claude --version
