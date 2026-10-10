"""Matched messages compare whole deployments, never infer an isolated backend effect."""
import datetime,json,pathlib,statistics,sys
root=pathlib.Path(__file__).resolve().parents[3];directory=(root/sys.argv[1]).resolve();raw=directory/'raw';m=json.loads((directory/'manifest.json').read_text());rows=[];table=[];summary={}
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def add(id,config,dep,repeat,metric,value,unit,path):rows.append([id+'-'+metric,config,'qwen35-9b-'+('q6' if dep=='gguf' else 'mlx-4bit'),'llama.cpp' if dep=='gguf' else 'mlx-lm','metal','8192',repeat if repeat!='warmup' else '',metric,str(value) if value is not None else '',unit,'measured' if value is not None else 'unavailable',str(path.relative_to(directory)),'' if value is not None else 'Primary field absent; no estimate.'])
for dep in ('gguf','mlx'):
 folder=raw/dep
 if not folder.exists():continue
 execution=json.loads((folder/'execution.json').read_text());memory=[json.loads(l) for l in (folder/'memory.jsonl').read_text().splitlines()] if (folder/'memory.jsonl').exists() else [];summary[dep]=dict(cold_ready_seconds=execution.get('cold_ready_seconds'),max_rss_gib=max((r['server_rss_bytes'] for r in memory),default=None),min_free_spec_gib=min((r['free_speculative_bytes'] for r in memory),default=None),max_swap_bytes=max((r['swap_used_bytes'] for r in memory),default=None),samples=len(memory),cleanup_returncode=execution.get('returncode'),sigint_count=execution.get('sigint_count'),guard=execution.get('guard'))
 for metric in ('max_rss_gib','min_free_spec_gib'):
  if summary[dep][metric] is not None:summary[dep][metric]/=2**30
 for f in sorted(folder.glob('*.metrics.json')):
  r=json.loads(f.read_text());case,repeat=f.name.removesuffix('.metrics.json').rsplit('-',1);id=f'{dep}-{case}-{repeat}';attempt=next(a for a in m['planned_attempts'] if a['id']==id);usage=r.get('usage') or {};final=folder/(case+'-'+repeat+'.final.json');content=json.loads(final.read_text()).get('content') if final.exists() else None
  table.append(f'| {dep}/{case}/{repeat} | {attempt["status"]} | {repr(content)} | {r.get("ttft_content_s")} | {r.get("duration_s")} | {usage.get("prompt_tokens")}/{usage.get("completion_tokens")} |')
  for metric,value,unit in [('ttft_content_s',r.get('ttft_content_s'),'s'),('duration_s',r.get('duration_s'),'s'),('prompt_tokens',usage.get('prompt_tokens'),'tokens'),('completion_tokens',usage.get('completion_tokens'),'tokens')]:add(id,attempt['configuration_id'],dep,repeat,metric,value,unit,f)
save(raw/'runtime-summary.json',summary);m['unavailable'].update(energy='No energy collector.',temperature='No temperature collector.',gpu_budget_gib='Maximum GPU allocation not measured.',mlx_hard_context_cap='MLX labels an input budget, not a reserved KV context or hard cap.')
m['evidence_files']=sorted(str(f.relative_to(directory)) for f in raw.rglob('*') if f.is_file());save(directory/'manifest.json',m)
header='observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split();(directory/'measurements.tsv').write_text('\t'.join(header)+'\n'+''.join('\t'.join(r)+'\n' for r in rows))
counts={s:sum(a['status']==s for a in m['planned_attempts']) for s in ('completed','failed','not-run')}
(directory/'report.md').write_text(f'''# LAB31 — одинаковые HTTP-входы для GGUF и MLX

Сессия `{m['session_id']}`, статус **{m['status']}**. {m['conclusion']}

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. GGUF Q6_K revision 3885219b6810b007914f3a7950a8d1b469d598a5 / llama.cpp 312cf03328496df9c56fe843952cf02a8964c59a tensor tile16 Metal против MLX affine 4-bit/group64 revision 938d8919941c6e7efd3c7150eff7fe9d12afa631 / MLX-LM 0.32.0 / MLX 0.32.3. Exact paths/bytes/hashes: [GGUF](raw/gguf-reference.json), [MLX runtime](raw/runtime-manifest.json), [artifacts](raw/artifact-manifest.json), [full MLX prestart pins](raw/prestart-pins.json). Две MLX safetensors shards не оцениваются по размеру GGUF. VLM artifact используется только для текста. Агентных episodes нет.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration закреплены commit до исполнения. Порядок GGUF → MLX, один собственный сервер. [Входы](raw/shared-inputs.json) совпадают по messages; temp 0, seed 1, top_p 1, output cap 256, thinking false, streaming/include_usage. На каждый вход — один прогрев и три повтора. Final сравнивается буквально, без trim и нормализации. Внутренние templates, token IDs и квантизация могут различаться: оцениваются целые deployments.

## Ход выполнения

[Контроллер](raw/run_common.py) проверяет model/native pins до Popen, отсутствие чужих моделей и порт. GGUF logs/props/slots проверяют M5/tensor/offload 33/33/context 8192. MLX observer проверяет actual default GPU, loaded native images и allocator. Resource guard каждые 2 с: free+spec ≥8 GiB, pressure level 1, swap 0, AC/mode 0, RSS ≤24 GiB, gap ≤15 с, deadline 900 с. HTTP клиент ограничен 120 с. Shutdown: один собственный SIGINT, 30 с, затем own kill при необходимости. ОС и чужие приложения не меняются.

## Результаты

Attempts: {json.dumps(counts)}. Cold readiness от Popen учитывается отдельно в [runtime summary](raw/runtime-summary.json). TTFT — первое непустое content delta, total — время до полного SSE; usage из первичного ответа.

| Deployment/case/repeat | Статус | Raw final | TTFT, с | Total, с | Input/output tokens |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(table) or '| — | Не выполнено | — | — | — | — |'}

## Ошибки и ограничения

{m['unavailable'].get('completion','Все зарегистрированные попытки выполнены.')} Одинаковые messages не означают одинаковый prompt token count. GGUF резервирует context 8192; MLX short-input budget 8192 не является hard cap. Три повтора не доказывают статистическую эквивалентность. Энергия, температура и максимальный GPU budget неизвестны. Смена формата и quant исключает вывод о влиянии одного Metal/MLX backend.

## Вывод по гипотезе

{m['conclusion']} Вывод ограничен этими входами, настройками, версиями и состоянием памяти. Скорость HTTP примитива не означает качество автономного агента.

## Ответы на контрольные вопросы

1. Новая CLI-команда запускает новый процесс и может включать загрузку весов; здесь используется resident HTTP server, cold readiness отделена.
2. 4-bit MLX и GGUF Q6_K используют разные схемы квантования, упаковку, kernels и templates; эффект одного engine не изолирован.
3. RSS измеряет собственный server PID; MLX allocator active/cache/peak наблюдается отдельно. Суммировать пересекающиеся страницы нельзя.
4. /v1/models сообщает alias, но не удостоверяет bytes/revision/runtime. Нужны full prestart hashes, actual model path, native loaded images и pinned source.

## Комплект сдачи

Manifest v2, протокол, source registration, full model/native pins, raw inputs/SSE/finals/metrics, непрерывные ресурсы и cleanup сохранены. TSV хранит отдельные наблюдения с условиями. lab:check submission проверяет комплект; reviewer decision **не проверено**.
''')
