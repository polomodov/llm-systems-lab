"""Synthetic evidence fixtures only: no provider requests and no real run records."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import accounting as a


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = a.read(a.HERE / "plan.json")
        self.slot = self.plan["slots"][0]
        self.run_id = "2026-11-06-fixture-hn-o01"
        catalog = self.root / "experiments/common/harbor-native-pilot/task"
        catalog.mkdir(parents=True)
        for filename in ("registration.json", "contract.md", "agent-spec.md"):
            shutil.copy2(a.HERE / "task" / filename, catalog / filename)
        profile = self.root / "experiments" / self.slot["harness"]
        profile.mkdir(parents=True)
        (profile / "README.md").write_text("Fixture profile, not an execution result.\n")
        self.package = self.root / "package"
        (self.package / "tests").mkdir(parents=True)
        (self.package / "task.toml").write_text('version = "1.0"\n')
        (self.package / "instruction.md").write_text("Fixture only.\n")
        (self.package / "tests/evaluate.py").write_text("# Fixture verifier only.\n")
        self.image_id = "sha256:" + "a" * 64
        self.runtime = self.root / "runtime.json"
        a.write(self.runtime, {"images": {self.slot["harness"]: {"image_id": self.image_id, "version": self.slot["version"]}}, "verifier": {"image_id": "sha256:" + "b" * 64}})
        self.package_lock = self.root / "packages.json"
        a.write(self.package_lock, {"runtime_lock_sha256": a.digest(self.runtime), "source_sha256": {}, "packages": [{"slot_id": self.slot["slot_id"],
            "mode": "prepared", "image_id": self.image_id, "verifier_image_id": "sha256:" + "b" * 64,
            "task_digest": "sha256:" + a.hashlib.sha256("".join(f"{row['path']}\0{row['sha256']}\n" for row in a.inventory(self.package)).encode()).hexdigest(),
            "file_sha256": {row["path"]: row["sha256"] for row in a.inventory(self.package)},
            "harbor_file_sha256": {row["path"]: row["sha256"] for row in a.inventory(self.package)}}]})
        self.plan_path = self.root / "plan.json"
        a.write(self.plan_path, self.plan)

    def prepare(self):
        return a.prepare(self.root, self.run_id, self.slot, self.package, self.runtime, self.package_lock, self.plan_path)

    def start(self):
        bundle = self.prepare()
        a.mark_started(self.root, self.run_id, {"image_id": self.image_id, "observed_version": self.slot["version"],
            "command": ["fixture-only-no-execution"], "cwd": "/app", "started_at": "2026-11-06T12:00:00Z"})
        return bundle

    def evidence(self, *, model=True, settled=True):
        evidence = self.root / "evidence"
        evidence.mkdir()
        native = {"fixture": True, "model": self.slot["wire_model_id"] if model is True else model,
                  "tokens_in": 13, "tokens_out": 5, "turns": 1, "wall_clock_s": 1.0, "compactions": 0, "subagents": 0, "asked": 0, "tool_operations": 1, "estimated_cost": 0}
        a.write(evidence / "native.json", native)
        a.write(evidence / "artifact.json", {"fixture": True})
        a.write(evidence / "verifier.json", {"result": "pass", "check_output": "fixture verifier pass",
            "artifact_file": "artifact.json", "artifact_sha256": a.digest(evidence / "artifact.json"),
            "verifier_sha256": a.digest(self.package / "tests/evaluate.py")})
        a.write(evidence / "boundary.json", {"passed": True, "cleanup_complete": True})
        a.write(evidence / "billing.json", {"status": "settled" if settled else "settling", "run_id": self.run_id, "cost_usd": 0.01})
        a.write(evidence / "atif.json", {"schema_version": "ATIF-v1.7", "session_id": self.run_id,
            "agent": {"name": self.slot["harness"], "version": self.slot["version"], "model_name": self.slot["wire_model_id"]},
            "steps": [{"step_id": 1, "source": "agent", "message": "Synthetic fixture"}],
            "final_metrics": {"total_prompt_tokens": 0, "total_completion_tokens": 0, "total_cost_usd": 0}})
        ref = lambda file, pointer, kind: {"file": file, "pointer": pointer, "kind": kind}
        observation = {"native_log": "native.json", "atif": "atif.json", "terminal_native_trace": True,
            "identity": ref("native.json", "/model", "native_response"),
            "metrics": {key: ref("native.json", "/" + key, "native_usage") for key in ("tokens_in", "tokens_out", "turns", "wall_clock_s", "compactions", "subagents")},
            "tool_operations": ref("native.json", "/tool_operations", "native_usage"),
            "billing": ref("billing.json", "", "provider_billing"),
            "verifier": ref("verifier.json", "", "independent_verifier"),
            "boundary": ref("boundary.json", "", "coordinator_observation"),
            "execution": {"finished_at": "2026-11-06T12:00:01Z", "exit_code": 0, "signal": None, "timed_out": False}}
        observation["metrics"]["permissions.asked"] = ref("native.json", "/asked", "native_usage")
        if model is None:
            observation.pop("identity")
        return evidence, observation

    def test_prepared_is_valid_and_unexecuted_and_no_overwrite(self):
        bundle = self.prepare()
        before = (bundle / "run.json").read_bytes()
        record = a.read(bundle / "run.json")
        self.assertEqual(record["status"], "prepared")
        self.assertIsNone(record["execution"]["started_at"])
        self.assertIsNone(record["loop"]["cost_usd"])
        self.assertEqual((bundle / "trace/.gitkeep").read_bytes(), b"")
        a.core_check(self.root, record)
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((bundle / "run.json").read_bytes(), before)

    def test_completed_fixture_binds_raw_evidence_and_exact_measurements(self):
        bundle = self.start()
        record = a.finish(self.root, self.run_id, *self.evidence())
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["loop"]["tokens_in"], 13)
        self.assertEqual(record["loop"]["cost_usd"], 0.01)
        self.assertEqual(a.read(bundle / "trace/accounting.json")["qualification"], "qualified")
        a.core_check(self.root, record)
        with self.assertRaisesRegex(ValueError, "nonterminal"):
            a.finish(self.root, self.run_id, self.root / "evidence", {})
        (bundle / "trace/evidence/native.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Harbor evidence"):
            a.core_check(self.root, record)

    def test_unknown_usage_and_identity_stay_null_despite_atif_zero(self):
        bundle = self.start()
        evidence, observation = self.evidence(model=None, settled=False)
        observation["metrics"] = {}
        observation.pop("billing")
        record = a.finish(self.root, self.run_id, evidence, observation)
        self.assertEqual(record["verdict"]["result"], "pass")
        self.assertIsNone(record["model"]["observed_id"])
        for key in ("tokens_in", "tokens_out", "cost_usd"):
            self.assertIsNone(record["loop"][key])
            self.assertIn("loop." + key, record["metrics_unavailable"])
        self.assertEqual(a.read(bundle / "trace/accounting.json")["qualification"], "inconclusive")
        gate = a.admission(self.root, [self.run_id], self.plan["slots"][1], self.plan)
        self.assertFalse(gate["admitted"])
        self.assertIn("billing", gate["reason"])

    def test_unsettled_billing_is_not_zero_and_blocks_admission(self):
        self.start()
        record = a.finish(self.root, self.run_id, *self.evidence(settled=False))
        self.assertIsNone(record["loop"]["cost_usd"])
        self.assertFalse(a.admission(self.root, [self.run_id], self.plan["slots"][1], self.plan)["admitted"])

    def test_model_mismatch_aborts_and_retains_actual_spend(self):
        self.start()
        record = a.finish(self.root, self.run_id, *self.evidence(model="unexpected-model"))
        self.assertEqual(record["status"], "aborted")
        self.assertEqual(record["loop"]["stop_reason"], "observed-model-mismatch")
        self.assertEqual(record["loop"]["cost_usd"], 0.01)
        self.assertFalse(a.admission(self.root, [self.run_id], self.plan["slots"][1], self.plan)["admitted"])
        a.core_check(self.root, record)

    def test_native_cost_estimate_cannot_be_billing(self):
        self.start()
        evidence, observation = self.evidence()
        observation["billing"] = {"file": "native.json", "pointer": "/estimated_cost", "kind": "native_estimate"}
        with self.assertRaisesRegex(ValueError, "provenance"):
            a.finish(self.root, self.run_id, evidence, observation)
        self.assertFalse((self.root / "results/runs" / self.run_id / "trace/evidence").exists())

    def test_sealed_input_and_runtime_tampering_fail_closed(self):
        bundle = self.prepare()
        record = a.read(bundle / "run.json")
        (bundle / "inputs/task.md").write_text("Up to 8 turns or $100")
        with self.assertRaises(ValueError):
            a.core_check(self.root, record)

    def test_package_lock_mismatch_rejected_before_record_creation(self):
        (self.package / "instruction.md").write_text("Mutated")
        with self.assertRaisesRegex(ValueError, "frozen slot lock"):
            self.prepare()
        self.assertFalse((self.root / "results/runs" / self.run_id).exists())

    def test_catalog_mapping_is_exact_and_cannot_register_arbitrary_tasks(self):
        bundle = self.prepare()
        record = a.read(bundle / "run.json")
        for field, value in (("agent", "unregistered"), ("task", "unregistered")):
            changed = copy.deepcopy(record)
            changed[field] = value
            with self.assertRaises(ValueError):
                a.core_check(self.root, changed)
        changed = copy.deepcopy(record)
        changed["harness"]["mode"] = "sdk"
        with self.assertRaises(ValueError):
            a.core_check(self.root, changed)

    def test_missing_turns_with_settled_billing_stays_inconclusive(self):
        bundle = self.start()
        evidence, observation = self.evidence()
        observation["metrics"].pop("turns")
        a.finish(self.root, self.run_id, evidence, observation)
        self.assertEqual(a.read(bundle / "trace/accounting.json")["qualification"], "inconclusive")

    def test_nonzero_native_exit_aborts_even_with_passing_verifier(self):
        self.start()
        evidence, observation = self.evidence()
        observation["execution"]["exit_code"] = 1
        record = a.finish(self.root, self.run_id, evidence, observation)
        self.assertEqual(record["status"], "aborted")
        self.assertEqual(record["loop"]["stop_reason"], "native-process-failure")

    def test_admission_rejects_omitted_prefix_unknown_slot_and_inflight_attempt(self):
        self.start()
        self.assertFalse(a.admission(self.root, [], self.plan["slots"][1], self.plan)["admitted"])
        changed = copy.deepcopy(self.plan["slots"][0])
        changed["wire_model_id"] = "different-model"
        self.assertFalse(a.admission(self.root, [], changed, self.plan)["admitted"])
        self.assertFalse(a.admission(self.root, [], self.plan["slots"][0], self.plan)["admitted"])

    def test_invalid_declared_atif_is_inconclusive(self):
        bundle = self.start()
        evidence, observation = self.evidence()
        atif = a.read(evidence / "atif.json")
        atif["schema_version"] = "ATIF-v999"
        a.write(evidence / "atif.json", atif, exclusive=False)
        a.finish(self.root, self.run_id, evidence, observation)
        self.assertFalse(a.read(bundle / "trace/accounting.json")["atif_valid"])
        self.assertEqual(a.read(bundle / "trace/accounting.json")["qualification"], "inconclusive")

    def test_pilot_manifest_cannot_be_omitted_even_for_planned_record(self):
        bundle = self.prepare()
        record = a.read(bundle / "run.json")
        record["status"] = "planned"
        record["inputs"]["manifest_path"] = None
        with self.assertRaisesRegex(ValueError, "sealed preparation"):
            a.core_check(self.root, record)

    def test_symlinks_and_path_escape_are_rejected(self):
        self.start()
        evidence, observation = self.evidence()
        observation["identity"]["file"] = "../plan.json"
        with self.assertRaisesRegex(ValueError, "inside"):
            a.finish(self.root, self.run_id, evidence, observation)
        (evidence / "link").symlink_to(self.plan_path)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            a.inventory(evidence)

    def test_accounting_edit_and_wrong_verifier_artifact_are_detected(self):
        bundle = self.start()
        evidence, observation = self.evidence()
        verifier = a.read(evidence / "verifier.json")
        verifier["artifact_sha256"] = "0" * 64
        a.write(evidence / "verifier.json", verifier, exclusive=False)
        with self.assertRaisesRegex(ValueError, "binding"):
            a.finish(self.root, self.run_id, evidence, observation)
        verifier["artifact_sha256"] = a.digest(evidence / "artifact.json")
        a.write(evidence / "verifier.json", verifier, exclusive=False)
        record = a.finish(self.root, self.run_id, evidence, observation)
        (bundle / "trace/accounting.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "accounting seal"):
            a.core_check(self.root, record)


if __name__ == "__main__":
    unittest.main()
