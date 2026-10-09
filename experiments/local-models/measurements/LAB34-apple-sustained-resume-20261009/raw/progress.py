"""Read only compact campaign progress; never controls the server."""
import json, pathlib, datetime
raw=pathlib.Path(__file__).resolve().parent
directories=[raw/'warmup']+sorted(p for p in raw.glob('r*-c*') if p.is_dir())
directories+=sorted((raw/'sustained').glob('block-*')) if (raw/'sustained').exists() else []
completed=[];current=None;total=0;failures=0
for directory in directories:
    records=[]
    for path in directory.glob('request-*.json'):
        try:records.append(json.loads(path.read_text()))
        except json.JSONDecodeError:continue
    total+=len(records);failures+=sum(not r['ok'] for r in records)
    if (directory/'summary.json').exists():completed.append(str(directory.relative_to(raw)))
    else:current={'block':str(directory.relative_to(raw)),'finished':len(records),'failed':sum(not r['ok'] for r in records)}
memory=None
if (raw/'memory-timeline.jsonl').exists():
    for line in reversed((raw/'memory-timeline.jsonl').read_text().splitlines()):
        try:
            row=json.loads(line)
            memory={'timestamp':row['timestamp'],'free_speculative_gib':round(row['free_speculative_bytes']/2**30,3),
                'rss_gib':round((row['server_rss_bytes'] or 0)/2**30,3),'swap_bytes':row['swap_used_bytes'],
                'pressure_level':row['pressure_level'],'pressure_free_percent':row['pressure_free_percentage']}
            break
        except json.JSONDecodeError:continue
selection=json.loads((raw/'sustained-selection.json').read_text()) if (raw/'sustained-selection.json').exists() else None
sustained={'concurrency':selection['concurrency'],'elapsed_minutes':round((datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(selection['timestamp'])).total_seconds()/60,2)} if selection else None
print(json.dumps({'sustained':sustained,'completed_blocks':completed,'current':current,'finished_requests':total,'failures':failures,'memory':memory}))
