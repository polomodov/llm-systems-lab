# -*- coding: utf-8 -*-
"""Separate, preregistered 32K budget comparison on an owned native server."""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import traceback

RAW=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('base_driver',RAW/'lab32_runner.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


def run_probe(server,label,kind,repeat,count):
    case=f'ctx32768-{label}-{kind}-{repeat}'
    fixture=RAW/f'{label}-{kind}-request.json'
    offset=server.log.stat().st_size
    failure=None
    try:
        r.probe(server,case,fixture,'LAB_SENTINEL_42' if kind=='long' else 'LAB_VALUE_42' if kind.startswith('tool') else 'LAB_READY',
                tool=kind.startswith('tool'),expected_tokens=count if kind=='long' else None)
    except RuntimeError as exc:
        failure=exc
    finally:
        fragment=server.log.read_text()[offset:]
        (RAW/(case+'-server-fragment.txt')).write_text(fragment)
        manifest=json.loads(r.MANIFEST.read_text())
        attempt=next(a for a in manifest['planned_attempts'] if a['id']==case)
        attempt['evidence_files']=sorted(set(attempt['evidence_files']+[f'raw/{case}-server-fragment.txt']))
        manifest['evidence_files']=sorted('raw/'+p.name for p in RAW.iterdir() if p.is_file())
        r.MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    if failure:
        execution=json.loads((RAW/(case+'-execution.json')).read_text())
        metrics=execution['metrics'] or {}
        # These are model-output failures, not permission to ignore resource/transport errors.
        semantic=execution['reason'] in ['Final marker/tool mismatch','Non-stop final']
        healthy=execution['returncode']==0 and metrics.get('http_status')==200 and metrics.get('stream_done') and metrics.get('usage',{}).get('prompt_tokens')==count
        if kind!='long' or not semantic or not healthy or not r.safe(execution['before']) or not r.safe(execution['after']):
            raise failure
        server.ensure()
        print(json.dumps({'case':case,'semantic_failure_retained':True,'finish_reason':metrics['finish_reason']}),flush=True)


def run():
    expected={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (RAW/'baseline-binaries.sha256').read_text().splitlines()}
    actual={name:hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() for name in expected}
    assert expected==actual
    r.write('all-binaries-verification.json',{'timestamp':r.now(),'accepted':True,'sha256':actual})
    hardware={name:subprocess.check_output(cmd,text=True).strip() for name,cmd in [
        ('chip',['sysctl','-n','machdep.cpu.brand_string']),('ram_bytes',['sysctl','-n','hw.memsize']),
        ('macos',['sw_vers','-productVersion']),('build',['sw_vers','-buildVersion']),('architecture',['uname','-m'])]}
    r.write('fresh-hardware.json',{'timestamp':r.now(),'hardware':hardware,'memory_power':r.sample()})
    r.preflight()
    runtime=json.loads((RAW/'runtime-manifest.json').read_text())
    runtime.update(contexts=[32768],scope='separate reasoning-budget diagnostic',server_reasoning_budget=-1,request_reasoning_budgets=[None,128,512],output_cap=2048)
    r.write('runtime-manifest.json',runtime)
    m=json.loads(r.MANIFEST.read_text());m['conditions']['hardware_snapshot']=str((RAW/'fresh-hardware.json').relative_to(pathlib.Path.cwd()))
    next(a for a in m['planned_attempts'] if a['id']=='preflight')['evidence_files'] += ['raw/all-binaries-verification.json','raw/fresh-hardware.json']
    r.MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    server=r.Server(32768)
    try:
        server.ready()
        payload=json.loads((RAW/'baseline-ctx32768-long-request.json').read_text())
        _,template=r.request('/apply-template',{'messages':payload['messages'],'chat_template_kwargs':payload['chat_template_kwargs']})
        _,tokens=r.request('/tokenize',{'content':template['prompt'],'add_special':False,'parse_special':True})
        old=json.loads((RAW/'baseline-ctx32768-long-count.json').read_text())
        count=len(tokens['tokens']);digest=hashlib.sha256(template['prompt'].encode()).hexdigest()
        assert count==old['input_tokens']==28670 and digest==old['prompt_sha256']
        r.write('prompt-verification.json',{'timestamp':r.now(),'accepted':True,'input_tokens':count,'prompt_sha256':digest,'baseline_count':old})
        r.register_result('prompt-verification',True,['raw/prompt-verification.json'])
        for repeat in ['warmup','r1','r2','r3']:
            for label in ['control','budget128','budget512']:
                run_probe(server,label,'long',repeat,count)
        for label in ['budget128','budget512']:
            for kind in ['chat','chat-stream','tool','tool-stream']:
                for repeat in ['warmup','r1','r2','r3']:
                    run_probe(server,label,kind,repeat,count)
    finally:
        server.shutdown()


if __name__=='__main__':
    try:run()
    except Exception:
        (RAW/'driver-error.txt').write_text(traceback.format_exc())
        raise
