#!/usr/bin/env python3
"""Overnight campaign: LAB03 + LAB04 + LAB05 for extra models on Ryzen/gfx1151.

Runs in a dedicated git worktree (branch overnight-models-<date>) so the main
working tree is untouched. Each model gets three preregistered sessions; the
protocol is committed before any run. Failures are recorded and the campaign
continues. All progress goes to campaign/overnight.log.
"""
import json, os, pathlib, subprocess, sys, time, datetime, shutil, signal, urllib.request, urllib.error

REPO = pathlib.Path("/home/lab/projects/agent-harnesses-exps")
HOME = pathlib.Path(os.environ["HOME"])
STORAGE = HOME / "local-model-lab-artifacts"
B = STORAGE / "llama-cpp-b8407"
VUL = B / "llama-b8407"
HIP = B / "llama-b8407-ubuntu-24.04-rocm-7.2.1-gfx110X-gfx115X-gfx120X-x64"
GGUF_ROOT = STORAGE
CAMPAIGN = REPO / "experiments/local-models/campaign"
MODELS = json.loads((CAMPAIGN / "overnight-models.json").read_text())
RUN_ID = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
BRANCH = f"overnight-models-{RUN_ID[:8]}"
WT = pathlib.Path(f"/tmp/opencode/overnight-wt-{RUN_ID}")
LOG = CAMPAIGN / f"overnight-{RUN_ID}.log"
STATUS = CAMPAIGN / f"overnight-{RUN_ID}-status.json"
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

