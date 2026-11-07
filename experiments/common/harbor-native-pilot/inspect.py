#!/usr/bin/env python3
"""Record source inventory and offline CLI surfaces; never launch a task or model.

Uses the already-installed Harbor source and existing local Docker images.
No credentials, env files, host mounts, downloads, installations or rebuilds.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
INTEROP = BASE.with_name("harbor-interop")
SOURCE = INTEROP / ".cache/harbor"
CAMPAIGN = BASE.parent / "campaigns/2026-11-first-comparison"
PRIORITY = ["claude-code", "opencode", "codex", "pi", "mini-swe-agent"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, timeout=30):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"argv": args, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"argv": args, "exit_code": 124, "stdout": "",
                "stderr": "Offline inspection command timed out", "timed_out": True}


def registered_agents():
    tree = ast.parse((SOURCE / "src/harbor/models/agent/name.py").read_text())
    names = {}
    for item in ast.walk(tree):
        if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant):
            for target in item.targets:
                if isinstance(target, ast.Name) and isinstance(item.value.value, str):
                    names[target.id] = item.value.value
    factory = ast.parse((SOURCE / "src/harbor/agents/factory.py").read_text())
    registry = next(item.value for item in ast.walk(factory)
                    if isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.target.id == "_AGENT_MAP")
    return {names[key.attr]: ast.literal_eval(value)
            for key, value in zip(registry.keys, registry.values)}


def probe(image, executable, args):
    container = "harbor-native-inspect-" + uuid4().hex
    invocation = [
        "docker", "--context", "colima", "run", "--rm", "--pull=never",
        "--name", container,
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "1000:1000",
        "--cpus", "1", "--memory", "512m", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m", "--env", "HOME=/tmp",
        "--env", "LITELLM_LOCAL_MODEL_COST_MAP=True",
        "--env", "HARBOR_TELEMETRY=0", "--entrypoint", executable,
        image, *args,
    ]
    try:
        result = command(invocation)
    finally:
        cleanup = command(["docker", "--context", "colima", "rm", "--force", container], timeout=10)
    result["cleanup_confirmed"] = cleanup["exit_code"] == 0 or (
        cleanup["exit_code"] == 1 and "No such container" in cleanup["stderr"]
    )
    return result


def failed_probes(probes):
    return [(name, p["exit_code"]) for name, items in probes.items()
            for p in items if p["exit_code"] or not p["cleanup_confirmed"]]


def main():
    lock = json.loads((INTEROP / "lock.json").read_text())
    revision = command(["git", "-C", str(SOURCE), "rev-parse", "HEAD"])
    assert revision["exit_code"] == 0
    assert revision["stdout"].strip() == lock["harbor_commit"]
    assert command(["git", "-C", str(SOURCE), "diff", "--exit-code", "HEAD"])["exit_code"] == 0
    protected = {str(p.relative_to(REPO)): sha(p) for p in sorted(CAMPAIGN.iterdir()) if p.is_file()}
    registry = registered_agents()
    profiles = {p.parent.name: json.loads(p.read_text()) for p in sorted((REPO / "experiments").glob("*/harness.json"))}
    mappings = {name: name for name in profiles}
    mappings["openhands"] = "openhands-sdk"
    sources = ["src/harbor/agents/factory.py", "src/harbor/models/agent/name.py",
               "src/harbor/agents/base.py", "src/harbor/agents/options.py",
               "src/harbor/agents/installed/base.py", "src/harbor/models/job/config.py",
               "src/harbor/models/trial/config.py", "src/harbor/models/task/config.py"]
    sources += ["src/" + registry[mappings[name]].split(":")[0].replace(".", "/") + ".py"
                for name in profiles if mappings[name] in registry]
    images = {item["harness"]: item["image_id"] for item in
              json.loads((CAMPAIGN / "docker-preflight.json").read_text())["images"]}
    surfaces = {
        "claude-code": [("claude", ["--version"]), ("claude", ["--help"])],
        "opencode": [("opencode", ["--version"]), ("opencode", ["run", "--help"])],
        "codex": [("codex", ["--version"]), ("codex", ["exec", "--help"])],
        "pi": [("pi", ["--version"]), ("pi", ["--help"])],
        "mini-swe-agent": [("python", ["-c", "import importlib.metadata,json,shutil; print(json.dumps({'version':importlib.metadata.version('mini-swe-agent'),'uv':shutil.which('uv'),'mini':shutil.which('mini')}))"]),
                           ("mini", ["--help"])],
    }
    probes = {name: [probe(images[name], executable, args) for executable, args in surfaces[name]]
              for name in PRIORITY}
    failures = failed_probes(probes)
    assert all(sha(REPO / path) == digest for path, digest in protected.items()), "Campaign changed"
    report = {
        "kind": "offline-native-adapter-compatibility-inspection",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "harbor_commit": lock["harbor_commit"], "harbor_version": lock["harbor_version"],
        "execution_authorized": False, "model_requests": 0, "credentials_read": False,
        "scope": "AST/source inspection and version/help only; no Harbor agent lifecycle or task execution",
        "registered_lab_harnesses": {
            name: {"lab_version": p["version"], "lab_mode": p.get("mode", "cli"),
                   "harbor_name": mappings[name] if mappings[name] in registry else None,
                   "harbor_class": registry.get(mappings[name])}
            for name, p in profiles.items()},
        "harbor_source_sha256": {path: sha(SOURCE / path) for path in sorted(set(sources))},
        "lab_profile_sha256": {name: sha(REPO / "experiments" / name / "harness.json") for name in profiles},
        "campaign_files_sha256": protected, "campaign_changed_files": [],
        "existing_image_ids": {name: images[name] for name in PRIORITY},
        "cli_probes": probes,
        "all_probes_passed": not failures,
        "limitations": ["Help/version success does not establish API access, request compatibility or task success.",
                        "Image IDs are local arm64 qualification inputs; no claim of cross-platform rebuild reproducibility.",
                        "CLI help can hide options; consult the additional source-evidence files."]}
    (BASE / "offline-checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"registered": sum(v["harbor_name"] is not None for v in report["registered_lab_harnesses"].values()),
                      "harnesses": len(profiles), "probes": sum(map(len, probes.values())),
                      "failed_probes": failures,
                      "campaign_files_unchanged": len(protected), "model_requests": 0}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
