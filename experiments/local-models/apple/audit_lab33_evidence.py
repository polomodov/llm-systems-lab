"""Offline review corrections; preserves original samples, proofs, pins and execution."""
import hashlib
import json
import pathlib
import sys
from lms_evidence import active_metal_frames

root = pathlib.Path(__file__).resolve().parents[3]
directory = (root / sys.argv[1]).resolve()
assert directory.parent == root / 'experiments/local-models/measurements'
assert directory.name.startswith('LAB33-apple-')

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

for path in sorted((directory / 'raw').glob('lms-*/backend-*/proof.json')):
    original = json.loads(path.read_text())
    proof = dict(original_proof=str(path.relative_to(directory)), original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), parser='experiments/local-models/apple/lms_evidence.py', parser_sha256=hashlib.sha256(pathlib.Path(__file__).with_name('lms_evidence.py').read_bytes()).hexdigest(), samples=[], metal_call_path_lines=[])
    for sample in original['samples']:
        source = (directory / sample['file']).resolve()
        assert directory in source.parents and source.parent == path.parent
        frames = active_metal_frames(source.read_text(errors='replace')) if sample['returncode'] == 0 and source.is_file() else []
        proof['samples'].append(dict(sample, active_frames=len(frames), sha256=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None))
        proof['metal_call_path_lines'].extend(frames)
    proof.update(metal_call_path_observed=bool(proof['metal_call_path_lines']), curl_exit=original['curl_exit'], stream_complete=original['stream_complete'], all_layer_offload=None, physical_gpu_release=None, scope='Offline reanalysis of already recorded call graphs; no new model execution, no binary-image or wait-only acceptance.')
    save(path.with_name('active-metal-proof.json'), proof)

for path in sorted((directory / 'raw').glob('lms-*/execution.json')):
    original = json.loads(path.read_text())
    observed = original.get('models_after')
    save(path.with_name('lifecycle-audit.json'), dict(original_execution=str(path.relative_to(directory)), original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), recorded_loaded_flag=original.get('loaded'), loaded_after=False if observed == [] else None, models_after=observed, unload_error=original.get('unload_error'), server_stop_error=original.get('server_stop_error'), scope='loaded_after is derived only from the recorded models_after observation; original stale flag is preserved. No new unload or GPU release measurement.'))
