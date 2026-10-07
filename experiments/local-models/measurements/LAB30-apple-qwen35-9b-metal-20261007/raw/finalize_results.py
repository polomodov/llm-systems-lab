# -*- coding: utf-8 -*-
import csv,hashlib,json,pathlib,re,shutil,statistics,subprocess
raw=pathlib.Path(__file__).resolve().parent;report=raw.parent;repo=pathlib.Path.cwd()
relative=report.relative_to(repo).as_posix()
pilot=[f'{kind}-r{n}' for n in [1,2,3] for kind in ['pp','tg']]
primary=[f'{kind}-power-r{n}' for n in [1,2,3] for kind in ['pp','tg']]
records={name:json.loads((raw/(name+'-execution.json')).read_text()) for name in ['smoke','warmup-pp','warmup-tg']+pilot+primary}
assert all(v['accepted'] and v['returncode']==0 for v in records.values())
summary={'engine_source_commit':'312cf03328496df9c56fe843952cf02a8964c59a','model':'Qwen3.5-9B-Q6_K','backend':'Metal','primary_series':'confirmed AC power','primary':{},'pilot':{},'cases':{}}
allocations={}
columns=(report/'measurements.tsv').read_text().splitlines()[0].split('\t');rows=[]
configs={a['id']:a['configuration_id'] for a in json.loads((report/'manifest.json').read_text())['planned_attempts']}
def obs(name,metric,value,unit,file,repeat='',context=''):
    row={k:'' for k in columns};row.update(observation_id=name+'-'+metric,configuration_id=configs[name],model_id='Qwen/Qwen3.5-9B',engine='llama.cpp b8407 source commit312cf033',backend='metal',repeat=str(repeat),context_tokens=str(context),metric=metric,value=str(value),unit=unit,status='measured',evidence_path='raw/'+file);rows.append(row)
for name,v in records.items():
    timeline=[json.loads(line) for line in (raw/(name+'-memory.jsonl')).read_text().splitlines() if line]
    before=json.loads((raw/(name+'-memory-before.json')).read_text());after=v['after'];samples=[before]+timeline+[after]
    min_free=min(s['free_pages_bytes'] for s in samples if s['free_pages_bytes'] is not None)
    swaps=[s['swap_used_bytes'] for s in samples if s['swap_used_bytes'] is not None]
    item={'native_exit':v['returncode'],'benchmark_rows':v['benchmark_rows'],'time_wall_seconds':v['time_wall_seconds'],'controller_observed_wall_seconds':v['observed_wall_seconds'],'max_rss_bytes':v['max_rss_bytes'],'minimum_sampled_free_pages_bytes':min_free,'swap_usage_range_bytes':[min(swaps),max(swaps)],'power_observed':all(s.get('on_ac_power') and s.get('ac_power_mode')==0 for s in samples) if name in primary else None}
    summary['cases'][name]=item
    if name in primary:assert item['power_observed'] and max(swaps)==min(swaps)==0 and min_free>=16*2**30
    log=(raw/(name+'-process.txt')).read_text()
    mapped=[{'backend':backend,'mib':float(mib)} for backend,mib in re.findall(r'(CPU_Mapped|MTL0_Mapped) model buffer size\s*=\s*([0-9.]+) MiB',log)]
    buffers=[{'backend':backend,'kind':kind,'mib':float(mib)} for backend,kind,mib in re.findall(r'(MTL0|CPU) (KV|RS|compute) buffer size\s*=\s*([0-9.]+) MiB',log)]
    allocations[name]={'mapped_model_buffers':mapped,'context_buffers':buffers,'offloaded_layers':re.findall(r'offloaded (\d+)/(\d+) layers to GPU',log),'do_not_sum_with_rss':True}
    if name in pilot+primary:
        bench=v['benchmark_rows'][0];repeat=name[-1]
        # Context is workload depth plus output, not a declared 8K/16K/32K server cap.
        ctx_values=re.findall(r'llama_context: n_ctx\s*=\s*(\d+)',log)
        context=int(ctx_values[-1]) if ctx_values else ''
        for metric,value,unit in [('tokens_per_second',bench['avg_ts'],'tokens/s'),('wall_seconds',v['time_wall_seconds'],'seconds'),('max_rss_bytes',v['max_rss_bytes'],'bytes'),('min_sampled_free_pages_bytes',min_free,'bytes'),('max_swap_used_bytes',max(swaps),'bytes')]:
            obs(name,metric,value,unit,'results-summary.json' if metric in ['max_swap_used_bytes','min_sampled_free_pages_bytes'] else name+'-execution.json',repeat,context)
