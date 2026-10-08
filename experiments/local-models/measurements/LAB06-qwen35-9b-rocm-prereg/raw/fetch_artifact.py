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
        # Не используйте одновременно две копии этого скрипта для одного файла.
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
            # .part сохраняется для диагностики; удалять только после разбора ошибки.
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