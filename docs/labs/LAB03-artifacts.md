# LAB03. Model selection and artifact pinning

## Profile

- Time: 1–2 hours of work plus downloading the selected weights.
- Prerequisites: [LAB01](LAB01-reproducibility.md) and [LAB02](LAB02-hardware.md) submitted; Python 3.11+, Node.js, and disk space available on the target Linux machine.
- Readiness: calculations and manifest preparation can be performed now; the lab participant downloads and verifies files. The repository contains no downloaded weights or hardware results.
- Minimum: estimate memory for all 12 candidates; download and verify **one** control GGUF, `qwen35-9b`. The second control, `gpt-oss-20b`, and other downloads are extensions.

## Objective

Obtain a verified local artifact that can be passed to several engines without silently changing weights, and justify the remaining model queue using the actual memory budget from LAB02.

## Hypothesis

“The selected shards match the pinned revision and SHA-256, and the control GGUF passes the preliminary memory budget at 8192 tokens and one sequence.” The first part is tested here; placement during actual inference is tested in LAB04–05. A positive estimate alone does not confirm GPU residency.

## Preparation

Work from the repository root in Bash. Create a report and specify a separate weights directory, preferably on the disk whose free space was measured in LAB02:

```bash
npm run lab:new -- --lab LAB03 --session my-session
export LAB_DIR="$PWD/experiments/local-models/measurements/LAB03-my-session"
export LAB_STORAGE="$HOME/local-model-lab-artifacts"
mkdir -p "$LAB_STORAGE"
df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-before.txt"
git rev-parse HEAD > "$LAB_DIR/raw/repository-revision.txt"
cp experiments/local-models/models.json "$LAB_DIR/raw/catalog.json"
cp experiments/local-models/hardware.json "$LAB_DIR/raw/planning-hardware.json"
```

The LAB02 profile and its measured `MemTotal`, `MemAvailable`, GPU heap/GTT, and swap must be referenced in `manifest.json`. Do not add CPU RAM to the GPU budget: these share the same UMA memory. By default, the planner uses **assumptions** of 119.2 GiB RAM, 89.4 GiB GPU budget, 16 GiB for the OS, 6 GiB runtime, and 4/8/16 GiB for 8K/16K/32K contexts. These are reserves, not calculations of a specific architecture's KV cache.

## Procedure

1. **Record the selection before downloading.** Save the overall plan:

   ```bash
   node scripts/local-plan.mjs --format json > "$LAB_DIR/raw/plan-default.json"
   node scripts/local-plan.mjs --model qwen35-9b --context 8192 --format json > "$LAB_DIR/raw/control-plan.json"
   ```

   If the LAB02 budget differs, repeat the command with `--memory-gib NUMBER --gpu-budget-gib NUMBER`, preserving a separate JSON and the exact command. Use numbers from the machine report; available memory and total capacity are different quantities. For each of the 12 models, record “first run / later / does not fit the selected budget” and a condition for reconsidering the decision.

   | Candidate | Pinned GGUF | Weights, GiB, rounded-up estimate | Queue |
   | --- | --- | ---: | --- |
   | `qwen35-9b` | Q6_K | 7.0 | P1, control |
   | `qwen36-35b-a3b` | UD-Q5_K_M | 24.7 | P1 |
   | `qwen36-27b` | Q5_K_M | 18.2 | P1 |
   | `qwen3-coder-next` | Q5_K_M | 52.9 | P1 |
   | `gpt-oss-20b` | MXFP4 | 11.3 | P1, second control |
   | `glm-47-flash` | Q8_0 | 29.7 | P1 |
   | `qwen3-coder-30b-a3b` | Q5_K_M | 20.3 | P2 |
   | `gpt-oss-120b` | MXFP4 | 59.1 | P2, conditional |
   | `qwen35-122b-a10b` | Q4_K_M | 71.3 | P2, conditional |
   | `gemma4-31b-it` | Q5_K_M | 20.2 | P2 |
   | `qwen35-35b-a3b` | Q5_K_M | 24.5 | P3 |
   | `glm-45-air` | Q4_K_M | 68.0 | P3, conditional |

   The table describes catalog files as of 2026-09-20; these are not measured peak RAM values. All 12 artifacts together occupy about 406.7 GiB of disk before additional copies. Downloading all of them is not required to complete the lab. For MoE, active parameters describe computation per token, but all experts are loaded. Hybrid attention requires its own cache/state calculation. Account separately for KV, scratch space, graph buffers, tokenizer, mmap/page cache, and other processes.

