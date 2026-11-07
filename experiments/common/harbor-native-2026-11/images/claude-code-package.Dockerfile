ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN npm install --global  @anthropic-ai/claude-code@2.1.319 && claude --version
USER 1000:1000
