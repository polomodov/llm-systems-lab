# python:3.12.12-slim-bookworm, local immutable base asserted by build-images.py
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
WORKDIR /app
COPY expected.json /opt/verifier-fixtures/expected.json
COPY evaluate.py test.sh /tests/
RUN groupadd --gid 1000 verifier && useradd --uid 1000 --gid 1000 --create-home verifier \
    && mkdir -p /app/output /logs/verifier && chmod 755 /tests/test.sh \
    && chown verifier:verifier /app/output /logs/verifier
USER 1000:1000
