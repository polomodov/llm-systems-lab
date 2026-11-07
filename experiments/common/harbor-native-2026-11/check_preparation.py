#!/usr/bin/env python3
"""Read-only aggregate check of sealed offline evidence and prepared records.

Uses pinned Harbor schemas, local Git identity, and the lab's Node validators.
Never starts Docker, an agent, a provider request, or a model trial. Raw evidence
must still be present locally: summaries alone cannot pass this check.
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.dont_write_bytecode = True
sys.path = [entry for entry in sys.path if Path(entry).resolve() != BASE]
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import re

SLOTS = ["HN-O01", "HN-A01", "HN-A02", "HN-A03", "HN-O02", "HN-O03"]
HARNESSES = {"codex", "claude-code", "opencode", "pi", "mini-swe-agent"}
VERSION_PATTERNS = {"claude-code": r"([0-9]+\.[0-9]+\.[0-9]+) \(Claude Code\)",
                    "codex": r"codex-cli ([0-9]+\.[0-9]+\.[0-9]+)",
                    "opencode": r"([0-9]+\.[0-9]+\.[0-9]+)",
                    "pi": r"([0-9]+\.[0-9]+\.[0-9]+)",
                    "mini-swe-agent": r"mini-swe-agent v([0-9]+\.[0-9]+\.[0-9]+)"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def owned(root, relative):
    path = Path(relative)
    require(not path.is_absolute() and path.parts and ".." not in path.parts,
            "Evidence path escapes its declared root")
    cursor = Path(root)
    require(not cursor.is_symlink(), "Evidence root cannot be a symlink")
    for part in path.parts:
        cursor /= part
        require(not cursor.is_symlink(), "Symlink evidence is not accepted")
    return cursor


def files(root, *, exclude=()):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Raw evidence directory is missing")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Symlink in evidence inventory")
        if path.is_dir():
            continue
        require(path.is_file(), "Unsupported evidence file type")
        name = path.relative_to(root).as_posix()
        if name not in exclude:
            result[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    return result


def check_hashes(root, mapping, label):
    require(isinstance(mapping, dict) and mapping, label + " inventory is missing")
    for name, expected in mapping.items():
        require(re.fullmatch(r"[a-f0-9]{64}", expected) is not None, label + " has an invalid hash")
        require(sha(owned(root, name)) == expected, label + " changed: " + name)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def slot_hash(plan):
    data = [{key: value for key, value in slot.items() if key not in {"status", "run_id", "image_id"}} for slot in plan["slots"]]
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check_runtime(plan):
    runtime = read(BASE / "runtime-lock.json")
    evidence = read(BASE / "runtime-evidence.json")
    require(runtime["provider_requests"] == 0 and runtime["credential_files_read"] is False,
            "Runtime preparation was not credential-free")
    require(runtime["build_network"] == "none", "Runtime build network differs")
    require(runtime["harbor_commit"] == plan["harbor_commit"], "Runtime Harbor pin differs")
    check_hashes(ROOT, runtime["source_sha256"], "Runtime source")
    inventory_path = owned(BASE, evidence["package_inventory_file"])
    require(sha(inventory_path) == evidence["package_inventory_sha256"], "Runtime package inventory changed")
    inventories = read(inventory_path)
    require(set(runtime["images"]) == HARNESSES, "Expected exactly five frozen runtime images")
    require(set(inventories) == HARNESSES | {"verifier"} and set(evidence["images"]) == set(inventories),
            "Runtime evidence does not cover all agent/verifier images")
    require(evidence["model_requests"] == 0, "Runtime evidence includes model requests")
    for name, inventory in inventories.items():
        image = runtime["verifier"] if name == "verifier" else runtime["images"][name]
        probe = evidence["images"][name]
        require(re.fullmatch(r"sha256:[a-f0-9]{64}", image["image_id"]) is not None,
                "Runtime image is not immutable")
        require(inventory["image_id"] == image["image_id"], "Runtime inventory image differs: " + name)
        require(inventory["os_packages"], "Runtime OS inventory is empty")
        require(probe["uid"] == 1000 and probe["network"] == "none" and probe["provider_requests"] == 0,
                "Runtime isolation probe differs: " + name)
        if name != "verifier":
            versions = [match.group(1) for line in probe["version_output"].splitlines()
                        if (match := re.fullmatch(VERSION_PATTERNS[name], line))]
            require(versions == [image["version"]], "Runtime version probe differs: " + name)
            require(probe["workspace_and_logs_writable"] is True and probe["verifier_paths_and_docker_socket_absent"] is True,
                    "Runtime filesystem boundary failed: " + name)
    require(evidence["images"]["verifier"]["fixture_directory_writable"] is False,
            "Verifier fixture is writable")
    pi = evidence["images"]["pi"]["runtime_details"]
    expected_model = next(slot["wire_model_id"] for slot in plan["slots"] if slot["slot_id"] == "HN-O03")
    model_metadata = read(BASE / "runtime/pi/models.json")["providers"]["openai"]["models"]
    require(len(model_metadata) == 1 and model_metadata[0]["id"] == expected_model,
            "Pi frozen model metadata does not select the exact planned model")
    require(all(pi["model"].get(key) == value for key, value in model_metadata[0].items()),
            "Pi observed model metadata/cost/limits differ from frozen models.json")
    require(pi["model"]["id"] == expected_model and pi["model"]["api"] == "openai-responses" and
            pi["model"]["provider"] == "openai" and pi["compaction"] is False and pi["retry"] is False,
            "Pi exact-model metadata/settings probe differs")
    mini = evidence["images"]["mini-swe-agent"]["runtime_details"]
    require(mini["mini-swe-agent"] == runtime["images"]["mini-swe-agent"]["version"] and
            mini["uv"] == "0.13.7" and mini["full_dependency_check"] == "No broken requirements found.",
            "mini uv/dependency qualification is incomplete")
    return runtime


def check_smoke(plan, runtime):
    report = read(BASE / "native-smoke-evidence.json")
    require(report["runtime_lock_sha256"] == sha(BASE / "runtime-lock.json"), "Native evidence uses a stale runtime lock")
    require(report["slot_configuration_sha256"] == slot_hash(plan), "Native evidence uses stale slot configuration")
    require(report["harbor_commit"] == plan["harbor_commit"], "Native Harbor pin differs")
    require(report["frozen_inputs_stable"] == {"components": True, "runtime_lock": True, "slot_configuration": True},
            "Native evidence input drift detected")
    check_hashes(BASE, report["components_sha256"], "Native smoke source")
    require(set(report["components_sha256"]) == {"offline_smoke.py", "mock-provider.mjs", "task/instruction.md", "task/environment/input.json"},
            "Native source coverage is incomplete")
    frozen = owned(BASE, report["frozen_input_directory"])
    require(sha(frozen / "plan.json") == report["plan_sha256"] and
            sha(frozen / "runtime-lock.json") == report["runtime_lock_sha256"], "Native frozen input snapshots changed")
    require(slot_hash(read(frozen / "plan.json")) == slot_hash(plan), "Native plan snapshot differs from current slots")
    require(report["provider_requests"] == 0 and report["paid_runs"] == 0 and report["real_credentials_read"] is False,
            "Native fixture evidence contains real execution")
    require([row["slot_id"] for row in report["slots"]] == SLOTS, "Native evidence does not cover the six ordered slots")
    for slot, row in zip(plan["slots"], report["slots"]):
        require(row["status"] == "passed" and row["cleanup_confirmed"] is True, "Native slot failed or cleanup is missing: " + slot["slot_id"])
        require(row["harness"] == slot["harness"] and row["model"] == slot["wire_model_id"] and
                row["image_id"] == runtime["images"][slot["harness"]]["image_id"] and row["observed_version"] == slot["version"],
                "Native slot identity differs: " + slot["slot_id"])
        require(row["docker_network"] == "none" and row["host_mounts"] == [] and row["provider_requests"] == 0,
                "Native isolation differs")
        require(row["synthetic_protocol_usage"] is True and row["native_trace_complete"] is True and
                row["artifact_verified"] is True and row["native_process_exit_code"] == 0 and
                row["tool_executed_as_uid"] == 1000 and row["task_effective_capabilities"] == [],
                "Native tool/trace evidence is incomplete")
        require(row["observed_request_models"] == [slot["wire_model_id"]] and row["fixture_requests"] > 0,
                "Native fixture model route is unverified")
        require(row["instruction_sha256"] == sha(BASE / "task/instruction.md") and
                row["input_sha256"] == sha(BASE / "task/environment/input.json"), "Native public inputs differ")
        raw = owned(BASE, row["raw_directory"])
        manifest = raw / "evidence-manifest.json"
        require(sha(manifest) == row["evidence_manifest_sha256"], "Native evidence manifest changed")
        expected = read(manifest)
        require(files(raw, exclude={"evidence-manifest.json"}) == expected, "Native raw evidence changed")
        require(all(expected.get(name) == value for name, value in row["evidence_files"].items()),
                "Native summary files differ from complete evidence inventory")
    return len(report["slots"])


def check_controls(plan, runtime):
    report = read(BASE / "control-evidence.json")
    require(report["control_count"] == 4 and len(report["controls"]) == 4, "Expected exactly four representative boundary controls")
    require(report["cleanup_passed"] is True and report["provider_api_calls"] == 0 and
            report["paid_runs"] == 0 and report["host_credentials_forwarded"] is False,
            "Boundary controls are not clean offline evidence")
    require(report["harbor_commit"] == plan["harbor_commit"], "Control Harbor pin differs")
    require(report["package_lock_sha256"] == sha(BASE / "package-lock.json"), "Control package lock is stale")
    require(report["runner_sha256"] == sha(BASE / "verify_controls.py") and
            report["reused_helpers_sha256"] == sha(BASE.parent / "harbor-interop/synthetic_controls.py"),
            "Control runner/helper changed")
    check_hashes(BASE.parent, report["source_sha256"], "Control source")
    require(set(report["source_sha256"]) == {"harbor-native-2026-11/verify_controls.py", "harbor-native-2026-11/materialize.py", "harbor-interop/synthetic_controls.py"},
            "Control source coverage is incomplete")
    packages = read(BASE / "package-lock.json")["packages"]
    package = next(row for row in packages if row["slot_id"] == "HN-O02" and row["mode"] == "offline")
    require([row["scenario"] for row in report["controls"]] == ["oracle", "nop", "bad", "tamper"], "Boundary control scenarios differ")
    fixture_sha = sha(BASE / "task/tests/expected.json")
    for control, reward in zip(report["controls"], [1, 0, 0, 0]):
        require(control["slot_id"] == "HN-O02" and control["image_id"] == runtime["images"]["mini-swe-agent"]["image_id"],
                "Representative control image differs")
        require(control["expected_reward"] == reward and control["actual_reward"] == reward and control["exception"] is None,
                "Boundary control failed: " + control["scenario"])
        require(control["task_lock_digest"] == package["task_digest"] and control["verifier_environment_mode"] == "separate" and
                not control["agent_info"].get("model_info") and control["sidecar_policy_observations"],
                "Control task/verifier/model/network conditions differ")
        raw = owned(BASE, control["raw_trial"])
        require({name: item["sha256"] for name, item in files(raw).items()} == control["raw_file_sha256"],
                "Boundary raw trial evidence changed")
        require(sha(raw.parent / "package-lock.json") == report["package_lock_sha256"], "Control frozen package lock changed")
        result = read(raw / "result.json")
        require(result["verifier_result"]["rewards"]["reward"] == reward and result["exception_info"] is None and
                result["agent_info"] == control["agent_info"] and result["verifier_environment_mode"] == "separate",
                "Control verdict/identity summary differs from raw trial result")
        require(read(raw / "lock.json")["task"]["digest"] == control["task_lock_digest"], "Raw trial package digest differs")
        verifier = control["verifier_evidence"]
        require(read(raw / "verifier/evidence.json") == verifier, "Control verifier summary differs from raw evidence")
        require(verifier["fixture_sha256"] == fixture_sha and verifier["effective_uid"] == 1000 and
                verifier["fixture_writable"] is False and verifier["external_https_probe_blocked"] is True and
                not verifier["agent_input_present_in_verifier"] and not verifier["agent_solution_present_in_verifier"] and
                not verifier["agent_tamper_marker_present_in_verifier"], "Separate verifier boundary failed")
        if control["scenario"] != "nop":
            boundary = control["agent_boundary"]
            require(read(raw / "agent/boundary.json") == boundary and boundary["external_https_probe_blocked"] is True and
                    boundary["effective_uid"] == 1000 and boundary["hostname"] != verifier["hostname"], "Agent boundary failed")
        if control["scenario"] == "tamper":
            require(boundary["protected_directory_creation_denied"] == ["/tests", "/opt/verifier-fixtures"] and
                    boundary["forged_shared_reward"] == "1" and boundary["modified_agent_input"] == ["wrong"],
                    "Tamper negative control is incomplete")
    return len(report["controls"])


def check_records(plan):
    accounting = load_module("native_pilot_accounting_check", BASE / "accounting.py")
    ids = [slot["run_id"] for slot in plan["slots"]]
    require(all(isinstance(value, str) and value for value in ids) and len(set(ids)) == 6, "Six unique prepared run IDs are required")
    for slot in plan["slots"]:
        bundle = owned(ROOT, "results/runs/" + slot["run_id"])
        record = read(bundle / "run.json")
        accounting.core_check(ROOT, record)
        require(record["status"] == "prepared" and record["verdict"]["result"] == "pending", "Pilot record is not unexecuted/prepared")
        require(record["execution"]["command"] == [] and record["execution"]["started_at"] is None and
                record["execution"]["finished_at"] is None and record["model"]["observed_id"] is None,
                "Prepared pilot record contains execution observations")
        require(all(record["loop"][metric] is None for metric in accounting.METRICS) and
                record["permissions"]["asked"] is None and record["loop"]["stop_reason"] is None,
                "Prepared pilot record contains measured outcomes")
        require(read(bundle / "inputs/pilot-slot.json") == slot and read(bundle / "inputs/plan.json") == plan,
                "Prepared record does not seal the current final plan")
        require(sha(bundle / "inputs/runtime-lock.json") == sha(BASE / "runtime-lock.json") and
                sha(bundle / "inputs/package-lock.json") == sha(BASE / "package-lock.json"), "Prepared record locks are stale")
    return len(ids)


def check(skip_records=False):
    plan = read(BASE / "plan.json")
    require(plan["execution_authorized"] is False and plan["launchable"] is False, "Preparation must remain unauthorized and non-executable")
    require([row["slot_id"] for row in plan["slots"]] == SLOTS, "Expected the exact six ordered pilot slots")
    materializer = load_module("native_pilot_materialize_check", BASE / "materialize.py")
    with redirect_stdout(io.StringIO()):
        materializer.materialize(check=True)
    runtime = check_runtime(plan)
    native_count = check_smoke(plan, runtime)
    control_count = check_controls(plan, runtime)
    records = None if skip_records else check_records(plan)
    return {"ok": True, "offline_only": True, "native_fixture_slots": native_count,
            "boundary_controls": control_count, "prepared_records": records, "records_skipped": skip_records,
            "paid_runs": 0, "execution_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-records", action="store_true", help="Temporary evidence check before six records are prepared")
    args = parser.parse_args()
    # Harbor imports/validators are data-only here. Forbid host connections as a
    # defensive check; neither Docker nor provider clients are used by this file.
    def no_connections(event, args):
        if event == "socket.connect":
            raise RuntimeError("Network/socket connections are disabled during offline preparation validation")
    sys.addaudithook(no_connections)
    try:
        print(json.dumps(check(args.skip_records), separators=(",", ":")))
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "offline_only": True, "error": str(error)}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
