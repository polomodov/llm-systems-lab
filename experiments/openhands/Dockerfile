FROM node:24.13.1-bookworm-slim AS node
FROM python:3.12.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ARG HARNESS_VERSION=1.49.2
RUN test "$HARNESS_VERSION" = "1.49.2"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates tmux libatomic1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "openhands-sdk==${HARNESS_VERSION}" "openhands-tools==${HARNESS_VERSION}" && python -c "from importlib.metadata import version; print(version('openhands-sdk'))"
ENV LITELLM_LOCAL_MODEL_COST_MAP=True DO_NOT_TRACK=1
