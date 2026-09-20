ARG BASE_IMAGE=node:24.13.1-bookworm-slim
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION
RUN test -n "$HARNESS_VERSION"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY install.mjs /tmp/agy-installer/install.mjs
COPY releases /tmp/agy-installer/releases
RUN node /tmp/agy-installer/install.mjs "$HARNESS_VERSION" && agy --version && rm -rf /tmp/agy-installer
