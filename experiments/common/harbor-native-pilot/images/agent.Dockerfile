ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN if ! getent group 1000 >/dev/null; then groupadd --gid 1000 agent; fi \
    && if getent passwd 1000 >/dev/null; then usermod --home /home/agent --login agent "$(getent passwd 1000 | cut -d: -f1)"; else useradd --uid 1000 --gid 1000 --home-dir /home/agent agent; fi \
    && mkdir -p /home/agent/.nvm /app/output /logs/agent /logs/verifier /installed-agent \
    && chown -R 1000:1000 /home/agent /app /logs /installed-agent
COPY input.json /app/input.json
COPY fixed-node.sh /home/agent/.nvm/nvm.sh
RUN chown 1000:1000 /app/input.json /home/agent/.nvm/nvm.sh
ENV HOME=/home/agent \
    PATH=/home/agent/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    HARBOR_TELEMETRY=0 \
    DISABLE_AUTOUPDATER=1 \
    OPENCODE_DISABLE_AUTOUPDATE=true \
    LITELLM_LOCAL_MODEL_COST_MAP=True
WORKDIR /app
USER 1000:1000
