#!/usr/bin/env python3
"""Bounded local chat load probe for LAB26; no tools, credentials, or retries."""

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import math
from pathlib import Path
import socket
import statistics
import sys
import threading
import time
from urllib.parse import urlsplit

MAX_RESPONSE = 1024 * 1024
MAX_REQUEST = 64 * 1024


def endpoint(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path != "/v1/chat/completions"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.port is None or not 1 <= parsed.port <= 65535):
        raise ValueError("use an explicit http://127.0.0.1:PORT/v1/chat/completions (or [::1])")
    if not ipaddress.ip_address(parsed.hostname).is_loopback:
        raise ValueError("only literal loopback endpoints are allowed")
    return parsed.hostname, parsed.port, parsed.path


def load_request(path):
    with Path(path).open("rb") as source:
        raw = source.read(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        raise ValueError("request exceeds 64 KiB")
    value = json.loads(raw)
    allowed = {"model", "messages", "max_tokens", "stream", "temperature", "top_p", "seed"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("request contains unsupported fields (tools/auth/extensions are forbidden)")
    model = value.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        raise ValueError("request needs a nonempty model alias of at most 256 characters")
    messages = value.get("messages")
    if (not isinstance(messages, list) or len(messages) != 1
            or not isinstance(messages[0], dict)
            or set(messages[0]) != {"role", "content"}
            or messages[0]["role"] != "user"
            or not isinstance(messages[0]["content"], str)
            or not messages[0]["content"].strip()):
        raise ValueError("request must contain exactly one plain-text user message")
    if type(value.get("max_tokens")) is not int or not 1 <= value["max_tokens"] <= 4096:
        raise ValueError("max_tokens must be an integer in 1..4096")
    if value.get("stream") is not False:
        raise ValueError("stream must be false; this probe measures complete-response latency")
    for key, lower, upper in (("temperature", 0, 2), ("top_p", 0, 1)):
        if key in value and (type(value[key]) not in (int, float)
                             or not math.isfinite(value[key])
                             or not lower <= value[key] <= upper):
            raise ValueError(f"invalid {key}")
    if "seed" in value and (type(value["seed"]) is not int or not 0 <= value["seed"] < 2**31):
        raise ValueError("seed must be an integer in 0..2**31-1")
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    if len(body) > MAX_REQUEST:
        raise ValueError("encoded request exceeds 64 KiB")
    return body


def save_json(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def usage_count(value):
    return value if type(value) is int and value >= 0 else None


def request_one(index, target, body, timeout, out):
    started = time.monotonic()
    result = {"index": index, "ok": False, "http_status": None, "error": None,
              "latency_seconds": None, "completion_tokens": None, "prompt_tokens": None,
              "finish_reason": None, "response_bytes": 0, "response_truncated": False}
    chunks = bytearray()
    connection = http.client.HTTPConnection(target[0], target[1], timeout=timeout)
    timer = None
    expired = threading.Event()
    try:
        connection.connect()
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("request deadline reached during connect")
        connected_socket = connection.sock

        def cancel():
            expired.set()
            try:
                connected_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connected_socket.close()

        # A watchdog also bounds slow headers/chunks; a socket inactivity timeout alone does not.
        timer = threading.Timer(remaining, cancel)
        timer.daemon = True
        timer.start()
        connection.request("POST", target[2], body=body,
                           headers={"Content-Type": "application/json", "Accept": "application/json",
                                    "Connection": "close"})
        response = connection.getresponse()
        result["http_status"] = response.status
        with response:
            while True:
                chunk = response.read1(min(65536, MAX_RESPONSE + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE:
                    result["response_truncated"] = True
                    del chunks[MAX_RESPONSE:]
                    raise ValueError("response exceeds 1 MiB")
            if response.length not in (None, 0):
                raise ValueError("response ended before Content-Length")
        if expired.is_set() or time.monotonic() - started >= timeout:
            raise TimeoutError("request deadline reached")
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}; no retry or redirect")
        value = json.loads(chunks)
        choices = value.get("choices") if isinstance(value, dict) else None
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("expected exactly one chat choice")
        message = choices[0].get("message")
        if (not isinstance(message, dict) or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str) or not message["content"].strip()
                or message.get("tool_calls") or message.get("function_call")):
            raise ValueError("expected nonempty assistant text without tool calls")
        result["finish_reason"] = choices[0].get("finish_reason")
        if result["finish_reason"] not in {"stop", "length"}:
            raise ValueError("expected finish_reason stop or length")
        usage = value.get("usage")
        if isinstance(usage, dict):
            result["prompt_tokens"] = usage_count(usage.get("prompt_tokens"))
            result["completion_tokens"] = usage_count(usage.get("completion_tokens"))
        result["ok"] = True
    except Exception as error:
        result["error"] = "TimeoutError: request deadline reached" if expired.is_set() else f"{type(error).__name__}: {error}"
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        connection.close()
        if expired.is_set():
            result["ok"] = False
            result["error"] = "TimeoutError: request deadline reached"
        result["latency_seconds"] = time.monotonic() - started
        result["response_bytes"] = len(chunks)
        with (out / f"request-{index:04d}.response.bin").open("xb") as target_file:
            target_file.write(chunks)
        save_json(out / f"request-{index:04d}.json", result)
    return result


def percentile95(values):
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def linux_sample():
    sample = {"timestamp": datetime.now(timezone.utc).isoformat(), "mem_total_bytes": None,
              "mem_available_bytes": None, "pswpin_pages": None, "pswpout_pages": None,
              "unavailable": None}
    try:
        memory = {line.split(":", 1)[0]: int(line.split()[1]) * 1024
                  for line in Path("/proc/meminfo").read_text().splitlines()
                  if line.startswith(("MemTotal:", "MemAvailable:"))}
        swap = {line.split()[0]: int(line.split()[1])
                for line in Path("/proc/vmstat").read_text().splitlines()
                if line.startswith(("pswpin ", "pswpout "))}
        sample.update(mem_total_bytes=memory.get("MemTotal"), mem_available_bytes=memory.get("MemAvailable"),
                      pswpin_pages=swap.get("pswpin"), pswpout_pages=swap.get("pswpout"))
    except (OSError, ValueError) as error:
        sample["unavailable"] = f"Linux /proc telemetry unavailable: {type(error).__name__}"
    return sample


def run(endpoint_url, body, concurrency, requests, timeout, out):
    target = endpoint(endpoint_url)
    if concurrency not in (1, 2, 4) or not concurrency <= requests <= 256:
        raise ValueError("concurrency must be 1, 2, or 4; requests must be concurrency..256")
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError("timeout must be >0 and <=600 seconds")
    out = Path(out)
    # mkdir without exist_ok rejects existing directories and symlinks, before any HTTP call.
    out.mkdir()
    save_json(out / "config.json", {"endpoint": endpoint_url, "concurrency": concurrency,
                                   "requests": requests, "timeout_seconds": timeout,
                                   "request_sha256": hashlib.sha256(body).hexdigest(),
                                   "response_limit_bytes": MAX_RESPONSE, "retries": 0,
                                   "created_at": datetime.now(timezone.utc).isoformat(),
                                   "kind": "http-load-probe", "agent_run": False})
    with (out / "request.json").open("xb") as request_file:
        request_file.write(body)
    started = time.monotonic()
    stop_sampling = threading.Event()
    samples = []
    with (out / "system-memory.jsonl").open("x", encoding="utf-8") as telemetry:
        def sample():
            observation = linux_sample()
            samples.append(observation)
            telemetry.write(json.dumps(observation) + "\n")
            telemetry.flush()

        def collect():
            while not stop_sampling.wait(1):
                sample()

        sample()
        collector = threading.Thread(target=collect, daemon=True)
        collector.start()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = [pool.submit(request_one, i, target, body, timeout, out) for i in range(1, requests + 1)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
        finally:
            stop_sampling.set()
            collector.join()
            sample()
    elapsed = time.monotonic() - started
    successful = [row for row in results if row["ok"]]
    latencies = [row["latency_seconds"] for row in successful]
    measured = [row for row in successful if row["completion_tokens"] is not None]
    tokens = sum(row["completion_tokens"] for row in measured) if len(measured) == len(successful) and successful else None
    summary = {"kind": "http-load-probe", "agent_run": False, "requests": requests,
               "concurrency": concurrency, "successful": len(successful), "failed": requests - len(successful),
               "batch_wall_seconds": elapsed, "successful_requests_per_second": len(successful) / elapsed,
               "success_latency_median_seconds": statistics.median(latencies) if latencies else None,
               "success_latency_p95_seconds": percentile95(latencies),
               "success_latency_max_seconds": max(latencies) if latencies else None,
               "successes_with_completion_usage": len(measured), "completion_tokens_successful": tokens,
               "successful_completion_tokens_per_second": tokens / elapsed if tokens is not None else None,
               "ttft_seconds": None, "ttft_unavailable": "non-streaming complete-response probe",
               "memory_bytes": None, "memory_unavailable": "collect server/system telemetry separately",
               "minimum_sampled_mem_available_bytes": min((row["mem_available_bytes"] for row in samples
                                                           if row["mem_available_bytes"] is not None), default=None),
               "system_memory_sampling_seconds": 1, "finished_at": datetime.now(timezone.utc).isoformat(),
               "results": sorted(results, key=lambda row: row["index"])}
    save_json(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 4), required=True)
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--out", required=True, help="new directory; parent must exist")
    args = parser.parse_args()
    try:
        summary = run(args.endpoint, load_request(args.request), args.concurrency, args.requests, args.timeout, args.out)
        print(json.dumps({key: summary[key] for key in ("requests", "concurrency", "successful", "failed", "batch_wall_seconds")}))
        return 0 if summary["failed"] == 0 else 1
    except (ValueError, OSError) as error:
        print(f"probe: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
