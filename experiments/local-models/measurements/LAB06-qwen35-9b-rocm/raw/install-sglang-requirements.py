"""Install the SGLang runtime requirements that Dockerfile step 22 intended.

The pinned rocm-gfx1151.Dockerfile step 22 installs the flattened extras via a
BuildKit heredoc (`RUN ... && python3 - <<'PY'`). On a host without BuildKit the
legacy builder drops the heredoc body, so `python3 -` reads an empty script and
installs nothing. This script reproduces the exact same dependency set with a
plain file so it can run under either builder.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

project = tomllib.loads(
    Path("/sgl-workspace/sglang/python/pyproject.toml").read_text()
)["project"]
extras = project["optional-dependencies"]
requirements = list(project["dependencies"])
for group in ("runtime_base", "runtime_common", "srt_hip"):
    requirements.extend(
        "compressed-tensors==0.15.0"
        if requirement == "compressed-tensors"
        else requirement
        for requirement in extras[group]
        if not requirement.startswith("sglang[") and requirement != "torch"
    )
requirements = list(dict.fromkeys(requirements))
print("requirements:", len(requirements), file=sys.stderr)
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "--no-cache-dir", *requirements]
)
