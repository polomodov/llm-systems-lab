"""Trusted operator client, fixed loopback, already loaded alias only."""
import datetime
import json
import pathlib
import sys
import threading
import time
import lmstudio as lms

directory=pathlib.Path(sys.argv[1]);alias=sys.argv[2];kind=sys.argv[3]
directory.mkdir(parents=True,exist_ok=True)
expected_path=sys.argv[4]
prompt='Пиши целые числа от 1 до 10000, каждое на новой строке, не останавливайся.' if kind=='cancel' else 'Ответь ровно LAB_READY без пояснений.'
expected_final='\n\nLAB_READY'
config={'maxTokens':2048,'temperature':0,'topPSampling':1}
start=time.time();record=dict(started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,alias=alias,
    api_host='127.0.0.1:1234',prompt=prompt,config=config,cancel_called_at=None,fragments=[],accepted=False)
def save(): (directory/'sdk-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
save()
try:
    with lms.Client('127.0.0.1:1234') as client:
        loaded=client.llm.list_loaded();assert len(loaded)==1 and loaded[0].identifier==alias
        model=loaded[0]  # Never get-or-load an arbitrary model.
        stream=model.respond_stream(prompt,config=config)
        cancel=None
        if kind=='cancel':
            def stop():
                record['cancel_called_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
                try:stream.cancel()
                except Exception as error:record['cancel_error']=type(error).__name__+': '+str(error)
            # Start before timer: cancel() does nothing on a not-started stream.
            stream.start();cancel=threading.Timer(1,stop);cancel.start()
        try:
            for fragment in stream:
                record['fragments'].append(dict(content=fragment.content,reasoning_type=fragment.reasoning_type,observed_seconds=time.time()-start))
                if len(record['fragments'])>4096:raise RuntimeError('Fragment limit')
            result=stream.result()
            record.update(content=result.content,stats=result.stats.to_dict(),model_info=result.model_info.to_dict(),
                load_config=result.load_config.to_dict(),prediction_config=result.prediction_config.to_dict())
            record['final_content']=''.join(f['content'] for f in record['fragments'] if f['reasoning_type']=='none')
            assert record['model_info']['path']==expected_path
            record['response_alias']=None
            record['response_alias_unavailable']='SDK PredictionResult.model_info is LlmInfo without instance identifier; loaded handle selector and observed path validate this controlled deployment'
            if kind=='cancel':record['accepted']=result.stats.stop_reason=='userStopped' and record['cancel_called_at'] is not None and 'cancel_error' not in record
            else:record['accepted']=record['final_content']==expected_final and result.stats.stop_reason in ['eosFound','stopStringFound']
        finally:
            if cancel:cancel.cancel();cancel.join(timeout=5)
except Exception as error:record['error']=type(error).__name__+': '+str(error)
record.update(ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),total_seconds=time.time()-start)
save();print(json.dumps({k:v for k,v in record.items() if k not in ['fragments','load_config','prediction_config','model_info']},ensure_ascii=False))
if not record['accepted']:sys.exit(1)
