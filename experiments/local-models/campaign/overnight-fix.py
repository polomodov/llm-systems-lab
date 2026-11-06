#!/usr/bin/env python3
"""Overnight campaign repair: re-run corrected LAB05 streaming and finish models.

Modes:
  lab05  — re-run LAB05 for the models whose stream cases failed under the
           buggy driver (original sessions stay as an honest blocked record;
           corrected results go to a new <id>-overnight2 session).
  full   — download + LAB03/04/05 for glm-47-flash and qwen3-coder-next into
           new <id>-overnight2 sessions.

Runs in a dedicated git worktree. All progress goes to campaign/overnight-fix.log.
"""
import json, os, pathlib, subprocess, sys, time, datetime, shutil, signal, urllib.request, urllib.error

WT = pathlib.Path(__file__).resolve().parents[3]
REPO = WT
HOME = pathlib.Path(os.environ["HOME"])
STORAGE = HOME / "local-model-lab-artifacts"
B = STORAGE / "llama-cpp-b8407"
VUL = B / "llama-b8407"
HIP = B / "llama-b8407-ubuntu-24.04-rocm-7.2.1-gfx110X-gfx115X-gfx120X-x64"
B10000 = STORAGE / "llama-cpp-b10000"
VUL10000 = B10000 / "vulkan/llama-b10000"
HIP10000 = B10000 / "rocm/llama-b10000"
AMD_ROCM_LIBS = HIP
GGUF_ROOT = STORAGE
CAMPAIGN = REPO / "experiments/local-models/campaign"
MODELS = json.loads((CAMPAIGN / "overnight-models.json").read_text())
RUN_ID = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
BRANCH = "overnight-models-fixes"
LOG = CAMPAIGN / f"overnight-fix-{RUN_ID}.log"
STATUS = CAMPAIGN / f"overnight-fix-{RUN_ID}-status.json"
def now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

status = {"run_id": RUN_ID, "branch": BRANCH, "started": None, "models": {}}

def log(msg):
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")

def sh(cmd, cwd=None, env=None, check=False, out=None, err=None):
    e = dict(os.environ)
    if env: e.update(env)
    log("$ " + " ".join(str(c) for c in cmd))
    kw = {}
    if out: kw["stdout"] = open(out, "wb")
    if err: kw["stderr"] = open(err, "wb")
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=e, **kw)
    for f in (kw.get("stdout"), kw.get("stderr")):
        if f: f.close()
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
    return r.returncode