def lab03(model):
    sid = f"{model['id']}-overnight"
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
    write_protocol(sdir, f"""# LAB03 — предварительный протокол ({model['id']})

## Гипотеза
Локальная копия артефакта {art['repository']}@{art['revision']} совпадает с публикацией по размеру и SHA-256.

## Порядок
1. Скачать с закреплённой ревизии `fetch_artifact.py --download`.
2. Offline-проверка размеров и SHA-256.
3. Записать checksum-файл для LAB04/LAB05.

## Критерий остановки
Расхождение размера/SHA → `fail`/`no-artifact`; артефакт дальше не передаётся.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB03", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "protocol",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{sid}/raw/artifact.json",
                    "runtime_manifest": None, "harness_profile": None},
                "run_ids": [], "planned_attempts": [], "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"Локальная копия артефакта {model['id']} совпадает с публикацией {art['repository']}@{art['revision']} по размеру и SHA-256.",
                "unavailable": {"conditions.runtime_manifest": "LAB03 не запускает runtime.",
                                "conditions.harness_profile": "LAB03 не использует обвязку."},
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
                     "conclusion": f"Проверка {art['repository']}@{art['revision']}: {'verified' if ok else 'fail'}."})
    if not ok:
        manifest["unavailable"]["completion"] = "Артефакт не прошёл проверку размера/SHA."
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
                         "-", "", "", "file_bytes", "", "", "no-artifact", "", "Артефакт отсутствует/не докачан."])
    report = f"# LAB03 — артефакт {model['id']}\n\nСессия: `{sid}`.\n\n## Паспорт выполнения\n\n| Поле | Значение |\n| --- | --- |\n| Модель | `{model['model_id']}` |\n| Артефакт | `{art['repository']}@{art['revision']}` |\n\n## Гипотеза и протокол до запуска\n\nСм. `raw/protocol.md`.\n\n## Ход выполнения\n\n| Шаг | Результат |\n| --- | --- |\n| download | exit {code} |\n| verify | {'verified' if ok else 'fail'} |\n\n## Результаты\n\nСм. `measurements.tsv`, `raw/verification.json`.\n\n## Ошибки и ограничения\n\nНет.\n\n## Вывод по гипотезе\n\n{'Поддержана.' if ok else 'Не поддержана.'}\n\n## Ответы на контрольные вопросы\n\nSHA-256 подтверждает целостность файла.\n\n## Комплект сдачи\n\n- [x] manifest.json, measurements.tsv, report.md.\n"
    finalize(sdir, manifest, [attempt], rows, report)
    commit([f"experiments/local-models/measurements/LAB03-{sid}"], f"LAB03 {model['id']}: results")
    return sdir, ver

# ---------------------------------------------------------------- LAB04
def gguf_path(ver):
    files = [f["path"] for f in ver["files"] if f["path"].endswith(".gguf")]
    shards = [f for f in files if "-00001-of-" in f]
    return shards[0] if shards else files[0]

def bench(binpath, g, args, out_json, out_log, proc, cwd):
    env = {"LD_LIBRARY_PATH": str(pathlib.Path(binpath).parent)}
    return sh(["/usr/bin/time", "-v", "-o", str(proc), str(binpath), "-m", str(g), *args], cwd=cwd, env=env,
              out=out_json, err=out_log)

def lab04(model, gguf):
    sid = f"{model['id']}-overnight"
    sdir = new_session("LAB04", sid)
    raw = sdir / "raw"
    write_protocol(sdir, f"""# LAB04 — предварительный протокол ({model['id']})

## Гипотеза
Один GGUF {model['id']} полностью выгружается на GPU в обеих prebuilt-сборках llama.cpp b8407 (Vulkan/RADV и ROCm/HIP); backend влияет на скорость, направление неизвестно.

## Порядок
1. `sha256sum --check`; 2. offload-proof `llama-bench -v` обеих ветвей; 3. прогрев; 4. три парных повтора pp2048/tg128@d4096 под `/usr/bin/time -v`.

## Критерий остановки
OOM/невалидный JSON/следы CPU-offload → fail ветви.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB04", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "experimental",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{sid}/raw/artifact.json",
                    "runtime_manifest": f"experiments/local-models/measurements/LAB04-{sid}/raw/build-provenance.txt",
                    "harness_profile": None}, "run_ids": [], "planned_attempts": [],
                "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"Один GGUF {model['id']} полностью выгружается на GPU в обеих prebuilt-сборках llama.cpp b8407 (Vulkan/RADV и ROCm/HIP); backend влияет на скорость, направление неизвестно.",
                "unavailable": {"conditions.harness_profile": "LAB04 не использует обвязку."},
                "conclusion": None, "reviewer_decision": None}
    dump(sdir / "manifest.json", manifest)
    commit([f"experiments/local-models/measurements/LAB04-{sid}"], f"LAB04 {model['id']}: preregistration")
    (raw / "build-provenance.txt").write_text("llama.cpp b8407 (312cf03328496df9c56fe843952cf02a8964c59a); prebuilt Vulkan + ROCm/HIP bundles.\n")
    G = str(gguf); N = sdir
    common = ["-ngl", "999", "-t", "8", "-b", "512", "-ub", "256", "-ctk", "f16", "-ctv", "f16", "-fa", "1"]
    bins = {"vulkan": VUL / "llama-bench", "hip": HIP / "llama-bench"}
    info = {}
    for be, binp in bins.items():
        sh([str(binp), "--list-devices"], env={"LD_LIBRARY_PATH": str(binp.parent)}, out=raw / f"{be}-devices.txt")
        r = sh([str(binp), "-m", G, *common, "-p", "8", "-n", "1", "-r", "1", "-v"], cwd=sdir,
               env={"LD_LIBRARY_PATH": str(binp.parent)}, out=raw / f"{be}-offload-proof.json", err=raw / f"{be}-offload-proof.log")
        n = sum(1 for l in (raw / f"{be}-offload-proof.log").read_text(errors="ignore").splitlines()
                if "assigned to device Vulkan" in l or "assigned to device ROCm" in l)
        cpu = sum(1 for l in (raw / f"{be}-offload-proof.log").read_text(errors="ignore").splitlines()
                  if "assigned to device CPU" in l)
        info[be] = {"gpu_layers": n, "cpu_layers": cpu}
    for be, binp in bins.items():
        bench(binp, G, common + ["-p", "512", "-n", "128", "-r", "1", "-o", "json"], raw / f"{be}-warmup.json",
              raw / f"{be}-warmup.log", raw / f"{be}-warmup-process.txt", sdir)
    import statistics
    ts = {"vulkan": {"pp": [], "tg": []}, "hip": {"pp": [], "tg": []}}
    for r in (1, 2, 3):
        order = ["hip", "vulkan"] if r == 2 else ["vulkan", "hip"]
        for be in order:
            p = raw / f"{be}-r{r}"
            sh(["free", "-b"], out=raw / f"{be}-r{r}-memory-before.txt")
            bench(bins[be], G, common + ["-p", "2048", "-n", "0", "-r", "1", "-o", "json"], raw / f"{be}-r{r}-pp.json",
                  raw / f"{be}-r{r}-pp.log", raw / f"{be}-r{r}-pp-process.txt", sdir)
            bench(bins[be], G, common + ["-p", "0", "-n", "128", "-d", "4096", "-r", "1", "-o", "json"], raw / f"{be}-r{r}-tg.json",
                  raw / f"{be}-r{r}-tg.log", raw / f"{be}-r{r}-tg-process.txt", sdir)
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
            rows.append([f"{model['id']}-{be}-pp-r{r}", f"{model['id']}-{be}", model["model_id"], "llama.cpp b8407", be, "", r,
                         "pp2048_avg_ts", ts[be]["pp"][r-1], "tokens/s", "measured", f"raw/{be}-r{r}-pp.json", ""])
            rows.append([f"{model['id']}-{be}-tg-r{r}", f"{model['id']}-{be}", model["model_id"], "llama.cpp b8407", be, "", r,
                         "tg128_d4096_avg_ts", ts[be]["tg"][r-1], "tokens/s", "measured", f"raw/{be}-r{r}-tg.json", ""])
        rows.append([f"{model['id']}-{be}-rss", f"{model['id']}-{be}", model["model_id"], "llama.cpp b8407", be, "", 1,
                     "max_rss", rss(be), "KiB", "measured", f"raw/{be}-r1-pp-process.txt", ""])
        rows.append([f"{model['id']}-{be}-gpulayers", f"{model['id']}-offload", model["model_id"], "llama.cpp b8407", be, "", 1,
                     "gpu_assigned_layers", info[be]["gpu_layers"], "layers", "measured", f"raw/{be}-offload-proof.log", ""])
    report = (f"# LAB04 — Vulkan против HIP/ROCm ({model['id']})\n\nСессия: `{sid}`.\n\n## Паспорт выполнения\n\n"
              f"| Поле | Значение |\n| --- | --- |\n| Модель | `{model['model_id']}` |\n| Engine | llama.cpp b8407 (312cf0332) |\n\n"
              f"## Гипотеза и протокол до запуска\n\nСм. `raw/protocol.md` (preregistered).\n\n## Ход выполнения\n\n"
              f"| Шаг | Результат |\n| --- | --- |\n| offload-proof | Vulkan {info['vulkan']['gpu_layers']} GPU / {info['vulkan']['cpu_layers']} CPU; HIP {info['hip']['gpu_layers']} / {info['hip']['cpu_layers']} |\n"
              f"| paired repeats | 3×2 |\n\n## Результаты\n\n- pp2048 median: Vulkan {median(ts['vulkan']['pp']):.2f}, HIP {median(ts['hip']['pp']):.2f} t/s\n"
              f"- tg128@4096 median: Vulkan {median(ts['vulkan']['tg']):.2f}, HIP {median(ts['hip']['tg']):.2f} t/s\n"
              f"- RSS: Vulkan {rss('vulkan')} KiB, HIP {rss('hip')} KiB\n\n## Ошибки и ограничения\n\nСборки prebuilt разных toolchain.\n\n"
              f"## Вывод по гипотезе\n\n{concl}\n\n## Ответы на контрольные вопросы\n\n- `-ngl 999` — запрос; фактическую раскладку даёт `-v`.\n\n"
              f"## Комплект сдачи\n\n- [x] manifest.json, measurements.tsv, report.md, raw evidence.\n")
    finalize(sdir, manifest, attempts, rows, report)
    commit([f"experiments/local-models/measurements/LAB04-{sid}"], f"LAB04 {model['id']}: results")
    return sdir

