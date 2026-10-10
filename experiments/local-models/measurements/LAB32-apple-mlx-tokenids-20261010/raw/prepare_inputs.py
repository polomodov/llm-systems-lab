"""CPU tokenizer only, no weights; same artifact/template kwargs as server."""
import hashlib
import json
import pathlib
from transformers import AutoTokenizer
raw = pathlib.Path(__file__).resolve().parent
runtime = json.loads((raw/'runtime-manifest.json').read_text())
t = AutoTokenizer.from_pretrained(runtime['model_path'],local_files_only=True,trust_remote_code=False)
assert hashlib.sha256(t.chat_template.encode()).hexdigest() == runtime['tokenizer']['effective_template_sha256']
def count(messages):
    ids=t.apply_chat_template(messages,tokenize=True,return_dict=False,add_generation_prompt=True,enable_thinking=False)
    assert isinstance(ids,list) and ids and all(isinstance(i,int) for i in ids), 'Expected flat token IDs, not BatchEncoding'
    return len(ids)
def messages(n):
    return [{'role':'user','content':'Контрольное значение LAB_SENTINEL_42.\n'+
        ''.join(f'Строка {i}: нейтральные данные.\n' for i in range(n))+
        'Верни контрольное значение из первой строки.'}]
for ctx in (8192,16384,32768):
    lo,hi=0,ctx
    while lo<hi:
        mid=(lo+hi+1)//2
        if count(messages(mid))<=ctx-4096:lo=mid
        else:hi=mid-1
    body=dict(model=runtime['model_path'],messages=messages(lo),max_tokens=2048,stream=True,
        temperature=0,seed=1,top_p=1,chat_template_kwargs={'enable_thinking':False},stream_options={'include_usage':True})
    assert count(body['messages'])<=ctx-4096
    (raw/f'ctx{ctx}-long-request.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
    (raw/f'ctx{ctx}-long-count.json').write_text(json.dumps(dict(input_tokens=count(body['messages']),input_budget=ctx-4096,lines=lo,template_sha256=runtime['tokenizer']['effective_template_sha256']),indent=2)+'\n')
    cancel=dict(body);cancel['messages']=[{'role':'user','content':body['messages'][0]['content']+'\nТеперь перечисляй подряд числа от 1 до 10000, каждое в отдельной строке, не останавливайся.'}]
    assert count(cancel['messages'])<ctx-2048
    (raw/f'ctx{ctx}-cancel-request.json').write_text(json.dumps(cancel,ensure_ascii=False,indent=2)+'\n')
    (raw/f'ctx{ctx}-cancel-count.json').write_text(json.dumps(dict(input_tokens=count(cancel['messages'])),indent=2)+'\n')
