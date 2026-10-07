# -*- coding: utf-8 -*-
"""Finalize the registered LAB31 observations, preserving the diagnostic failure."""
import csv
import hashlib
import json
import pathlib
import statistics

raw = pathlib.Path(__file__).resolve().parent
root = raw.parent
manifest = json.loads((root/'manifest.json').read_text())
assert all(a['status'] in {'completed','failed'} for a in manifest['planned_attempts'])
cases = ['warmup','r1','r2','r3']
records = {case:json.loads((raw/(case+'-execution.json')).read_text()) for case in cases}
assert all(record['accepted'] for record in records.values())
server = json.loads((raw/'server-execution.json').read_text())
assert server['accepted']
metrics = ['prompt_tokens_per_second','generation_tokens_per_second','runtime_peak_memory_bytes','max_rss_bytes','time_wall_seconds']
summary = {metric:dict(values=[records[case][metric] for case in ['r1','r2','r3']],
    median=statistics.median(records[case][metric] for case in ['r1','r2','r3']),
    minimum=min(records[case][metric] for case in ['r1','r2','r3']),
    maximum=max(records[case][metric] for case in ['r1','r2','r3'])) for metric in metrics}
summary.update(prompt_tokens=42,output_tokens=105,
    identical_texts=len({record['generated_text'] for record in records.values()})==1,
    swap_growth_bytes=0,server_status=server['chat_http_status'],server_usage=server['usage'],
    server_wall_seconds=server['chat_wall_seconds'],server_finish_reason=server['finish_reason'],
    server_max_rss_bytes=server['max_rss_bytes'],server_runtime_peak_bytes=server['runtime_peak_memory_bytes'],
    conditions='M5 Max/macOS26.5/arm64, mlx0.32.3/mlx-lm0.32.0, Qwen3.5-9B MLX4-bit text-only, prompt42/output105, temp0/seed1/thinking=false; CLI process repeats, not comparable to LAB30 synthetic workload')
