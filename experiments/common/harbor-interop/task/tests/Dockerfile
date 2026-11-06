# python:3.12.12-slim-bookworm
FROM python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY expected.json /opt/verifier-fixtures/expected.json
COPY evaluate.py test.sh /tests/
RUN groupadd --gid 1000 verifier && useradd --uid 1000 --gid 1000 --create-home verifier \
    && mkdir -p /app/output /logs/verifier && chmod 755 /tests/test.sh \
    && chown verifier:verifier /app/output /logs/verifier
USER 1000:1000