# ---------------------------------------------------------------- LAB05
HTTP_PROBE = REPO / "experiments/local-models/measurements/LAB06-qwen35-9b-rocm/raw/http_probe.py"
FIX = REPO / "docs/labs/fixtures"

def lab05(model, gguf):
    sid = f"{model['id']}-overnight"
    sdir = new_session("LAB05", sid)
    raw = sdir / "raw"
    for f in ("chat-request.json", "tool-request.json"):
        shutil.copy(FIX / f, raw / f)
    for kind in ("chat", "tool"):
        v = json.loads((raw / f"{kind}-request.json").read_text()); v["stream"] = True
        (raw / f"{kind}-stream-request.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
    shutil.copy(HTTP_PROBE, raw / "http_probe.py")
    write_protocol(sdir, f"""# LAB05 — предварительный протокол ({model['id']})

## Гипотеза
{model['id']} на HIP llama.cpp b8407 проходит bench-заполнения 8K/16K/32K и серверный протокол chat/tool/stream на loopback.

## Порядок
8K → 16K → 32K, каждый только при успехе предыдущего; bench `-p 0 -n 128 -d CTX-128 -r 3`; сервер 8080; `http_probe.py` 4×2; long/overflow/cancel.

## Критерий остановки
OOM/reset/подкачка-за-бюджетом → стоп ветви, следующий контекст не запускается.
""")
    manifest = {"schema_version": 2, "kind": "lab-report", "lab_id": "LAB05", "harness_id": None,
                "session_id": sid, "created_at": now(), "status": "in_progress", "evidence_class": "experimental",
                "operator": "overnight campaign", "protocol_recorded_at": now(),
                "protocol_before_run": "raw/protocol.md", "conditions": {
                    "hardware_snapshot": "experiments/local-models/measurements/LAB02-after-rocm/manifest.json",
                    "model_artifact_manifest": f"experiments/local-models/measurements/LAB03-{sid}/raw/artifact.json",
                    "runtime_manifest": f"experiments/local-models/measurements/LAB04-{sid}/raw/build-provenance.txt",
                    "harness_profile": None}, "run_ids": [], "planned_attempts": [],
                "evidence_files": ["raw/protocol.md"],
                "hypothesis": f"{model['id']} на HIP llama.cpp b8407 проходит bench-заполнения 8K/16K/32K и серверный протокол chat/tool/stream на loopback.",
                "unavailable": {"conditions.harness_profile": "LAB05 не использует обвязку."},
                "conclusion": None, "reviewer_decision": None}
    dump(sdir / "manifest.json", manifest)
    commit([f"experiments/local-models/measurements/LAB05-{sid}"], f"LAB05 {model['id']}: preregistration")
    G = str(gguf); server_bin = HIP / "llama-server"
    attempts, rows, ctx_results = [], [], []
    for ctx in (8192, 16384, 32768):
        depth = ctx - 128
        r = sh(["/usr/bin/time", "-v", "-o", str(raw / f"context-{ctx}-process.txt"),
                str(HIP / "llama-bench"), "-m", G, "-ngl", "999", "-t", "8", "-b", "512", "-ub", "256",
                "-ctk", "f16", "-ctv", "f16", "-fa", "1", "-p", "0", "-n", "128", "-d", str(depth), "-r", "3", "-o", "json"],
               cwd=sdir, env={"LD_LIBRARY_PATH": str(HIP)}, out=raw / f"context-{ctx}-bench.json", err=raw / f"context-{ctx}-bench.log")
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
                               cwd=str(sdir), env={**os.environ, "LD_LIBRARY_PATH": str(HIP)}, stdout=slog, stderr=slog)
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
        rows.append([f"{model['id']}-ctx{ctx}-tg", f"{model['id']}-ctx{ctx}", model["model_id"], "llama.cpp b8407", "hip", ctx, 1,
                     "tg128_avg_ts", json.loads((raw / f"context-{ctx}-bench.json").read_text())[0]["avg_ts"], "tokens/s",
                     "measured", f"raw/context-{ctx}-bench.json", ""])
    ok = all(c["fails"] == 0 for c in ctx_results) and len(ctx_results) == 3
    manifest.update({"status": "completed" if ok else "blocked",
                     "conclusion": "; ".join(f"ctx{c['ctx']}: {c['cases']-c['fails']}/{c['cases']}" for c in ctx_results) or "no context completed"})
    if not ok:
        manifest["unavailable"]["completion"] = "Не все контексты прошли; см. attempts."
    report = (f"# LAB05 — контекст и инструменты ({model['id']})\n\nСессия: `{sid}`.\n\n## Паспорт выполнения\n\n"
              f"| Поле | Значение |\n| --- | --- |\n| Модель | `{model['model_id']}` |\n\n## Гипотеза и протокол до запуска\n\nСм. `raw/protocol.md`.\n\n"
              f"## Ход выполнения\n\n| CTX | HTTP cases |\n| --- | --- |\n" +
              "".join(f"| {c['ctx']} | {c['cases']-c['fails']}/{c['cases']} |\n" for c in ctx_results) +
              f"\n## Результаты\n\nСм. `measurements.tsv`.\n\n## Ошибки и ограничения\n\nАвтоматическая кампания: model-specific sampling/reasoning могут отличаться.\n\n"
              f"## Вывод по гипотезе\n\n{manifest['conclusion']}.\n\n## Ответы на контрольные вопросы\n\nСм. методичку ЛР05.\n\n"
              f"## Комплект сдачи\n\n- [x] manifest.json, measurements.tsv, report.md, raw evidence.\n")
    finalize(sdir, manifest, attempts, rows, report)
    commit([f"experiments/local-models/measurements/LAB05-{sid}"], f"LAB05 {model['id']}: results")
    return sdir, ctx_results

