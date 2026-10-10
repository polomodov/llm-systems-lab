"""Measurement helpers: active compute frames and successful owned-model unload."""
import hashlib
import pathlib
import re

# Only counted call-graph frames, never image names, summaries or wait-only frames.
_FRAME = re.compile(r'^\s+[+|:! ]*\d+\s+(?:ggml_metal_(?:graph_compute|op_(?:encode|mul_mat|mul_mat_id|ssm_conv|ssm_scan|bin|norm)|encoder_dispatch_(?:threadgroups|threads)))\b.*\(in libggml-metal\.dylib\)')

def active_metal_frames(text):
    active = False
    frames = []
    for line in text.splitlines():
        if line.strip() == 'Call graph:':
            active = True
            continue
        if active and line.startswith(('Total number in stack', 'Sort by top of stack', 'Binary Images:')):
            break
        if active and _FRAME.match(line):
            frames.append(line)
    return frames


def unload_owned(cli, alias, folder, state):
    cli(['unload', alias], 'unload', folder, 30)
    state['loaded'] = False


def require_helper_pin(pins, path=None):
    path = pathlib.Path(path or __file__).resolve()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if not any(pathlib.Path(record['path']).resolve() == path and record['bytes'] == path.stat().st_size and record['sha256'] == sha for record in pins['files']):
        raise ValueError('Fresh prestart pins must include lms_evidence.py')