for label,names in [('primary',primary),('pilot',pilot)]:
    for kind in ['pp','tg']:
        values=[records[n]['benchmark_rows'][0]['avg_ts'] for n in names if n.startswith(kind)]
        summary[label][kind]={'median_tokens_per_second':statistics.median(values),'min_tokens_per_second':min(values),'max_tokens_per_second':max(values),'repeat_count':len(values)}
ryzen=repo/'experiments/local-models/measurements/LAB04-qwen35-9b-prebuilt/raw'
comparison={'kind':'deployment microbench comparison','primary_apple_series':'confirmed AC power','source_commit':'312cf03328496df9c56fe843952cf02a8964c59a','conditions_checked':['n_prompt','n_gen','n_depth','n_batch','n_ubatch','n_threads','type_k','type_v','n_gpu_layers','flash_attn'],'backends':{},'limitations':['Different hardware/OS/compiler and source/prebuilt bundles.','Apple tensor API probe failed; standard Metal SIMD path active.','Historical Ryzen evidence, not simultaneous randomized trials.','No agent success/quality or energy claim.']}
for backend in ['vulkan','hip']:
    comparison['backends'][backend]={}
    for kind in ['pp','tg']:
        source_rows=[]
        apple=records[kind+'-power-r1']['benchmark_rows'][0]
        for n in [1,2,3]:
            file=backend+'-r'+str(n)+'-'+kind+'.json'
            row=json.loads((ryzen/file).read_text())[0]
            assert all(row[key]==apple[key] for key in comparison['conditions_checked'])
            assert '312cf03328496df9c56fe843952cf02a8964c59a'.startswith(row['build_commit'])
            shutil.copyfile(ryzen/file,raw/('ryzen-'+file));source_rows.append(row)
        median=statistics.median(x['avg_ts'] for x in source_rows);applemedian=summary['primary'][kind]['median_tokens_per_second']
        comparison['backends'][backend][kind]={'ryzen_median_tokens_per_second':median,'apple_median_tokens_per_second':applemedian,'apple_to_ryzen_ratio':applemedian/median,'apple_change_percent':100*(applemedian/median-1)}
(raw/'results-summary.json').write_text(json.dumps(summary,indent=2)+'\n');(raw/'buffer-allocation-summary.json').write_text(json.dumps(allocations,indent=2)+'\n');(raw/'ryzen-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
with (report/'measurements.tsv').open('w',newline='',encoding='utf-8') as out:
    writer=csv.DictWriter(out,fieldnames=columns,delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
pp=summary['primary']['pp']['median_tokens_per_second'];tg=summary['primary']['tg']['median_tokens_per_second'];peak=max(v['max_rss_bytes'] for v in records.values())/2**30
m=json.loads((report/'manifest.json').read_text());m.update(status='completed',conditions={'hardware_snapshot':relative+'/raw/hardware-snapshot.json','model_artifact_manifest':relative+'/raw/artifact-manifest.json','runtime_manifest':relative+'/raw/runtime-manifest.json','harness_profile':None},conclusion=f'Native arm64 Metal source build b8407/312cf033 работает с Qwen3.5-9B Q6_K: offload33/33, FA1, swap0. Подтверждённая AC серия: PP2048 median {pp:.2f} tokens/s, TG128@4096 median {tg:.2f}; max RSS {peak:.3f} GiB. Tensor API unavailable; standard Metal SIMD. GPU allocation limit и агентное качество не измерены.',unavailable={'conditions.harness_profile':'Backend microbench без агентского harness.','gpu_budget_gib':'Подтверждена заданная нагрузка, не максимальный безопасный GPU allocation limit.','energy':'Энергия не измерялась.','temperature':'Температура/thermal throttling не измерялись.','pilot-power-timeline':'В первичной pilot серии нет свежей power telemetry; отдельная primary серия исправляет наблюдаемость.'})
m['evidence_files']=['raw/'+f.name for f in sorted(raw.iterdir()) if f.is_file()];(report/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'primary':summary['primary'],'peak_rss_gib':peak,'ratios':comparison['backends']},indent=2))
