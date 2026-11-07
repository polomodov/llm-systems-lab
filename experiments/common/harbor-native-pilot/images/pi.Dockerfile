ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY models.json settings.json /home/agent/.pi/agent/
RUN chown -R 1000:1000 /home/agent/.pi
USER 1000:1000
