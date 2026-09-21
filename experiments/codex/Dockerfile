ARG BASE_IMAGE=node:24.13.1-bookworm-slim
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=0.155.1
# Пин совпадает с experiments/codex/harness.json; npm run check сверяет оба файла.
RUN test "$HARNESS_VERSION" = "0.155.1"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install --global --ignore-scripts "@openai/codex@${HARNESS_VERSION}" && codex --version
