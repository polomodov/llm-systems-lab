#!/usr/bin/env python3
"""Fetch verified Docker plugins into this experiment, without global Docker changes."""
import hashlib
import json
from pathlib import Path
import platform
import urllib.request

ROOT = Path(__file__).resolve().parent


def main():
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise SystemExit("These plugin binaries are qualified only for Darwin arm64.")
    lock = json.loads((ROOT / "lock.json").read_text())
    directory = ROOT / ".cache/docker-plugins"
    directory.mkdir(parents=True, exist_ok=True)
    for name, spec in lock["docker_plugins_darwin_arm64"].items():
        target = directory / name
        if not target.exists():
            temporary = target.with_suffix(".download")
            urllib.request.urlretrieve(spec["url"], temporary)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != spec["sha256"]:
                temporary.unlink()
                raise SystemExit(f"Checksum mismatch: {name}")
            temporary.replace(target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != spec["sha256"]:
            raise SystemExit(f"Existing plugin checksum mismatch: {name}")
        target.chmod(0o755)
        print(f"Verified {name} {spec['version']}", flush=True)
    print(directory)


if __name__ == "__main__":
    main()
