"""Offline inventory/report summary. Never calls a server or judges a task."""
import csv,datetime,hashlib,json,pathlib
RAW=pathlib.Path(__file__).resolve().parent;ROOT=RAW.parent;REPOSITORY=ROOT.parents[3]
def read(path):return json.loads(path.read_text())
def export():
    manifest=read(ROOT/'manifest.json');runs=[]
    for identifier in manifest['run_ids']:
        folder=REPOSITORY/'results/runs'/identifier;record=read(folder/'run.json')
        assert record['status']=='aborted' and record['verdict']['result']=='aborted'
        proof=read(folder/'trace/local-native/startup-process.json');assert record['local_inference']['observed']==proof
        expected={f['path']:f['sha256'] for f in record['local_inference']['deployment']['engine']['files']}
        assert all(proof['verified_files'][name]==digest for name,digest in expected.items())
        assert len(expected)==23 and sum(name.endswith('.dylib') for name in expected)==21
        assert proof['verified_before_popen'] and proof['verified_at']<=proof['popen_invoked_at']
        shutdown=read(folder/'trace/local-native/shutdown-process.json');assert shutdown['exit']=={'code':0,'signal':None} and shutdown['sigint_count']==1
        replies=sorted([read(p) for p in (folder/'trace/inference').glob('*-record.json')],key=lambda r:r['index']) if (folder/'trace/inference').exists() else []
        successful=[r for r in replies if r['accepted']];assert all(r['usage'] for r in successful)
        assert all(record['loop'][field] is None for field in ['tokens_in','tokens_out','cost_usd','turns'])
        samples=[json.loads(line) for line in (folder/'trace/local-native/native-memory.jsonl').read_text().splitlines()]
        gaps=[(datetime.datetime.fromisoformat(b['timestamp'])-datetime.datetime.fromisoformat(a['timestamp'])).total_seconds() for a,b in zip(samples,samples[1:])]
        runs.append({'run_id':identifier,'status':record['status'],'stop_reason':record['loop']['stop_reason'],'configured_timeout_s':record['execution']['timeout_s'],'agent_wall_clock_s':record['loop']['wall_clock_s'],'leased_jobs':len(replies),'accepted_http_responses':len(successful),'failed_jobs':len(replies)-len(successful),'primary_requests':len(list((folder/'trace/inference').glob('*-request.json'))) if (folder/'trace/inference').exists() else 0,'partial_prompt_tokens':sum(row['usage']['input'] for row in successful) if successful else None,'partial_completion_tokens':sum(row['usage']['output'] for row in successful) if successful else None,'complete_usage':False,'samples':len(samples),'max_sample_gap_s':max(gaps,default=None),'observed_max_rss_bytes':max((r['server_rss_bytes'] for r in samples),default=None),'max_observed_swap_bytes':max((r['swap_used_bytes'] for r in samples),default=None),'normal_observed_pressure':all(r['pressure_level']==1 for r in samples),'all_observed_ac':all(r['on_ac_power'] for r in samples),'shutdown':shutdown,'identity':'controlled native process; 23 engine pins checked before Popen','library_identity_verified':True})
    summary={'status':'blocked','scope':'First Pi/T002/macOS-Metal bridge implementation; no agent pass or completed LAB08 admission','runs':runs,'offline_tests_passed':171,'offline_tests_skipped':2,'docker_boundary_passed':True,'docker_sdk_roundtrip_passed':True,'fresh_native_requalification_after_stale_guard':False,'independent_verdicts':None,'full_lab08_completed':False}
    (RAW/'runtime-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    for configuration,run in zip(['pi-qwen35-q6-metal-8k','pi-qwen35-q6-metal-8k-readiness-fixed'],runs):
        evidence='raw/runtime-summary.json'
        for metric,key,unit in [('accepted_http_responses','accepted_http_responses','requests'),('failed_jobs','failed_jobs','jobs'),('primary_requests','primary_requests','requests'),('wall_clock_s','agent_wall_clock_s','s'),('partial_prompt_tokens','partial_prompt_tokens','tokens'),('partial_completion_tokens','partial_completion_tokens','tokens'),('observed_peak_rss_bytes','observed_max_rss_bytes','bytes'),('max_sample_gap_s','max_sample_gap_s','s')]:
            value=run[key];rows.append([f'o{len(rows)+1}',configuration,'qwen35-9b-q6-k','llama-cpp-b8407-tensor','metal',8192,1,metric,value if value is not None else '',unit,'measured' if value is not None else 'unavailable',evidence,'No agent execution or no successful primary responses.' if value is None else ''])
        for metric,reason in [('complete_tokens_in','Incomplete attempt; primary usage missing for failed/canceled job.'),('complete_tokens_out','Incomplete attempt; primary usage missing for failed/canceled job.'),('cost_usd','Hardware/energy cost not measured; SDK placeholders not accepted.'),('ttft_seconds','SSE buffered until finish/DONE.'),('energy_joules','No energy collector.'),('temperature','No verified thermal collector.')]:rows.append([f'o{len(rows)+1}',configuration,'qwen35-9b-q6-k','llama-cpp-b8407-tensor','metal',8192,1,metric,'','','unavailable',evidence,reason])
    with (ROOT/'measurements.tsv').open('w',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t',lineterminator='\n');writer.writerow('observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split());writer.writerows(rows)
    manifest.update(status='blocked',conclusion='Pi local bridge and synthetic/Docker acceptance implemented. First pilot failed broker readiness; retry timed out after a 913.904 s telemetry gap. Failures retained; wall/stale guards fixed in software, new native qualification and independent judged pilot remain pending.')
    retry=next(a for a in manifest['planned_attempts'] if a['id']=='pilot-t002-retry');retry.update(status='failed',reason='Actual pilot aborted by timeout; telemetry gap 913.904 s, cause unknown. Twelve accepted HTTP responses; canceled job lacks usage. No independent success verdict.',evidence_files=['raw/pilot-retry-driver.txt','raw/runtime-summary.json','raw/pilot-retry-registration.json'])
    manifest['conditions']['runtime_manifest']='experiments/local-models/measurements/'+ROOT.name+'/raw/runtime-summary.json'
    manifest['unavailable'].pop('conditions.runtime_manifest',None);manifest['unavailable'].update(completion='Fresh native requalification after wall/stale guard changes and independently judged T002 pilot absent.',gpu_budget_gib='Maximum GPU allocation not measured.',energy='No energy collector.',ttft='Buffered SSE.',temperature='No verified thermal collector.',telemetry_gap_cause='No independent sleep/suspension/clock-change evidence; cause remains unknown.')
    manifest['evidence_files']=sorted('raw/'+str(p.relative_to(RAW)) for p in RAW.rglob('*') if p.is_file());(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'blocked','runs':len(runs),'accepted_http_responses':sum(r['accepted_http_responses'] for r in runs),'observations':len(rows)}))
if __name__=='__main__':export()
