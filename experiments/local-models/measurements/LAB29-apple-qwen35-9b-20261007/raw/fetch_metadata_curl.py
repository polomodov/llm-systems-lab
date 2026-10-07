import datetime,hashlib,json,pathlib,subprocess,time
raw=pathlib.Path(__file__).resolve().parent
rows=[];started=time.monotonic()
for variant,metadata in [('gguf','gguf-api.json'),('mlx','mlx-api.json'),('source-reference','source-api.json')]:
    meta=json.loads((raw/metadata).read_text());repo,rev=meta['id'],meta['sha']
    root=pathlib.Path('/Users/lab/local-model-lab-artifacts')/repo/rev
    root.mkdir(parents=True,exist_ok=True)
    whitelist={'README.md','LICENSE','config.json','tokenizer_config.json','generation_config.json','chat_template.jinja'}
    for file in meta['siblings']:
        name,size=file['rfilename'],file['size']
        if name.startswith('.') or size>64*1024*1024 or name.endswith(('.safetensors','.gguf')):continue
        if variant=='gguf' and name!='README.md':continue
        if variant=='source-reference' and name not in whitelist:continue
        if pathlib.PurePosixPath(name).is_absolute() or '..' in pathlib.PurePosixPath(name).parts:raise ValueError('Unsafe name')
        path=root/name;reused=path.exists()
        if not reused:
            path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix(path.suffix+'.download')
            if temp.exists():raise ValueError('Unexpected prior download')
            url=f'https://huggingface.co/{repo}/resolve/{rev}/{name}?download=true&metadata={int(time.time())}'
            code=subprocess.run(['curl','-q','--http1.1','--location','--fail','--silent','--show-error',
                '--connect-timeout','20','--max-time','120','--retry','3','--retry-delay','2',
                '--max-filesize',str(size),'--output',str(temp),url],capture_output=True).returncode
            if code:raise RuntimeError(f'curl metadata failed with exit {code}')
            temp.rename(path)
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();blob=hashlib.sha1(f'blob {size}\0'.encode()+data).hexdigest()
        expected=file.get('lfs',{}).get('sha256')
        if len(data)!=size or (expected and sha!=expected) or (not expected and blob!=file['blobId']):
            raise ValueError('Metadata publisher hash/size mismatch')
        rows.append({'variant':variant,'repository':repo,'revision':rev,'path':name,'local_path':str(path),
            'bytes':size,'sha256':sha,'publisher_sha256':expected,'publisher_git_blob_sha1':file['blobId'],
            'git_blob_sha1_verified':not bool(expected),'reused':reused})
        (raw/'metadata-curl-status.json').write_text(json.dumps({'files':rows,'completed':False},indent=2)+'\n')
        print(f'Verified {variant}/{name}',flush=True)
(raw/'metadata-curl-status.json').write_text(json.dumps({'files':rows,'completed':True,
    'elapsed_seconds':time.monotonic()-started,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
