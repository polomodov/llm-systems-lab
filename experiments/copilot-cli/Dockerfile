ARG BASE_IMAGE=node:24.13.1-bookworm-slim
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=1.0.86
# Пин совпадает с experiments/copilot-cli/harness.json; npm run check сверяет оба файла.
RUN test "$HARNESS_VERSION" = "1.0.86"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install --global --ignore-scripts "@github/copilot@${HARNESS_VERSION}" && copilot --version
ENV COPILOT_AUTO_UPDATE=false
