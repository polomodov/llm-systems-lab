"""Materialize immutable-image Harbor task packages; never execute an agent."""

import sys
from pathlib import Path
# Keep the historical inspect.py script from shadowing Python's stdlib module.
sys.path = [p for p in sys.path if Path(p).resolve() != Path(__file__).resolve().parent]
import argparse
import hashlib
import json
import re
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
COMMIT = "ff2a1ef48070a8df374669138e4d4db79b77f013"
SLOTS = {"HN-O01", "HN-A01", "HN-A02", "HN-A03", "HN-O02", "HN-O03"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [Path(__file__), *sorted((BASE / "task").rglob("*"))]
    return {str(p.relative_to(BASE)): sha(p) for p in paths
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def slot_configuration_sha256(slots):
    conditions = [{key: value for key, value in slot.items() if key not in {"status", "run_id", "image_id"}} for slot in slots]
    return hashlib.sha256(json.dumps(conditions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def task_config(image, verifier, provider, offline):
    policy = 'network_mode = "no-network"' if offline else (
        'network_mode = "allowlist"\nallowed_hosts = ["' +
        {"openai": "api.openai.com", "anthropic": "api.anthropic.com"}[provider] + '"]')
    return f'''schema_version = "1.4"
artifacts = [{{ source = "/app/output/result.json", destination = "result.json" }}]

[task]
name = "llm-systems-lab/harbor-native-normalize"
version = "1.0.0"
description = "Separate native-adapter infrastructure qualification."

[metadata]
category = "synthetic-native-adapter-qualification"

[agent]
user = "1000:1000"
timeout_sec = 180.0
{policy}

[environment]
docker_image = "{image}"
network_mode = "no-network"
cpus = 1
memory_mb = 2048
storage_mb = 2048
gpus = 0

[verifier]
user = "1000:1000"
environment_mode = "separate"
network_mode = "no-network"
timeout_sec = 60.0

[verifier.environment]
docker_image = "{verifier}"
network_mode = "no-network"
cpus = 1
memory_mb = 256
storage_mb = 512
gpus = 0
'''


def materialize(check=False):
    from harbor.models.task.task import Task
    from harbor.publisher.packager import Packager
    checkout = ROOT / "experiments/common/harbor-interop/.cache/harbor"
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != COMMIT:
        raise ValueError("Harbor source pin mismatch")
    runtime_path = BASE / "runtime-lock.json"
    runtime = json.loads(runtime_path.read_text())
    plan = json.loads((BASE / "plan.json").read_text())
    if len(plan["slots"]) != 6 or {s["slot_id"] for s in plan["slots"]} != SLOTS:
        raise ValueError("Exactly the six frozen pilot slots are required")
    if plan["execution_authorized"] or plan["launchable"]:
        raise ValueError("Preparation must remain non-executable and unauthorized")
    for path, digest in runtime["source_sha256"].items():
        if sha(ROOT / path) != digest:
            raise ValueError(f"Runtime source drift: {path}")
    packages = []
    for slot in plan["slots"]:
        image = runtime["images"][slot["harness"]]["image_id"]
        verifier = runtime["verifier"]["image_id"]
        for identity in (image, verifier):
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", identity):
                raise ValueError("A local immutable image ID is required")
        if runtime["images"][slot["harness"]]["version"] != slot["version"]:
            raise ValueError("Harness version mismatch")
        for mode in ("prepared", "offline"):
            target = BASE / ".cache/tasks" / mode / slot["slot_id"]
            expected_config = task_config(image, verifier, slot["provider"], mode == "offline")
            if not check:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(BASE / "task", target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                (target / "task.toml").write_text(expected_config)
            elif (target / "task.toml").read_text() != expected_config:
                raise ValueError(f"Task configuration drift: {target}")
            Task(target)  # Validate with the pinned Harbor task schema.
            digest, files = Packager.compute_content_hash(target)
            packages.append({"slot_id": slot["slot_id"], "mode": mode,
                "path": str(target.relative_to(BASE)), "image_id": image,
                "verifier_image_id": verifier, "task_digest": "sha256:" + digest,
                "harbor_file_sha256": {str(p.relative_to(target)): sha(p) for p in files},
                "file_sha256": {str(p.relative_to(target)): sha(p) for p in sorted(target.rglob("*")) if p.is_file()}})
    lock = {"schema_version": 1, "kind": "native-pilot-prepared-task-packages",
        "execution_authorized": False, "harbor_commit": COMMIT,
        "slot_configuration_sha256": slot_configuration_sha256(plan["slots"]),
        "runtime_lock_sha256": sha(runtime_path), "source_sha256": source_hashes(),
        "network_scope": "Prepared packages allow only the selected API in the agent phase; offline packages deny controlled TCP in every phase. DNS/ICMP remain permitted by Harbor. Neither package authorizes execution.",
        "packages": packages}
    path = BASE / "package-lock.json"
    if check:
        if json.loads(path.read_text()) != lock:
            raise ValueError("Package lock or task content drift")
    else:
        path.write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps({"packages": len(packages), "check": check, "execution_authorized": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    materialize(parser.parse_args().check)
