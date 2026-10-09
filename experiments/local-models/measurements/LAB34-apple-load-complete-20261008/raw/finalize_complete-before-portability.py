# -*- coding: utf-8 -*-
"""Revalidate primary load records and the full sustained interval offline."""
import collections, csv, hashlib, json, math, pathlib, statistics

RAW=pathlib.Path(__file__).resolve().parent
ROOT=RAW.parent

def read(name):return json.loads((RAW/name).read_text())

def validate_block(name):
    summary=read(name+'/summary.json')
    directory=RAW/name
    records=[read(str(p.relative_to(RAW))) for p in sorted(directory.glob('request-*.json'))]
    assert records==summary['results'] and len(records)==summary['requests']
    assert sum(r['ok'] for r in records)==summary['successful']
    assert sum(not r['ok'] for r in records)==summary['failed']
    body=json.dumps(read('load-request.json'),ensure_ascii=False,separators=(',',':')).encode()
    assert (directory/'request.json').read_bytes()==body
    assert read(name+'/config.json')['request_sha256']==hashlib.sha256(body).hexdigest()
    for record in records:
        response=directory/f'request-{record["index"]:04d}.response.bin'
        assert response.stat().st_size==record['response_bytes']
        if record['ok']:
            data=json.loads(response.read_bytes())
            assert len(data['choices'])==1 and record['http_status']==200
            choice=data['choices'][0];message=choice['message']
            assert message['role']=='assistant' and message['content'].strip()
            assert not message.get('tool_calls') and not message.get('function_call')
            assert choice['finish_reason']==record['finish_reason'] in ['stop','length']
            for key in ['prompt_tokens','completion_tokens']:
                assert data['usage'][key]==record[key] and type(record[key]) is int and record[key]>=0
        else:assert record['error']
    good=[r for r in records if r['ok']]
    latencies=[r['latency_seconds'] for r in good]
    assert statistics.median(latencies)==summary['success_latency_median_seconds']
    assert sorted(latencies)[math.ceil(.95*len(latencies))-1]==summary['success_latency_p95_seconds']
    assert max(latencies)==summary['success_latency_max_seconds']
    assert sum(r['completion_tokens'] for r in good)==summary['completion_tokens_successful']
    assert summary['successful_completion_tokens_per_second']==summary['completion_tokens_successful']/summary['batch_wall_seconds']
    assert summary['successful_requests_per_second']==len(good)/summary['batch_wall_seconds']
    return summary,records