2. **Choose an exact object, not a search alias.** Export the profile from the saved catalog:

   ```bash
   python3 - "$LAB_DIR" qwen35-9b <<'PY'
   import json, pathlib, sys
   out = pathlib.Path(sys.argv[1]) / "raw"
   catalog = json.loads((out / "catalog.json").read_text())
   model = next(m for m in catalog["models"] if m["id"] == sys.argv[2])
   (out / "artifact.json").write_text(json.dumps(model, indent=2) + "\n")
   print(json.dumps(model["artifact"], indent=2))
   PY
   ```

   Check `model_id/model_revision`, the quantizer repository, `artifact.revision`, file names and count, `bytes`, `sha256`, precision, and license. The base-model and GGUF revisions differ. The catalog's SHA values come from publisher metadata; local verification has not yet been performed. If a file is unavailable or the license changes, stop this configuration with `no-artifact` status; record any replacement selection in a new manifest.

3. **Prepare a reproducible download.** Save the following public teaching script as `$LAB_DIR/raw/fetch_artifact.py`. It also works with the native-checkpoint manifest from LAB06. Without `--download`, the script only verifies existing files and exits with an error on a mismatch. An existing incorrect file is not replaced automatically.

   ```python
   import argparse, hashlib, json, os, pathlib, re, urllib.parse, urllib.request

   p = argparse.ArgumentParser()
   p.add_argument("manifest")
   p.add_argument("storage")
   p.add_argument("--download", action="store_true")
   a = p.parse_args()
   model = json.loads(pathlib.Path(a.manifest).read_text())
   artifact = model["artifact"]
   repo, rev = artifact["repository"], artifact["revision"]
   assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
   assert re.fullmatch(r"[0-9a-f]{40}", rev)
   root = (pathlib.Path(a.storage).expanduser() / repo / rev).resolve()
   results = []
   for item in artifact["files"]:
       rel = pathlib.PurePosixPath(item["path"])
       assert not rel.is_absolute() and ".." not in rel.parts
       dest = root.joinpath(*rel.parts)
       assert dest.resolve().is_relative_to(root)
       url = "https://huggingface.co/" + repo + "/resolve/" + rev + "/"
       url += urllib.parse.quote(str(rel), safe="/")
       if not dest.exists() and a.download:
           dest.parent.mkdir(parents=True, exist_ok=True)
           partial = dest.with_name(dest.name + ".part")
           # Do not run two copies of this script on the same file simultaneously.
           try:
               with urllib.request.urlopen(url, timeout=120) as src, partial.open("xb") as out:
                   while chunk := src.read(8 * 1024 * 1024):
                       out.write(chunk)
               with partial.open("rb") as src:
                   digest = hashlib.file_digest(src, "sha256").hexdigest()
               assert partial.stat().st_size == item["bytes"], "size mismatch"
               assert not item.get("sha256") or digest == item["sha256"], "hash mismatch"
               os.replace(partial, dest)
           except BaseException:
               # Preserve .part for diagnosis; remove it only after investigating the error.
               raise
       if not dest.is_file():
           results.append({"path": str(dest), "status": "no-artifact"})
           continue
       with dest.open("rb") as src:
           digest = hashlib.file_digest(src, "sha256").hexdigest()
       size_ok = dest.stat().st_size == item["bytes"]
       hash_ok = not item.get("sha256") or digest == item["sha256"]
       results.append({"path": str(dest), "bytes": dest.stat().st_size,
                       "sha256": digest,
                       "publisher_hash_present": bool(item.get("sha256")),
                       "status": "verified" if size_ok and hash_ok else "fail"})
   print(json.dumps({"repository": repo, "revision": rev,
                     "files": results}, indent=2))
   raise SystemExit(0 if all(x["status"] == "verified" for x in results) else 1)
   ```

   Python **3.11+** is required for `hashlib.file_digest`; its version goes into the report. The script does not resume interrupted downloads, so an unverified partial download cannot be concealed. Check disk headroom against the sum of `artifact.total_bytes`, temporary files, and future service copies. File verification sequentially reads the entire data volume.

4. **Download only the selected artifact, then verify it again offline.** The lab participant runs these commands on the target machine after step 3:

   ```bash
   python3 --version > "$LAB_DIR/raw/python-version.txt"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" --download > "$LAB_DIR/raw/download-verification.json"
   python3 "$LAB_DIR/raw/fetch_artifact.py" "$LAB_DIR/raw/artifact.json" "$LAB_STORAGE" > "$LAB_DIR/raw/verification.json"
   df -B1 "$LAB_STORAGE" > "$LAB_DIR/raw/disk-after.txt"
   ```

   On error, preserve stderr and the nonzero exit code in the report. A split GGUF requires **all original shards** in their original structure; the server later receives the first shard. Do not concatenate or rename shards. Do not add a vision projector, speculative draft, or different quant without a new manifest. For a protected repository, use the documented HF client and access credentials from `.env`; this public control requires no token.

