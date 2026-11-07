#!/usr/bin/env python3
"""Build local frozen pilot images without model calls or runtime downloads.

Build stages have network=none. --fetch-wheels explicitly downloads only the
public wheel URLs and SHA-256 values recorded in runtime/wheels.lock.json.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import urllib.request
from uuid import uuid4

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
INTEROP = BASE.with_name("harbor-interop")
CACHE = BASE / ".cache/image-builds"
PYTHON = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(args, timeout=300, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=timeout, **kwargs).stdout.strip()


def local_image(docker, reference):
    return json.loads(invoke([*docker, "image", "inspect", reference]))[0]


def copy_inputs(directory, files):
    directory.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def build(docker, name, base_id, dockerfile, files):
    # Alias only within this experiment. Assert its ID before and after build;
    # Docker local image IDs are not registry-retrievable manifest digests.
    alias = "harbor-native-input/" + name + ":" + base_id.removeprefix("sha256:")
    assert local_image(docker, base_id)["Id"] == base_id
    invoke([*docker, "tag", base_id, alias])
    assert local_image(docker, alias)["Id"] == base_id
    context = CACHE / name
    if context.exists():
        shutil.rmtree(context)
    copy_inputs(context, files)
    shutil.copyfile(dockerfile, context / "Dockerfile")
    tag = "harbor-native-pilot/" + name + ":frozen"
    invocation = [*docker, "build", "--network", "none", "--pull=false", "--build-arg", "BASE_IMAGE=" + alias,
                  "--tag", tag, str(context)]
    result = subprocess.run(invocation, capture_output=True, text=True,
                            env={**os.environ, "DOCKER_BUILDKIT": "0"}, timeout=300)
    (CACHE / (name + ".log")).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Image build failed: {name}; see .cache/image-builds/{name}.log")
    assert local_image(docker, alias)["Id"] == base_id
    image = local_image(docker, tag)
    assert image["Config"]["User"] == "1000:1000"
    assert image["Architecture"] == "arm64" and image["Os"] == "linux"
    print(json.dumps({"built": name, "image_id": image["Id"]}), flush=True)
    return {"image_id": image["Id"], "tag": tag, "base_image_id": base_id, "platform": "linux/arm64",
            "container_config": {key: image["Config"].get(key) for key in ["User", "WorkingDir", "Entrypoint", "Cmd"]}}


def probe(docker, image, command, stderr=False):
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image)
    assert local_image(docker, image)["Id"] == image
    name = "harbor-image-probe-" + uuid4().hex
    try:
        result = subprocess.run([*docker, "run", "--rm", "--pull=never", "--name", name,
                       "--network", "none", "--cap-drop", "ALL",
                       "--security-opt", "no-new-privileges", "--pids-limit", "128",
                       "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m", "--entrypoint", "sh", image, "-c", command],
                       timeout=45, check=True, capture_output=True, text=True)
        return (result.stdout + (result.stderr if stderr else "")).strip()
    finally:
        removed = subprocess.run([*docker, "rm", "--force", name], capture_output=True, text=True, timeout=15)
        if removed.returncode:
            absent = subprocess.run([*docker, "container", "inspect", name], capture_output=True, text=True, timeout=15)
            if absent.returncode == 0 or "No such container" not in absent.stderr:
                raise RuntimeError("Could not verify probe container cleanup: " + name)


def wheel_files(fetch):
    lock = json.loads((BASE / "runtime/wheels.lock.json").read_text())
    destination = BASE / ".cache/wheels"
    destination.mkdir(parents=True, exist_ok=True)
    files = {}
    for spec in lock["wheels"]:
        path = destination / spec["filename"]
        if not path.exists() and fetch:
            urllib.request.urlretrieve(spec["url"], path)
        if not path.is_file() or sha(path) != spec["sha256"]:
            raise ValueError("Missing or mismatched wheel: " + spec["filename"])
        files["wheels/" + path.name] = path
    return files


def validate_runtime(docker, name, image, version):
    commands = {"claude-code": "claude --version", "codex": "codex --version",
                "opencode": "opencode --version", "pi": ". ~/.nvm/nvm.sh; pi --version",
                "mini-swe-agent": "uv tool list"}
    observed = probe(docker, image, commands[name], stderr=True)
    patterns = {"claude-code": r"([0-9]+\.[0-9]+\.[0-9]+) \(Claude Code\)",
                "codex": r"codex-cli ([0-9]+\.[0-9]+\.[0-9]+)",
                "opencode": r"([0-9]+\.[0-9]+\.[0-9]+)",
                "pi": r"([0-9]+\.[0-9]+\.[0-9]+)",
                "mini-swe-agent": r"mini-swe-agent v([0-9]+\.[0-9]+\.[0-9]+)"}
    version_lines = [match.group(1) for line in observed.splitlines()
                     if (match := re.fullmatch(patterns[name], line))]
    assert version_lines == [version], (name, observed)
    common = probe(docker, image, 'id -u; printf "%s\\n" "$HOME"; node --version; test -w /app/output; test -w /logs/agent; test ! -e /tests; test ! -e /opt/verifier-fixtures; test ! -e /var/run/docker.sock')
    assert common.splitlines() == ["1000", "/home/agent", "v24.13.1"]
    details = {}
    if name == "pi":
        script = """import {ModelRegistry} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/model-registry.js';
