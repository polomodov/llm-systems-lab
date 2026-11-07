#!/usr/bin/env python3
"""Data-only native-pilot record bridge. This module never starts a process/model trial.

prepare seals an unexecuted slot; mark_started imports an execution receipt;
finish imports immutable raw evidence. Native estimates never become billing.
All functions reject existing terminal attempts and modified snapshots.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TASK = "harbor-native-normalize"
AGENT = "harbor-native-normalizer"
IMPORTER = "harbor-native-pilot-v1"
METRICS = ("turns", "cost_usd", "tokens_in", "tokens_out", "wall_clock_s", "compactions", "subagents")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value, *, exclusive=True):
    with Path(path).open("x" if exclusive else "w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def safe(root, relative):
    root = Path(root).absolute()
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ("..", ".") for p in path.parts):
        raise ValueError("Evidence path must stay inside its bundle")
    cursor = root
    if root.is_symlink():
        raise ValueError("Symlink root is forbidden")
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("Symlink evidence is forbidden")
    return cursor


def inventory(root):
    rows = []
    for path in sorted(Path(root).iterdir()):
        if path.is_symlink():
            raise ValueError("Symlink snapshot is forbidden")
        if path.is_dir():
            rows.extend({**row, "path": path.name + "/" + row["path"]} for row in inventory(path))
        elif path.is_file():
            rows.append({"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size,
                         "executable": bool(path.stat().st_mode & 0o111)})
        else:
            raise ValueError("Unsupported snapshot file type")
    return rows


def copy_tree(source, dest):
    inventory(source)  # Reject symlinks before copying any bytes.
    shutil.copytree(source, dest)


def limits(contract):
    match = re.findall(r"Up to (\d+) turns or \$(\d+(?:\.\d+)?)", contract)
    timeout = re.findall(r"(\d+)-second external timeout", contract)
    if len(match) != 1 or len(timeout) != 1:
        raise ValueError("Ambiguous sealed task budget")
    return {"turns": int(match[0][0]), "usd": float(match[0][1]), "timeout_s": int(timeout[0])}


def core_check(root, record):
    """Use the existing lab schema, lifecycle, catalog and integrity validators."""
    script = """import {readFileSync} from 'node:fs';