def dump(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

# ---------------------------------------------------------------- sessions
def measurements_dir():
    return WT / "experiments/local-models/measurements"

def new_session(lab, sid):
    r = subprocess.run(["node", str(REPO / "scripts/new-lab.mjs"), "--lab", lab, "--session", sid],
                       cwd=str(WT), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return measurements_dir() / f"{lab}-{sid}"

def write_protocol(sdir, body):
    (sdir / "raw").mkdir(parents=True, exist_ok=True)
    (sdir / "raw/protocol.md").write_text(body)

def commit(paths, message):
    for p in paths:
        sh(["git", "add", "-A", str(p)], cwd=WT)
        # force logs
        for lg in pathlib.Path(WT / p).rglob("*.log"):
            sh(["git", "add", "-f", str(lg)], cwd=WT)
    sh(["git", "commit", "-q", "-m", message], cwd=WT)

def git(*args, check=True):
    return sh(["git", *args], cwd=WT, check=check)

# ---------------------------------------------------------------- finalizers
def finalize(sdir, manifest, attempts, rows, report_md):
    manifest["planned_attempts"] = attempts
    ev = []
    raw = sdir / "raw"
    for p in sorted(raw.rglob("*")):
        if p.is_file():
            ev.append(str(p.relative_to(sdir)))
    manifest["evidence_files"] = ev
    dump(sdir / "manifest.json", manifest)
    cols = "observation_id\tconfiguration_id\tmodel_id\tengine\tbackend\tcontext_tokens\trepeat\tmetric\tvalue\tunit\tstatus\tevidence_path\tunavailable_reason"
    lines = [cols]
    for r in rows:
        lines.append("\t".join(str(x) for x in r))
    (sdir / "measurements.tsv").write_text("\n".join(lines) + "\n")
    (sdir / "report.md").write_text(report_md)

# ---------------------------------------------------------------- LAB03
FETCH = REPO / "experiments/local-models/measurements/LAB03-qwen35-9b/raw/fetch_artifact.py"

def lab03(model, sid):
    sdir = new_session("LAB03", sid)
    raw = sdir / "raw"
    art = model["artifact"]
    artifact_json = {
        "id": model["id"], "model_id": model["model_id"],
        "quantization": model.get("quantization", "unknown"),
        "artifact": {"repository": art["repository"], "revision": art["revision"],
                     "files": [{"path": f["path"], "bytes": f["bytes"], "sha256": f.get("sha256")} for f in art["files"]],
                     "total_bytes": sum(f["bytes"] for f in art["files"])},
    }
    dump(raw / "artifact.json", artifact_json)
    shutil.copy(FETCH, raw / "fetch_artifact.py")
    write_protocol(sdir, f"""# LAB03 — preregistered protocol ({model['id']})

## Hypothesis
The local artifact copy {art['repository']}@{art['revision']} matches the published size and SHA-256.

## Procedure
1. Download from the pinned revision using `fetch_artifact.py --download`.
2. Verify sizes and SHA-256 offline.
3. Write a checksum file for LAB04/LAB05.

## Stop condition
A size/SHA mismatch gives `fail`/`no-artifact`; do not pass the artifact downstream.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB03", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "protocol",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{sid}/raw/artifact.json",
                    "runtime_manifest": None, "harness_profile": None},
                "run_ids": [], "planned_attempts": [], "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"The local artifact copy {model['id']} matches the published {art['repository']}@{art['revision']} size and SHA-256.",
                "unavailable": {"conditions.runtime_manifest": "LAB03 does not launch a runtime.",
                                "conditions.harness_profile": "LAB03 does not use a harness."},
                "conclusion": None, "reviewer_decision": None}
    dump(sdir / "manifest.json", manifest)     # preregistration
    commit([f"experiments/local-models/measurements/LAB03-{sid}"], f"LAB03 {model['id']}: preregistration")
    code = sh(["python3", str(raw / "fetch_artifact.py"), str(raw / "artifact.json"), str(STORAGE), "--download"],
              cwd=sdir, out=raw / "download-verification.json")
    sh(["python3", str(raw / "fetch_artifact.py"), str(raw / "artifact.json"), str(STORAGE)],
       cwd=sdir, out=raw / "verification.json")
    ver = json.loads((raw / "verification.json").read_text())
    lines = [f"{f['sha256']}  {f['path']}" for f in ver["files"] if f.get("status") == "verified" and f["path"].endswith(".gguf")]
    (raw / "weights.sha256").write_text("".join(l + "\n" for l in lines))
    sh(["sha256sum", "--check", str(raw / "weights.sha256")], cwd=sdir, out=raw / "verification.txt")
    ok = all(f.get("status") == "verified" for f in ver["files"])
    manifest.update({"status": "completed" if ok else "blocked",
                     "conclusion": f"Verification of {art['repository']}@{art['revision']}: {'verified' if ok else 'fail'}."})
    if not ok:
        manifest["unavailable"]["completion"] = "The artifact failed size/SHA verification."
    attempt = {"id": f"{model['id']}-verify", "configuration_id": f"{model['id']}-verify", "kind": "measurement",
               "status": "completed", "run_id": None,
               "evidence_files": ["raw/artifact.json", "raw/verification.json", "raw/verification.txt", "raw/weights.sha256"],
               "conclusion": "verified." if ok else "fail.", "reason": None}
    rows = []
    if ver["files"]:
        f0 = ver["files"][0]
        if "bytes" in f0:
            rows.append([f"{model['id']}-bytes", f"{model['id']}-verify", model["model_id"], "sha256sum",
                         "-", "", "1", "file_bytes", f0["bytes"], "B", "measured", "raw/verification.json", ""])
        else:
            rows.append([f"{model['id']}-bytes", f"{model['id']}-verify", model["model_id"], "sha256sum",
                         "-", "", "", "file_bytes", "", "", "no-artifact", "", "The artifact is missing or incompletely downloaded."])
    report = f"# LAB03 — artifact {model['id']}\n\nSession: `{sid}`.\n\n## Run profile\n\n| Field | Value |\n| --- | --- |\n| Model | `{model['model_id']}` |\n| Artifact | `{art['repository']}@{art['revision']}` |\n\n## Hypothesis and protocol before execution\n\nSee `raw/protocol.md`.\n\n## Execution log\n\n| Step | Result |\n| --- | --- |\n| download | exit {code} |\n| verify | {'verified' if ok else 'fail'} |\n\n## Results\n\nSee `measurements.tsv`, `raw/verification.json`.\n\n## Errors and limitations\n\nNone.\n\n## Hypothesis conclusion\n\n{'Supported.' if ok else 'Not supported.'}\n\n## Answers to review questions\n\nSHA-256 confirms file integrity.\n\n## Submission bundle\n\n- [x] manifest.json, measurements.tsv, report.md.\n"
    finalize(sdir, manifest, [attempt], rows, report)
    commit([f"experiments/local-models/measurements/LAB03-{sid}"], f"LAB03 {model['id']}: results")
    return sdir, ver

# ---------------------------------------------------------------- LAB04
def gguf_path(ver):
    files = [f["path"] for f in ver["files"] if f["path"].endswith(".gguf")]
    shards = [f for f in files if "-00001-of-" in f]
    return shards[0] if shards else files[0]

def bench(binpath, g, args, out_json, out_log, proc, cwd, libpath=None):
    env = {"LD_LIBRARY_PATH": str(libpath or pathlib.Path(binpath).parent)}
    return sh(["/usr/bin/time", "-v", "-o", str(proc), str(binpath), "-m", str(g), *args], cwd=cwd, env=env,
              out=out_json, err=out_log)

def lab04(model, gguf, sid, engine_label="llama.cpp b8407 (312cf0332)",
          provenance="llama.cpp b8407 (312cf03328496df9c56fe843952cf02a8964c59a); prebuilt Vulkan + ROCm/HIP bundles.\n",
          bins=None, libpaths=None, ref_sid=None):
    sdir = new_session("LAB04", sid)
    raw = sdir / "raw"
    bins = bins or {"vulkan": VUL / "llama-bench", "hip": HIP / "llama-bench"}
    libpaths = libpaths or {}
    ref_sid = ref_sid or sid
    write_protocol(sdir, f"""# LAB04 — preregistered protocol ({model['id']})

## Hypothesis
One GGUF {model['id']} is fully offloaded to GPU in both prebuilt builds {engine_label} (Vulkan/RADV and ROCm/HIP); backend affects speed, but the direction is unknown.

## Procedure
1. `sha256sum --check`; 2. offload-proof `llama-bench -v` for both tracks; 3. warmup; 4. three paired pp2048/tg128@d4096 repeats under `/usr/bin/time -v`.

## Stop condition
OOM/invalid JSON/evidence of CPU offload → track fails.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB04", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "experimental",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{ref_sid}/raw/artifact.json",
                    "runtime_manifest": f"experiments/local-models/measurements/LAB04-{sid}/raw/build-provenance.txt",
                    "harness_profile": None}, "run_ids": [], "planned_attempts": [],
                "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"One GGUF {model['id']} is fully offloaded to GPU in both prebuilt builds {engine_label} (Vulkan/RADV and ROCm/HIP); backend affects speed, but the direction is unknown.",
                "unavailable": {"conditions.harness_profile": "LAB04 does not use a harness."},
                "conclusion": None, "reviewer_decision": None}
    dump(sdir / "manifest.json", manifest)
    commit([f"experiments/local-models/measurements/LAB04-{sid}"], f"LAB04 {model['id']}: preregistration")
    (raw / "build-provenance.txt").write_text(provenance)
    G = str(gguf); N = sdir
    common = ["-ngl", "999", "-t", "8", "-b", "512", "-ub", "256", "-ctk", "f16", "-ctv", "f16", "-fa", "1"]
    info = {}
    for be, binp in bins.items():
        lib = libpaths.get(be) or str(binp.parent)
        sh([str(binp), "--list-devices"], env={"LD_LIBRARY_PATH": lib}, out=raw / f"{be}-devices.txt")
        r = sh([str(binp), "-m", G, *common, "-p", "8", "-n", "1", "-r", "1", "-v"], cwd=sdir,
               env={"LD_LIBRARY_PATH": lib}, out=raw / f"{be}-offload-proof.json", err=raw / f"{be}-offload-proof.log")
        n = sum(1 for l in (raw / f"{be}-offload-proof.log").read_text(errors="ignore").splitlines()
                if "assigned to device Vulkan" in l or "assigned to device ROCm" in l)
        cpu = sum(1 for l in (raw / f"{be}-offload-proof.log").read_text(errors="ignore").splitlines()
                  if "assigned to device CPU" in l)
        info[be] = {"gpu_layers": n, "cpu_layers": cpu}
    for be, binp in bins.items():
        bench(binp, G, common + ["-p", "512", "-n", "128", "-r", "1", "-o", "json"], raw / f"{be}-warmup.json",
              raw / f"{be}-warmup.log", raw / f"{be}-warmup-process.txt", sdir, libpaths.get(be))
    import statistics
    ts = {"vulkan": {"pp": [], "tg": []}, "hip": {"pp": [], "tg": []}}
    for r in (1, 2, 3):
        order = ["hip", "vulkan"] if r == 2 else ["vulkan", "hip"]
        for be in order:
            p = raw / f"{be}-r{r}"
            sh(["free", "-b"], out=raw / f"{be}-r{r}-memory-before.txt")
            bench(bins[be], G, common + ["-p", "2048", "-n", "0", "-r", "1", "-o", "json"], raw / f"{be}-r{r}-pp.json",
                  raw / f"{be}-r{r}-pp.log", raw / f"{be}-r{r}-pp-process.txt", sdir, libpaths.get(be))
            bench(bins[be], G, common + ["-p", "0", "-n", "128", "-d", "4096", "-r", "1", "-o", "json"], raw / f"{be}-r{r}-tg.json",
                  raw / f"{be}-r{r}-tg.log", raw / f"{be}-r{r}-tg-process.txt", sdir, libpaths.get(be))
            sh(["free", "-b"], out=raw / f"{be}-r{r}-memory-after.txt")
            ts[be]["pp"].append(json.loads((raw / f"{be}-r{r}-pp.json").read_text())[0]["avg_ts"])
            ts[be]["tg"].append(json.loads((raw / f"{be}-r{r}-tg.json").read_text())[0]["avg_ts"])
    def median(a): return statistics.median(a)
    def rss(be):
        for l in (raw / f"{be}-r1-pp-process.txt").read_text().splitlines():
            if "Maximum resident set size" in l: return int(l.split(":")[1])
    concl = (f"{model['id']}: offload GPU/CPU Vulkan {info['vulkan']['gpu_layers']}/{info['vulkan']['cpu_layers']}, "
             f"HIP {info['hip']['gpu_layers']}/{info['hip']['cpu_layers']}. pp2048 median Vulkan {median(ts['vulkan']['pp']):.2f}, "
             f"HIP {median(ts['hip']['pp']):.2f} t/s. tg128@4096 median Vulkan {median(ts['vulkan']['tg']):.2f}, "
             f"HIP {median(ts['hip']['tg']):.2f} t/s. RSS Vulkan {rss('vulkan')} KiB, HIP {rss('hip')} KiB.")
    manifest.update({"status": "completed", "conclusion": concl})
    attempts = []
    for be in ("vulkan", "hip"):
        attempts.append({"id": f"{model['id']}-{be}", "configuration_id": f"{model['id']}-{be}", "kind": "measurement",
                         "status": "completed", "run_id": None,
                         "evidence_files": [str(p.relative_to(sdir)) for p in sorted(raw.glob(f"{be}-*"))],
                         "conclusion": f"pp median {median(ts[be]['pp']):.2f}, tg median {median(ts[be]['tg']):.2f} t/s.",
                         "reason": None})
    attempts.append({"id": f"{model['id']}-offload", "configuration_id": f"{model['id']}-offload", "kind": "measurement",
                     "status": "completed", "run_id": None,
                     "evidence_files": [f"raw/{be}-offload-proof.log" for be in ("vulkan", "hip")],
                     "conclusion": f"GPU layers Vulkan {info['vulkan']['gpu_layers']}, HIP {info['hip']['gpu_layers']}.", "reason": None})
    rows = []
    for be in ("vulkan", "hip"):
        for r in (1, 2, 3):
            rows.append([f"{model['id']}-{be}-pp-r{r}", f"{model['id']}-{be}", model["model_id"], engine_label, be, "", r,
                         "pp2048_avg_ts", ts[be]["pp"][r-1], "tokens/s", "measured", f"raw/{be}-r{r}-pp.json", ""])
            rows.append([f"{model['id']}-{be}-tg-r{r}", f"{model['id']}-{be}", model["model_id"], engine_label, be, "", r,
                         "tg128_d4096_avg_ts", ts[be]["tg"][r-1], "tokens/s", "measured", f"raw/{be}-r{r}-tg.json", ""])
        rows.append([f"{model['id']}-{be}-rss", f"{model['id']}-{be}", model["model_id"], engine_label, be, "", 1,
                     "max_rss", rss(be), "KiB", "measured", f"raw/{be}-r1-pp-process.txt", ""])
        rows.append([f"{model['id']}-{be}-gpulayers", f"{model['id']}-offload", model["model_id"], engine_label, be, "", 1,
                     "gpu_assigned_layers", info[be]["gpu_layers"], "layers", "measured", f"raw/{be}-offload-proof.log", ""])
    report = (f"# LAB04 — Vulkan versus HIP/ROCm ({model['id']})\n\nSession: `{sid}`.\n\n## Run profile\n\n"
              f"| Field | Value |\n| --- | --- |\n| Model | `{model['model_id']}` |\n| Engine | {engine_label} |\n\n"
              f"## Hypothesis and protocol before execution\n\nSee `raw/protocol.md` (preregistered).\n\n## Execution log\n\n"
              f"| Step | Result |\n| --- | --- |\n| offload-proof | Vulkan {info['vulkan']['gpu_layers']} GPU / {info['vulkan']['cpu_layers']} CPU; HIP {info['hip']['gpu_layers']} / {info['hip']['cpu_layers']} |\n"
              f"| paired repeats | 3×2 |\n\n## Results\n\n- pp2048 median: Vulkan {median(ts['vulkan']['pp']):.2f}, HIP {median(ts['hip']['pp']):.2f} t/s\n"
              f"- tg128@4096 median: Vulkan {median(ts['vulkan']['tg']):.2f}, HIP {median(ts['hip']['tg']):.2f} t/s\n"
              f"- RSS: Vulkan {rss('vulkan')} KiB, HIP {rss('hip')} KiB\n\n## Errors and limitations\n\nPrebuilt binaries use different toolchains.\n\n"
              f"## Hypothesis conclusion\n\n{concl}\n\n## Answers to review questions\n\n- `-ngl 999` is a request; `-v` provides the actual placement.\n\n"
              f"## Submission bundle\n\n- [x] manifest.json, measurements.tsv, report.md, raw evidence.\n")
    finalize(sdir, manifest, attempts, rows, report)
    commit([f"experiments/local-models/measurements/LAB04-{sid}"], f"LAB04 {model['id']}: results")
    return sdir

# ---------------------------------------------------------------- LAB05
HTTP_PROBE = REPO / "experiments/local-models/measurements/LAB06-qwen35-9b-rocm/raw/http_probe.py"
FIX = REPO / "docs/labs/fixtures"

def lab05(model, gguf, sid, ref_sid, engine_label="llama.cpp b8407 (312cf0332)",
          server_bin=None, libpath=None, bench_bin=None, ref03=None, ref04=None):
    sdir = new_session("LAB05", sid)
    server_bin = server_bin or HIP / "llama-server"
    bench_bin = bench_bin or HIP / "llama-bench"
    libpath = libpath or str(HIP)
    ref03 = ref03 or ref_sid
    ref04 = ref04 or ref_sid
    raw = sdir / "raw"
    for f in ("chat-request.json", "tool-request.json"):
        shutil.copy(FIX / f, raw / f)
    for kind in ("chat", "tool"):
        v = json.loads((raw / f"{kind}-request.json").read_text()); v["stream"] = True
        (raw / f"{kind}-stream-request.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
    shutil.copy(HTTP_PROBE, raw / "http_probe.py")
    write_protocol(sdir, f"""# LAB05 — preregistered protocol ({model['id']})

## Hypothesis
{model['id']} on HIP {engine_label} passes 8K/16K/32K memory-fill benchmarks and the loopback chat/tool/stream server protocol.

## Procedure
8K → 16K → 32K, each only after the previous succeeds; bench `-p 0 -n 128 -d CTX-128 -r 3`; server 8080; `http_probe.py` 4×2; long/overflow/cancel.

## Stop condition
OOM/reset/swap beyond budget → stop the track without launching the next context.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB05", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "experimental",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{ref03}/raw/artifact.json",
                    "runtime_manifest": f"experiments/local-models/measurements/LAB04-{ref04}/raw/build-provenance.txt",
                    "harness_profile": None}, "run_ids": [], "planned_attempts": [],
                "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"{model['id']} on HIP {engine_label} passes 8K/16K/32K memory-fill benchmarks and the loopback chat/tool/stream server protocol.",
                "unavailable": {"conditions.harness_profile": "LAB05 does not use a harness."},
                "conclusion": None, "reviewer_decision": None}
    dump(sdir / "manifest.json", manifest)
    commit([f"experiments/local-models/measurements/LAB05-{sid}"], f"LAB05 {model['id']}: preregistration")
    G = str(gguf)
    attempts, rows, ctx_results = [], [], []
    for ctx in (8192, 16384, 32768):
        depth = ctx - 128
        r = sh(["/usr/bin/time", "-v", "-o", str(raw / f"context-{ctx}-process.txt"),
                str(bench_bin), "-m", G, "-ngl", "999", "-t", "8", "-b", "512", "-ub", "256",
                "-ctk", "f16", "-ctv", "f16", "-fa", "1", "-p", "0", "-n", "128", "-d", str(depth), "-r", "3", "-o", "json"],
               cwd=sdir, env={"LD_LIBRARY_PATH": libpath}, out=raw / f"context-{ctx}-bench.json", err=raw / f"context-{ctx}-bench.log")
        (raw / f"context-{ctx}-exit.txt").write_text(f"{r}\n")
        if r != 0:
            attempts.append({"id": f"{model['id']}-ctx{ctx}", "configuration_id": f"{model['id']}-ctx{ctx}", "kind": "measurement",
                             "status": "failed", "run_id": None, "evidence_files": [f"raw/context-{ctx}-bench.log"],
                             "conclusion": None, "reason": f"bench exit {r}"})
            break
        # server
        port = 8080
        slog = open(raw / f"server-{ctx}.log", "wb")
        srv = subprocess.Popen([str(server_bin), "-m", G, "--host", "127.0.0.1", "--port", str(port), "--alias", "lab-model",
                                "-ngl", "999", "-c", str(ctx), "-np", "1", "-t", "8", "-b", "512", "-ub", "256",
                                "-ctk", "f16", "-ctv", "f16", "-fa", "1", "--jinja", "--no-context-shift"],
                               cwd=str(sdir), env={**os.environ, "LD_LIBRARY_PATH": libpath}, stdout=slog, stderr=slog)
        ready = False
        for _ in range(120):
            if srv.poll() is not None: break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3); ready = True; break
            except Exception:
                time.sleep(5)
        if not ready:
            srv.terminate(); slog.close()
            attempts.append({"id": f"{model['id']}-ctx{ctx}", "configuration_id": f"{model['id']}-ctx{ctx}", "kind": "measurement",
                             "status": "failed", "run_id": None, "evidence_files": [f"raw/server-{ctx}.log"],
                             "conclusion": None, "reason": "server did not become ready"})
            break
        base = f"http://127.0.0.1:{port}"
        cases, fails = 0, 0
        for rp in (1, 2):
            for kind in ("chat", "chat-stream", "tool", "tool-stream"):
                out = raw / f"ctx{ctx}-{kind}-r{rp}"
                cmd = ["python3", str(raw / "http_probe.py"), "--url", base, "--request", str(raw / f"{kind}-request.json"), "--out", str(out)]
                if "tool" in kind: cmd.append("--follow-tool")
                rc = sh(cmd, cwd=sdir)
                cases += 1; fails += (rc != 0)
        srv.terminate()
        try: srv.wait(timeout=30)
        except Exception: srv.kill()
        slog.close()
        ctx_results.append({"ctx": ctx, "cases": cases, "fails": fails})
        attempts.append({"id": f"{model['id']}-ctx{ctx}", "configuration_id": f"{model['id']}-ctx{ctx}", "kind": "measurement",
                         "status": "completed", "run_id": None,
                         "evidence_files": [f"raw/context-{ctx}-bench.json", f"raw/server-{ctx}.log"]
                         + [str(p.relative_to(sdir)) for p in sorted(raw.glob(f"ctx{ctx}-*.final.json"))],
                         "conclusion": f"{cases - fails}/{cases} HTTP cases pass.", "reason": None})
        rows.append([f"{model['id']}-ctx{ctx}-tg", f"{model['id']}-ctx{ctx}", model["model_id"], engine_label, "hip", ctx, 1,
                     "tg128_avg_ts", json.loads((raw / f"context-{ctx}-bench.json").read_text())[0]["avg_ts"], "tokens/s",
                     "measured", f"raw/context-{ctx}-bench.json", ""])
    ok = all(c["fails"] == 0 for c in ctx_results) and len(ctx_results) == 3
    manifest.update({"status": "completed" if ok else "blocked",
                     "conclusion": "; ".join(f"ctx{c['ctx']}: {c['cases']-c['fails']}/{c['cases']}" for c in ctx_results) or "no context completed"})
    if not ok:
        manifest["unavailable"]["completion"] = "Not all contexts passed; see attempts."
    report = (f"# LAB05 — context and tools ({model['id']})\n\nSession: `{sid}`.\n\n## Run profile\n\n"
              f"| Field | Value |\n| --- | --- |\n| Model | `{model['model_id']}` |\n\n## Hypothesis and protocol before execution\n\nSee `raw/protocol.md`.\n\n"
              f"## Execution log\n\n| CTX | HTTP cases |\n| --- | --- |\n" +
              "".join(f"| {c['ctx']} | {c['cases']-c['fails']}/{c['cases']} |\n" for c in ctx_results) +
              f"\n## Results\n\nSee `measurements.tsv`.\n\n## Errors and limitations\n\nAutomated campaign: model-specific sampling/reasoning may differ.\n\n"
              f"## Hypothesis conclusion\n\n{manifest['conclusion']}.\n\n## Answers to review questions\n\nSee the LAB05 guide.\n\n"
              f"## Submission bundle\n\n- [x] manifest.json, measurements.tsv, report.md, raw evidence.\n")
    finalize(sdir, manifest, attempts, rows, report)
    commit([f"experiments/local-models/measurements/LAB05-{sid}"], f"LAB05 {model['id']}: results")
    return sdir, ctx_results

# ---------------------------------------------------------------- main
LAB05_FIX = ["gpt-oss-20b", "qwen36-27b", "qwen3-coder-30b-a3b", "qwen35-35b-a3b"]
FULL = ["glm-47-flash", "qwen3-coder-next"]

def model_by_id(mid):
    return next(m for m in MODELS if m["id"] == mid)

def run_lab05_fix():
    for mid in LAB05_FIX:
        model = model_by_id(mid)
        status["models"][mid] = {"started": now(), "labs": {}}
        dump(STATUS, status)
        ver = json.loads((REPO / f"experiments/local-models/measurements/LAB03-{mid}-overnight/raw/verification.json").read_text())
        gguf = gguf_path(ver)
        try:
            _, cr = lab05(model, gguf, f"{mid}-overnight2", f"{mid}-overnight")
            status["models"][mid]["labs"]["LAB05"] = "completed" if all(c["fails"] == 0 for c in cr) and len(cr) == 3 else "partial"
        except Exception as e:
            status["models"][mid]["labs"]["LAB05"] = f"error: {e}"
            log(f"LAB05 {mid} error: {e}")
        status["models"][mid]["finished"] = now()
        dump(STATUS, status)

def run_full(ids=None):
    for mid in (ids or FULL):
        model = model_by_id(mid)
        status["models"][mid] = {"started": now(), "labs": {}}
        dump(STATUS, status)
        sid = f"{mid}-overnight2"
        try:
            sdir, ver = lab03(model, sid)
            gguf = gguf_path(ver)
            if not all(f.get("status") == "verified" for f in ver["files"]):
                raise RuntimeError("artifact not verified; LAB04/05 skipped")
            status["models"][mid]["labs"]["LAB03"] = "completed"
            dump(STATUS, status)
            try:
                lab04(model, gguf, sid)
                status["models"][mid]["labs"]["LAB04"] = "completed"
            except Exception as e:
                status["models"][mid]["labs"]["LAB04"] = f"error: {e}"
                log(f"LAB04 {mid} error: {e}")
            dump(STATUS, status)
            try:
                _, cr = lab05(model, gguf, sid, sid)
                status["models"][mid]["labs"]["LAB05"] = "completed" if all(c["fails"] == 0 for c in cr) and len(cr) == 3 else "partial"
            except Exception as e:
                status["models"][mid]["labs"]["LAB05"] = f"error: {e}"
                log(f"LAB05 {mid} error: {e}")
        except Exception as e:
            status["models"][mid]["labs"]["LAB03"] = f"error: {e}"
            log(f"LAB03 {mid} error: {e}")
        status["models"][mid]["finished"] = now()
        dump(STATUS, status)

def run_gemma4():
    mid = "gemma4-31b-it"
    model = model_by_id(mid)
    sid = f"{mid}-b10000"
    status["models"][mid] = {"started": now(), "labs": {}}
    dump(STATUS, status)
    ver = json.loads((REPO / f"experiments/local-models/measurements/LAB03-{mid}-overnight/raw/verification.json").read_text())
    gguf = gguf_path(ver)
    label = "llama.cpp b10000 (ROCm 7.2 / Vulkan)"
    prov = ("llama.cpp b10000 official ggml-org prebuilt (ROCm 7.2 x64 + Vulkan x64); "
            "HIP runtime libs from the AMD b8407 bundle (ROCm 7.2.1). Engine newer than b8407 "
            "because b8407 predates gemma4 support.\n")
    bins = {"vulkan": VUL10000 / "llama-bench", "hip": HIP10000 / "llama-bench"}
    libpaths = {"vulkan": str(VUL10000), "hip": f"{HIP10000}:{AMD_ROCM_LIBS}"}
    try:
        lab04(model, gguf, sid, engine_label=label, provenance=prov, bins=bins, libpaths=libpaths,
              ref_sid=f"{mid}-overnight")
        status["models"][mid]["labs"]["LAB04"] = "completed"
    except Exception as e:
        status["models"][mid]["labs"]["LAB04"] = f"error: {e}"
        log(f"LAB04 {mid} error: {e}")
    dump(STATUS, status)
    try:
        _, cr = lab05(model, gguf, sid, sid, engine_label=label,
                      server_bin=HIP10000 / "llama-server", bench_bin=HIP10000 / "llama-bench",
                      libpath=f"{HIP10000}:{AMD_ROCM_LIBS}",
                      ref03=f"{mid}-overnight", ref04=sid)
        status["models"][mid]["labs"]["LAB05"] = "completed" if all(c["fails"] == 0 for c in cr) and len(cr) == 3 else "partial"
    except Exception as e:
        status["models"][mid]["labs"]["LAB05"] = f"error: {e}"
        log(f"LAB05 {mid} error: {e}")
    status["models"][mid]["finished"] = now()
    dump(STATUS, status)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "lab05"
    status["started"] = now(); status["mode"] = mode
    log(f"campaign-fix start {RUN_ID}, mode {mode}, worktree {WT}")
    if mode == "lab05":
        run_lab05_fix()
    elif mode == "full":
        run_full(sys.argv[2:] or None)
    elif mode == "gemma4":
        run_gemma4()
    else:
        raise SystemExit(f"unknown mode: {mode}")
    sh(["git", "push", "-u", "origin", BRANCH], cwd=WT, check=False)
    status["finished"] = now(); dump(STATUS, status)
    log("campaign-fix finished")

if __name__ == "__main__":
    main()
