"""Offline mapping/integrity checks; fixtures contain no model calls."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("export_run", Path(__file__).with_name("export-run.py"))
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def fixture_record():
    return {
        "run_id": "2026-10-15-pi-fixture", "status": "completed",
        "harness": {"name": "pi", "version": "0.73.1", "mode": "sdk"},
        "task": "T002-fixture", "model": {"id": "requested-id", "provider": "local",
            "observed_id": "observed-id", "identity_evidence": "fixture response evidence"},
        "loop": {"turns": 2, "stop_reason": "stop", "cost_usd": None,
                 "tokens_in": 100, "tokens_out": 20, "wall_clock_s": 5},
        "metrics_unavailable": {"loop.cost_usd": "local energy cost unavailable"},
        "verdict": {"result": "pass", "check_output": "historical synthetic verdict"},
        "execution": {"started_at": "2026-10-15T00:00:00Z", "finished_at": "2026-10-15T00:00:06Z"},
        "evaluation": {"evaluated_at": "2026-10-15T00:01:00Z"},
    }


def fixture_events():
    assistant = {"role": "assistant", "model": "sdk-configured-id", "timestamp": 1792022401000,
                 "usage": {"input": 6, "cacheRead": 2, "cacheWrite": 3, "output": 4,
                           "cost": {"total": 0}}, "stopReason": "toolUse",
                 "content": [{"type": "thinking", "thinking": "Проверяю"},
                             {"type": "toolCall", "id": "call-1", "name": "bash",
                              "arguments": {"command": "printf 'literal $(do-not-run)'"}}]}
    return [
        {"type": "agent_start"},
        {"type": "message_end", "message": {"role": "user", "content": [{"type": "text", "text": "Исправь тест"}]}},
        {"type": "message_update", "message": assistant},
        {"type": "message_end", "message": assistant},
        {"type": "tool_execution_end", "toolCallId": "call-1", "result": {"content": "duplicate"}},
        {"type": "message_end", "message": {"role": "toolResult", "toolCallId": "call-1", "toolName": "bash",
             "isError": False, "content": [{"type": "text", "text": "готово"}]}},
        {"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "Готово"}],
                                             "stopReason": "stop"}},
        {"type": "lab_pi_result", "turns": 2, "stopReason": "stop", "sessionId": "fixture-session"},
    ]


def trace(events=None):
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in (events or fixture_events()))


def write_source(parent):
    record = fixture_record()
    root = parent / record["run_id"]
    files = {"trace/stdout.jsonl": trace().encode(), "inputs/manifest.json": b'{}\n',
             "trace/final-workspace.json": b'[]\n', "artifacts/report.md": "Исходный отчёт\n".encode()}
    artifact = files["artifacts/report.md"]
    files["trace/artifacts.json"] = exporter.json_bytes([
        {"path": "report.md", "bytes": len(artifact), "sha256": exporter.digest(artifact)}])
    evaluation = {"run_id": record["run_id"], "result": "pass",
                  "artifacts_sha256": exporter.digest(files["trace/artifacts.json"]),
                  "workspace_sha256": exporter.digest(files["trace/final-workspace.json"])}
    files["trace/evaluation.json"] = exporter.json_bytes(evaluation)
    record["inputs"] = {"manifest_path": "inputs/manifest.json",
                        "manifest_sha256": exporter.digest(files["inputs/manifest.json"])}
    record["evaluation"].update({"evidence_path": "trace/evaluation.json",
                                "evidence_sha256": exporter.digest(files["trace/evaluation.json"])})
    files["run.json"] = exporter.json_bytes(record)
    for path, data in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root, files


class MappingTests(unittest.TestCase):
    def test_terminal_messages_and_tool_results_are_mapped_once(self):
        mapped = exporter.map_pi_trace(fixture_record(), trace())
        self.assertEqual(len(mapped["steps"]), 3)
        self.assertEqual(mapped["steps"][0]["message"], "Исправь тест")
        step = mapped["steps"][1]
        self.assertEqual(step["reasoning_content"], "Проверяю")
        self.assertEqual(step["tool_calls"][0]["arguments"]["command"], "printf 'literal $(do-not-run)'")
        self.assertEqual(step["observation"]["results"][0]["content"], "готово")
        self.assertEqual(len(step["observation"]["results"]), 1)

    def test_authoritative_totals_unknowns_and_identity_are_not_reinvented(self):
        mapped = exporter.map_pi_trace(fixture_record(), trace())
        final = mapped["final_metrics"]
        self.assertEqual((final["total_prompt_tokens"], final["total_completion_tokens"]), (100, 20))
        self.assertIsNone(final["total_cost_usd"])
        self.assertIsNone(final["total_cached_tokens"])
        self.assertEqual(final["total_steps"], 3)
        self.assertEqual(final["extra"]["lab_turns"], 2)
        self.assertIn("loop.cost_usd", final["extra"]["metrics_unavailable"])
        self.assertEqual(mapped["steps"][1]["metrics"]["prompt_tokens"], 11)
        self.assertIsNone(mapped["steps"][1]["metrics"]["cost_usd"])
        self.assertIsNone(mapped["steps"][2]["metrics"]["prompt_tokens"])
        self.assertEqual(mapped["agent"]["model_name"], "local/requested-id")
        self.assertEqual(mapped["agent"]["extra"]["observed_model_id"], "observed-id")

    def test_malformed_unsupported_and_incomplete_traces_are_rejected(self):
        bad_traces = [trace() + "\n{", "null", trace() + '\n{"type":"agent_start"}',
                      trace(fixture_events()[:-1]), trace([{"type": "compaction_end"}])]
        orphan = fixture_events()
        orphan[5]["message"]["toolCallId"] = "missing"
        bad_traces.append(trace(orphan))
        duplicate = fixture_events()
        duplicate.insert(6, copy.deepcopy(duplicate[5]))
        bad_traces.append(trace(duplicate))
        unresolved = fixture_events()
        del unresolved[5]
        bad_traces.append(trace(unresolved))
        invalid_usage = fixture_events()
        invalid_usage[3]["message"]["usage"]["input"] = -1
        bad_traces.append(trace(invalid_usage))
        for bad in bad_traces:
            with self.subTest(trace=bad[:30]), self.assertRaises(ValueError):
                exporter.map_pi_trace(fixture_record(), bad)
        for change in [{"harness": {"name": "codex"}}, {"status": "aborted"},
                       {"verdict": {"result": "partial"}}]:
            with self.assertRaises(ValueError):
                exporter.map_pi_trace({**fixture_record(), **change}, trace())

    def test_envelopes_validate_and_scanner_loads_without_executing(self):
        from harbor.models.trajectories import Trajectory
        from harbor.viewer.scanner import JobScanner
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source, original = write_source(parent)
            jobs = parent / "jobs"
            target = exporter.export_run(source, jobs)
            scanner = JobScanner(jobs)
            self.assertEqual(scanner.list_jobs(), [target.name])
            self.assertIsNotNone(scanner.get_job_config(target.name))
            result = scanner.get_trial_result(target.name, source.name)
            self.assertIsNotNone(result)
            self.assertEqual(result.verifier_result.rewards, {"reward": 1})
            self.assertIsNone(result.agent_result.cost_usd)
            self.assertEqual(result.agent_result.metadata["original_loop"]["wall_clock_s"], 5)
            self.assertTrue(result.config.verifier.disable)
            self.assertIn("__derived_read_only__", str(result.config.task.path))
            self.assertIsNone(scanner.get_job_result(target.name).stats.cost_usd)
            atif = target / source.name / "agent/trajectory.json"
            Trajectory.model_validate_json(atif.read_text())
            provenance = json.loads((target / source.name / "provenance.json").read_text())
            self.assertFalse(provenance["rerun"])
            for path, data in original.items():
                self.assertEqual((source / path).read_bytes(), data)
                self.assertEqual((target / source.name / "source-evidence" / path).read_bytes(), data)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                exporter.export_run(source, jobs)

    def test_tampered_artifacts_and_unsafe_paths_fail_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source, _ = write_source(parent)
            (source / "artifacts/report.md").write_text("changed")
            jobs = parent / "jobs"
            with self.assertRaisesRegex(ValueError, "Artifact integrity"):
                exporter.export_run(source, jobs)
            self.assertFalse(jobs.exists())
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                exporter.safe_source(source, "../outside")
            with self.assertRaisesRegex(ValueError, "overlap"):
                exporter.export_run(source, source / "export")


if __name__ == "__main__":
    unittest.main()
