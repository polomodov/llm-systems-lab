"""Run the unmodified MLX-LM server with device observations in its process."""
import json
import pathlib
import runpy
import mlx.core as mx

raw = pathlib.Path(__file__).resolve().parent
assert mx.default_device() == mx.gpu
assert mx.device_info()['device_name'] == 'Apple M5 Max'
with (raw/'server-device-before.json').open('x') as f:
    json.dump({'device':mx.device_info(),'default_device':str(mx.default_device())},f,indent=2)
    f.write('\n')
try:
    runpy.run_module('mlx_lm',run_name='__main__')
finally:
    mx.synchronize()
    with (raw/'server-device-after.json').open('x') as f:
        json.dump({'device':mx.device_info(),'default_device':str(mx.default_device()),
                   'peak_memory_bytes':mx.get_peak_memory(),'active_memory_bytes':mx.get_active_memory()},f,indent=2)
        f.write('\n')
