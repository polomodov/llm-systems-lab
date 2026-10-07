"""Bounded resumable public curl transfers. Pins, lengths and final SHA are mandatory."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

raw=pathlib.Path(__file__).resolve().parent
variant=sys.argv[1]
meta=json.loads((raw/('gguf-api.json' if variant=='gguf' else 'mlx-api.json')).read_text())
repo,rev=meta['id'],meta['sha']
filename=sys.argv[2]
file=next(f for f in meta['siblings'] if f['rfilename']==filename)
size=file['size'];expected_sha=file['lfs']['sha256']
root=pathlib.Path('/Users/lab/local-model-lab-artifacts')/repo/rev
root.mkdir(parents=True,exist_ok=True)
parts=root/('.http-parts' if variant=='gguf' else '.'+filename+'.parts')
parts.mkdir(exist_ok=True)
prefix=parts/'prefix.bin'
prefix_size=prefix.stat().st_size if prefix.exists() else 0
chunk=128*1024*1024
jobs=[(i,start,min(start+chunk,size)-1) for i,start in enumerate(range(prefix_size,size,chunk))]
started=time.monotonic();lock=threading.Lock()
state={'repository':repo,'revision':rev,'path':filename,'bytes':size,'expected_sha256':expected_sha,
 'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'prefix_bytes':prefix_size,
 'workers':2,'chunks':[],'complete':False}
statusfile=raw/(variant+'-'+filename+'-curl-status.json')

def record():
 state['elapsed_seconds']=time.monotonic()-started
 state['received_bytes']=prefix_size+sum(c['bytes'] for c in state['chunks'])
 statusfile.write_text(json.dumps(state,indent=2)+'\n')

def fetch(job):
 index,start,end=job;path=parts/f'part-{index:04d}.bin';attempts=[]
 for attempt in range(8):
  received=path.stat().st_size if path.exists() else 0
  if received==end-start+1:break
  if received>end-start+1:raise ValueError('Invalid existing range extent')
  begin=start+received;remaining=end-begin+1
  temp=parts/f'transfer-{index:04d}.tmp';headers=parts/f'headers-{index:04d}.tmp'
  url=f'https://huggingface.co/{repo}/resolve/{rev}/{filename}?download=true&part={index}-{attempt}-{int(time.time())}'
  command=['curl','-q','--http1.1','--location','--fail','--silent','--show-error',
   '--connect-timeout','20','--max-time','120','--range',f'{begin}-{end}',
   '--max-filesize',str(remaining),'--dump-header',str(headers),'--output',str(temp),
   '--write-out','%{http_code}',url]
  p=subprocess.run(command,capture_output=True,text=True)
  content_range=re.findall(r'(?im)^content-range:\s*([^\r\n]+)',headers.read_text(errors='replace'))[-1:] if headers.exists() else []
  expected_range=f'bytes {begin}-{end}/{size}'
  acceptable=p.stdout=='206' and content_range==[expected_range]
  transferred=temp.stat().st_size if temp.exists() else 0
  if acceptable and 0<transferred<=remaining:
   with path.open('ab') as out, temp.open('rb') as source:shutil.copyfileobj(source,out,8*1024*1024)
  attempts.append({'attempt':attempt+1,'range_start':begin,'curl_exit':p.returncode,
   'http_status':p.stdout,'content_range':content_range,'bytes_received':transferred,
   'accepted':acceptable and transferred<=remaining})
  temp.unlink(missing_ok=True);headers.unlink(missing_ok=True)
  if path.exists() and path.stat().st_size==end-start+1:break
  time.sleep(min(2*(attempt+1),12))
 success=path.exists() and path.stat().st_size==end-start+1
 with lock:
  state['chunks'].append({'index':index,'start':start,'end':end,'bytes':path.stat().st_size if path.exists() else 0,'complete':success,'attempts':attempts})
  record();print(f'{variant}/{filename}: {state["received_bytes"]/2**30:.2f}/{size/2**30:.2f} GiB',flush=True)
 if not success:raise RuntimeError('Range remained incomplete')
 return index,path

record()
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:completed=dict(pool.map(fetch,jobs))
 temp=root/(filename+'.assembled')
 if temp.exists():raise ValueError('Unexpected previous assembly; refusing overwrite')
 h=hashlib.sha256()
 with temp.open('xb') as out:
  for part in ([prefix] if prefix_size else [])+[completed[i] for i in range(len(jobs))]:
   with part.open('rb') as source:
    for block in iter(lambda:source.read(8*1024*1024),b''):out.write(block);h.update(block)
 if temp.stat().st_size!=size or h.hexdigest()!=expected_sha:raise ValueError('Final publisher SHA/size mismatch')
 if (root/filename).exists():raise ValueError('Refusing overwrite')
 temp.rename(root/filename);state.update(complete=True,sha256=h.hexdigest())
except Exception as error:
 state['error_type']=type(error).__name__;print(type(error).__name__,flush=True);raise SystemExit(1) from None
finally:
 state['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();record()
