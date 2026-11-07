ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY model-refresh.mjs /opt/model-refresh.mjs
RUN node /opt/model-refresh.mjs
COPY models.json settings.json /home/agent/.pi/agent/
RUN chown -R 1000:1000 /home/agent/.pi
USER root
RUN chown -R 1000:1000 /home/agent
USER 1000:1000
