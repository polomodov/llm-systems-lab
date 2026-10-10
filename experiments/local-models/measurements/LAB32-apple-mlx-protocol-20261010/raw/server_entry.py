"""Observation wrapper; installed MLX-LM sources and generation remain unchanged."""
import datetime
import json
import pathlib
import threading
import ctypes
import hashlib
import mlx.core as mx
from mlx_lm import server

raw = pathlib.Path(__file__).resolve().parent
ctx = int(__import__('sys').argv[1])
directory = raw / ('ctx' + str(ctx))
lock = threading.Lock()
def observe(event, **fields):
    with lock:
        row = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   event=event, phase=(directory/'phase.txt').read_text(),
                   active_memory_bytes=mx.get_active_memory(),
                   cache_memory_bytes=mx.get_cache_memory(), peak_memory_bytes=mx.get_peak_memory(), **fields)
        with (directory/'server-events.jsonl').open('a') as out:
            out.write(json.dumps(row)+'\n')

assert mx.default_device() == mx.gpu and mx.device_info()['device_name'] == 'Apple M5 Max'
def loaded_images(label):
    loader=ctypes.CDLL(None)
    loader._dyld_image_count.restype=ctypes.c_uint32
    loader._dyld_get_image_name.argtypes=[ctypes.c_uint32]
    loader._dyld_get_image_name.restype=ctypes.c_char_p
    pins={str(pathlib.Path(p['path']).resolve()):p['sha256'] for p in json.loads((raw/'prestart-pins.json').read_text())['files']}
    rows=[]
    for index in range(loader._dyld_image_count()):
        name=loader._dyld_get_image_name(index).decode();path=pathlib.Path(name)
        if name.startswith(('/System/','/usr/lib/')):
            rows.append(dict(path=name,sha256=None,reason='Apple system image fixed by macOS build; file bytes not separately pinned'))
        else:
            h=hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(dict(path=name,sha256=h,registered=pins.get(str(path.resolve()))==h))
    (directory/(label+'-loaded-images.json')).write_text(json.dumps(rows,indent=2)+'\n')
    assert all(r.get('registered',True) for r in rows), 'Unregistered loaded native image'
loaded_images('before')
(directory/'device-before.json').write_text(json.dumps(dict(device=mx.device_info(),default_device=str(mx.default_device())),indent=2)+'\n')
original_stop = server.GenerationContext.stop
def observed_stop(self):
    observe('stop_requested', context_object=id(self))
    return original_stop(self)
server.GenerationContext.stop = observed_stop
original_single = server.ResponseGenerator._serve_single
def observed_single(self, request, stream):
    observe('generation_begin')
    try:
        return original_single(self, request, stream)
    finally:
        observe('generation_end')
server.ResponseGenerator._serve_single = observed_single
__import__('sys').argv = ['mlx_lm.server', *__import__('sys').argv[2:]]
try:
    server.main()
finally:
    mx.synchronize()
    observe('server_end')
    loaded_images('after')
    (directory/'device-after.json').write_text(json.dumps(dict(device=mx.device_info(),default_device=str(mx.default_device()),
        peak_memory_bytes=mx.get_peak_memory(),active_memory_bytes=mx.get_active_memory(),cache_memory_bytes=mx.get_cache_memory()),indent=2)+'\n')
