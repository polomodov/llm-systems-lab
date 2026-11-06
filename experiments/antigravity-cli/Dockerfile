ARG BASE_IMAGE=node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=1.2.7
# Пин совпадает с experiments/antigravity-cli/harness.json; npm run check сверяет оба файла.
RUN test "$HARNESS_VERSION" = "1.2.7"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY install.mjs /tmp/agy-installer/install.mjs
COPY releases /tmp/agy-installer/releases
RUN node /tmp/agy-installer/install.mjs "$HARNESS_VERSION" && agy --version && rm -rf /tmp/agy-installer
