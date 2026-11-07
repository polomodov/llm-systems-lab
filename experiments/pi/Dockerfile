FROM node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2
ARG HARNESS_VERSION=0.73.1
RUN test "$HARNESS_VERSION" = "0.73.1"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
# Exception to --ignore-scripts: dependency koffi builds its native
# binding through an install script. Verified in image 0.73.1 (2026-09-21).
RUN npm install --prefix /opt/pi "@mariozechner/pi-coding-agent@${HARNESS_VERSION}" && ln -s /opt/pi/node_modules/.bin/pi /usr/local/bin/pi && pi --version

# Sonnet5.5 compatibility delta is hash-bound to the upstream provider artifact.
COPY model-refresh.mjs /opt/pi-model-refresh.mjs
RUN node /opt/pi-model-refresh.mjs
