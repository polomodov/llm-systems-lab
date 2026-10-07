import datetime
import json
import pathlib
import subprocess
import sys
import time

raw = pathlib.Path(sys.argv[1])
status = {}
start = time.monotonic()

def collect(label):
    sample_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    elapsed = time.monotonic() - start
    for name, command in {
        'memory': ['vm_stat'],
        'swap': ['sysctl', 'vm.swapusage'],
        'pressure': ['memory_pressure', '-Q'],
    }.items():
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=10)
            body, code = p.stdout + p.stderr, p.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            body, code = str(error), None
        filename = name + '-' + label + '.txt'
        (raw / filename).write_text(body)
        status[filename] = {'command': command, 'exit_code': code}
    status[label] = {'started_at': sample_start, 'elapsed_since_first_seconds': elapsed,
                     'ended_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (raw / 'memory-status.json').write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status[label]), flush=True)

collect('before')
time.sleep(60)
collect('after-idle')
