"""Observe the pinned upstream CLI in its own process; do not patch its generation."""
import json
import pathlib
import runpy
import sys
import mlx.core as mx

raw = pathlib.Path(__file__).resolve().parent
case = sys.argv.pop(1)
assert case in {'warmup','r1','r2','r3'}
assert mx.default_device() == mx.gpu
assert mx.device_info()['device_name'] == 'Apple M5 Max'
record = {'device':mx.device_info(), 'default_device':str(mx.default_device()),
          'peak_memory_before_bytes':mx.get_peak_memory(), 'upstream_argv':sys.argv[1:]}
try:
    runpy.run_module('mlx_lm', run_name='__main__')
finally:
    mx.synchronize()
    record.update(peak_memory_bytes=mx.get_peak_memory(), active_memory_bytes=mx.get_active_memory(),
                  cache_memory_bytes=mx.get_cache_memory(), default_device_after=str(mx.default_device()))
    with (raw / (case+'-device.json')).open('x') as f:
        json.dump(record,f,indent=2)
        f.write('\n')