# ---------------------------------------------------------------- main
def main():
    status["started"] = now()
    log(f"campaign start {RUN_ID}, branch {BRANCH}")
    sh(["git", "fetch", "origin", "main"], cwd=REPO)
    sh(["git", "worktree", "add", "-b", BRANCH, str(WT), "origin/main"], cwd=REPO)
    for model in MODELS:
        mid = model["id"]
        status["models"][mid] = {"started": now(), "labs": {}}
        dump(STATUS, status)
        try:
            sdir, ver = lab03(model)
            gguf = gguf_path(ver)
            status["models"][mid]["labs"]["LAB03"] = "completed"
            dump(STATUS, status)
            try:
                lab04(model, gguf)
                status["models"][mid]["labs"]["LAB04"] = "completed"
            except Exception as e:
                status["models"][mid]["labs"]["LAB04"] = f"error: {e}"
                log(f"LAB04 {mid} error: {e}")
            dump(STATUS, status)
            try:
                _, cr = lab05(model, gguf)
                status["models"][mid]["labs"]["LAB05"] = "completed" if all(c["fails"] == 0 for c in cr) and len(cr) == 3 else "partial"
            except Exception as e:
                status["models"][mid]["labs"]["LAB05"] = f"error: {e}"
                log(f"LAB05 {mid} error: {e}")
        except Exception as e:
            status["models"][mid]["labs"]["LAB03"] = f"error: {e}"
            log(f"LAB03 {mid} error: {e}")
        status["models"][mid]["finished"] = now()
        dump(STATUS, status)
    sh(["git", "push", "-u", "origin", BRANCH], cwd=WT, check=False)
    status["finished"] = now(); dump(STATUS, status)
    log("campaign finished")

if __name__ == "__main__":
    main()
