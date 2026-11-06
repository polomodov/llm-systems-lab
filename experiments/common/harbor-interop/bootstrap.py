#!/usr/bin/env python3
"""Install pinned Harbor and build its viewer locally; never execute a task."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
LOCK = json.loads((ROOT / "lock.json").read_text())


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.version.split()[0] != LOCK["python"]:
        raise SystemExit(f"Use Python {LOCK['python']} through the repository's mise environment.")
    node = subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v")
    if node != LOCK["node"]:
        raise SystemExit(f"Use Node {LOCK['node']} through the repository's mise environment.")
    source = ROOT / ".cache/harbor"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        run(["git", "clone", "--no-checkout", LOCK["harbor_repository"], source])
        run(["git", "-C", source, "checkout", "--detach", LOCK["harbor_commit"]])
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != LOCK["harbor_commit"]:
        raise SystemExit("Harbor source revision mismatch; refusing to alter an existing checkout.")
    run(["git", "-C", source, "diff", "--exit-code", "HEAD", "--", "."])
    for relative, key in [("uv.lock", "upstream_uv_lock_sha256"),
                          ("apps/viewer/bun.lock", "upstream_bun_lock_sha256")]:
        if digest(source / relative) != LOCK[key]:
            raise SystemExit(f"Upstream lock mismatch: {relative}")
    bootstrap = ROOT / ".bootstrap"
    if not (bootstrap / "bin/python").exists():
        venv.create(bootstrap, with_pip=True)
    run([bootstrap / "bin/python", "-m", "pip", "install", f"uv=={LOCK['uv']}"])
    environment = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(ROOT / ".venv"))
    run([bootstrap / "bin/uv", "sync", "--project", source, "--frozen", "--no-dev",
         "--python", sys.executable], env=environment)
    run(["npm", "install", "--prefix", bootstrap / "js", "--ignore-scripts",
         "--no-audit", "--no-fund", "--save-exact", f"bun@{LOCK['bun']}"])
    # The optional platform package supplies the binary without executing npm postinstall.
    binaries = list((bootstrap / "js/node_modules/@oven").glob("*/bin/bun"))
    if len(binaries) != 1:
        raise SystemExit("Expected exactly one platform Bun binary.")
    bun = binaries[0]
    version = subprocess.check_output([str(bun), "--version"], text=True).strip()
    if version != LOCK["bun"]:
        raise SystemExit("Bun version mismatch.")
    viewer = source / "apps/viewer"
    run([bun, "install", "--frozen-lockfile", "--ignore-scripts"], cwd=viewer)
    run([bun, "run", "build"], cwd=viewer)
    static = source / "src/harbor/viewer/static"
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(viewer / "build/client", static)
    print("Pinned Harbor and viewer ready. No model calls or task runs were made.")


if __name__ == "__main__":
    main()
