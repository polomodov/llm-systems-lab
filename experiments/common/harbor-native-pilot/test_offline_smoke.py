"""Regression tests for native completion evidence and configuration identity."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("native_offline_smoke", Path(__file__).with_name("offline_smoke.py"))
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class CompletionEvidenceTests(unittest.TestCase):
    def test_mini_exit_zero_and_valid_artifact_cannot_mask_format_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            trace = logs / "mini-swe-agent.trajectory.json"
            trace.write_text(json.dumps({"info": {"exit_status": "RepeatedFormatError"}}))
            with self.assertRaisesRegex(ValueError, "did not submit"):
                SMOKE.terminal_event("mini-swe-agent", logs)
            trace.write_text(json.dumps({"info": {"exit_status": "Submitted"}}))
            self.assertEqual(SMOKE.terminal_event("mini-swe-agent", logs), "Submitted")

    def test_claude_result_requires_success_and_non_error(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            trace = logs / "claude-code.txt"
            for result in [
                {"type": "result", "subtype": "error_max_turns", "is_error": False},
                {"type": "result", "subtype": "success", "is_error": True},
                {"type": "assistant", "message": "partial answer"},
            ]:
                trace.write_text(json.dumps(result) + "\n")
                with self.assertRaisesRegex(ValueError, "did not terminate"):
                    SMOKE.terminal_event("claude-code", logs)

    def test_bookkeeping_does_not_change_config_identity_but_model_does(self):
        plan = {"slots": [{"slot_id": "example", "model_name": "original", "status": "planned", "run_id": None, "image_id": None}]}
        before = SMOKE.slot_configuration_sha256(plan)
        plan["slots"][0].update(status="prepared", run_id="fixture", image_id="sha256:example")
        self.assertEqual(SMOKE.slot_configuration_sha256(plan), before)
        plan["slots"][0]["model_name"] = "different"
        self.assertNotEqual(SMOKE.slot_configuration_sha256(plan), before)


if __name__ == "__main__":
    unittest.main()
