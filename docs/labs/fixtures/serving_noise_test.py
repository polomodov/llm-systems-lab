#!/usr/bin/env python3
"""Offline LAB53 checks: loopback mock SSE server, never a model."""

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

import serving_noise as noise

REQUEST = {"model": "lab-model", "messages": [{"role": "user", "content": "Run-id: run-1. Fix tests."}],
           "tools": [{"type": "function", "function": {"name": "bash", "parameters": {"type": "object"}}}],
           "stream": True, "stream_options": {"include_usage": True}, "max_tokens": 64,
           "temperature": 0, "top_p": 1, "seed": 1, "parallel_tool_calls": False}


def sse(reasoning, command, logprobs=None):
    events = [{"choices": [{"index": 0, "delta": {"reasoning_content": part}}]} for part in reasoning]
    events.append({"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "function": {"name": "bash", "arguments": json.dumps({"command": command})}}]}}]})
    if logprobs:
        events[0]["choices"][0]["logprobs"] = {"content": logprobs}
    events.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    return ("".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n").encode()


@contextlib.contextmanager
def server(answers):
    state = {"bodies": [], "active": 0, "peak": 0}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            with lock:
                state["bodies"].append(body)
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
                raw = answers(len(state["bodies"]), body)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            finally:
                with lock:
                    state["active"] -= 1

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/v1/chat/completions", state
    finally:
        httpd.shutdown()
        httpd.server_close()


def trace(root, turns=2):
    inference = Path(root) / "run" / "trace" / "inference"
    inference.mkdir(parents=True)
    for n in range(1, turns + 1):
        (inference / f"{n}-request.json").write_text(json.dumps(REQUEST))
        (inference / f"{n}-response.bin").write_bytes(sse(["think"], f"ls {n}"))
    return inference


class ServingNoiseTest(unittest.TestCase):
    def run_cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return noise.main(list(argv))

    def test_endpoint_is_loopback_only(self):
        for bad in ("http://192.168.0.2:8080/v1/chat/completions", "https://127.0.0.1:1/v1/chat/completions",
                    "http://localhost:8080/v1/chat/completions", "http://127.0.0.1:8080/admin"):
            with self.assertRaises(ValueError):
                noise.endpoint(bad)

    def test_request_validation_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "1-request.json"
            path.write_text(json.dumps({**REQUEST, "api_key": "x"}))
            with self.assertRaises(ValueError):
                noise.load_request(path)
            path.write_text(json.dumps(REQUEST))
            body = json.loads(noise.load_request(path, temperature=0.7, substitutions=[("run-1", "run-2")],
                                                 cache_prompt="false", top_logprobs=2))
            self.assertEqual(body["temperature"], 0.7)
            self.assertIn("run-2", body["messages"][0]["content"])
            self.assertIs(body["cache_prompt"], False)
            self.assertEqual(body["top_logprobs"], 2)
            with self.assertRaises(ValueError):
                noise.load_request(path, substitutions=[("absent", "x")])

    def test_replay_records_every_answer_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp, server(lambda i, body: sse(["think"], "ls")) as (url, state):
            inference = trace(tmp)
            out = Path(tmp) / "replay"
            code = self.run_cli("replay", "--endpoint", url, "--trace", str(inference), "--repeats", "3",
                                "--parallel", "2", "--condition", "A", "--out", str(out))
            self.assertEqual(code, 0)
            rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
            self.assertEqual(sum(r["role"] == "target" for r in rows), 6)
            self.assertEqual(len(rows), 12)
            self.assertEqual(state["peak"] >= 1, True)
            self.assertEqual(json.loads((out / "config.json").read_text())["agent_run"], False)
            self.assertEqual(self.run_cli("replay", "--endpoint", url, "--trace", str(inference),
                                          "--condition", "A", "--out", str(out)), 2)

    def test_analyze_separates_text_noise_from_action_flips(self):
        answers = {1: sse(["think"], "ls"), 2: sse(["think"], "ls"), 3: sse(["thonk"], "ls"),
                   4: sse(["think"], "rm -rf build")}
        with tempfile.TemporaryDirectory() as tmp, server(lambda i, body: answers[i]) as (url, _):
            inference = trace(tmp, turns=1)
            out = Path(tmp) / "replay"
            self.run_cli("replay", "--endpoint", url, "--trace", str(inference), "--repeats", "4",
                         "--condition", "B", "--out", str(out))
            report_path = Path(tmp) / "report.json"
            self.assertEqual(self.run_cli("analyze", "--source", str(out), "--out", str(report_path)), 0)
            report = json.loads(report_path.read_text())
            row = report["turns"][0]
            self.assertEqual(row["compared"], 3)
            self.assertEqual(row["identical_outputs"], 1)
            self.assertEqual(row["same_action"], 2)
            self.assertEqual(row["distinct_actions_in_source"], 2)
            self.assertAlmostEqual(report["summary"]["B"]["action_flip_rate"], 1 / 3)

    def test_incomplete_streams_are_failures_not_answers(self):
        bodies = {1: b"", 2: sse(["think"], "ls").replace(b"data: [DONE]\n\n", b"")}
        with tempfile.TemporaryDirectory() as tmp, server(lambda i, body: bodies.get(i, sse(["think"], "ls"))) as (url, _):
            inference = trace(tmp, turns=1)
            out = Path(tmp) / "replay"
            self.assertEqual(self.run_cli("replay", "--endpoint", url, "--trace", str(inference), "--repeats", "3",
                                          "--condition", "C", "--out", str(out)), 1)
            rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
            self.assertEqual([bool(r["error"]) for r in rows], [True, True, False])
            report_path = Path(tmp) / "report.json"
            self.run_cli("analyze", "--source", str(out), "--out", str(report_path))
            self.assertEqual(json.loads(report_path.read_text())["summary"]["C"]["comparisons"], 0)

    def test_substituted_replay_is_not_same_input(self):
        with tempfile.TemporaryDirectory() as tmp, server(lambda i, body: sse(["think"], "ls")) as (url, _):
            inference = trace(tmp, turns=1)
            base, changed = Path(tmp) / "base", Path(tmp) / "changed"
            self.run_cli("replay", "--endpoint", url, "--trace", str(inference), "--repeats", "1",
                         "--condition", "base", "--out", str(base))
            self.run_cli("replay", "--endpoint", url, "--trace", str(inference), "--repeats", "1",
                         "--substitute", "Fix tests.=Do not fix tests.", "--condition", "changed", "--out", str(changed))
            report_path = Path(tmp) / "report.json"
            self.run_cli("analyze", "--source", str(base), "--source", str(changed), "--out", str(report_path))
            rows = json.loads(report_path.read_text())["turns"]
            self.assertEqual([r["same_input_as_reference"] for r in rows if r["source"] == "changed"], [False])

    def test_canonical_request_ignores_run_ids_and_tool_call_ids_only(self):
        def body(run_id, call_id, stamp):
            return json.dumps({"messages": [
                {"role": "user", "content": f"Run-id: {run_id}. Work in janitor/{run_id}."},
                {"role": "assistant", "tool_calls": [{"id": call_id, "function": {"name": "bash"}}]},
                {"role": "tool", "tool_call_id": call_id, "content": f"brief.md Oct 12 {stamp}"}]}).encode()
        first = noise.canonical_request(body("2026-10-12-pi-a2-janitor-t002-repo-janitor-4", "TokF", "13:06"))
        second = noise.canonical_request(body("2026-10-12-pi-a2-janitor-t002-repo-janitor-5", "LAKk", "13:06"))
        later = noise.canonical_request(body("2026-10-12-pi-a2-janitor-t002-repo-janitor-5", "LAKk", "13:52"))
        self.assertEqual(first, second)
        self.assertNotEqual(first, later)

    def test_parse_stream_reads_logprob_margin(self):
        raw = sse(["a"], "ls", logprobs=[{"token": "a", "logprob": -0.1,
                                          "top_logprobs": [{"logprob": -0.1}, {"logprob": -0.4}]}])
        answer = noise.parse_stream(raw)
        self.assertAlmostEqual(answer["tokens"][0]["margin"], 0.3)
        self.assertEqual(answer["tool_calls"][0]["name"], "bash")


if __name__ == "__main__":
    unittest.main()
