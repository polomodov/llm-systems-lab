ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY wheels/ /opt/pilot-wheels/
# Include the frozen optional MCP closure required by LiteLLM's tools path.
RUN python -m pip install --no-index --no-deps /opt/pilot-wheels/*.whl \
    && python -m pip check
USER 1000:1000
# Genuine uv tool installation; immutable global dependencies remain visible.
# The application wheel and every global package are inventoried in the lock.
RUN python -c 'from importlib.metadata import requires; from packaging.requirements import Requirement; rs=[Requirement(r) for r in requires("mini-swe-agent")]; print("\n".join(sorted({r.name for r in rs if r.name != "mini-swe-agent" and (r.marker is None or r.marker.evaluate())})))' > /home/agent/mini-system-dependencies.txt \
    && uv tool install --offline --excludes /home/agent/mini-system-dependencies.txt --python /usr/local/bin/python /opt/pilot-wheels/mini_swe_agent-*.whl \
    && sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' /home/agent/.local/share/uv/tools/mini-swe-agent/pyvenv.cfg \
    && uv tool list \
    && mini-swe-agent --help >/dev/null
ENV UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=1
