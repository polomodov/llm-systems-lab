"""Run four no-model controls through real Harbor Trial and separate verifier.

The native adapter lifecycle is tested separately by offline_smoke.py. These
controls qualify materialized Docker task boundaries, not provider access.
"""

import sys
from pathlib import Path
sys.path = [p for p in sys.path if Path(p).resolve() != Path(__file__).resolve().parent]
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import shlex

BASE = Path(__file__).resolve().parent
INTEROP = BASE.parent / "harbor-interop"


def isolate(docker_host, plugins):
    if not docker_host.startswith("unix://"):
        raise ValueError("Only a local Unix Docker daemon is supported")
    private = BASE / ".cache/control-home"
    config = private / ".docker"
    config.mkdir(parents=True, exist_ok=True)
    (config / "config.json").write_text(json.dumps({"cliPluginsExtraDirs": [str(plugins.resolve())]}) + "\n")
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    os.environ.clear()
    os.environ.update(PATH=path, HOME=str(private), DOCKER_CONFIG=str(config),
        DOCKER_HOST=docker_host, HARBOR_TELEMETRY="0", PYTHONDONTWRITEBYTECODE="1",
        LITELLM_LOCAL_MODEL_COST_MAP="True", LC_ALL="C.UTF-8")
    sys.dont_write_bytecode = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--docker-plugin-dir", type=Path, required=True)
    parser.add_argument("--all-images", action="store_true", help="Repeat the same boundary suite for every distinct image")
    args = parser.parse_args()
    isolate(args.docker_host, args.docker_plugin_dir)

from harbor.agents.nop import NopAgent
from harbor.models.trial.config import TrialConfig
from harbor.publisher.packager import Packager
from harbor.trial.trial import Trial
materializer_spec = importlib.util.spec_from_file_location("native_materialize", BASE / "materialize.py")
materializer = importlib.util.module_from_spec(materializer_spec)
materializer_spec.loader.exec_module(materializer)
materialize = materializer.materialize
sys.modules["verify_controls"] = sys.modules[__name__]