import {validateRun} from './scripts/lib/records.mjs';
import {verifyRunIntegrity} from './scripts/lib/integrity.mjs';
const record=JSON.parse(readFileSync(0,'utf8')), root=process.argv[1];
const errors=validateRun(record,{root,folderName:record.run_id});
if(errors.length)throw new Error(errors.join('\\n'));
verifyRunIntegrity(root,record);"""
    result = subprocess.run(["node", "--input-type=module", "-e", script, str(Path(root).resolve())],
                            cwd=REPO, input=json.dumps(record), text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip())


@contextmanager
def locked(bundle):
    lock = Path(bundle) / ".accounting-lock"
    lock.mkdir()  # One writer; an interrupted update must be inspected, not replayed silently.
    try:
        yield
    finally:
        lock.rmdir()


def save_record(bundle, record):
    temp = Path(bundle) / "run.json.next"
    write(temp, record)
    temp.replace(Path(bundle) / "run.json")


def prepare(root, run_id, slot, package_dir, runtime_lock, package_lock, plan_path, *, source_revision=None):
    """Prepare one unexecuted attempt. Existing directories are never reused."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*", run_id):
        raise ValueError("Invalid run ID")
    root = Path(root).resolve()
    plan, runtime = read(plan_path), read(runtime_lock)
    if slot not in plan["slots"]:
        raise ValueError("Slot is not in the frozen plan")
    runtime_image = runtime["images"][slot["harness"]]
    image = runtime_image["image_id"]
    if runtime_image["version"] != slot["version"]:
        raise ValueError("Runtime lock has a different harness version")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("An immutable local image ID is required")
    package_dir = Path(package_dir)
    if not (package_dir / "task.toml").is_file():
        raise ValueError("Materialized task package is required")
    package_seal = read(package_lock)
    if package_seal["runtime_lock_sha256"] != digest(runtime_lock):
        raise ValueError("Package lock refers to a different runtime lock")
    packages = [row for row in package_seal["packages"] if row["slot_id"] == slot["slot_id"] and row["mode"] == "prepared"]
    actual_files = {row["path"]: row["sha256"] for row in inventory(package_dir)}
    if len(packages) != 1:
        raise ValueError("Exactly one prepared package must be frozen for the slot")
    package = packages[0]
    expected_files = {key.removeprefix("task/"): value for key, value in package_seal["source_sha256"].items() if key.startswith("task/")}
    expected_files.update(package["file_sha256"])
    task_digest = "sha256:" + hashlib.sha256("".join(f"{path}\0{value}\n" for path, value in sorted(package["harbor_file_sha256"].items())).encode()).hexdigest()
    if package["image_id"] != image or expected_files != actual_files or package["task_digest"] != task_digest:
        raise ValueError("Materialized package differs from its frozen slot lock")
    if package["verifier_image_id"] != runtime["verifier"]["image_id"]:
        raise ValueError("Package verifier differs from runtime lock")
    contract = (HERE / "task/contract.md").read_text()
    budget = limits(contract)
    bundle = safe(root, "results/runs/" + run_id)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.mkdir()  # Fail before writing anything if this attempt already exists.
    try:
        inputs = bundle / "inputs"
        inputs.mkdir()
        (bundle / "trace").mkdir()
        # Git does not retain empty directories; published prepared records
        # still need their declared trace path before any execution evidence.
        (bundle / "trace/.gitkeep").touch(exist_ok=False)
        copy_tree(package_dir, inputs / "task-package")
        for source, name in [(HERE / "task/contract.md", "task.md"), (HERE / "task/agent-spec.md", "agent-spec.md"),
                             (HERE / "task/registration.json", "registration.json"),
                             (runtime_lock, "runtime-lock.json"), (package_lock, "package-lock.json"), (plan_path, "plan.json")]:
            shutil.copy2(source, inputs / name)
        write(inputs / "pilot-slot.json", slot)
        manifest = {"version": 1, "importer": IMPORTER, "task": TASK, "harness": slot["harness"],
                    "image_id": image, "files": inventory(inputs), "workspace": []}
        write(inputs / "manifest.json", manifest)
        stamp = now()
        record = {
            "schema_version": 1, "run_id": run_id, "date": run_id[:10], "status": "prepared",
            "harness": {"name": slot["harness"], "version": slot["version"], "mode": slot["harbor_mode"]},
            "agent": AGENT, "task": TASK,
            "model": {"id": slot["wire_model_id"], "lock": True, "reasoning": slot["planned_kwargs"]["reasoning_effort"],
                      "observed_id": None, "identity_evidence": "Requested ID only; no model request has been made.",
                      "provider": slot["provider"], "selection": "explicit"},
            "permissions": {"mode": "native-adapter; isolated UID1000", "blocked": [], "asked": None},
            "sandbox": {"kind": "container", "network": "allowlist"},
            "loop": {**{key: None for key in METRICS}, "stop_reason": None, "budget_usd": budget["usd"]},
            "metrics_unavailable": {**{"loop." + key: "Attempt has not started." for key in METRICS}, "permissions.asked": "Attempt has not started."},
            "inputs": {"manifest_path": "inputs/manifest.json", "manifest_sha256": digest(inputs / "manifest.json"), "prepared_at": stamp},
            "provenance": {"git_commit": source_revision, "git_dirty": True, "recorded_at": stamp, "runner_version": IMPORTER,
                           "source_revision_reason": "Experiment preparation; all exact package/configuration bytes are sealed in inputs."},
            "execution": {"command": [], "cwd": None, "started_at": None, "finished_at": None, "exit_code": None,
                          "signal": None, "timed_out": False, "image_id": image, "timeout_s": budget["timeout_s"],
                          "network_policy": "setup=no-network; agent=selected-provider-only; verifier=no-network; Harbor permits DNS/ICMP",
                          "budget_policy": "observed", "proxy_image_id": None},
            "evaluation": {key: None for key in ("method", "evaluator", "evidence_path", "evidence_sha256", "evaluated_at")},
            "verdict": {"result": "pending", "check_output": "", "human_notes": ""},
            "harness_changes": [{"component": "Frozen native Harbor runtime, isolated verifier and evidence accounting", "kind": "walls", "ledger": "L032"}], "trace_path": "trace/",
            "notes": "Separate native Harbor synthetic pilot. Preparation is not authorization or evidence of paid execution; existing campaigns are unchanged.",
        }
        write(bundle / "run.json", record)
        core_check(root, record)
    except Exception:
        shutil.rmtree(bundle)
        raise
    return bundle


