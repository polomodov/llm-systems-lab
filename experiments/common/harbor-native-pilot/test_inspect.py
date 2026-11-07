"""Exercise offline inspection failure paths without Docker or model calls."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("native_inspection", Path(__file__).with_name("inspect.py"))
inspection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspection)


class InspectionFailureTests(unittest.TestCase):
    def test_timeout_is_recorded_and_named_container_is_removed(self):
        timeout = subprocess.TimeoutExpired(["docker"], 30)
        removed = subprocess.CompletedProcess(["docker"], 0, "removed", "")
        with patch.object(inspection.subprocess, "run", side_effect=[timeout, removed]) as run:
            result = inspection.probe("sha256:fixture", "cli", ["--help"])
        invocation = run.call_args_list[0].args[0]
        container = invocation[invocation.index("--name") + 1]
        self.assertEqual(run.call_args_list[1].args[0][-3:], ["rm", "--force", container])
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["cleanup_confirmed"])
        self.assertTrue(inspection.failed_probes({"fixture": [result]}))

    def test_cli_or_cleanup_failure_blocks_success(self):
        probes = {"missing-image": [{"exit_code": 125, "cleanup_confirmed": True}],
                  "unfinished-cleanup": [{"exit_code": 0, "cleanup_confirmed": False}],
                  "success": [{"exit_code": 0, "cleanup_confirmed": True}]}
        self.assertEqual(inspection.failed_probes(probes),
                         [("missing-image", 125), ("unfinished-cleanup", 0)])


if __name__ == "__main__":
    unittest.main()
