ARG BASE_IMAGE=node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=1.18.29
# Пин совпадает с experiments/opencode/harness.json; npm run check сверяет оба файла.
RUN test "$HARNESS_VERSION" = "1.18.29"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
# Исключение из --ignore-scripts: postinstall opencode-ai выбирает platform binary
# из optionalDependencies. Проверено в образе 1.18.29 (2026-09-21).
RUN npm install --global "opencode-ai@${HARNESS_VERSION}" && opencode --version
