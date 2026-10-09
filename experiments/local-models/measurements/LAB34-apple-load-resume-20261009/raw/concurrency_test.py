#!/usr/bin/env python3
"""Offline LAB26 driver checks; uses loopback mock HTTP, never a model."""

import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

import concurrency_driver as driver


BODY = json.dumps({"model": "mock", "messages": [{"role": "user", "content": "public exercise"}],
                   "max_tokens": 16, "stream": False}).encode()
ANSWER = {"choices": [{"message": {"role": "assistant", "content": "public mock response"},
                        "finish_reason": "stop"}], "usage": {"prompt_tokens": 8, "completion_tokens": 4}}


@contextlib.contextmanager
def server(mode="ok"):
    state = {"active": 0, "peak": 0, "calls": 0}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            with lock:
                state["active"] += 1
                state["calls"] += 1
                state["peak"] = max(state["peak"], state["active"])
            try:
                self.rfile.read(int(self.headers["Content-Length"]))
                time.sleep(0.03)
                payload = json.loads(json.dumps(ANSWER))
                if mode == "missing-usage":
                    del payload["usage"]
                elif mode == "tools":
                    payload["choices"][0]["message"]["tool_calls"] = [{"id": "never-execute"}]
                elif mode in {"missing-finish", "tool-finish"}:
                    payload["choices"][0]["finish_reason"] = None if mode == "missing-finish" else "tool_calls"
                raw = json.dumps(payload).encode()
                status = 200
                if mode == "invalid-json":
                    raw = b"not-json"
                elif mode == "oversize":
                    raw = b"x" * (driver.MAX_RESPONSE + 100)
                elif mode == "error":
                    status, raw = 503, b'{"error":"mock unavailable"}'
                elif mode == "redirect":
                    status, raw = 302, b"redirect forbidden"
                elif mode == "slow-header":
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    self.wfile.flush()
                    for _ in range(20):
                        self.wfile.write(b"a")
                        self.wfile.flush()
                        time.sleep(0.04)
                    return
                self.send_response(status)
                if mode == "redirect":
                    self.send_header("Location", "/admin")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw) + (10 if mode == "short-body" else 0)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(raw)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with lock:
                    state["active"] -= 1

    service = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=service.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{service.server_port}/v1/chat/completions", state
    finally:
        service.shutdown()
        service.server_close()
        thread.join()


class ConcurrencyTests(unittest.TestCase):
    def probe(self, mode="ok", concurrency=1, requests=1, timeout=2):
        with tempfile.TemporaryDirectory() as directory, server(mode) as (url, state):
            out = Path(directory) / "new"
            summary = driver.run(url, BODY, concurrency, requests, timeout, out)
            self.assertEqual(len(list(out.glob("request-*.json"))), requests)
            self.assertEqual(len(list(out.glob("request-*.response.bin"))), requests)
            self.assertTrue((out / "summary.json").is_file())
            config = json.loads((out / "config.json").read_text())
            self.assertEqual(config["request_sha256"], hashlib.sha256((out / "request.json").read_bytes()).hexdigest())
            return summary, state

    def test_concurrency_and_usage(self):
        summary, state = self.probe(concurrency=4, requests=8)
        self.assertEqual(summary["successful"], 8)
        self.assertEqual(summary["completion_tokens_successful"], 32)
        self.assertGreater(state["peak"], 1)
        self.assertLessEqual(state["peak"], 4)
        self.assertEqual(state["calls"], 8)
        self.assertIsNone(summary["ttft_seconds"])

    def test_missing_usage_is_null(self):
        summary, _ = self.probe("missing-usage")
        self.assertEqual(summary["successful"], 1)
        self.assertIsNone(summary["completion_tokens_successful"])
        self.assertIsNone(summary["successful_completion_tokens_per_second"])

    def test_http_error_and_redirect_do_not_retry(self):
        for mode, status in (("error", 503), ("redirect", 302)):
            with self.subTest(mode=mode):
                summary, state = self.probe(mode)
                self.assertEqual(summary["failed"], 1)
                self.assertEqual(summary["results"][0]["http_status"], status)
                self.assertEqual(state["calls"], 1)

    def test_invalid_json_tools_and_short_body(self):
        for mode in ("invalid-json", "tools", "short-body", "missing-finish", "tool-finish"):
            with self.subTest(mode=mode):
                summary, _ = self.probe(mode)
                self.assertEqual(summary["failed"], 1)
                self.assertIsNotNone(summary["results"][0]["error"])

    def test_response_limit(self):
        summary, _ = self.probe("oversize")
        self.assertEqual(summary["failed"], 1)
        self.assertTrue(summary["results"][0]["response_truncated"])
        self.assertEqual(summary["results"][0]["response_bytes"], driver.MAX_RESPONSE)

    def test_absolute_timeout_for_slow_headers(self):
        summary, _ = self.probe("slow-header", timeout=0.12)
        self.assertEqual(summary["failed"], 1)
        self.assertIn("TimeoutError", summary["results"][0]["error"])
        self.assertLess(summary["batch_wall_seconds"], 1)

    def test_existing_output_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory, server() as (url, state):
            with self.assertRaises(FileExistsError):
                driver.run(url, BODY, 1, 1, 1, Path(directory))
            self.assertEqual(state["calls"], 0)

    def test_endpoint_restrictions(self):
        for value in ("https://127.0.0.1:8080/v1/chat/completions", "http://localhost:8080/v1/chat/completions",
                      "http://192.168.1.2:8080/v1/chat/completions", "http://127.0.0.1:8080/admin",
                      "http://user:pass@127.0.0.1:8080/v1/chat/completions",
                      "http://127.0.0.1:8080/v1/chat/completions?secret=x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                driver.endpoint(value)
        self.assertEqual(driver.endpoint("http://[::1]:8080/v1/chat/completions"), ("::1", 8080, "/v1/chat/completions"))

    def test_request_restrictions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            for key, value in (("tools", []), ("max_tokens", 9000), ("stream", True), ("temperature", float("nan"))):
                data = json.loads(BODY)
                data[key] = value
                path.write_text(json.dumps(data))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    driver.load_request(path)
            path.write_bytes(BODY)
            self.assertEqual(json.loads(driver.load_request(path)), json.loads(BODY))

    def test_invalid_limits_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "new"
            for concurrency, requests, timeout in ((3, 4, 1), (4, 2, 1), (1, 257, 1), (1, 1, float("nan"))):
                with self.subTest(limits=(concurrency, requests, timeout)), self.assertRaises(ValueError):
                    driver.run("http://127.0.0.1:8080/v1/chat/completions", BODY, concurrency, requests, timeout, out)
                self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
