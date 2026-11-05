#!/usr/bin/env python3
"""LAB53 serving-noise tool: replay recorded agent requests and compare the answers.

replay  sends chat requests saved by the local bridge (trace/inference/<n>-request.json)
        to a loopback server, repeats them and can add concurrent neighbour requests.
        Tool calls in answers are recorded, never executed. No retries.
analyze rebuilds reasoning, text and tool calls from saved SSE streams and reports,
        per request, how often outputs and agent actions differ from a reference.
"""

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import itertools
import json
import math
from pathlib import Path
import re
import socket
import sys
import threading
import time
from urllib.parse import urlsplit

MAX_REQUEST = 8 * 1024 * 1024
MAX_RESPONSE = 32 * 1024 * 1024
REQUEST_KEYS = {"model", "messages", "tools", "stream", "stream_options", "max_tokens", "temperature",
                "top_p", "seed", "parallel_tool_calls", "tool_choice"}
REQUEST_NAME = re.compile(r"^([1-9][0-9]{0,4})-request\.json$")
RUN_ID = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-t\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*")


def endpoint(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path != "/v1/chat/completions"
            or parsed.hostname not in {"127.0.0.1", "::1"} or parsed.port is None):
        raise ValueError("use an explicit http://127.0.0.1:PORT/v1/chat/completions (or [::1])")
    if not ipaddress.ip_address(parsed.hostname).is_loopback:
        raise ValueError("only literal loopback endpoints are allowed")
    return parsed.hostname, parsed.port, parsed.path


def save_json(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def recorded_requests(inference_dir):
    """Map turn number -> path for every bridge request file in a trace/inference directory."""
    found = {}
    for path in Path(inference_dir).iterdir():
        match = REQUEST_NAME.match(path.name)
        if match and path.is_file() and not path.is_symlink():
            found[int(match.group(1))] = path
    if not found:
        raise ValueError(f"no <n>-request.json files in {inference_dir}")
    return found


def load_request(path, temperature=None, substitutions=(), cache_prompt="keep", top_logprobs=0):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_REQUEST:
        raise ValueError(f"{path}: request exceeds {MAX_REQUEST} bytes")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) - REQUEST_KEYS:
        raise ValueError(f"{path}: unsupported request fields {sorted(set(value) - REQUEST_KEYS)}")
    if not isinstance(value.get("model"), str) or not isinstance(value.get("messages"), list) or not value["messages"]:
        raise ValueError(f"{path}: request needs a model alias and messages")
    if value.get("stream") is not True:
        raise ValueError(f"{path}: only streamed bridge requests are supported")
    text = json.dumps(value["messages"], ensure_ascii=False)
    for old, new in substitutions:
        if old not in text:
            raise ValueError(f"{path}: substitution source not found: {old!r}")
        text = text.replace(old, new)
    value["messages"] = json.loads(text)
    if temperature is not None:
        value["temperature"] = temperature
    if cache_prompt != "keep":
        value["cache_prompt"] = cache_prompt == "true"
    if top_logprobs:
        value["logprobs"] = True
        value["top_logprobs"] = top_logprobs
    value["stream_options"] = {"include_usage": True}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def post(target, body, timeout):
    """One streamed POST; returns (status, raw bytes, error, seconds). Never retries."""
    started = time.monotonic()
    data, status, error = bytearray(), None, None
    connection = http.client.HTTPConnection(target[0], target[1], timeout=timeout)
    expired = threading.Event()
    timer = None
    try:
        connection.connect()
        sock = connection.sock

        def cancel():
            expired.set()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

        timer = threading.Timer(max(0.0, timeout - (time.monotonic() - started)), cancel)
        timer.daemon = True
        timer.start()
        connection.request("POST", target[2], body=body, headers={
            "Content-Type": "application/json", "Accept": "text/event-stream", "Connection": "close"})
        response = connection.getresponse()
        status = response.status
        with response:
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_RESPONSE:
                    raise ValueError("response exceeds limit")
        if status != 200:
            raise ValueError(f"HTTP {status}; no retry")
        incomplete = stream_problem(bytes(data))
        if incomplete:
            raise ValueError(incomplete)
    except Exception as exc:  # recorded, never retried
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()
        if expired.is_set():
            error = "TimeoutError: request deadline reached"
    return status, bytes(data), error, time.monotonic() - started


