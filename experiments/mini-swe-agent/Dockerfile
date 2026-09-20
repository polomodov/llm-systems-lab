FROM node:24.13.1-bookworm-slim AS node
FROM python:3.12.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ARG HARNESS_VERSION=2.4.6
RUN test "$HARNESS_VERSION" = "2.4.6"
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "mini-swe-agent==${HARNESS_VERSION}" && python -c "from importlib.metadata import version; print(version('mini-swe-agent'))"
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
