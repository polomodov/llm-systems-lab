"""Exercise real Harbor oracle/nop trials and explicit synthetic attack controls.

Run with the pinned .venv Python, Docker on PATH, and --docker-host pointing to
the local daemon. No provider, judge, cloud sandbox, or model is configured.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

BASE = Path(__file__).resolve().parent
HARBOR_COMMIT = "ff2a1ef48070a8df374669138e4d4db79b77f013"
PYTHON_BASE = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
EGRESS_BASE = "gogost/gost:3.2.7-nightly.20260602@sha256:afc0137758ab4ce399d47a299f9abbacbf522b52a17e59cbb4b4e7a1a66e9196"
KERNEL_PROBE_BASE = "alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11"


def isolated_environment(docker_host: str, docker_plugin_dir: Path | None) -> None:
    if not docker_host.startswith("unix://"):
        raise ValueError("Only a local Unix Docker socket is allowed")
    sys.dont_write_bytecode = True
    synthetic_home = BASE / ".cache/synthetic-home"
    docker_config = synthetic_home / ".docker"
    docker_config.mkdir(parents=True, exist_ok=True)
    plugin_config = {"cliPluginsExtraDirs": [str(docker_plugin_dir.resolve())]} if docker_plugin_dir else {}
    (docker_config / "config.json").write_text(json.dumps(plugin_config) + "\n")
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    os.environ.clear()
    os.environ.update({
        "PATH": path,
        "HOME": str(synthetic_home),
        "DOCKER_CONFIG": str(docker_config),
        "DOCKER_HOST": docker_host,
        "HARBOR_TELEMETRY": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "LC_ALL": "C.UTF-8",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--docker-plugin-dir", type=Path)
    parsed = parser.parse_args()
    isolated_environment(parsed.docker_host, parsed.docker_plugin_dir)

# Imports follow environment isolation when executed as a script.
from harbor.agents.nop import NopAgent
from harbor.models.task.task import Task
from harbor.models.trial.config import TrialConfig
from harbor.trial.trial import Trial


class ArtifactControlAgent(NopAgent):
    """No-model control that emits an incorrect artifact or attempts local tampering."""

    @staticmethod
    def name():
        return "synthetic-artifact-control"

    def __init__(self, *args, scenario="bad", **kwargs):
        super().__init__(*args, **kwargs)
        if scenario not in {"bad", "tamper"}:
            raise ValueError(scenario)
        self.scenario = scenario

    async def run(self, instruction, environment, context):
        code = '''
import json, socket, urllib.request
from pathlib import Path
absent = ["/tests", "/opt/verifier-fixtures", "/var/run/docker.sock"]
assert all(not Path(p).exists() for p in absent), "boundary leak"
try:
    with urllib.request.urlopen("https://example.com/", timeout=3) as response:
        response.read(2048)
        blocked = False
except OSError:
    blocked = True
assert blocked, "external HTTPS unexpectedly succeeded"
Path("/logs/agent/boundary.json").write_text(json.dumps({
    "absent_paths": absent, "external_https_probe_blocked": blocked,
    "hostname": socket.gethostname(), "scenario": SCENARIO
}, indent=2) + "\\n")
Path("/app/output").mkdir(exist_ok=True)
Path("/app/output/result.json").write_text('["wrong"]\\n')
if SCENARIO == "tamper":
    Path("/tests").mkdir()
    Path("/tests/test.sh").write_text("#!/bin/sh\\necho 1 > /logs/verifier/reward.txt\\n")
    Path("/opt/verifier-fixtures").mkdir()
    Path("/opt/verifier-fixtures/expected.json").write_text('["wrong"]\\n')
    Path("/logs/verifier").mkdir(exist_ok=True)
    Path("/logs/verifier/reward.txt").write_text("1\\n")
    Path("/app/input.json").write_text('["wrong"]\\n')
    Path("/app/agent-only.txt").write_text("must not reach verifier\\n")
'''.replace("SCENARIO", repr(self.scenario))
        result = await environment.exec(command="python -c " + shlex.quote(code))
        if result.return_code:
            raise RuntimeError(f"Synthetic control failed: {result.stderr or result.stdout}")


async def docker_output(*args):
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    return process.returncode, stdout.decode()


async def observe_sidecars(trial_name, captured):
    _, output = await docker_output(
        "ps", "--filter", "label=com.docker.compose.service=harbor-docker-egress-control-sidecar",
        "--format", "{{.ID}} {{.Label \"com.docker.compose.project\"}}",
    )
    for line in output.splitlines():
        container, project = line.split(maxsplit=1)
        if not project.startswith(trial_name) or container in captured:
            continue
        code, policy = await docker_output("exec", container, "network-policy", "show")
        if code or "empty: deny all controlled TCP egress" not in policy:
            continue
        code, rules = await docker_output("exec", container, "network-policy", "rules")
        if code:
            continue
        _, metadata = await docker_output("inspect", container, "--format", "{{json .Config.Labels}}")
        retained_labels = {
            "com.docker.compose.image", "com.docker.compose.project",
            "com.docker.compose.service", "com.docker.compose.version",
            "com.docker.compose.config-hash",
        }
        labels = {key: value for key, value in json.loads(metadata).items() if key in retained_labels}
        captured[container] = {"container": container, "project": project, "policy": policy, "nftables_rules": rules, "labels": labels}


def component_hashes():
    components = sorted((BASE / "task").rglob("*")) + [Path(__file__), BASE / "test_synthetic_task.py"]
    return {
        str(path.relative_to(BASE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in components
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    }


async def run_controls():
    actual_commit = subprocess.check_output(
        ["git", "-C", str(BASE / ".cache/harbor"), "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual_commit == HARBOR_COMMIT, "Harbor source does not match the experiment pin"
    frozen_components = component_hashes()
    frozen_task_checksum = Task(BASE / "task").checksum
    baseline_code, baseline_text = await docker_output(
        "run", "--rm", "--network", "bridge", PYTHON_BASE, "python", "-c",
        'import json, urllib.request; r=urllib.request.urlopen("https://example.com/",timeout=10); b=r.read(2048); print(json.dumps({"status":r.status,"example_domain":b"Example Domain" in b}))',
    )
    assert baseline_code == 0, "Public-network HTTPS positive control failed"
    https_baseline = json.loads(baseline_text)
    assert https_baseline == {"status": 200, "example_domain": True}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trials_dir = BASE / ".cache/synthetic-runs" / run_id
    fixture_sha = hashlib.sha256((BASE / "task/tests/expected.json").read_bytes()).hexdigest()
    controls = []
    frozen_lock_digest = None
    for scenario, expected in [("oracle", 1), ("nop", 0), ("bad", 0), ("tamper", 0)]:
        assert component_hashes() == frozen_components, "Experiment sources changed between controls"
        assert Task(BASE / "task").checksum == frozen_task_checksum, "Task changed between controls"
        agent = {"name": scenario} if scenario in {"oracle", "nop"} else {
            "import_path": "synthetic_controls:ArtifactControlAgent",
            "kwargs": {"scenario": scenario},
        }
        config = TrialConfig.model_validate({
            "task": {"path": str(BASE / "task")},
            "trial_name": "synthetic-" + scenario,
            "trials_dir": str(trials_dir),
            "agent": agent,
            "environment": {"type": "docker", "delete": True},
        })
        trial = await Trial.create(config)
        active = asyncio.create_task(trial.run())
        sidecars = {}
        while not active.done():
            await observe_sidecars(config.trial_name, sidecars)
            await asyncio.sleep(0.25)
        result = await active
        trial_dir = trials_dir / config.trial_name
        lock_digest = json.loads((trial_dir / "lock.json").read_text())["task"]["digest"]
        if frozen_lock_digest is None:
            frozen_lock_digest = lock_digest
        assert lock_digest == frozen_lock_digest, "Harbor task lock digest changed between controls"
        reward = result.verifier_result.rewards.get("reward") if result.verifier_result else None
        verifier_path = trial_dir / "verifier/evidence.json"
        verifier = json.loads(verifier_path.read_text()) if verifier_path.exists() else None
        boundary_path = trial_dir / "agent/boundary.json"
        boundary = json.loads(boundary_path.read_text()) if boundary_path.exists() else None
        control = {
            "scenario": scenario, "expected_reward": expected, "actual_reward": reward,
            "exception": result.exception_info.model_dump(mode="json") if result.exception_info else None,
            "raw_trial": str(trial_dir.relative_to(BASE)),
            "task_checksum": result.task_checksum,
            "task_lock_digest": lock_digest,
            "verifier_environment_mode": result.verifier_environment_mode.value if result.verifier_environment_mode else None,
            "agent_info": result.agent_info.model_dump(mode="json"),
            "sidecar_policy_observations": list(sidecars.values()),
            "agent_boundary": boundary, "verifier_evidence": verifier,
        }
        controls.append(control)
        print(json.dumps({"scenario": scenario, "reward": reward, "exception": control["exception"]}), flush=True)
        assert not result.exception_info, f"{scenario}: infrastructure failure"
        assert result.task_checksum == frozen_task_checksum, "Trial task checksum drifted"
        assert Task(BASE / "task").checksum == frozen_task_checksum, "Task changed during control"
        assert component_hashes() == frozen_components, "Experiment sources changed during control"
        assert control["verifier_environment_mode"] == "separate"
        assert not result.agent_info.model_info
        assert reward == expected, f"{scenario}: unexpected reward"
        assert verifier and verifier["fixture_sha256"] == fixture_sha
        assert verifier["external_https_probe_blocked"]
        assert not verifier["agent_input_present_in_verifier"]
        assert not verifier["agent_solution_present_in_verifier"]
        assert not verifier["agent_tamper_marker_present_in_verifier"]
        if scenario != "nop":
            assert boundary and boundary["external_https_probe_blocked"]
            assert boundary["hostname"] != verifier["hostname"]
    assert component_hashes() == frozen_components, "Experiment sources changed after controls"
    assert Task(BASE / "task").checksum == frozen_task_checksum, "Task checksum changed after controls"
    report = {
        "kind": "synthetic-infrastructure-evidence", "checked_at": datetime.now(timezone.utc).isoformat(),
        "harbor_commit": actual_commit, "harbor_version": version("harbor"),
        "python_version": sys.version.split()[0], "python_base": PYTHON_BASE, "egress_base": EGRESS_BASE,
        "kernel_probe_base": KERNEL_PROBE_BASE,
        "frozen_task_checksum": frozen_task_checksum, "frozen_task_lock_digest": frozen_lock_digest,
        "task_identity_note": "TrialLock.task.digest is Harbor's durable package identity; task_checksum is the deprecated directory checksum retained as an additional stability check. Explicit ignore rules exclude generated Python bytecode.",
        "source_stability": "Component hashes and Harbor task checksums matched before/after every control; all trial lock digests matched.",
        "model": None, "provider_api_calls": 0, "paid_runs": 0,
        "telemetry_enabled": False, "host_credentials_forwarded": False,
        "network_policy": "no-network (native Harbor Docker egress sidecar)",
        "network_probe_scope": "Full HTTPS GET https://example.com/ must fail in agent and verifier; a temporary public-network container must first return200 with Example Domain. Not a complete egress audit.",
        "public_network_https_positive_control": https_baseline,
        "network_policy_limitations": "Native Harbor no-network denies controlled TCP egress through a transparent proxy; configured DNS and ICMP/ICMPv6 remain permitted. It is not Docker network_mode=none; raw TCP connect can reach the local proxy.",
        "summary_redactions": "Sidecar Compose labels retain only image, project, service, version and config-hash. Host and temporary paths remain only in ignored raw trial diagnostics.",
        "controls": controls, "component_sha256": frozen_components,
    }
    (BASE / "synthetic-results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(run_controls())