def mark_started(root, run_id, receipt):
    """Import a receipt captured by a separately authorized coordinator; never launch."""
    bundle = safe(root, "results/runs/" + run_id)
    with locked(bundle):
        record = read(bundle / "run.json")
        core_check(root, record)
        if record["status"] != "prepared":
            raise ValueError("Only an unused prepared attempt may start")
        if receipt["image_id"] != record["execution"]["image_id"] or receipt["observed_version"] != record["harness"]["version"]:
            raise ValueError("Observed runtime differs from sealed version/image")
        for key in ("command", "cwd", "started_at"):
            if not receipt.get(key):
                raise ValueError("Incomplete execution receipt")
            record["execution"][key] = receipt[key]
        record["status"] = "running"
        write(bundle / "trace/start-receipt.json", receipt)
        core_check(root, record)
        save_record(bundle, record)
    return record


def value_from(evidence, reference, allowed):
    """Read an explicit native/provider value; never infer it from an ATIF fallback."""
    if reference.get("kind") not in allowed:
        raise ValueError("Unsupported measurement provenance")
    path = safe(evidence, reference["file"])
    if path.suffix == ".jsonl":
        value = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        value = read(path)
    pointer = reference["pointer"]
    if pointer and not pointer.startswith("/"):
        raise ValueError("Expected JSON pointer")
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def numeric(value, *, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (integer and not isinstance(value, int)):
        raise ValueError("Measurement must be a finite nonnegative number of the declared type")
    return value


def finish(root, run_id, evidence_dir, observation):
    """Import a terminal evidence bundle. Caller supplies provenance pointers, not metrics.

    observation fields: execution (finished_at/exit_code/signal/timed_out),
    native_log, atif, identity reference, metrics references, billing reference,
    verifier reference, boundary reference. Pointers are into copied JSON/JSONL.
    Billing must be provider_billing with {status: settled, run_id, cost_usd}.
    ATIF final_metrics and native cost estimates are deliberately never imported.
    """
    bundle = safe(root, "results/runs/" + run_id)
    with locked(bundle):
        record = read(bundle / "run.json")
        core_check(root, record)
        if record["status"] != "running":
            raise ValueError("Only a started, nonterminal attempt may be finalized")
        evidence = bundle / "trace/evidence"
        if evidence.exists():
            raise ValueError("Evidence was already imported; inspect interrupted finalization")
        # Check references and measurements before creating the immutable evidence copy.
        source = Path(evidence_dir)
        inventory(source)
        if (source / "import-observation.json").exists():
            raise ValueError("Reserved import-observation filename")
        native = safe(source, observation["native_log"])
        if not native.is_file() or not native.stat().st_size:
            raise ValueError("Native trace is required")
        identity_ref = observation.get("identity")
        observed = value_from(source, identity_ref, {"provider_response", "native_response"}) if identity_ref else None
        if observed is not None and (not isinstance(observed, str) or not observed):
            raise ValueError("Observed model identity must be a string")
        record["model"]["observed_id"] = observed
        record["model"]["identity_evidence"] = json.dumps(identity_ref) if identity_ref else "No response-level model identity; requested/native configuration is not observed identity."
        permission_ref = observation.get("metrics", {}).get("permissions.asked")
        record["permissions"]["asked"] = numeric(value_from(source, permission_ref, {"native_usage", "coordinator_observation"}), integer=True) if permission_ref else None
        record["metrics_unavailable"] = {} if permission_ref else {"permissions.asked": "Native permission counter not available."}
        for key in METRICS:
            reference = observation.get("metrics", {}).get(key)
            if key == "cost_usd":
                reference = None  # Only settled attributable billing can populate cost_usd.
            value = value_from(source, reference, {"native_usage", "provider_response", "coordinator_observation"}) if reference else None
            record["loop"][key] = numeric(value, integer=key not in ("wall_clock_s", "cost_usd")) if value is not None else None
            if value is None:
                record["metrics_unavailable"]["loop." + key] = "No attributable raw measurement; native/ATIF zero defaults and estimates are not measurements."
        billing_ref = observation.get("billing")
        billing = value_from(source, billing_ref, {"provider_billing"}) if billing_ref else None
        cost_status = "unknown"
        if billing:
            if billing.get("run_id") != run_id:
                raise ValueError("Billing attribution differs from run")
            cost_status = billing.get("status", "unknown")
            if cost_status == "settled":
                record["loop"]["cost_usd"] = numeric(billing["cost_usd"])
                record["metrics_unavailable"].pop("loop.cost_usd", None)
        boundary = value_from(source, observation["boundary"], {"coordinator_observation"})
        if not isinstance(boundary, dict) or not all(isinstance(boundary.get(key), bool) for key in ("passed", "cleanup_complete")):
            raise ValueError("Boundary and teardown observations are required")
        execution = observation["execution"]
        for key in ("finished_at", "exit_code", "signal", "timed_out"):
            record["execution"][key] = execution[key]
        failure = None
        if observed is not None and observed != record["model"]["id"]:
            failure = "observed-model-mismatch"
        elif execution["timed_out"]:
            failure = "timeout"
        elif execution["exit_code"] not in (None, 0) or execution["signal"] is not None:
            failure = "native-process-failure"
        elif not boundary["passed"] or not boundary["cleanup_complete"]:
            failure = "boundary-or-cleanup-failure"
        elif not observation.get("terminal_native_trace", False):
            failure = "incomplete-native-trace"
        atif_valid = False
        atif_error = None
        if observation.get("atif"):
            # The neighboring historical inspect.py must not shadow stdlib inspect.
            sys.path = [entry for entry in sys.path if Path(entry).resolve() != HERE]
            from harbor.utils.trajectory_validator import TrajectoryValidator
            validator = TrajectoryValidator()
            try:
                atif_path = safe(source, observation["atif"])
                atif_valid = validator.validate(atif_path)
                atif_error = None if atif_valid else "; ".join(validator.get_errors())
            except (ValueError, OSError) as error:
                atif_error = str(error)
        verifier = value_from(source, observation["verifier"], {"independent_verifier"}) if observation.get("verifier") else None
        if not verifier and not failure:
            failure = "missing-independent-verifier"
        if verifier:
            artifact = safe(source, verifier["artifact_file"])
            sealed_verifier = bundle / "inputs/task-package/tests/evaluate.py"
            if digest(artifact) != verifier["artifact_sha256"] or digest(sealed_verifier) != verifier["verifier_sha256"]:
                raise ValueError("Independent verifier artifact or frozen code binding differs")
        if verifier and (verifier.get("result") not in ("pass", "fail", "partial") or not verifier.get("check_output")):
            raise ValueError("Invalid independent verifier verdict")
        record["status"] = "aborted" if failure else "completed"
        record["loop"]["stop_reason"] = failure or "native-terminal-evidence-imported"
        record["verdict"] = {"result": "aborted" if failure else verifier["result"], "check_output": failure or verifier["check_output"],
                             "human_notes": "Synthetic infrastructure qualification only; full qualification requires observed identity, valid ATIF and settled billing."}
        tool_ref = observation.get("tool_operations")
        tool_count = numeric(value_from(source, tool_ref, {"native_usage"}), integer=True) if tool_ref else None
        qualification = "failed" if failure or verifier["result"] == "fail" else (
            "qualified" if verifier["result"] == "pass" and observed and atif_valid and cost_status == "settled" and tool_count and tool_count > 0 and not record["metrics_unavailable"] else "inconclusive")
        copy_tree(source, evidence)
        write(evidence / "import-observation.json", observation)
        accounting = {"schema_version": 1, "run_id": run_id, "status": record["status"], "qualification": qualification,
                      "observed_model_id": observed, "cost_usd": record["loop"]["cost_usd"], "cost_status": cost_status,
                      "atif_valid": atif_valid, "atif_error": atif_error, "task_tool_operations": tool_count, "evidence_files": inventory(evidence),
                      "loop": record["loop"], "permissions_asked": record["permissions"]["asked"], "identity_reference": identity_ref, "metrics_references": observation.get("metrics", {}),
                      "billing_reference": billing_ref, "start_receipt_sha256": digest(bundle / "trace/start-receipt.json")}
        write(bundle / "trace/accounting.json", accounting)
        # The evaluator checks the artifact in the preserved native evidence bundle.
        # Inventories are empty because the original workspace is never imported as a lab workspace.
        for name in ("artifacts", "final-workspace"):
            write(bundle / ("trace/" + name + ".json"), [])
        evaluation = {"run_id": run_id, "result": record["verdict"]["result"], "method": "separate-native-harbor-verifier",
                      "evaluator": "frozen-synthetic-verifier", "check_output": record["verdict"]["check_output"],
                      "artifacts_sha256": digest(bundle / "trace/artifacts.json"), "workspace_sha256": digest(bundle / "trace/final-workspace.json"),
                      "accounting_sha256": digest(bundle / "trace/accounting.json")}
        write(bundle / "trace/evaluation.json", evaluation)
        record["evaluation"] = {"method": evaluation["method"], "evaluator": evaluation["evaluator"], "evidence_path": "trace/evaluation.json",
                                "evidence_sha256": digest(bundle / "trace/evaluation.json"), "evaluated_at": now()}
        core_check(root, record)
        save_record(bundle, record)
    return record


def admission(root, run_ids, next_slot, plan):
    """Return accounting admission only. This never authorizes or launches a trial."""
    if next_slot not in plan["slots"] or len({slot["slot_id"] for slot in plan["slots"]}) != len(plan["slots"]):
        return {"admitted": False, "reason": "Next slot is not an exact member of the frozen plan"}
    index = plan["slots"].index(next_slot)
    prior = plan["slots"][:index]
    if len(run_ids) != len(prior) or len(set(run_ids)) != len(run_ids):
        return {"admitted": False, "reason": "Complete prior slot prefix is required"}
    discovered = set()
    for path in (Path(root) / "results/runs").glob("*/run.json"):
        candidate = read(path)
        if candidate["task"] == TASK and candidate["execution"]["started_at"]:
            candidate_plan = read(path.parent / "inputs/plan.json")
            if candidate_plan["pilot_id"] == plan["pilot_id"]:
                discovered.add(candidate["run_id"])
    if discovered != set(run_ids):
        return {"admitted": False, "reason": "Every started attempt must be reconciled; omitted or extra attempt"}
    spent = {"total": 0.0, "openai": 0.0, "anthropic": 0.0}
    seen = set()
    for position, run_id in enumerate(run_ids):
        bundle = safe(root, "results/runs/" + run_id)
        record = read(bundle / "run.json")
        core_check(root, record)
        sealed_slot = read(bundle / "inputs/pilot-slot.json")
        if sealed_slot != prior[position] or read(bundle / "inputs/plan.json") != plan:
            return {"admitted": False, "reason": "Prior attempt does not match the exact ordered frozen plan"}
        slot = sealed_slot["slot_id"]
        if slot in seen or slot == next_slot["slot_id"]:
            return {"admitted": False, "reason": "No duplicate slots or implicit retries"}
        seen.add(slot)
        if record["status"] not in ("completed", "aborted"):
            return {"admitted": False, "reason": "Previous attempt is not terminal"}
        accounting = read(bundle / "trace/accounting.json")
        if accounting["cost_status"] != "settled" or record["loop"]["cost_usd"] is None:
            return {"admitted": False, "reason": "Previous attributable billing is unknown or unsettled"}
        if accounting["qualification"] != "qualified":
            return {"admitted": False, "reason": "Previous attempt is failed or inconclusive"}
        cost = record["loop"]["cost_usd"]
        if cost > record["loop"]["budget_usd"]:
            return {"admitted": False, "reason": "Attempt target exceeded"}
        spent["total"] += cost
        spent[record["model"]["provider"]] += cost
    budget = plan["budget_proposal"]
    target = budget["per_attempt_target"]
    admitted = (budget["total_target"] - spent["total"] >= target and
                budget["per_provider_target"] - spent[next_slot["provider"]] >= target)
    return {"admitted": admitted, "reason": "Accounting allocation available; separate authorization still required" if admitted else "Insufficient allocation", "spent": spent}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    for name in ("root", "slot", "run-id", "package", "runtime-lock", "package-lock", "plan"):
        prep.add_argument("--" + name, required=True)
    check = sub.add_parser("check")
    check.add_argument("--root", required=True)
    check.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        plan = read(args.plan)
        slot = next(slot for slot in plan["slots"] if slot["slot_id"] == args.slot)
        print(prepare(args.root, args.run_id, slot, args.package, args.runtime_lock, args.package_lock, args.plan))
    else:
        record = read(safe(args.root, "results/runs/" + args.run_id + "/run.json"))
        core_check(args.root, record)
        print(json.dumps({"run_id": args.run_id, "status": record["status"], "valid": True}))


if __name__ == "__main__":
    main()
