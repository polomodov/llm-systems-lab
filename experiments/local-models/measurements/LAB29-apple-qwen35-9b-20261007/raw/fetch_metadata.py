"""Public pinned downloads only; no implicit token or execution of model code."""
import os
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_XET'] = '1'
import datetime
import hashlib
import json
import pathlib
import shutil
import time
from huggingface_hub import HfApi, hf_hub_download

raw = pathlib.Path(__file__).resolve().parent
storage = pathlib.Path('/Users/lab/local-model-lab-artifacts')
ceiling = 30 * 2**30
started = time.monotonic()
status = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': [], 'completed': False}
api = HfApi(token=False)

def digest(path, kind='sha256', prefix=b''):
    h = hashlib.new(kind)
    h.update(prefix)
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()

specs = [
    ('gguf', 'unsloth/Qwen3.5-9B-GGUF', '3885219b6810b007914f3a7950a8d1b469d598a5', ['README.md']),
    ('mlx', 'mlx-community/Qwen3.5-9B-MLX-4bit', '938d8919941c6e7efd3c7150eff7fe9d12afa631', ['README.md', 'chat_template.jinja', 'config.json', 'model.safetensors.index.json', 'preprocessor_config.json', 'processor_config.json', 'tokenizer.json', 'tokenizer_config.json', 'video_preprocessor_config.json', 'vocab.json']),
    ('source-reference', 'Qwen/Qwen3.5-9B', 'c202236235762e1c871ad0ccb60c8ee5ba337b9a', ['README.md', 'LICENSE', 'config.json', 'tokenizer_config.json', 'generation_config.json', 'chat_template.jinja']),
]
planned = []
for variant, repo, revision, whitelist in specs:
    info = api.model_info(repo, revision=revision, files_metadata=True, token=False)
    if info.sha != revision:
        raise ValueError('Immutable revision mismatch')
    names = {row.rfilename: row for row in info.siblings}
    selected = sorted(whitelist if whitelist else [name for name in names if not name.startswith('.')])
    if variant == 'source-reference':
        selected = [name for name in selected if name in names]
    (raw/(variant+'-api-pinned.json')).write_text(json.dumps({'repository':repo,'revision':revision,'selected_files':selected},indent=2)+'\n')
    for name in selected:
        relative = pathlib.PurePosixPath(name)
        if relative.is_absolute() or any(x in ('..', '.', '') for x in relative.parts):
            raise ValueError('Unsafe filename')
        meta = names[name]
        if not isinstance(meta.size, int) or meta.size <= 0:
            raise ValueError('Unknown size')
        lfs = meta.lfs
        sha = lfs.sha256 if lfs else None
        planned.append((variant, repo, revision, name, meta.size, sha, meta.blob_id))

if sum(row[4] for row in planned) > ceiling:
    raise ValueError('Selected artifacts exceed registered SSD ceiling')
if shutil.disk_usage(storage.parent).free < 40*2**30:
    raise ValueError('Insufficient initial SSD reserve')
try:
    for variant, repo, revision, name, size, expected_sha, blob in planned:
        destination = storage/repo/revision/name
        reused = destination.exists()
        if reused:
            if destination.is_symlink() or destination.stat().st_size != size:
                raise ValueError('Existing artifact mismatch; refusing overwrite')
            if expected_sha and digest(destination) != expected_sha:
                raise ValueError('Existing artifact hash mismatch; refusing overwrite')
            if not expected_sha and digest(destination, 'sha1', f'blob {size}\0'.encode()) != blob:
                raise ValueError('Existing Git blob mismatch; refusing overwrite')
        else:
            print(f'Downloading {variant}/{name}: {size/2**30:.3f} GiB', flush=True)
            result = hf_hub_download(repo_id=repo, filename=name, revision=revision,
                local_dir=str(storage/repo/revision), token=False)
            if pathlib.Path(result) != destination:
                raise ValueError('Unexpected download destination')
        actual_sha = digest(destination)
        if destination.stat().st_size != size:
            raise ValueError('Downloaded size mismatch')
        if expected_sha and actual_sha != expected_sha:
            raise ValueError('Downloaded SHA-256 mismatch')
        actual_blob = digest(destination,'sha1',f'blob {size}\0'.encode()) if not expected_sha else None
        if not expected_sha and actual_blob != blob:
            raise ValueError('Downloaded Git blob mismatch')
        status['files'].append({'variant':variant,'repository':repo,'revision':revision,'path':name,
            'local_path':str(destination),'bytes':size,'sha256':actual_sha,'publisher_sha256':expected_sha,
            'publisher_git_blob_sha1':blob,'git_blob_sha1_verified':not bool(expected_sha),'reused':reused})
        status['elapsed_seconds'] = time.monotonic()-started
        (raw/'metadata-acquisition-status.json').write_text(json.dumps(status,indent=2)+'\n')
        print(f'Verified {variant}/{name}; elapsed {status["elapsed_seconds"]:.1f}s',flush=True)
    status['completed']=True
except Exception as error:
    status['error_type']=type(error).__name__
    # Do not serialize signed CDN URLs from exception text.
    print(f'Acquisition failed: {type(error).__name__}; inspect verified-file register.',flush=True)
    raise SystemExit(1) from None
finally:
    status['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    status['elapsed_seconds']=time.monotonic()-started
    (raw/'metadata-acquisition-status.json').write_text(json.dumps(status,indent=2)+'\n')
