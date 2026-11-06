"""Grade only the declared artifact against an image-owned fixture."""

import hashlib
import json
import socket
import urllib.request
from pathlib import Path


def evaluate(output: Path, fixture: Path) -> tuple[int, str]:
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    if output.is_symlink() or not output.is_file():
        return 0, "missing-or-nonregular-output"
    if output.stat().st_size > 1024:
        return 0, "oversized-output"
    try:
        actual = json.loads(output.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError):
        return 0, "invalid-json-output"
    if actual != expected:
        return 0, "incorrect-output"
    return 1, "correct-output"


if __name__ == "__main__":
    fixture = Path("/opt/verifier-fixtures/expected.json")
    reward, reason = evaluate(Path("/app/output/result.json"), fixture)
    try:
        with urllib.request.urlopen("https://example.com/", timeout=3) as response:
            response.read(2048)
            external_https_blocked = False
    except OSError:
        external_https_blocked = True
    assert external_https_blocked, "verifier external HTTPS request unexpectedly succeeded"
    evidence = {
        "reward": reward,
        "reason": reason,
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "hostname": socket.gethostname(),
        "external_https_probe_blocked": external_https_blocked,
        "agent_input_present_in_verifier": Path("/app/input.json").exists(),
        "agent_solution_present_in_verifier": Path("/solution/solve.sh").exists(),
        "agent_tamper_marker_present_in_verifier": Path("/app/agent-only.txt").exists(),
    }
    Path("/logs/verifier/evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    Path("/logs/verifier/reward.txt").write_text(str(reward) + "\n")
    print(json.dumps(evidence, sort_keys=True))
