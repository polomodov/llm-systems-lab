# -*- coding: utf-8 -*-
"""Export the recorded stop without inventing unexecuted load cells."""
import collections, csv, hashlib, json, pathlib, statistics

RAW=pathlib.Path(__file__).resolve().parent
ROOT=RAW.parent
manifest=json.loads((ROOT/'manifest.json').read_text())
attempts={a['id']:a for a in manifest['planned_attempts']}
rows=[];summaries={}

def read(path):return json.loads((RAW/path).read_text())
def add(case,metric,value,unit,evidence,reason='',status=None):
    rows.append([f'o{len(rows)+1}',attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tile16','metal',8192,
        int(case[1]) if case.startswith('r') else '',metric,value if value is not None else '',unit,
        status or ('measured' if value is not None else 'unavailable'),'raw/'+evidence,reason])

registered=read('registered-source-hashes.json')
for name,digest in registered.items():
    path=RAW/('run_load-at-start.py' if name=='run_load.py' else name)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
assert read('startup-execution.json')['accepted']
assert read('startup-props.json')['default_generation_settings']['n_ctx']==8192
for case in attempts:
    directory=RAW/case
    if not (directory/'summary.json').is_file():continue
    summary=read(case+'/summary.json');summaries[case]=summary
    records=[read(str(p.relative_to(RAW))) for p in sorted(directory.glob('request-*.json'))]
    assert len(records)==summary['requests']
    assert records==summary['results']
    assert sum(r['ok'] for r in records)==summary['successful']
    assert sum(not r['ok'] for r in records)==summary['failed']
    assert (directory/'request.json').read_bytes()==json.dumps(read('load-request.json'),ensure_ascii=False,separators=(',',':')).encode()
    for record in records:
        evidence=f'{case}/request-{record["index"]:04d}.json'
        response=directory/f'request-{record["index"]:04d}.response.bin'
        assert response.stat().st_size==record['response_bytes']
        if record['ok']:
            data=json.loads(response.read_bytes());choice=data['choices'][0];message=choice['message']
            assert record['http_status']==200 and message['content'].strip() and not message.get('tool_calls')
            assert choice['finish_reason']==record['finish_reason'] in ['stop','length']
            assert data['usage']['completion_tokens']==record['completion_tokens']
            assert data['usage']['prompt_tokens']==record['prompt_tokens']
        else:assert record['error']
        for metric,unit in [('latency_seconds','s'),('completion_tokens','tokens'),('prompt_tokens','tokens'),('http_status','http-status')]:
            value=record[metric]
            add(case,f'request-{record["index"]}-{metric}',value,unit,evidence,reason='Failed response/usage not available.' if value is None else '')
    measured=[r['latency_seconds'] for r in records if r['ok']]
    assert statistics.median(measured)==summary['success_latency_median_seconds']
    assert summary['successful_completion_tokens_per_second']==summary['completion_tokens_successful']/summary['batch_wall_seconds']
    for metric,unit in [('batch_wall_seconds','s'),('successful','requests'),('failed','requests'),('success_latency_median_seconds','s'),('success_latency_p95_seconds','s'),('success_latency_max_seconds','s'),('successful_requests_per_second','requests/s'),('successful_completion_tokens_per_second','tokens/s')]:
        add(case,metric,summary[metric],unit,case+'/summary.json')
    add(case,'ttft',None,'s',case+'/summary.json',reason='Non-streaming client; no token arrival timing.')
for attempt in attempts.values():
    assert attempt['status'] in ['completed','failed','not-run']
    if attempt['status']!='completed':
        assert attempt['reason']
        add(attempt['id'],'attempt-outcome',None,'status',attempt['evidence_files'][0].removeprefix('raw/'),reason=attempt['reason'],status=attempt['status'])
samples=[json.loads(line) for line in (RAW/'memory-timeline.jsonl').read_text().splitlines()]
shutdown=read('shutdown-execution.json')
assert samples[-1]['free_speculative_bytes']<16*2**30
assert shutdown['guard_reason']=='Memory/power admission failed'
assert shutdown['returncode']==-6
summary={'status':'blocked','attempts':dict(collections.Counter(a['status'] for a in attempts.values())),
    'blocks':{case:{k:v for k,v in value.items() if k!='results'} for case,value in summaries.items()},
    'memory':{'samples':len(samples),'min_free_speculative_bytes':min(s['free_speculative_bytes'] for s in samples),
        'min_pressure_free_percentage':min(s['pressure_free_percentage'] for s in samples),
        'max_server_rss_bytes':max(s['server_rss_bytes'] or 0 for s in samples),'max_swap_bytes':max(s['swap_used_bytes'] for s in samples),
        'guard_last_row':samples[-1],'after_cleanup':shutdown['resources_after']},
    'native_exit_code':shutdown['returncode'],'shutdown_failure':'Second SIGINT from original controller; Metal resource-set teardown assertion.',
    'concurrency_scaling':None,'concurrency_scaling_unavailable':'Only part of r1-c1 ran; c2/c4 not run.',
    'sustained_seconds':None,'sustained_unavailable':'Short resource admission failed; 1800s series not started.'}
(RAW/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
manifest.update(status='blocked',conclusion='Warmup2/2 passed. First c1 block stopped at free+speculative16GiB guard,1/12 successful,11 failures retained; c2/c4 and30min not run. Second controller SIGINT caused native Metal teardown assertion; no spontaneous GPU crash claim.')
manifest['unavailable'].update(completion='Memory guard interrupted first short block; subsequent cells/sustained not-run. Original cleanup sent a second SIGINT, native exit -6; fixed controller has not been rerun.',concurrency_scaling='No full three-repeat matrix; no parallelism inference.',sustained='1800s sustained series not admitted.')
manifest['conditions']['runtime_manifest']=str(RAW.relative_to(pathlib.Path.cwd())/'runtime-manifest.json')
manifest['unavailable'].pop('conditions.runtime_manifest',None)
(RAW/'evidence-sha256.json').write_text(json.dumps({str(p.relative_to(RAW)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
manifest['evidence_files']=sorted('raw/'+str(p.relative_to(RAW)) for p in RAW.rglob('*') if p.is_file())
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with (ROOT/'measurements.tsv').open('w',newline='') as stream:
    writer=csv.writer(stream,delimiter='\t',lineterminator='\n')
    writer.writerow('observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split())
    writer.writerows(rows)
print(json.dumps({'status':'blocked','attempts':summary['attempts'],'observations':len(rows)}))
