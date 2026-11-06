ARG BASE_IMAGE=node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=0.0.1789920039-gafe14b
# Пин совпадает с experiments/amp/harness.json; npm run check сверяет оба файла.
RUN test "$HARNESS_VERSION" = "0.0.1789920039-gafe14b"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
# Исключение из --ignore-scripts: postinstall install.cjs размещает native binary.
# Проверено в образе 0.0.1789920039-gafe14b (2026-09-21).
RUN npm install --global "@ampcode/cli@${HARNESS_VERSION}" && amp --version
