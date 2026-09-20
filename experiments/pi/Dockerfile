FROM node:24.13.1-bookworm-slim
ARG HARNESS_VERSION=0.73.1
RUN test "$HARNESS_VERSION" = "0.73.1"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install --prefix /opt/pi "@mariozechner/pi-coding-agent@${HARNESS_VERSION}" && ln -s /opt/pi/node_modules/.bin/pi /usr/local/bin/pi && pi --version