def stream_problem(raw):
    """None for a finished SSE answer; otherwise why it cannot count as one."""
    finished, done = False, False
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.strip() == "data: [DONE]":
            done = True
        elif line.startswith("data: "):
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                return "malformed SSE event"
            finished = finished or any(c.get("finish_reason") for c in event.get("choices") or [])
    if not finished:
        return "stream ended without finish_reason"
    if not done:
        return "stream ended without [DONE]"
    return None


def replay(args):
    target = endpoint(args.endpoint)
    if not 1 <= args.repeats <= 50:
        raise ValueError("repeats must be 1..50")
    if args.parallel not in (1, 2, 4, 8):
        raise ValueError("parallel must be 1, 2, 4 or 8")
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 1800:
        raise ValueError("timeout must be in (0, 1800] seconds")
    if args.temperature is not None and not 0 <= args.temperature <= 2:
        raise ValueError("temperature must be in 0..2")
    if not 0 <= args.top_logprobs <= 20:
        raise ValueError("top-logprobs must be 0..20")
    substitutions = []
    for item in args.substitute or []:
        old, sep, new = item.partition("=")
        if not sep or not old:
            raise ValueError("--substitute expects OLD=NEW")
        substitutions.append((old, new))
    available = recorded_requests(args.trace)
    wanted = sorted(available) if args.turns == "all" else sorted({int(x) for x in args.turns.split(",")})
    missing = [n for n in wanted if n not in available]
    if missing:
        raise ValueError(f"turns not in trace: {missing}")
    neighbours = sorted(available)
    bodies = {n: load_request(available[n], args.temperature, substitutions, args.cache_prompt, args.top_logprobs)
              for n in set(wanted) | set(neighbours if args.parallel > 1 else [])}
    out = Path(args.out)
    out.mkdir()  # refuses an existing directory before any HTTP call
    for n in sorted(bodies):  # the bytes actually sent, after overrides and substitutions
        with (out / f"t{n:05d}-request.json").open("xb") as sent:
            sent.write(bodies[n])
    save_json(out / "config.json", {
        "kind": "serving-noise-replay", "agent_run": False, "condition": args.condition,
        "endpoint": args.endpoint, "trace": str(Path(args.trace).resolve()), "turns": wanted,
        "repeats": args.repeats, "parallel": args.parallel, "order": args.order,
        "temperature_override": args.temperature, "cache_prompt": args.cache_prompt,
        "top_logprobs": args.top_logprobs, "substitutions": [list(s) for s in substitutions],
        "timeout_seconds": args.timeout, "retries": 0,
        "request_sha256": {str(n): sha256(bodies[n]) for n in sorted(bodies)},
        "created_at": datetime.now(timezone.utc).isoformat()})
    if args.order == "blocked":
        schedule = [(n, k) for n in wanted for k in range(1, args.repeats + 1)]
    else:
        schedule = [(n, k) for k in range(1, args.repeats + 1) for n in wanted]
    rotation = itertools.cycle(neighbours)
    failures = 0
    with (out / "results.jsonl").open("x", encoding="utf-8") as log:
        for n, k in schedule:
            jobs = [("target", n)]
            for j in range(1, args.parallel):
                other = next(rotation)
                jobs.append((f"neighbour{j}", other))
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                futures = {pool.submit(post, target, bodies[m], args.timeout): (role, m) for role, m in jobs}
                for future in concurrent.futures.as_completed(futures):
                    role, m = futures[future]
                    status, raw, error, seconds = future.result()
                    name = f"t{n:05d}-r{k:02d}-{role}.sse"
                    with (out / name).open("xb") as target_file:
                        target_file.write(raw)
                    if role == "target" and error:
                        failures += 1
                    log.write(json.dumps({"turn": n, "repeat": k, "role": role, "request_turn": m,
                                          "file": name, "http_status": status, "error": error,
                                          "seconds": round(seconds, 3), "response_sha256": sha256(raw)}) + "\n")
                    log.flush()
    print(json.dumps({"out": str(out), "targets": len(schedule), "failed_targets": failures}))
    return 0 if failures == 0 else 1


