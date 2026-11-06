# python:3.12.12-slim-bookworm
FROM python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY input.json /app/input.json
RUN groupadd --gid 1000 agent && useradd --uid 1000 --gid 1000 --create-home agent \
    && mkdir -p /app/output && chown -R agent:agent /app
USER 1000:1000