5. **Pass the artifact to the next lab.** Take the control GGUF's absolute path from `verification.json` and record it as `GGUF` in your report; the runtime will receive this file. Create a standard checksum file for all shards for use with `sha256sum --check` in LAB04–07. JSON is not a checksum-file format:

   ```bash
   python3 - "$LAB_DIR" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / "raw"
   verification = json.loads((raw / "verification.json").read_text())
   assert verification["files"]
   lines = []
   for item in verification["files"]:
       assert item["status"] == "verified" and item["publisher_hash_present"]
       path = pathlib.Path(item["path"])
       assert path.is_absolute() and "\n" not in str(path) and "\\" not in str(path)
       lines.append(item["sha256"] + "  " + str(path) + "\n")
   (raw / "weights.sha256").write_text("".join(lines))
   PY
   sha256sum --check "$LAB_DIR/raw/weights.sha256" > "$LAB_DIR/raw/checksums-recheck.txt"
   ```

   Paths are absolute and refer to this machine; when moving files, update the path in a separate copy of the checksum file while keeping hashes unchanged. Include hashes of the input catalog, exported manifest, and script:

   ```bash
   sha256sum "$LAB_DIR/raw/catalog.json" "$LAB_DIR/raw/artifact.json" "$LAB_DIR/raw/fetch_artifact.py" > "$LAB_DIR/raw/input-hashes.txt"
   ```

   Complete `report.md`, `measurements.tsv`, and `manifest.json`. The `verified` status applies to bytes/hash, `candidate` to the memory estimate, and `not-run` to inference that has not occurred. An access/hash error is a separate observation, not a speed of 0 tokens/s. A later model or quantizer update creates a new configuration.

## Results tables

Fill in the first table for all 12 candidates; rows may be copied. Cells for actual measurements start empty.

| Model slug | Context | Weights, GiB | Runtime/cache reserve, GiB | Budget/source | Planned headroom | Decision and reason |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| | | | | | | |

| Model / artifact revision | Shards: expected / obtained | Bytes: expected / measured | SHA-256 verdict | Verification path | Status / reason |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

| Observation | Value | Unit | Conditions | Evidence |
| --- | ---: | --- | --- | --- |
| Free disk before / after | | bytes | | |
| Download / verification time | | s | | |

## Deliverables

The report directory containing all three completed helper files, a copy of the original catalog, 12 memory decisions, the selected `artifact.json`, download script, repeated verification result, hardware-budget source, and absolute weights path. **Do not add the weights themselves to Git.** State separately in the conclusion what will be tested when the model is actually loaded in LAB04–05.

## Completion criteria

- [ ] All 12 candidates have a decision with memory conditions and queue priority.
- [ ] All bytes/SHA-256 values for one control GGUF are verified, or `no-artifact`/`fail` is documented with a reason and corrective step.
- [ ] Model revision, quantizer revision, quantization, and shards are distinguishable in the manifest.
- [ ] Disk, RAM, GPU budget, weights, and KV/state are not conflated into one quantity.
- [ ] Missing hardware runs remain `not-run`; an estimate is not called a measurement.
- [ ] The report allows another participant to reproduce the selection and verification without searching for aliases.

## Review questions

1. Why does 3B active in an MoE not mean that only 3B parameters need to be stored on disk or in RAM?
2. Why do GGUF Q5 and UD-Q5 from the same family not provide a clean generation ablation?
3. What does SHA-256 prove, and what does it say nothing about regarding quantization quality and inference-kernel correctness?
4. Why does saving the hash from publisher metadata not yet amount to verifying the local file?
5. Which memory costs can turn a positive 32K estimate into OOM?

## Sources

- [Catalog with pinned revisions, shards, and hashes](../../experiments/local-models/models.json), [candidate analysis and limitations](../local-model-candidates.md).
- [Memory plan and hardware campaign order](../local-models.md), [Linux runbook](../local-model-runtime.md).
- [Hugging Face: versions and file downloads](https://huggingface.co/docs/huggingface_hub/guides/download).
- [Official Qwen3.5-9B model](https://huggingface.co/Qwen/Qwen3.5-9B), [publisher's GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF).
- [Python hashlib.file_digest](https://docs.python.org/3/library/hashlib.html#hashlib.file_digest).
