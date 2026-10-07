"""Read-only metadata extraction and second offline verification; no inference."""
import hashlib
import json
import pathlib
import struct
import time
from collections import Counter
from gguf import GGUFReader

raw=pathlib.Path(__file__).resolve().parent
acquisition=json.loads((raw/'acquisition-http-status.json').read_text())
if not acquisition.get('completed'):
    raise ValueError('Acquisition is not complete')
files=acquisition['files']

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(8*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

started=time.monotonic()
checks=[]
for file in files:
    path=pathlib.Path(file['local_path'])
    actual=sha(path)
    check={'variant':file['variant'],'path':file['path'],'bytes':path.stat().st_size,
        'sha256':actual,'matches_acquisition':actual==file['sha256'] and path.stat().st_size==file['bytes']}
    checks.append(check)
    if not check['matches_acquisition']:
        raise ValueError('Offline recheck failed')
(raw/'offline-verification.json').write_text(json.dumps({'checks':checks,'all_match':True,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')

weights=next(row for row in files if row['variant']=='gguf' and row['path'].endswith('.gguf'))
reader=GGUFReader(weights['local_path'],mode='r')
metadata={}
tokenizer_hashes={}
for name,field in reader.fields.items():
    if name.startswith('tokenizer.'):
        value=field.contents()
        if name in ['tokenizer.ggml.tokens','tokenizer.ggml.merges','tokenizer.ggml.token_type','tokenizer.ggml.scores']:
            encoded=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
            tokenizer_hashes[name]={'items':len(value),'sha256_canonical_json':hashlib.sha256(encoded).hexdigest(),
                'serialization':'UTF-8, ensure_ascii=False, compact JSON; decoded directly from pinned GGUF'}
        else:
            metadata[name]=value
    elif not field.types or field.types[0].name!='ARRAY':
        metadata[name]=field.contents()
(raw/'gguf-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
(raw/'gguf-tokenizer-hashes.json').write_text(json.dumps(tokenizer_hashes,indent=2)+'\n')
if isinstance(metadata.get('tokenizer.chat_template'),str):
    (raw/'gguf-chat-template.jinja').write_text(metadata['tokenizer.chat_template'])
quant=Counter(str(t.tensor_type) for t in reader.tensors)
(raw/'gguf-summary.json').write_text(json.dumps({'tensor_count':len(reader.tensors),'tensor_types':dict(quant),
    'architecture':metadata.get('general.architecture'),'file_type':metadata.get('general.file_type'),
    'chat_template_sha256':sha(raw/'gguf-chat-template.jinja') if (raw/'gguf-chat-template.jinja').exists() else None},indent=2)+'\n')

mlxfiles=[row for row in files if row['variant']=='mlx']
mlxroot=pathlib.Path(mlxfiles[0]['local_path']).parent
index=json.loads((mlxroot/'model.safetensors.index.json').read_text())
expected_shards=set(index['weight_map'].values())
actual_shards={row['path'] for row in mlxfiles if row['path'].endswith('.safetensors')}
if expected_shards != actual_shards:
    raise ValueError('MLX shard/index mismatch')
headers={}
for shard in sorted(expected_shards):
    path=mlxroot/shard
    with path.open('rb') as source:
        header_size=struct.unpack('<Q',source.read(8))[0]
        if header_size>32*1024*1024:
            raise ValueError('Unreasonable safetensors header size')
        header=json.loads(source.read(header_size))
    tensors={k:v for k,v in header.items() if k!='__metadata__'}
    expected_names={k for k,v in index['weight_map'].items() if v==shard}
    if set(tensors)!=expected_names:
        raise ValueError('MLX tensor/index names mismatch')
    extent=path.stat().st_size-8-header_size
    ranges=[]
    for name,tensor in tensors.items():
        begin,end=tensor['data_offsets']
        if not 0<=begin<=end<=extent:
            raise ValueError('Tensor outside file bounds')
        ranges.append((begin,end))
    ranges.sort()
    if not ranges or ranges[0][0]!=0 or ranges[-1][1]!=extent or any(a[1]!=b[0] for a,b in zip(ranges,ranges[1:])):
        raise ValueError('MLX data gaps/overlap or incomplete tail')
    headers[shard]={'header_bytes':header_size,'tensor_count':len(tensors),'payload_bytes':extent,
        'dtypes':dict(Counter(t['dtype'] for t in tensors.values()))}
config=json.loads((mlxroot/'config.json').read_text())
(raw/'mlx-index-verification.json').write_text(json.dumps({'shards':sorted(expected_shards),'tensor_count':len(index['weight_map']),
    'headers':headers,'complete':True,'quantization':config.get('quantization_config',config.get('quantization'))},indent=2)+'\n')
for name in ['README.md','config.json','tokenizer_config.json','chat_template.jinja']:
    (raw/('mlx-'+name)).write_bytes((mlxroot/name).read_bytes())
# Full tokenizer bytes stay outside Git; exact SHA and location are in acquisition status.
reference=[row for row in files if row['variant']=='source-reference']
for row in reference:
    if row['path'] in ['README.md','LICENSE','config.json','tokenizer_config.json','generation_config.json','chat_template.jinja']:
        (raw/('source-'+row['path'])).write_bytes(pathlib.Path(row['local_path']).read_bytes())
print(json.dumps({'offline_files_verified':len(checks),'gguf_tensors':len(reader.tensors),'mlx_tensor_count':len(index['weight_map']),
    'mlx_quantization':config.get('quantization_config'),'gguf_chat_template_sha256':sha(raw/'gguf-chat-template.jinja')},indent=2))
