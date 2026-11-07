ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN npm install --global --ignore-scripts @openai/codex@0.167.0 && codex --version
USER 1000:1000