def parse_stream(raw):
    """Rebuild one streamed answer: reasoning, content, tool calls, token logprobs, usage."""
    reasoning, content, tools, tokens, usage, finish = [], [], {}, [], None, None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data: ") or line.strip() == "data: [DONE]":
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if isinstance(event.get("usage"), dict):
            usage = event["usage"]
        for choice in event.get("choices") or []:
            delta = choice.get("delta") or {}
            reasoning.append(delta.get("reasoning_content") or "")
            content.append(delta.get("content") or "")
            for call in delta.get("tool_calls") or []:
                slot = tools.setdefault(call.get("index", 0), {"name": "", "arguments": ""})
                function = call.get("function") or {}
                slot["name"] += function.get("name") or ""
                slot["arguments"] += function.get("arguments") or ""
            finish = choice.get("finish_reason") or finish
            for item in ((choice.get("logprobs") or {}).get("content") or []):
                top = [t.get("logprob") for t in item.get("top_logprobs") or [] if isinstance(t.get("logprob"), (int, float))]
                tokens.append({"token": item.get("token"), "logprob": item.get("logprob"),
                               "margin": (top[0] - top[1]) if len(top) > 1 else None})
    return {"reasoning": "".join(reasoning), "content": "".join(content),
            "tool_calls": [tools[i] for i in sorted(tools)], "tokens": tokens,
            "usage": usage, "finish_reason": finish}


def action(answer):
    """What the harness would do next: normalised tool calls, or the final text."""
    calls = []
    for call in answer["tool_calls"]:
        try:
            arguments = json.loads(call["arguments"]) if call["arguments"] else {}
        except json.JSONDecodeError:
            arguments = {"__unparsed__": call["arguments"]}
        calls.append({"name": call["name"], "arguments": arguments})
    if calls:
        return json.dumps({"tool_calls": calls}, sort_keys=True, ensure_ascii=False)
    return json.dumps({"final": answer["content"].strip()}, ensure_ascii=False)


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def canonical_request(raw):
    """Request messages with run IDs and harness-generated tool-call IDs replaced by stable labels.

    Everything else (timestamps in tool output, reasoning echoed back by the harness) stays,
    so two turns compare equal only when the model saw the same input apart from those labels."""
    messages = json.loads(raw).get("messages", [])
    names = {}

    def label(value):
        return names.setdefault(value, f"call-{len(names) + 1}")

    for message in messages:
        for call in message.get("tool_calls") or []:
            if isinstance(call.get("id"), str):
                call["id"] = label(call["id"])
        if isinstance(message.get("tool_call_id"), str):
            message["tool_call_id"] = label(message["tool_call_id"])
    text = RUN_ID.sub("<run-id>", json.dumps(messages, ensure_ascii=False, sort_keys=True))
    return sha256(text.encode())


def load_source(path):
    """A replay directory or a run's trace/inference directory -> {turn: [answers]}."""
    path = Path(path)
    answers, requests = {}, {}
    if (path / "config.json").is_file():
        config = json.loads((path / "config.json").read_text())
        label = config.get("condition") or path.name
        for turn in config["turns"]:
            sent = path / f"t{turn:05d}-request.json"
            if sent.is_file():
                requests[turn] = canonical_request(sent.read_bytes())
        for line in (path / "results.jsonl").read_text().splitlines():
            row = json.loads(line)
            if row["role"] != "target" or row["error"]:
                continue
            raw = (path / row["file"]).read_bytes()
            answers.setdefault(row["turn"], []).append(parse_stream(raw))
    else:
        label = path.parent.parent.name if path.name == "inference" else path.name
        for n in sorted(recorded_requests(path)):
            requests[n] = canonical_request((path / f"{n}-request.json").read_bytes())
            stream = path / f"{n}-response.bin"
            if stream.is_file():
                answers.setdefault(n, []).append(parse_stream(stream.read_bytes()))
    return label, answers, requests


