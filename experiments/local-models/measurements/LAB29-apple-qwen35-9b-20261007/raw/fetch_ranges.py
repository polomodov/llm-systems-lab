"""Resume public immutable files in bounded HTTP ranges; require complete SHA-256."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import shutil
import threading
import time
import urllib.request

raw=pathlib.Path(__file__).resolve().parent
repo='unsloth/Qwen3.5-9B-GGUF'
revision='3885219b6810b007914f3a7950a8d1b469d598a5'
name='Qwen3.5-9B-Q6_K.gguf'
size=7458301152
expected_sha='91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59'
root=pathlib.Path('/Users/lab/local-model-lab-artifacts')/repo/revision
parts=root/'.http-parts'
parts.mkdir()
candidates=list((root/'.cache/huggingface/download').glob('*.incomplete'))
if len(candidates)!=1:
    raise ValueError('Expected one closed sequential HTTP prefix')
prefix=parts/'prefix.bin'
candidates[0].rename(prefix)
with prefix.open('rb') as source:
    first=source.read(1048576)
probe=json.loads((raw/'range-probe.json').read_text())
if hashlib.sha256(first).hexdigest()!=probe['sha256']:
    raise ValueError('Prefix differs from pinned range probe')
prefix_size=prefix.stat().st_size
if not 0<prefix_size<size:
    raise ValueError('Invalid prefix size')
chunk=128*1024*1024
jobs=[(i,start,min(start+chunk,size)-1) for i,start in enumerate(range(prefix_size,size,chunk))]
started=time.monotonic()
lock=threading.Lock()
state={'repository':repo,'revision':revision,'path':name,'prefix_bytes':prefix_size,
    'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'chunk_bytes':chunk,'workers':6,'chunks':[],'completed':False}

def record():
    state['elapsed_seconds']=time.monotonic()-started
    state['verified_transfer_bytes']=prefix_size+sum(x['bytes'] for x in state['chunks'] if x['status']=='completed')
    (raw/'range-transfer-status.json').write_text(json.dumps(state,indent=2)+'\n')

def fetch(job):
    index,start,end=job
    path=parts/f'part-{index:04d}.bin'
    attempts=[]
    for attempt in range(3):
        received=path.stat().st_size if path.exists() else 0
        if received==end-start+1:
            break
        request_start=start+received
        url=f'https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true&segment={index}-{attempt}-{int(time.time())}'
        request=urllib.request.Request(url,headers={'Range':f'bytes={request_start}-{end}','User-Agent':'apple-local-model-lab/1'})
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                expected_range=f'bytes {request_start}-{end}/{size}'
                if response.status!=206 or response.headers.get('Content-Range')!=expected_range:
                    raise ValueError('Server range mismatch')
                remaining=end-request_start+1
                with path.open('ab') as target:
                    while remaining:
                        block=response.read(min(8*1024*1024,remaining))
                        if not block:
                            raise ValueError('Incomplete HTTP range')
                        target.write(block)
                        remaining-=len(block)
            attempts.append({'attempt':attempt+1,'status':'completed','range_start':request_start})
        except Exception as error:
            attempts.append({'attempt':attempt+1,'status':'failed','error_type':type(error).__name__,'range_start':request_start})
            if attempt==2:
                with lock:
                    state['chunks'].append({'index':index,'start':start,'end':end,'status':'failed','bytes':path.stat().st_size if path.exists() else 0,'attempts':attempts})
                    record()
                raise RuntimeError(f'Chunk {index} failed') from None
    if path.stat().st_size!=end-start+1:
        raise ValueError('Range file size mismatch')
    with lock:
        state['chunks'].append({'index':index,'start':start,'end':end,'status':'completed','bytes':path.stat().st_size,'attempts':attempts})
        record()
        print(f'Completed chunk {index}; {state["verified_transfer_bytes"]/2**30:.2f}/{size/2**30:.2f} GiB',flush=True)
    return index,path

record()
try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        completed=dict(pool.map(fetch,jobs))
    temp=root/(name+'.assembled')
    h=hashlib.sha256()
    with temp.open('xb') as out:
        for part in [prefix]+[completed[i] for i in range(len(jobs))]:
            with part.open('rb') as source:
                for block in iter(lambda:source.read(8*1024*1024),b''):
                    out.write(block)
                    h.update(block)
    state['sha256']=h.hexdigest()
    if temp.stat().st_size!=size or h.hexdigest()!=expected_sha:
        raise ValueError('Full assembled artifact verification failed')
    if (root/name).exists():
        raise ValueError('Refusing to replace existing complete artifact')
    temp.rename(root/name)
    state['completed']=True
except Exception as error:
    state['error_type']=type(error).__name__
    print(type(error).__name__,flush=True)
    raise SystemExit(1) from None
finally:
    state['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    record()