import {AuthStorage} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/auth-storage.js';
import {SettingsManager} from '/opt/pi/node_modules/@mariozechner/pi-coding-agent/dist/core/settings-manager.js';
const registry=ModelRegistry.create(AuthStorage.inMemory());
const settings=SettingsManager.create('/app');
console.log(JSON.stringify({model:registry.find('openai','gpt-5.4-mini-2026-03-17'),compaction:settings.getCompactionEnabled(),retry:settings.getRetryEnabled()}));"""
        details = json.loads(probe(docker, image, "node --input-type=module -e " + shlex.quote(script)))
        expected = json.loads((BASE / "runtime/pi/models.json").read_text())["providers"]["openai"]["models"][0]
        for key in ["id", "api", "reasoning", "input", "cost", "contextWindow", "maxTokens"]:
            assert details["model"][key] == expected[key], (key, details)
        assert details["model"]["baseUrl"] == "https://api.openai.com/v1"
        assert details["compaction"] is False and details["retry"] is False
        details["qualification"] = "Native ModelRegistry and SettingsManager imports with in-memory empty auth; no session or API request."
    if name == "mini-swe-agent":
        script = "import json,sys; from importlib.metadata import version; print(json.dumps({'python':sys.version.split()[0], 'executable':sys.executable,'mini-swe-agent':version('mini-swe-agent'),'litellm':version('litellm'),'uv':version('uv')}))"
        tool_python = "/home/agent/.local/share/uv/tools/mini-swe-agent/bin/python"
        details = json.loads(probe(docker, image, tool_python + " -c " + shlex.quote(script)))
        assert details["python"] == "3.12.12" and details["mini-swe-agent"] == version and details["uv"] == "0.13.7"
        assert details["litellm"] == "1.108.1"
        details["pyvenv_cfg"] = probe(docker, image, "cat /home/agent/.local/share/uv/tools/mini-swe-agent/pyvenv.cfg")
        assert "include-system-site-packages = true" in details["pyvenv_cfg"]
        details["uv_receipt"] = probe(docker, image, "cat /home/agent/.local/share/uv/tools/mini-swe-agent/uv-receipt.toml")
        details["immutable_system_dependencies"] = probe(docker, image, "cat /home/agent/mini-system-dependencies.txt").splitlines()
        script = "from importlib.metadata import requires,version; from packaging.requirements import Requirement; rs=[Requirement(r) for r in requires('mini-swe-agent')]; active=[r for r in rs if r.marker is None or r.marker.evaluate()]; assert all(r.specifier.contains(version(r.name)) for r in active); print('all active mini dependencies satisfy wheel requirements')"
        details["dependency_check"] = probe(docker, image, tool_python + " -c " + shlex.quote(script))
        script = "import json,litellm; import litellm.responses.mcp.chat_completions_handler; from importlib.metadata import version; print(json.dumps({'litellm_tools_route_import':'passed','mcp':version('mcp'),'mcp-types':version('mcp-types'),'httpx2':version('httpx2'),'fastuuid':version('fastuuid')}))"
        details["tools_route"] = json.loads(probe(docker, image, tool_python + " -c " + shlex.quote(script)))
        assert details["tools_route"]["mcp"] == "2.2.0" and details["tools_route"]["mcp-types"] == "2.2.0"
        details["full_dependency_check"] = probe(docker, image, tool_python + " -m pip check")
        assert details["full_dependency_check"] == "No broken requirements found."
    return {"version_output": observed, "runtime_details": details, "uid": 1000, "home": "/home/agent", "node": "24.13.1",
            "provider_requests": 0, "network": "none", "root_filesystem": "disposable writable container layer", "workspace_and_logs_writable": True,
            "verifier_paths_and_docker_socket_absent": True}


def inventory(docker, image, python=None, node=True):
    packages = probe(docker, image, "dpkg-query -W -f='${binary:Package}\t${Version}\n'")
    result = {"image_id": image, "os_packages": dict(line.split("\t", 1) for line in packages.splitlines())}
    script = """const fs=require('fs'),path=require('path'),out=[];
