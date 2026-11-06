#!/usr/bin/env python3
"""Data-only export of completed Pi SDK evidence for the pinned Harbor viewer.

This never runs an agent, task, verifier, or command from the source trace.
The generated Harbor configs describe a historical import, not a runnable task.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
from uuid import NAMESPACE_URL, uuid5

HARBOR_COMMIT = "ff2a1ef48070a8df374669138e4d4db79b77f013"
NOTICE = (
    "Derived historical import; no agent execution or verification was repeated. "
    "Original language and recorded verdict are preserved. ATIF steps count user/agent "
    "messages, not lab turns. Aggregate metrics come from run.json; SDK placeholder "
    "prices are not costs. Timestamp intervals and recorded wall_clock_s have different "
    "boundaries; the latter remains in metadata. Model names are requested configuration; "
    "observed identity and its evidence are recorded separately."
)
IGNORED_EVENTS = {
    "agent_start", "agent_end", "turn_start", "turn_end", "message_start",
    "message_update", "tool_execution_start", "tool_execution_update", "tool_execution_end",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def read_json(data):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    return json.loads(data, parse_constant=reject_constant)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def timestamp(value):
    if value is None:
        return None
    require(count(value), "Pi timestamps must be nonnegative milliseconds")
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def content_parts(content, allowed):
    require(isinstance(content, list), "Expected Pi content array")
    for part in content:
        require(isinstance(part, dict) and part.get("type") in allowed,
                "Unsupported Pi content type; refusing a lossy export")
    return content


def text_content(content):
    parts = content_parts(content, {"text"})
    require(all(isinstance(part.get("text"), str) for part in parts), "Invalid text content")
    return "".join(part["text"] for part in parts)


def validate_record(record):
    require(record.get("harness") == {"name": "pi", "version": "0.73.1", "mode": "sdk"},
            "Only Pi SDK 0.73.1 is qualified by this exporter")
    require(record.get("status") == "completed", "Only completed evidence is supported")
    require(record.get("verdict", {}).get("result") in {"pass", "fail"},
            "Only binary historical verdicts have a reward mapping")
    loop = record["loop"]
    for field in ("turns", "tokens_in", "tokens_out", "wall_clock_s"):
        require(loop.get(field) is None or count(loop[field]), f"Invalid recorded {field}")
        if loop.get(field) is None:
            require(bool(record.get("metrics_unavailable", {}).get("loop." + field)),
                    f"Unknown {field} needs a recorded explanation")
    cost = loop.get("cost_usd")
    require(cost is None or (type(cost) in (int, float) and math.isfinite(cost) and cost >= 0),
            "Invalid recorded cost")
    if cost is None:
        require(bool(record.get("metrics_unavailable", {}).get("loop.cost_usd")),
                "Unknown cost needs a recorded explanation")


def append_tool_result(message, line_number, calls, observed_results):
    call_id = message.get("toolCallId")
    require(isinstance(call_id, str) and call_id in calls, "Orphan tool result")
    require(call_id not in observed_results, "Duplicate tool result")
    step, name = calls[call_id]
    require(message.get("toolName") == name, "Tool result name differs from call")
    step.setdefault("observation", {"results": []})["results"].append({
        "source_call_id": call_id,
        "content": text_content(message.get("content")),
        "extra": {"is_error": message.get("isError"), "source_line": line_number,
                  "timestamp": timestamp(message.get("timestamp"))},
    })
    observed_results.add(call_id)


def map_tool_call(part, step, calls):
    call_id, name = part.get("id"), part.get("name")
    require(isinstance(call_id, str) and call_id and call_id not in calls,
            "Missing or duplicate tool-call ID")
    require(isinstance(name, str) and name and isinstance(part.get("arguments"), dict),
            "Malformed tool call")
    calls[call_id] = (step, name)
    return {"tool_call_id": call_id, "function_name": name, "arguments": part["arguments"]}


def map_message_usage(usage):
    require(isinstance(usage, dict), "Invalid usage")
    require(all(usage.get(key) is None or count(usage[key])
                for key in ("input", "cacheRead", "cacheWrite", "output")),
            "Invalid per-message token count")
    inputs = [usage.get(key) for key in ("input", "cacheRead", "cacheWrite")]
    return {
        "prompt_tokens": sum(inputs) if all(count(v) for v in inputs) else None,
        "completion_tokens": usage.get("output") if count(usage.get("output")) else None,
        "cached_tokens": usage.get("cacheRead") if count(usage.get("cacheRead")) else None,
        "cost_usd": None,
        "extra": {"source": "Pi SDK message usage; aggregate run metrics are authoritative",
                  "unknown_token_policy": "Null means the message lacks a complete nonnegative token count",
                  "cost_unavailable": "Per-call cost is not imported; preserve authoritative aggregate only"},
    }


def map_assistant_content(message, step, calls):
    parts = content_parts(message.get("content"), {"text", "thinking", "toolCall"})
    fragments, tool_calls = {"text": [], "thinking": []}, []
    for part in parts:
        key = part["type"]
        if key == "toolCall":
            tool_calls.append(map_tool_call(part, step, calls))
        else:
            require(isinstance(part.get(key), str), f"Invalid {key} content")
            fragments[key].append(part[key])
    step["message"] = "".join(fragments["text"])
    step["reasoning_content"] = "".join(fragments["thinking"]) if fragments["thinking"] else None
    step["tool_calls"] = tool_calls or None
    step["llm_call_count"] = 1
    step["extra"].update({"configured_model_in_sdk_message": message.get("model"),
                          "stop_reason": message.get("stopReason")})
    step["metrics"] = map_message_usage(message.get("usage", {}))


def append_message(message, line_number, steps, calls, observed_results):
    require(isinstance(message, dict), "message_end lacks a message")
    role = message.get("role")
    if role == "toolResult":
        append_tool_result(message, line_number, calls, observed_results)
        return 0
    require(role in {"user", "assistant"}, f"Unsupported message role: {role}")
    require(set(calls) == observed_results, "New message before all tool results")
    step = {"step_id": len(steps) + 1, "source": "agent" if role == "assistant" else "user",
            "timestamp": timestamp(message.get("timestamp")), "message": "",
            "extra": {"source_event": "message_end", "source_line": line_number}}
    if role == "user":
        step["message"] = text_content(message.get("content"))
    else:
        map_assistant_content(message, step, calls)
    steps.append(step)
    return int(role == "assistant")


def map_terminal_messages(record, trace):
    """Map only terminal messages; incremental and duplicate tool events stay raw."""
    steps, calls, observed_results, finals = [], {}, set(), []
    assistant_count = 0
    for line_number, line in enumerate(trace.splitlines(), 1):
        if not line.strip():
            continue
        event = read_json(line)
        require(isinstance(event, dict), f"Trace line {line_number} is not an object")
        event_type = event.get("type")
        require(not finals, "Events after final lab_pi_result are unsupported")
        if event_type in IGNORED_EVENTS:
            continue
        if event_type == "lab_pi_result":
            finals.append(event)
            continue
        require(event_type == "message_end", f"Unsupported trace event: {event_type}")
        assistant_count += append_message(event.get("message"), line_number, steps, calls, observed_results)
    require(len(finals) == 1 and assistant_count > 0 and steps and steps[0]["source"] == "user",
            "Trace requires user input, assistant messages and one final result")
    require(set(calls) == observed_results, "Trace ended with unresolved tool calls")
    require(count(finals[0].get("turns")) and finals[0]["turns"] == assistant_count == record["loop"]["turns"],
            "Recorded/final/observed turn counts differ")
    require(finals[0].get("stopReason") == record["loop"]["stop_reason"], "Stop reasons differ")
    return steps, finals[0]


def map_pi_trace(record, trace):
    validate_record(record)
    steps, final = map_terminal_messages(record, trace)
    model = record["model"]
    requested = f'{model["provider"]}/{model["id"]}'
    loop = record["loop"]
    metadata = {
        "derived_import": True, "source_run_id": record["run_id"], "rerun": False,
        "harbor_commit": HARBOR_COMMIT, "original_model_record": model,
        "original_loop": loop, "metrics_unavailable": record.get("metrics_unavailable", {}),
        "cache_total_unavailable": "run.json does not record an authoritative aggregate cache count",
        "source_notes": record.get("notes", ""), "notice": NOTICE,
    }
    return {
        "schema_version": "ATIF-v1.8", "session_id": final.get("sessionId"),
        "trajectory_id": "derived-" + record["run_id"],
        "agent": {"name": "pi", "version": "0.73.1", "model_name": requested,
                  "extra": {"requested_model_id": model["id"], "observed_model_id": model.get("observed_id"),
                            "identity_evidence": model.get("identity_evidence"), "mode": "sdk"}},
        "steps": steps, "notes": NOTICE, "extra": metadata,
        "final_metrics": {"total_prompt_tokens": loop["tokens_in"],
                          "total_completion_tokens": loop["tokens_out"], "total_cached_tokens": None,
                          "total_cost_usd": loop["cost_usd"], "total_steps": len(steps),
                          "extra": {"lab_turns": loop["turns"], "wall_clock_s": loop["wall_clock_s"],
                                    "metrics_unavailable": metadata["metrics_unavailable"]}},
    }


def safe_source(run_dir, relative):
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts, "Unsafe evidence path")
    target = run_dir / path
    for parent in [target, *target.parents]:
        require(not parent.is_symlink(), "Source symlinks are unsupported")
        if parent == run_dir:
            break
    require(target.is_file(), f"Missing source evidence: {relative}")
    return target.read_bytes()


def load_evidence(run_dir):
    files = {}
    def load(relative):
        files[relative] = safe_source(run_dir, relative)
        return files[relative]
    record = read_json(load("run.json"))
    require(isinstance(record, dict) and re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+", record.get("run_id", "")),
            "Invalid run identity")
    require(record["run_id"] == run_dir.name, "Source directory and run_id differ")
    trace = load("trace/stdout.jsonl").decode("utf8")
    manifest = load(record["inputs"]["manifest_path"])
    require(digest(manifest) == record["inputs"]["manifest_sha256"], "Input manifest hash mismatch")
    evaluation_data = load(record["evaluation"]["evidence_path"])
    require(digest(evaluation_data) == record["evaluation"]["evidence_sha256"], "Evaluation hash mismatch")
    evaluation = read_json(evaluation_data)
    require(evaluation.get("run_id") == record["run_id"] and evaluation.get("result") == record["verdict"]["result"],
            "Evaluation and run verdict differ")
    for relative, field in [("trace/artifacts.json", "artifacts_sha256"),
                            ("trace/final-workspace.json", "workspace_sha256")]:
        data = load(relative)
        require(digest(data) == evaluation[field], f"Evaluation-bound {relative} hash mismatch")
    for artifact in read_json(files["trace/artifacts.json"]):
        data = load("artifacts/" + artifact["path"])
        require(digest(data) == artifact["sha256"] and len(data) == artifact["bytes"], "Artifact integrity mismatch")
    privacy = run_dir / "privacy-redaction.json"
    if privacy.exists():
        load("privacy-redaction.json")
    return record, trace, files


def build_envelopes(record, trajectory, target):
    # Imports validate data only. No Job/Trial runner is constructed.
    from harbor.models.job.config import JobConfig
    from harbor.models.job.result import JobResult, JobStats
    from harbor.models.trial.config import TrialConfig
    from harbor.models.trial.result import TrialResult
    from harbor.models.trajectories import Trajectory

    Trajectory.model_validate(trajectory)
    run_id = record["run_id"]
    job_id = str(uuid5(NAMESPACE_URL, "llm-systems-lab:derived-job:" + run_id))
    trial_id = str(uuid5(NAMESPACE_URL, "llm-systems-lab:derived-trial:" + run_id))
    task = {"path": "__derived_read_only__/" + record["task"], "source": "historical-derived-no-rerun"}
    agent = {"name": "pi", "model_name": trajectory["agent"]["model_name"],
             "kwargs": {"version": record["harness"]["version"]}}
    config = TrialConfig.model_validate({"task": task, "trial_name": run_id, "trials_dir": str(target),
                                        "agent": agent, "verifier": {"disable": True}, "job_id": job_id})
    loop, execution = record["loop"], record["execution"]
    result = TrialResult.model_validate({
        "id": trial_id, "task_name": record["task"], "trial_name": run_id,
        "trial_uri": (target / run_id).as_uri(), "task_id": {"path": task["path"]},
        "source": task["source"], "task_checksum": record["inputs"]["manifest_sha256"],
        "config": config, "agent_info": {"name": "pi", "version": record["harness"]["version"],
            "model_info": {"name": record["model"]["id"], "provider": record["model"]["provider"]}},
        "agent_result": {"n_input_tokens": loop["tokens_in"], "n_output_tokens": loop["tokens_out"],
                         "n_cache_tokens": None, "cost_usd": loop["cost_usd"], "metadata": {
                             **trajectory["extra"], "historical_verdict": record["verdict"],
                             "task_checksum_kind": "lab input manifest SHA-256, not Harbor task checksum"}},
        "verifier_result": {"rewards": {"reward": 1 if record["verdict"]["result"] == "pass" else 0}},
        "started_at": execution["started_at"], "finished_at": record["evaluation"]["evaluated_at"],
        "agent_execution": {"started_at": execution["started_at"], "finished_at": execution["finished_at"]},
    })
    job_config = JobConfig.model_validate({"job_name": target.name, "jobs_dir": str(target.parent),
        "n_concurrent_trials": 1, "agents": [agent], "tasks": [task], "verifier": {"disable": True}})
    job_result = JobResult(id=job_id, started_at=result.started_at, finished_at=result.finished_at,
                          n_total_trials=1, stats=JobStats.from_trial_results([result]), trial_results=[result])
    dump = lambda value: value.model_dump(mode="json", exclude_none=False)
    return dump(job_config), dump(job_result), dump(config), dump(result)


def export_run(run_dir, jobs_dir):
    run_dir, jobs_dir = Path(run_dir).resolve(), Path(jobs_dir).resolve()
    require(not jobs_dir.is_relative_to(run_dir) and not run_dir.is_relative_to(jobs_dir),
            "Output and source evidence directories must not overlap")
    record, trace, files = load_evidence(run_dir)
    trajectory = map_pi_trace(record, trace)
    target = jobs_dir / ("derived-" + record["run_id"])
    require(not target.exists(), "Refusing to overwrite an existing export")
    envelopes = build_envelopes(record, trajectory, target)
    provenance = {"schema_version": 1, "kind": "derived-historical-export", "rerun": False,
                  "source_run_id": record["run_id"], "harbor_commit": HARBOR_COMMIT,
                  "created_at": datetime.now(timezone.utc).isoformat(), "notice": NOTICE,
                  "exporter_sha256": digest(Path(__file__).read_bytes()),
                  "files": [{"path": path, "bytes": len(data), "sha256": digest(data)}
                            for path, data in sorted(files.items())]}
    jobs_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".export-", dir=jobs_dir))
    try:
        trial = staging / record["run_id"]
        outputs = {"config.json": envelopes[0], "result.json": envelopes[1],
                   record["run_id"] + "/config.json": envelopes[2],
                   record["run_id"] + "/result.json": envelopes[3],
                   record["run_id"] + "/agent/trajectory.json": trajectory,
                   record["run_id"] + "/provenance.json": provenance}
        for path, value in outputs.items():
            dest = staging / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(json_bytes(value))
        for path, data in files.items():
            dest = trial / "source-evidence" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            require(safe_source(run_dir, path) == data, "Source changed during export")
        (trial / "README.md").write_text("# Historical import\n\n" + NOTICE + "\n", encoding="utf8")
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(export_run(args.run_dir, args.jobs_dir))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"Export refused: {error}\n")


if __name__ == "__main__":
    main()
