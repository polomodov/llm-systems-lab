import hashlib,json,pathlib
from collections import Counter
from gguf import GGUFReader
raw=pathlib.Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
weights={'local_path':'/Users/lab/local-model-lab-artifacts/unsloth/Qwen3.5-9B-GGUF/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q6_K.gguf'}
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

print(json.dumps(json.loads((raw/'gguf-summary.json').read_text()),indent=2))
