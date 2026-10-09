# -*- coding: utf-8 -*-
"""Offline replay of primary qualification bytes; never calls an endpoint."""
import collections,csv,hashlib,json,pathlib,statistics
RAW=pathlib.Path(__file__).resolve().parent
ROOT=RAW.parent

def read(name):return json.loads((RAW/name).read_text())
def export():
    manifest=json.loads((ROOT/'manifest.json').read_text());attempts={a['id']:a for a in manifest['planned_attempts']}
    assert all(a['status'] in ['completed','failed','not-run'] for a in attempts.values())
    for name,digest in read('registered-source-hashes.json').items():assert hashlib.sha256((RAW/name).read_bytes()).hexdigest()==digest,name
    suffix='.before-review-20261009'
    assert hashlib.sha256((RAW/('registered-source-hashes.json'+suffix)).read_bytes()).hexdigest()=='52e9c443621c63e3a7acdf53cecadd705a2c37d0543a252af60156cec4af0c9e'
    for name,digest in read('registered-source-hashes.json'+suffix).items():
        original=name+suffix if name in ['variants.json','metal-tensor/build-reference.json','run_qualification.py'] else name
        assert hashlib.sha256((RAW/original).read_bytes()).hexdigest()==digest,original
    assert hashlib.sha256((RAW/('evidence-sha256.json'+suffix)).read_bytes()).hexdigest()=='65bed427f6590c638509fa0655d52a84488780cbc04ac9461afd1ee85db4f844'
    changed=['registered-source-hashes.json','variants.json','metal-tensor/build-reference.json','run_qualification.py','export_qualification.py','write_report.py','summary.json','software-validation.json']
    for name,digest in read('evidence-sha256.json'+suffix).items():
        original=name+suffix if name in changed else name
        assert hashlib.sha256((RAW/original).read_bytes()).hexdigest()==digest,original
    rows=[];cases={};variants={};total=failed=0;finishes=collections.Counter()
    def add(identifier,metric,value,unit,evidence,repeat='',reason=''):
        variant=identifier.split('-chat-')[0].split('-load-')[0]
        rows.append([f'o{len(rows)+1}',attempts[identifier]['configuration_id'],'qwen35-9b-q6-k','llama-cpp-b8407-'+variant,'metal',8192,repeat,metric,value if value is not None else '',unit,'measured' if value is not None else 'unavailable','raw/'+evidence,reason])
    for variant,config in read('variants.json').items():
        data={'http_qualification_completed':all(a['status']=='completed' for key,a in attempts.items() if key.startswith(variant+'-')),'fixtures':{},'source_label':config['source_label'],'tensor':config['tensor']}
        data['qualification_completed']=data['http_qualification_completed']
        directory=RAW/variant
        for path in sorted(directory.glob('*/summary.json')):
            case=path.parent.name;identifier=variant+'-'+case;summary=json.loads(path.read_text())
            records=[json.loads(p.read_text()) for p in sorted(path.parent.glob('request-*.json'))]
            assert records==summary['results'] and len(records)==summary['requests']==1
            assert summary['successful']==sum(r['ok'] for r in records) and summary['failed']==sum(not r['ok'] for r in records)
            fixture=case.split('-')[0];request=read(variant+'/'+fixture+'-request.json');body=json.dumps(request,ensure_ascii=False,separators=(',',':')).encode()
            assert (path.parent/'request.json').read_bytes()==body
            cfg=json.loads((path.parent/'config.json').read_text());assert cfg['request_sha256']==hashlib.sha256(body).hexdigest() and cfg['concurrency']==1
            assert json.loads((path.parent/'request.json').read_bytes())==read(fixture+'-request.json')
            record=records[0];total+=1;failed+=not record['ok'];response=path.parent/'request-0001.response.bin'
            assert (response.stat().st_size if response.exists() else 0)==record['response_bytes']
            contract=None
            if record['ok']:
                payload=json.loads(response.read_bytes());assert record['http_status']==200
                choice=payload['choices'][0];message=choice['message'];assert message['role']=='assistant' and message['content'].strip()
                assert not message.get('tool_calls') and not message.get('function_call')
                assert choice['finish_reason']==record['finish_reason'] in ['stop','length']
                for key in ['prompt_tokens','completion_tokens']:assert payload['usage'][key]==record[key] and type(record[key]) is int and record[key]>=0
                assert summary['success_latency_median_seconds']==summary['success_latency_p95_seconds']==record['latency_seconds']
                assert summary['successful_completion_tokens_per_second']==record['completion_tokens']/summary['batch_wall_seconds']
                contract=message['content'].strip()=='LAB_READY' if fixture=='chat' else True
                finishes[record['finish_reason']]+=1
            else:assert record['error']
            contract_path=directory/(case+'-contract.json')
            if contract_path.exists():
                saved=json.loads(contract_path.read_text());assert saved['accepted']==bool(record['ok'] and contract and summary['success_latency_p95_seconds']<=240)
            if attempts[identifier]['status']=='completed':assert record['ok'] and contract and summary['success_latency_p95_seconds']<=240
            cases[identifier]={'status':attempts[identifier]['status'],'record':record,'batch_wall_seconds':summary['batch_wall_seconds'],'contract':contract,'input_sha256':cfg['request_sha256'],'evidence':str(path.relative_to(RAW))}
            repeat='' if case.endswith('warmup') else int(case[-1])
            for metric,unit in [('latency_seconds','s'),('completion_tokens','tokens'),('prompt_tokens','tokens'),('http_status','http-status')]:
                add(identifier,metric,record[metric],unit,variant+'/'+case+'/request-0001.json',repeat,'Failed response/usage unavailable.' if record[metric] is None else '')
            add(identifier,'successful_completion_tokens_per_second',summary['successful_completion_tokens_per_second'],'tokens/s',str(path.relative_to(RAW)),repeat,'Usage unavailable.' if summary['successful_completion_tokens_per_second'] is None else '')
            add(identifier,'final_contract',int(bool(contract)) if contract is not None else None,'bool',variant+'/'+case+'/request-0001.json',repeat,'No successful final content.' if contract is None else '')
            add(identifier,'ttft_seconds',None,'s',str(path.relative_to(RAW)),repeat,'Non-streaming full-response probe.')
        for fixture in ['chat','load']:
            ids=[variant+'-'+fixture+'-r'+str(r) for r in [1,2,3]]
            valid=all(identifier in cases and cases[identifier]['status']=='completed' for identifier in ids)
            data['fixtures'][fixture]={'complete_three_repeats':valid,'cases':ids,'median_latency_seconds':statistics.median(cases[i]['record']['latency_seconds'] for i in ids) if valid else None,'median_completion_tokens_per_second':statistics.median(cases[i]['record']['completion_tokens']/cases[i]['batch_wall_seconds'] for i in ids) if valid else None,'completion_tokens':[cases[i]['record']['completion_tokens'] for i in ids if i in cases],'reason':None if valid else 'Three completed measurement repeats required.'}
        if (directory/'startup-execution.json').exists():
            startup=read(variant+'/startup-execution.json');assert startup['tensor_capability']==config['tensor'] and startup['offload']=='33/33'
        families=['libggml','libggml-base','libggml-cpu','libggml-metal','libggml-blas','libllama','libmtmd']
        expected_libraries={name:digest for name,digest in config['binaries'].items() if name.endswith('.dylib')}
        assert all(str(pathlib.Path(config['build'])/'bin'/(family+'.dylib')) in expected_libraries for family in families)
        assert read(variant+'/build-reference.json')['binaries']==config['binaries']
        actual_pins=read(variant+'/startup-process.json')['pinned_binaries'] if (directory/'startup-process.json').exists() else {}
        missing=sorted(name for name,digest in expected_libraries.items() if actual_pins.get(name)!=digest)
        data['libraries_verified_at_execution']=not missing
        data['missing_library_pins_at_execution']=missing
        data['qualification_completed']=data['http_qualification_completed'] and not missing
        if (directory/'shutdown-execution.json').exists():data['shutdown']=read(variant+'/shutdown-execution.json')
        if (directory/'memory-timeline.jsonl').exists():
            samples=[json.loads(line) for line in (directory/'memory-timeline.jsonl').read_text().splitlines()]
            data['memory']={'samples':len(samples),'max_rss_bytes':max(s['server_rss_bytes'] or 0 for s in samples),'min_free_speculative_bytes':min(s['free_speculative_bytes'] for s in samples),'pressure_levels':sorted(set(s['pressure_level'] for s in samples)),'max_swap_bytes':max(s['swap_used_bytes'] for s in samples)}
            if data['http_qualification_completed']:
                from resources import safe
                assert all(safe(s) and (s['server_rss_bytes'] or 0)<=24*2**30 for s in samples)
                assert data['shutdown']['returncode']==0 and data['shutdown']['guard_reason'] is None
                assert len(data['shutdown']['interrupts'])==1
        variants[variant]=data
    summary={'status':'blocked','scope':'One-sided Apple qualification; no fresh paired Ryzen measurements or agent verdicts.','attempts':dict(collections.Counter(a['status'] for a in attempts.values())),'http_requests':total,'http_errors':int(failed),'finish_reasons':dict(finishes),'variants':variants,'cases':cases,'ryzen_comparison':None,'agent_comparison':None,'gpu_budget_gib':None,'ttft_seconds':None}
    (RAW/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    manifest['status']='blocked';manifest['conclusion']='Apple qualification recorded; complete LAB35 awaits fresh alternating Ryzen pair and accepted LAB08/LAB09 agent runs.'
    manifest['unavailable']['completion']='No fresh paired Ryzen HTTP series or accepted local provider bridge/agent verdicts.'
    manifest['unavailable']['tensor_library_identity']='Original tensor startup verified executables only; bundled dylib pins are a post-review correction. A new preregistered run is required to establish execution-time library identity.'
    manifest['conditions']['runtime_manifest']=str(pathlib.Path('experiments/local-models/measurements')/(manifest['lab_id']+'-'+manifest['session_id'])/'raw/summary.json')
    manifest['unavailable'].pop('conditions.runtime_manifest',None)
    with (ROOT/'measurements.tsv').open('w',newline='') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow('observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split());w.writerows(rows)
    (RAW/'evidence-sha256.json').write_text(json.dumps({str(p.relative_to(RAW)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
    manifest['evidence_files']=sorted('raw/'+str(p.relative_to(RAW)) for p in RAW.rglob('*') if p.is_file());(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'blocked','attempts':summary['attempts'],'http_requests':total,'http_errors':int(failed),'observations':len(rows)}))
if __name__=='__main__':export()