def analyze(args):
    sources = [load_source(p) for p in args.source]
    reference_label, reference, reference_requests = sources[0]
    rows = []
    for label, answers, requests in sources:
        for turn in sorted(answers):
            if turn not in reference:
                continue
            ref = reference[turn][0]
            ref_text = ref["reasoning"] + "␞" + ref["content"]
            outs = answers[turn] if label != reference_label else answers[turn][1:]
            if not outs:
                continue
            same_output = same_action = 0
            positions, margins = [], []
            for out in outs:
                text = out["reasoning"] + "␞" + out["content"]
                identical = text == ref_text and out["tool_calls"] == ref["tool_calls"]
                same_output += identical
                same_action += action(out) == action(ref)
                if not identical:
                    position = first_difference(ref_text, text)
                    if position is not None:
                        positions.append(position)
                    ref_tokens = [t["token"] for t in ref["tokens"]]
                    index = first_difference(ref_tokens, [t["token"] for t in out["tokens"]]) if ref_tokens else None
                    if index is not None and index < len(ref["tokens"]) and ref["tokens"][index]["margin"] is not None:
                        margins.append(round(ref["tokens"][index]["margin"], 4))
            distinct = len({action(o) for o in answers[turn]})
            rows.append({"source": label, "turn": turn,
                         "same_input_as_reference": (reference_requests.get(turn) is not None
                                                    and requests.get(turn) == reference_requests.get(turn)),
                         "compared": len(outs), "identical_outputs": same_output,
                         "same_action": same_action, "distinct_actions_in_source": distinct,
                         "first_divergence_chars": sorted(positions), "reference_margin_at_divergence": margins})
    summary = {}
    for label, _, _ in sources:
        mine = [r for r in rows if r["source"] == label]
        compared = sum(r["compared"] for r in mine)
        summary[label] = {
            "turns": len(mine), "comparisons": compared,
            "identical_output_rate": (sum(r["identical_outputs"] for r in mine) / compared) if compared else None,
            "action_flip_rate": (1 - sum(r["same_action"] for r in mine) / compared) if compared else None,
            "turns_with_any_action_flip": sum(1 for r in mine if r["same_action"] < r["compared"]),
            "first_action_flip": next(({"turn": r["turn"], "same_input_as_reference": r["same_input_as_reference"]}
                                       for r in mine if r["same_action"] < r["compared"]), None)}
    report = {"kind": "serving-noise-analysis", "reference": f"{reference_label} (first answer per turn)",
              "summary": summary, "turns": rows,
              "note": ("Rates are per (turn, repeat) comparison with the reference answer; they are not agent verdicts. "
                       "For two agent traces only turns up to the first input difference compare like with like.")}
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        with Path(args.out).open("x", encoding="utf-8") as target:
            target.write(text)
    else:
        sys.stdout.write(text)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("replay", help="send recorded requests to a loopback server")
    r.add_argument("--endpoint", required=True)
    r.add_argument("--trace", required=True, help="results/runs/<run-id>/trace/inference")
    r.add_argument("--turns", default="all", help="comma-separated turn numbers or 'all'")
    r.add_argument("--repeats", type=int, default=5)
    r.add_argument("--parallel", type=int, default=1, help="target plus N-1 concurrent neighbour requests")
    r.add_argument("--order", choices=("blocked", "interleaved"), default="interleaved")
    r.add_argument("--cache-prompt", choices=("keep", "true", "false"), default="keep",
                   help="llama.cpp cache_prompt field; keep sends the recorded request unchanged")
    r.add_argument("--temperature", type=float, help="override only for the sampling anchor condition")
    r.add_argument("--top-logprobs", type=int, default=0)
    r.add_argument("--substitute", action="append", help="OLD=NEW text change in messages (prompt anchor)")
    r.add_argument("--condition", required=True, help="neutral label recorded in config.json")
    r.add_argument("--timeout", type=float, default=600)
    r.add_argument("--out", required=True, help="new directory; parent must exist")
    a = sub.add_parser("analyze", help="compare answers; the first source is the reference")
    a.add_argument("--source", action="append", required=True, help="replay dir or trace/inference dir")
    a.add_argument("--out", help="new JSON file; stdout when omitted")
    args = parser.parse_args(argv)
    try:
        return replay(args) if args.command == "replay" else analyze(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"serving-noise: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
