#!/bin/sh
set -eu
python - <<'PY'
import json
import os
import socket
import urllib.request
from pathlib import Path

absent = ["/tests", "/opt/verifier-fixtures", "/var/run/docker.sock"]
assert os.geteuid() == 1000, "agent must run as the unprivileged image user"
assert all(not Path(path).exists() for path in absent), "verifier or Docker socket leaked"
try:
    with urllib.request.urlopen("https://example.com/", timeout=3) as response:
        response.read(2048)
        external_https_blocked = False
except OSError:
    external_https_blocked = True
assert external_https_blocked, "external HTTPS request unexpectedly succeeded"
evidence = {"absent_paths": absent, "external_https_probe_blocked": external_https_blocked, "hostname": socket.gethostname(), "effective_uid": os.geteuid()}
Path("/logs/agent/boundary.json").write_text(json.dumps(evidence, indent=2) + "\n")
values = json.loads(Path("/app/input.json").read_text())
result = sorted({value.strip().lower() for value in values if value.strip()})
Path("/app/output").mkdir(exist_ok=True)
Path("/app/output/result.json").write_text(json.dumps(result) + "\n")
PY
