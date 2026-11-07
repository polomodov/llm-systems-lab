ARG BASE_IMAGE=node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
FROM ${BASE_IMAGE}
ARG HARNESS_VERSION=2.1.319
# Pin matches experiments/claude-code/harness.json; npm run check compares both files.
RUN test "$HARNESS_VERSION" = "2.1.319"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*

# This pinned release requires its native-binary postinstall during image preparation.
RUN npm install --global "@anthropic-ai/claude-code@${HARNESS_VERSION}" && claude --version