function walk(p){if(!fs.existsSync(p))return;for(const e of fs.readdirSync(p,{withFileTypes:true})){const f=path.join(p,e.name);if(e.isDirectory())walk(f);else if(e.isFile()&&e.name==='package.json'){try{const j=JSON.parse(fs.readFileSync(f,'utf8'));if(j.name&&j.version)out.push({name:j.name,version:j.version,path:f});}catch{}}}}
walk('/usr/local/lib/node_modules');walk('/opt/pi/node_modules');out.sort((a,b)=>a.path.localeCompare(b.path));console.log(JSON.stringify(out));"""
    if node:
        result["node_packages"] = json.loads(probe(docker, image, "node -e " + shlex.quote(script)))
    if python:
        script = "import json; from importlib.metadata import distributions; print(json.dumps(sorted([{'name':d.metadata['Name'],'version':d.version,'path':str(d.locate_file(''))} for d in distributions()],key=lambda d:(d['name'].lower(),d['path']))))"
        result["python_packages"] = json.loads(probe(docker, image, python + " -c " + shlex.quote(script)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-wheels", action="store_true")
    args = parser.parse_args()
    docker = ["docker", "--context", "colima"]
    CACHE.mkdir(parents=True, exist_ok=True)
    wheels = wheel_files(args.fetch_wheels)
    existing = json.loads((BASE / "offline-checks.json").read_text())["existing_image_ids"]
    common_files = {"input.json": INTEROP / "task/environment/input.json", "fixed-node.sh": BASE / "runtime/fixed-node.sh"}
    images, evidence, inventories = {}, {}, {}
    for name, base_id in existing.items():
        assert local_image(docker, base_id)["Id"] == base_id
        image = build(docker, name, base_id, BASE / "images/agent.Dockerfile", common_files)
        if name == "pi":
            files = {p.name: p for p in (BASE / "runtime/pi").glob("*.json")}
            image = build(docker, "pi-configured", image["image_id"], BASE / "images/pi.Dockerfile", files)
        if name == "mini-swe-agent":
            image = build(docker, "mini-uv", image["image_id"], BASE / "images/mini.Dockerfile", wheels)
        image["lab_base_image_id"] = base_id
        version = json.loads((REPO / "experiments" / name / "harness.json").read_text())["version"]
        image["version"] = version
        images[name] = image
        evidence[name] = validate_runtime(docker, name, image["image_id"], version)
        inventories[name] = inventory(docker, image["image_id"],
                                      python="/home/agent/.local/share/uv/tools/mini-swe-agent/bin/python" if name == "mini-swe-agent" else None)
    python_id = local_image(docker, PYTHON)["Id"]
    verifier = build(docker, "verifier", python_id, BASE / "images/verifier.Dockerfile",
                     {p: INTEROP / "task/tests" / p for p in ["evaluate.py", "test.sh", "expected.json"]})
    verifier["base_manifest"] = PYTHON
    inventories["verifier"] = inventory(docker, verifier["image_id"], python="python", node=False)
    verifier_probe = probe(docker, verifier["image_id"], 'id -u; python --version; test ! -w /opt/verifier-fixtures; test -w /output; test -w /logs/verifier')
    assert verifier_probe.splitlines() == ["1000", "Python 3.12.12"]
    evidence["verifier"] = {"uid": 1000, "python": "3.12.12", "fixture_directory_writable": False,
                            "output_and_logs_writable": True, "network": "none", "provider_requests": 0}
    (BASE / "runtime-inventories.json").write_text(json.dumps(inventories, indent=2) + "\n")
    tracked = [p for subdir in ["images", "runtime"] for p in (BASE / subdir).rglob("*") if p.is_file()]
    tracked += [Path(__file__), INTEROP / "task/environment/input.json"]
    tracked += [INTEROP / "task/tests" / p for p in ["evaluate.py", "test.sh", "expected.json"]]
    lock = {"schema_version": 1, "kind": "local-immutable-native-pilot-images",
            "created_at": datetime.now(timezone.utc).isoformat(), "platform": "linux/arm64",
            "harbor_commit": "ff2a1ef48070a8df374669138e4d4db79b77f013", "images": images,
            "verifier": verifier, "build_network": "none", "provider_requests": 0,
            "credential_files_read": False, "source_sha256": {str(p.relative_to(REPO)): sha(p) for p in sorted(tracked)},
            "limitations": ["Local image IDs are immutable but not pullable registry manifest digests. Retain these local images or archive/export before moving hosts.",
                            "Immutable lab bases retain existing dependencies; no claim of bit-reproducible rebuilds from mutable upstream package indexes.",
                            "Pi uses a documented fixed-Node shim for Harbor's nvm source path; no NVM download or fake version output.",
                            "Mini is a genuine uv tool environment with system-site-packages enabled to reuse the immutable base dependency set.",
                            "Agent runtime packages differ: Node24.13.1 in all; Python3.12.12 in mini only. This is not general coding-environment parity."]}
    (BASE / "runtime-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    (BASE / "runtime-evidence.json").write_text(json.dumps({"kind": "offline-runtime-evidence", "images": evidence,
        "package_inventory_file": "runtime-inventories.json", "package_inventory_sha256": sha(BASE / "runtime-inventories.json"),
        "checked_at": datetime.now(timezone.utc).isoformat(), "model_requests": 0}, indent=2) + "\n")


if __name__ == "__main__":
    main()