def finalize():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    attempts={a['id']:a for a in manifest['planned_attempts']}
    assert all(a['status'] in ['completed','failed','not-run'] for a in attempts.values())
    for name,digest in read('registered-source-hashes.json').items():
        assert hashlib.sha256((RAW/name).read_bytes()).hexdigest()==digest,name
    runtime=read('runtime-manifest.json')
    assert runtime['server_slots']==1 and runtime['context_per_slot']==8192
    assert runtime['request_timeout_seconds']==300 and runtime['latency_p95_limit_seconds']==240
    rows=[];blocks={};finishes=collections.Counter()
    def add(case,metric,value,unit,evidence,repeat='',reason='',status=None):
        rows.append([f'o{len(rows)+1}',attempts[case]['configuration_id'],'qwen35-9b-q6-k','llama.cpp-b8407-tile16','metal',8192,
            repeat,metric,value if value is not None else '',unit,status or ('measured' if value is not None else 'unavailable'),
            'raw/'+evidence,reason])
    names=[a for a in attempts if (RAW/a/'summary.json').is_file()]
    series=read('sustained/series.json') if (RAW/'sustained/series.json').exists() else None
    if series:names += [b['directory'] for b in series['blocks']]
    for name in names:
        summary,records=validate_block(name)
        case='sustained' if name.startswith('sustained/') else name
        repeat=int(case[1]) if case.startswith('r') else ''
        blocks[name]={k:v for k,v in summary.items() if k!='results'}
        if attempts[case]['status']=='completed':
            assert summary['failed']==0 and summary['success_latency_p95_seconds']<=240
        for record in records:
            evidence=f'{name}/request-{record["index"]:04d}.json'
            if record['ok']:finishes[record['finish_reason']]+=1
            for metric,unit in [('latency_seconds','s'),('completion_tokens','tokens'),('prompt_tokens','tokens'),('http_status','http-status')]:
                add(case,f'{name}-request-{record["index"]}-{metric}',record[metric],unit,evidence,repeat,
                    reason='Failed response/usage unavailable.' if record[metric] is None else '')
        for metric,unit in [('batch_wall_seconds','s'),('successful','requests'),('failed','requests'),('success_latency_median_seconds','s'),
                ('success_latency_p95_seconds','s'),('success_latency_max_seconds','s'),('successful_requests_per_second','requests/s'),('successful_completion_tokens_per_second','tokens/s')]:
            add(case,name+'-'+metric,summary[metric],unit,name+'/summary.json',repeat)
        add(case,name+'-ttft',None,'s',name+'/summary.json',repeat,reason='Non-streaming complete-response probe.')
    samples=[json.loads(line) for line in (RAW/'memory-timeline.jsonl').read_text().splitlines()]
    shutdown=read('shutdown-execution.json')
    complete=all(a['status']=='completed' for a in attempts.values())
    if complete:
        assert series and series['status']=='completed' and series['planned_seconds']==1800 and series['actual_seconds']>=1800
        assert shutdown['returncode']==0 and shutdown['guard_reason'] is None
        assert len(shutdown['interrupts'])==1 and shutdown['interrupts'][0]['reason']=='normal shutdown'
        assert all(s['pressure_level']==1 and s['free_speculative_bytes']>=8*2**30 and s['pressure_free_percentage']>=50
            and s['swap_used_bytes']==0 and s['on_ac_power'] and s['ac_power_mode']==0
            and (s['server_rss_bytes'] is None or s['server_rss_bytes']<=24*2**30) for s in samples)
        assert len([name for name in blocks if name.startswith('r')])==9
        medians={c:statistics.median(blocks[f'r{r}-c{c}']['successful_requests_per_second'] for r in [1,2,3]) for c in [1,2,4]}
        expected=min(c for c,v in medians.items() if v>=.95*max(medians.values()))
        assert read('sustained-selection.json')['concurrency']==series['concurrency']==expected
    else:medians={}
    sustained_blocks=[blocks[b['directory']] for b in series['blocks']] if series else []
    sustained=None
    if sustained_blocks:
        tokens=sum(b['completion_tokens_successful'] for b in sustained_blocks)
        successes=sum(b['successful'] for b in sustained_blocks)
        sustained={'status':series['status'],'concurrency':series['concurrency'],'planned_seconds':1800,'actual_seconds':series['actual_seconds'],
            'blocks':len(sustained_blocks),'requests':sum(b['requests'] for b in sustained_blocks),'successful':successes,
            'failed':sum(b['failed'] for b in sustained_blocks),'completion_tokens_successful':tokens,
            'overall_successful_requests_per_second':successes/series['actual_seconds'],
            'overall_successful_completion_tokens_per_second':tokens/series['actual_seconds'],
            'first_block_tokens_per_second':sustained_blocks[0]['successful_completion_tokens_per_second'],
            'last_block_tokens_per_second':sustained_blocks[-1]['successful_completion_tokens_per_second']}
        for metric,unit in [('actual_seconds','s'),('overall_successful_requests_per_second','requests/s'),('overall_successful_completion_tokens_per_second','tokens/s')]:
            add('sustained',metric,sustained[metric],unit,'sustained/series.json')
    summary={'status':'completed' if complete else 'blocked','attempts':dict(collections.Counter(a['status'] for a in attempts.values())),
        'blocks':blocks,'median_short_requests_per_second':medians,'throughput_gain_vs_c1':{str(c):medians[c]/medians[1]-1 for c in [2,4]} if medians else {},
        'sustained':sustained,'finish_reasons':dict(finishes),
        'memory':{'samples':len(samples),'min_free_speculative_bytes':min(s['free_speculative_bytes'] for s in samples),
            'min_pressure_free_percentage':min(s['pressure_free_percentage'] for s in samples),'max_swap_used_bytes':max(s['swap_used_bytes'] for s in samples),
            'max_native_rss_bytes':max(s['server_rss_bytes'] or 0 for s in samples),'pressure_levels':sorted(set(s['pressure_level'] for s in samples)),
            'after_cleanup':shutdown['resources_after']},'shutdown':shutdown,'ttft_seconds':None,'gpu_budget_gib':None,
        'scope':'Fixed single server slot; client concurrency is queueing. This does not validate 2/4 simultaneous GPU slots, model quality or maximum GPU memory.'}
    (RAW/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    manifest['status']=summary['status']
    manifest['conclusion']='Full short matrix and1800s sustained completed within the separately registered boundaries; fixed single GPU slot, queue experiment.' if complete else 'Recorded campaign blocked; missing attempts/stops remain explicit.'
    if complete:manifest['unavailable'].pop('completion',None)
    else:manifest['unavailable']['completion']='Campaign failed or retains not-run attempts; see raw evidence.'
    manifest['conditions']['runtime_manifest']=str(RAW.relative_to(pathlib.Path.cwd())/'runtime-manifest.json')
    manifest['unavailable'].pop('conditions.runtime_manifest',None)
    (RAW/'evidence-sha256.json').write_text(json.dumps({str(p.relative_to(RAW)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in RAW.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
    manifest['evidence_files']=sorted('raw/'+str(p.relative_to(RAW)) for p in RAW.rglob('*') if p.is_file())
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'measurements.tsv').open('w',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t',lineterminator='\n')
        writer.writerow('observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split())
        writer.writerows(rows)
    print(json.dumps({'status':summary['status'],'attempts':summary['attempts'],'observations':len(rows),'sustained':sustained}))

if __name__=='__main__':finalize()
