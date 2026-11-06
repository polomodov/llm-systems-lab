FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY expected.json /opt/verifier-fixtures/expected.json
COPY evaluate.py test.sh /tests/
RUN mkdir -p /app/output /logs/verifier && chmod 755 /tests/test.sh
