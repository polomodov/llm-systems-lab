"""Ensure inspecting a historical export cannot launch or mutate a job."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from view import make_app


class ReadOnlyViewerTests(unittest.TestCase):
    def test_local_reads_remain_available_and_capabilities_are_disabled(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(make_app(directory)) as client:
            self.assertEqual(client.get("/api/health").json(), {"status": "ok"})
            config = client.get("/api/config").json()
            self.assertEqual(config["folder"], str(Path(directory).resolve()))
            self.assertFalse(any(config["capabilities"].values()))
            self.assertEqual(client.get("/api/jobs").status_code, 200)
            self.assertEqual(client.get("/api/auth/status").json(), {"authenticated": False})

    def test_launch_summary_upload_auth_and_delete_are_unreachable(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(make_app(directory)) as client:
            with patch("subprocess.Popen", side_effect=AssertionError("Must not spawn a process")):
                for method, path in [
                    ("POST", "/api/run"),
                    ("POST", "/api/jobs/example/summarize"),
                    ("POST", "/api/jobs/example/trials/trial/summarize"),
                    ("POST", "/api/jobs/example/upload"),
                    ("POST", "/api/source/jobs"),
                    ("DELETE", "/api/jobs/example"),
                ]:
                    with self.subTest(path=path):
                        self.assertEqual(client.request(method, path, json={}).status_code, 405)
                for path in ["/api/pricing?model=gpt-5", "/api/auth/organizations",
                             "/api/auth/login-url", "/api/run/options", "/api/source/jobs",
                             "/api/jobs/example/upload"]:
                    with self.subTest(path=path):
                        self.assertEqual(client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