# Reuse read-only helpers from the already qualified experiment. No old task or
# result is rewritten; only BASE is rebound in this private imported module.
spec = importlib.util.spec_from_file_location("prior_synthetic_controls", INTEROP / "synthetic_controls.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.BASE = BASE


class ArtifactControlAgent(NopAgent):
    @staticmethod
    def name():
        return "native-artifact-control"

    def __init__(self, *args, scenario="bad", **kwargs):
        super().__init__(*args, **kwargs)
        if scenario not in {"bad", "tamper"}:
            raise ValueError(scenario)
        self.scenario = scenario

    async def run(self, instruction, environment, context):
        code = r'''
const fs = require('node:fs'), os = require('node:os'), assert = require('node:assert/strict');
const absent = ['/tests', '/opt/verifier-fixtures', '/var/run/docker.sock'];
assert.equal(process.getuid(), 1000);
assert(absent.every(path => !fs.existsSync(path)));
const evidence = {effective_uid: process.getuid(), hostname: os.hostname(), absent_paths: absent, scenario: SCENARIO};
fs.mkdirSync('/app/output', {recursive:true});
fs.writeFileSync('/app/output/result.json', '["wrong"]\n');
if (SCENARIO === 'tamper') {
  evidence.protected_directory_creation_denied = [];
  for (const path of ['/tests', '/opt/verifier-fixtures']) {
    try { fs.mkdirSync(path); throw new Error('Protected directory writable: ' + path); }
    catch (error) { if (error.code !== 'EACCES') throw error; evidence.protected_directory_creation_denied.push(path); }
  }
  fs.mkdirSync('/logs/verifier', {recursive:true});
  fs.writeFileSync('/logs/verifier/reward.txt', '1\n');
  // Harbor copies environment/ after startup, retaining host file ownership.
  // The agent cannot chmod that copy, but can replace it through writable /app.
  // The independent verifier must survive this actual permitted attack path.
  fs.unlinkSync('/app/input.json');
  fs.writeFileSync('/app/input.json', '["wrong"]\n');
  evidence.input_tamper_method = 'replace-through-writable-parent';
  fs.writeFileSync('/app/agent-only.txt', 'must not reach verifier\n');
  evidence.forged_shared_reward = '1'; evidence.modified_agent_input = ['wrong'];
}
const request = require('node:https').get('https://example.com/', {timeout:3000}, response => {
  response.resume(); throw new Error('External HTTPS unexpectedly succeeded');
});
request.on('timeout', () => request.destroy(new Error('blocked by timeout')));
request.on('error', () => {
  evidence.external_https_probe_blocked = true;
  fs.writeFileSync('/logs/agent/boundary.json', JSON.stringify(evidence) + '\n');
});
'''.replace("SCENARIO", json.dumps(self.scenario))
        result = await environment.exec(command="node -e " + shlex.quote(code))
        if result.return_code:
            raise RuntimeError(result.stderr or result.stdout)


async def main():
    materialize(check=True)
    source_paths = [Path(__file__), BASE / "materialize.py", INTEROP / "synthetic_controls.py"]
    frozen_sources = {str(p.relative_to(BASE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    lock_path = BASE / "package-lock.json"
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    # The separate verifier and task policies are common to every slot. Test
    # their complete boundary on mini's Python/uv image; per-image runtime probes
    # and all six native lifecycles are recorded separately. --all-images repeats
    # the same controls when an image-specific boundary concern justifies it.
    packages = []
    seen = set()
    for package in lock["packages"]:
        selected = args.all_images or package["slot_id"] == "HN-O02"
        if selected and package["mode"] == "offline" and package["image_id"] not in seen:
            packages.append(package)
            seen.add(package["image_id"])
    assert len(packages) == (5 if args.all_images else 1), "Expected image coverage is missing"
    run_dir = BASE / ".cache/control-runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True)
    (run_dir / "package-lock.json").write_bytes(lock_bytes)
    fixture_sha = hashlib.sha256((BASE / "task/tests/expected.json").read_bytes()).hexdigest()
    controls = []
    for package in packages:
        target = BASE / package["path"]
        for scenario, expected in [("oracle", 1), ("nop", 0), ("bad", 0), ("tamper", 0)]:
            assert lock_path.read_bytes() == lock_bytes, "Package lock changed"
            assert "sha256:" + Packager.compute_content_hash(target)[0] == package["task_digest"]
            name = "native-" + package["slot_id"].lower() + "-" + scenario
            agent = {"name": scenario} if scenario in {"oracle", "nop"} else {
                "import_path": "verify_controls:ArtifactControlAgent", "kwargs": {"scenario": scenario}}
            config = TrialConfig.model_validate({"task": {"path": str(target)}, "trial_name": name,
                "trials_dir": str(run_dir), "agent": agent,
                "environment": {"type": "docker", "delete": True, "force_build": False}})
            trial = await Trial.create(config)
            active = asyncio.create_task(trial.run())
            sidecars = {}
            while not active.done():
                await prior.observe_sidecars(name, sidecars)
                await asyncio.sleep(0.25)
            result = await active
            trial_dir = run_dir / name
            digest = json.loads((trial_dir / "lock.json").read_text())["task"]["digest"]
            control = prior.control_record(result, trial_dir, scenario, expected, sidecars, digest)
            control.update(slot_id=package["slot_id"], image_id=package["image_id"])
            control["raw_file_sha256"] = {str(p.relative_to(trial_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(trial_dir.rglob("*")) if p.is_file()}
            print(json.dumps({"slot": package["slot_id"], "scenario": scenario,
                "reward": control["actual_reward"], "exception": control["exception"]}), flush=True)
            assert not result.exception_info, "Infrastructure failure"
            assert digest == package["task_digest"], "Harbor task digest drift"
            prior.validate_control(control, fixture_sha)
            assert sidecars, "No effective network rules captured"
            assert "sha256:" + Packager.compute_content_hash(target)[0] == digest
            controls.append(control)
    materialize(check=True)
    assert frozen_sources == {str(p.relative_to(BASE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}, "Control sources changed"
    assert len(controls) == (20 if args.all_images else 4), "Expected controls are missing"
    code, remaining = await prior.docker_output("ps", "-aq", "--filter", "label=com.docker.compose.project", "--filter", "name=native-hn-")
    assert code == 0 and not remaining.strip(), "Control containers remain"
    evidence = {"schema_version": 1, "kind": "native-pilot-offline-boundary-controls",
        "checked_at": datetime.now(timezone.utc).isoformat(), "harbor_commit": lock["harbor_commit"],
        "package_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reused_helpers_sha256": hashlib.sha256((INTEROP / "synthetic_controls.py").read_bytes()).hexdigest(),
        "source_sha256": frozen_sources,
        "provider_api_calls": 0, "paid_runs": 0, "host_credentials_forwarded": False,
        "controls": controls, "control_count": len(controls), "cleanup_passed": True,
        "network_scope": "Every phase denies controlled TCP via Harbor sidecar; rules captured and HTTPS blocked. DNS/ICMP remain permitted. No online positive control was run in this offline suite; prior experiment has a separately recorded positive control.",
        "interpretation": "Four real Harbor Trial controls on each selected image; default representative is mini's Python/uv image with the common task policy and separate verifier. This is not a full native-agent Trial or live API qualification. See runtime-evidence.json for per-image probes and native-smoke-evidence.json for all six actual native CLI fixture lifecycles."}
    (BASE / "control-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