(raw/'results-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (root/'measurements.tsv').open('w',newline='') as stream:
    writer = csv.writer(stream,delimiter='\t',lineterminator='\n')
    writer.writerow(['observation_id','configuration_id','model_id','engine','backend','context_tokens','repeat','metric','value','unit','status','evidence_path','unavailable_reason'])
    for case,record in records.items():
        items = [('prompt_tokens',record['prompt_tokens'],'tokens'),('output_tokens',record['output_tokens'],'tokens'),
            ('prefill_tokens_per_second',record['prompt_tokens_per_second'],'tokens/s'),
            ('decode_tokens_per_second',record['generation_tokens_per_second'],'tokens/s'),
            ('runtime_peak_memory',record['runtime_peak_memory_bytes'],'bytes'),
            ('process_max_rss',record['max_rss_bytes'],'bytes'),('process_wall',record['time_wall_seconds'],'seconds'),
            ('swap_delta',record['after']['swap_used_bytes']-json.loads((raw/(case+'-memory-before.json')).read_text())['swap_used_bytes'],'bytes')]
        for metric,value,unit in items:
            writer.writerow([case+'-'+metric,'mlx-qwen35-chat','qwen35-9b-mlx-4bit','mlx-lm-0.32.0','metal',42,case[1:] if case.startswith('r') else '',metric,value,unit,'measured','raw/'+case+'-execution.json',''])
    for metric,value,unit in [('chat_http_status',server['chat_http_status'],'http-status'),
        ('chat_wall',server['chat_wall_seconds'],'seconds'),('output_tokens',server['usage']['completion_tokens'],'tokens'),
        ('runtime_peak_memory',server['runtime_peak_memory_bytes'],'bytes'),('process_max_rss',server['max_rss_bytes'],'bytes')]:
        writer.writerow(['server-'+metric,'mlx-server-local','qwen35-9b-mlx-4bit','mlx-lm-0.32.0','metal',42,1,metric,value,unit,'measured','raw/server-execution.json',''])

decode = summary['generation_tokens_per_second'];prefill = summary['prompt_tokens_per_second']
peak_gib = summary['runtime_peak_memory_bytes']['maximum']/2**30
rss_gib = summary['max_rss_bytes']['maximum']/2**30
conclusion = f"Native MLX-LM0.32.0/MLX0.32.3 работает на M5 Max/macOS26.5 с языковой частью Qwen3.5-9B MLX4-bit @938d8919941c6e7efd3c7150eff7fe9d12afa631. GPU подтверждён; prompt42/output105, median PP {prefill['median']:.3f}, TG {decode['median']:.3f} tokens/s, allocator peak {peak_gib:.3f}GiB, CLI RSS≤{rss_gib:.3f}GiB, swap growth0. Local HTTP model identity/chat200 проверены. Различия с GGUF и нагрузкой LAB30 не позволяют выделить эффект engine."
manifest.update(status='completed',conclusion=conclusion,reviewer_decision=None)
manifest['unavailable'] = {
    'conditions.harness_profile':'Native inference, без agent harness.',
    'source_conversion_revision':'Издатель MLX artifact не закрепил source commit/version mlx-vlm конверсии; неизвестно с LAB29.',
    'gpu_budget_gib':'Одна малая конфигурация не устанавливает максимальный безопасный memory budget.',
    'wired_limit_before':'MLX0.32.3 не предоставляет read-only get_wired_limit; setter для чтения не использовался. Поведение runtime известно по закреплённому source, readback не измерен.',
    'temperature':'Thermal telemetry не измерялась.',
    'energy':'Энергия не измерялась.',
    'model_quality':'Текст сохранён, независимой оценки качества и агентного эпизода не было.',
    'vision':'MLX-LM использует языковую часть VLM, vision weights санитизируются; image inference не выполнялся.',
    'ttft':'HTTP smoke non-streaming, end-to-end wall не является TTFT.',
    'cold_start':'Новые CLI процессы и cache-warmed files; отдельная серия с холодными caches не выполнялась.'
}
rows = '\n'.join(f"| {case} | {r['prompt_tokens']} | {r['output_tokens']} | {r['prompt_tokens_per_second']:.3f} | {r['generation_tokens_per_second']:.3f} | {r['runtime_peak_memory_bytes']/2**30:.3f} | {r['max_rss_bytes']} | {r['time_wall_seconds']:.2f} / {r['returncode']} |" for case,r in records.items())
commit = json.loads((raw/'source-pins.json').read_text())['mlx_lm_tag_commit']
report = f'''# LAB31 — MLX-LM на M5 Max

Сессия: `apple-qwen35-9b-mlx-20261007`. Статус: **выполнено, ожидает проверки**. {conclusion}

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель / дата | Codex по запросу владельца, 07.10.2026 |
| Hardware / OS | Apple M5 Max CPU18/GPU40, RAM128GiB, macOS26.5/25F71, native arm64; свежий snapshot и LAB28 |
| Runtime | Python3.12.14, MLX0.32.3 +mlx-metal0.32.3, MLX-LM0.32.0; macOS26 arm64 wheels |
| Остальные зависимости | Transformers5.19.0, tokenizers0.23.2, huggingface-hub1.33.0, numpy2.5.3; [полный lock](raw/python-lock.txt), [wheel URL/hashes](raw/install-report.json) |
| Artifact | mlx-community/Qwen3.5-9B-MLX-4bit @938d8919941c6e7efd3c7150eff7fe9d12afa631, affine4-bit/group64; два safetensors5950221072 bytes/5.541575GiB включают vision tensors |
| Проверка артефакта | Все12 локальных файлов совпали с LAB29 SHA-256; [verification](raw/artifact-verification.json) |
| Template / sampling | enable_thinking=false, temp0, seed1, cap128, без persistent prompt cache/KV quantization; prompt42 tokens; effective EOS248046/im_end |
| Memory / power | AC/powermode0, telemetry2s, free-page floor16GiB, peak ceiling24GiB; без operator tuning системных лимитов |
| Harness / run IDs | Не применимы: аппаратный опыт, `run_ids=[]`; агент не запускался |
| Связанные отчёты | LAB28 паспорт, LAB29 artifact verification, две LAB30-сессии baseline/tensor |
| Отклонения | CLI observer перед/после стандартного dispatch; pinned runtime сам временно задаёт process-local рекомендованный wired limit — default behavior, а не ручной tuning |

## Гипотеза и протокол до запуска

[Исходный протокол](raw/protocol.md), [SHA](raw/protocol.sha256) и protocol_recorded_at в manifest сохранены до установки/инференса. [Уточнение observer до прогрева](raw/instrumentation-before-warmup.md) описывает точные GPU allocator метрики из того же процесса. Подлинность предварительного плана подтверждается авторскими timestamp/hash, не независимым внешним удостоверением. Один warmup и три CLI повтора, один server smoke. Не скрываются первая diagnostic ошибка и исправление её getter. Не задавались speed targets или порог качества; допуск ограничен исполнением/ресурсами.

## Ход выполнения

| Шаг | Действие | Результат / evidence |
| --- | --- | --- |
| Pins/install | Отдельный venv вне Git, mlx==0.32.3/mlx-metal==0.32.3/mlx-lm==0.32.0, only-binary | Exit0, pip check clean; [install](raw/install.txt), [lock](raw/python-lock.txt), [native wheels](raw/native-wheel-pins.json) |
| Native preflight | M5 device, default GPU, explicit GPU half matmul; hashes12 artifact files; local tokenizer | GPU OK; первая diagnostic попытка упала на отсутствующем get_wired_limit, сохранена как failed; retry отмечает unknown, не читает через setter. [Correction](raw/preflight-correction.json), [device](raw/mlx-device.json) |
| Input/stop | Chat template с thinking=false; runtime tokenizer config | 42 tokens, effective EOS248046/im_end; config discrepancy LAB29 resolved для этого runtime, веса/конфиги не менялись. [Rendered prompt](raw/rendered-prompt.txt), [runtime tokenizer](raw/tokenizer-runtime.json) |
| Warmup/повторы | [run_case.py](raw/run_case.py), четыре отдельных upstream generate CLI через [observer](raw/cli_entry.py) | Exit0, GPU/M5 до/после, одинаковый output105; exact argv и telemetry в каждом `*-execution.json` |
| Server | Тот же local artifact/venv, 127.0.0.1:8081, concurrency1, offline environment и отдельный пустой HF cache | `/v1/models`200 с абсолютным local model id; chat200, prompt42/completion64, finish_reason=length, cached_tokens0. [Models](raw/server-models.json), [request](raw/server-chat-request.json), [response](raw/server-chat-response.json) |
| Teardown | SIGINT только собственному process group, after-device и time stats сохранены | Command returncode−2 — преднамеренная остановка после smoke, не crash. Driver exit0; listener8081 отсутствует. [Server execution](raw/server-execution.json) |

## Результаты

Runtime throughput округлён upstream CLI до0.001 tokens/s. Allocator peak наблюдается как точное число bytes через mx.get_peak_memory; его GiB ниже — bytes/2³⁰. CLI `Peak memory` отдельно печатает decimal GB до0.001; единицы не смешиваются.

| Попытка | Prompt tokens | Output tokens | Prompt tokens/s | Generate tokens/s | Allocator peak GiB | Process RSS bytes | Wall s / exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

Медианы r1–r3: **PP {prefill['median']:.3f}** (min–max {prefill['minimum']:.3f}–{prefill['maximum']:.3f}), **TG {decode['median']:.3f}** ({decode['minimum']:.3f}–{decode['maximum']:.3f}) tokens/s. Process wall median {summary['time_wall_seconds']['median']:.2f}s. Allocator peak повторов {peak_gib:.3f}GiB, CLI max RSS {rss_gib:.3f}GiB, swap growth0. Прогрев не включён в медианы; его более медленный PP сохранён без приписывания причины. Новые процессы, ранее проверенные/cached files; холодные caches не создавались. Во всех четырёх CLI текст совпал; это не оценка качества.

HTTP: один non-streaming functional smoke, wall **{server['chat_wall_seconds']:.3f}s**, 42/64 tokens, length stop поcap64; max server RSS **{server['max_rss_bytes']/2**30:.3f}GiB**, allocator peak **{server['runtime_peak_memory_bytes']/2**30:.3f}GiB**. Один sample не является latency benchmark, wall не является TTFT и не переводится в decode TPS. [TSV](measurements.tsv) хранит каждое отдельное наблюдение, [summary](raw/results-summary.json) — медианы/min/max.

| Различие с LAB30 GGUF | MLX-LM | Следствие |
| --- | --- | --- |
| Artifact / quant | MLX affine4-bit/group64, pinned revision выше; GGUF Q6_K @3885219… | Разные quantization и веса; disk sizes не переносятся |
| Состав загрузки | Языковая часть VLM; sanitize исключает vision tower | Disk safetensors bytes не равны resident text model bytes |
| Конверсия | MLX-vlm по карточке; exact source conversion commit/version unknown | Одинаковый model name не доказывает одинаковую conversion source |
| Tokenizer / template | Общие основные token IDs в LAB29; template hashes отличаются; effective EOS здесь im_end | Input protocol отдельно закреплён; GGUFEOS248046, metadata MLXouterEOS248044 сами по себе не описывали effective stop |
| Workload | Chat42/output105, thinking=false/temp0/seed1 против LAB30 synthetic PP2048/TG128@4096 | Прямой speed ratio не выделяет engine и здесь не считается |
| Backend / memory | MLX default GPU, runtime allocator bytes, RSS; llama.cpp Metal tensor или SIMD, offload/buffer logs | Allocations разных runtime и RSS могут пересекаться; не складывать |
| Wired policy | Default MLX-LM временно ставит device recommendation в process-local limit | Это задокументированное default отличие; собственные limits оператор не задавал |

## Ошибки и ограничения

Первоначальный preflight ошибочно ожидал read-only mx.get_wired_limit, отсутствующий в0.32.3. [Failed source/log](raw/preflight-initial.py) и [traceback](raw/preflight-initial.txt) сохранены; отсутствие метрики исправлено на null с причиной. GPU/модель не объявлялись несовместимыми из-за этой диагностической ошибки. [Поведение wired limit](raw/wired-limit-source.txt) установлено по source; readback/restoration не измерены, setter для чтения не использовался. Это default runtime behavior, отклонение от строгой формулировки методички о wired tuning записано до исполнения.

Server telemetry сохранена до/во время readiness, после запроса и после остановки; во время блокирующего HTTP smoke (0.892s) отдельного sampler thread не было, peak RSS/allocator сняты средствами процесса. Native GPU подтверждён device/default stream и allocator observations в каждом процессе, без GPU instruction capture/per-operator tracing; не заявляем GPU offload каждого оператора по одному device name. Text-only sanitizer подтверждён pinned source; vision inference не выполнялся. `/v1/models` дополнен source/wheel/artifact hashes, exact local argv и chat-response model/fingerprint. Internet model fetch отключён, remote code не разрешён. Model source conversion pin остаётся неизвестным. Малый prompt42 не проверяет длинный prefill, context ceiling, tool use, streaming, качество или максимальный GPU budget. Температура/энергия не измерялись. SIGINT завершает server smoke, не имитирует проверку отмены отдельной generation в LAB32. Client cached_tokens0 — сообщение server, не отдельное измерение всей cache policy.

## Вывод по гипотезе

**Поддержана данными для этой конфигурации:** MLX-LM0.32.0/MLX0.32.3 и языковая часть закреплённого MLX4-bit артефакта работают на M5 Max/macOS26.5; warmup+три повтора и local HTTP smoke приняты без swap growth. LAB32 может отдельно проверять этот deployment. Итоги не доказывают преимущество MLX перед llama.cpp: quantization, загрузка, template и нагрузки различаются.

Версии выбраны по [PyPI mlx0.32.3](https://pypi.org/project/mlx/0.32.3/) и [mlx-lm0.32.0](https://pypi.org/project/mlx-lm/0.32.0/); [qwen3_5 pinned source](https://github.com/ml-explore/mlx-lm/blob/{commit}/mlx_lm/models/qwen3_5.py) поддерживает языковую загрузку и sanitize VLM. Installed qwen3_5/generate/utils/server bytes совпадают с v0.32.0 tag: [verification](raw/wheel-source-verification.json). Upstream LICENSE приложена. Hardware compatibility установлена своим опытом, не карточкой модели.

## Ответы на контрольные вопросы

1. Новый CLI процесс заново загружает Python/runtime/model и создаёт cache/state; это не resident HTTP server. File/shader caches могут сохраниться между процессами. Wall включает startup, runtime throughput — свои стадии генерации.
2. 4-bit MLX affine/group64 и GGUF Q4_K_M/Q6_K — разные schemes, scales, смешанные tensor dtypes и конверсии. Равенство номинальной bitness не контролирует quantization как один фактор.
3. macOS time RSS относится к интерпретатору и его mappings; mx allocator peak — к MLX allocations, здесь наблюдается в том же процессе. Они перекрываются и не складываются. Disk safetensors включает исключённые vision tensors.
4. `/v1/models` сообщает identifier/доступность, а не доказывает bytes weights или backend. Нужны exact local path, verified hashes, command/runtime pins, device observations и фактический запрос.

## Комплект сдачи

- [x] Manifest v2, protocol/hash и полный список попыток, включая failed preflight.
- [x] Native pins/install provenance/lock, device, artifact verification и tokenizer/runtime manifests.
- [x] Warmup+три raw CLI повтора, generated texts, точные allocator bytes, RSS/time, power/memory telemetry.
- [x] Local server identity/chat smoke, ожидаемый SIGINT teardown и отсутствие listener.
- [x] TSV/summary, ограничения сравнения и ответы на контрольные вопросы.

Решение проверяющего: **не проверено**. `lab:check` проверяет комплектность; содержательный вывод остаётся за проверяющим.
'''
(root/'report.md').write_text(report,encoding='utf-8')
(root/'.gitattributes').write_text('raw/** whitespace=-blank-at-eol,-blank-at-eof,cr-at-eol\nmeasurements.tsv whitespace=-blank-at-eol\n')
hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name!='evidence-hashes.json'}
(raw/'evidence-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
manifest['evidence_files'] = sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
(root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
