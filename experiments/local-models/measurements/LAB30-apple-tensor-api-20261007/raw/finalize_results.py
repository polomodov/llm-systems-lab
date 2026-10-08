# -*- coding: utf-8 -*-
"""Summarize the registered tensor diagnostic session without dropping failed probes."""
import csv
import hashlib
import json
import pathlib
import statistics

raw = pathlib.Path(__file__).resolve().parent
root = raw.parent
manifest = json.loads((root / 'manifest.json').read_text())
for attempt in manifest['planned_attempts']:
    if attempt['status'] != 'completed':
        raise SystemExit('Series incomplete: ' + attempt['id'])

summary = {}
for mode, prefix in [('tensor', ''), ('control', 'control-')]:
    summary[mode] = {}
    for workload in ['pp', 'tg']:
        records = [json.loads((raw / (prefix + workload + '-r' + str(n) + '-execution.json')).read_text()) for n in [1, 2, 3]]
        assert all(record['accepted'] for record in records)
        values = [record['benchmark_rows'][0]['avg_ts'] for record in records]
        summary[mode][workload] = dict(values=values, median=statistics.median(values), minimum=min(values), maximum=max(values))
summary['ratio_tensor_over_control'] = {workload: summary['tensor'][workload]['median'] / summary['control'][workload]['median'] for workload in ['pp', 'tg']}
records = [json.loads(p.read_text()) for p in raw.glob('*-execution.json')]
bench_records = [r for r in records if 'benchmark_rows' in r]
assert len(bench_records) == 17
summary['max_rss_gib'] = max(r['max_rss_bytes'] for r in bench_records) / 2**30
summary['swap_growth_bytes'] = max(r['after']['swap_used_bytes'] - json.loads((raw / (r['case'] + '-memory-before.json')).read_text())['swap_used_bytes'] for r in bench_records)
summary['scope'] = 'M5 Max, macOS26.5, b8407+tile16 patch, Qwen3.5-9B Q6_K, PP2048/TG128@4096; three repeats, AC/powermode0; no thermal/energy measurement'
(raw / 'results-summary.json').write_text(json.dumps(summary, indent=2) + '\n')

with (root / 'measurements.tsv').open('w', newline='') as f:
    writer = csv.writer(f, delimiter='\t', lineterminator='\n')
    writer.writerow(['observation_id','configuration_id','model_id','engine','backend','context_tokens','repeat','metric','value','unit','status','evidence_path','unavailable_reason'])
    for record in bench_records:
        case = record['case']
        attempt = next(a for a in manifest['planned_attempts'] if a['id'] == case)
        for i, row in enumerate(record['benchmark_rows']):
            metric = 'prefill_tokens_per_second' if row['n_prompt'] else 'decode_tokens_per_second'
            repeat = case.rsplit('-r', 1)[-1] if '-r' in case else ''
            writer.writerow([case+'-speed-'+str(i), attempt['configuration_id'], 'qwen35-9b-q6-k', 'llama.cpp-b8407-tile16', 'metal', row['n_prompt'] or row['n_depth'] or '', repeat, metric, row['avg_ts'], 'tokens/s', 'measured', 'raw/'+case+'-bench.json', ''])
        for metric, value, unit in [('process_max_rss',record['max_rss_bytes'],'bytes'), ('process_wall',record['time_wall_seconds'],'seconds')]:
            writer.writerow([case+'-'+metric, attempt['configuration_id'], 'qwen35-9b-q6-k', 'llama.cpp-b8407-tile16', 'metal', '', '', metric, value, unit, 'measured', 'raw/'+case+'-execution.json', ''])
    for attempt_id, file in [('probe','probe-execution.json'),('probe-tile16','probe-tile16-execution.json')]:
        attempt = next(a for a in manifest['planned_attempts'] if a['id'] == attempt_id)
        probes = json.loads((raw / file).read_text())['attempts']
        for i, probe in enumerate(probes):
            writer.writerow([attempt_id+'-exit-'+str(i), attempt['configuration_id'], '', 'Metal compiler', 'metal', '', '', 'exit_code', probe['exit_code'], 'exit-code', 'measured', 'raw/'+file, ''])

pp = summary['tensor']['pp']; tg = summary['tensor']['tg']
cp = summary['control']['pp']; ct = summary['control']['tg']
conclusion = f"Tensor API активирован в b8407 на M5 Max/macOS26.5 исправлением probe8×8→16×16, без full Xcode/forced flags. 14/14 выборочных MUL_MAT CPU-reference tests прошли, offload33/33. PP2048 median {pp['median']:.2f} против {cp['median']:.2f} tokens/s; TG128@4096 {tg['median']:.2f} против {ct['median']:.2f}. Это microbench, не агентное качество."
manifest.update(status='completed', conclusion=conclusion, reviewer_decision=None)
manifest['unavailable'] = {
    'conditions.harness_profile': 'Native backend microbench без агентского harness.',
    'gpu_budget_gib': 'Безопасный максимальный budget не измерялся; рекомендованный working set не является свободной памятью.',
    'temperature': 'Thermal telemetry не собиралась; разброс скорости не доказывает throttling.',
    'energy': 'Энергия не измерялась.',
    'model_quality': 'Benchmark генерирует техническую нагрузку; агентный прогон и оценка качества не выполнялись.',
    'upstream_build': 'Текущий upstream не собирался; локально проверен b8407 с сохранённым patch.'
}
manifest['evidence_files'] = sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

rows = '\n'.join(f"| {n} | {pp['values'][n-1]:.2f} | {cp['values'][n-1]:.2f} | {tg['values'][n-1]:.2f} | {ct['values'][n-1]:.2f} |" for n in [1,2,3])
report = f'''# LAB30 — активация Metal tensor API

Сессия: `apple-tensor-api-20261007`. Статус: **выполнено, ожидает проверки**. {conclusion}

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Исполнитель, дата | Codex по запросу владельца, 07.10.2026 |
| Hardware/OS | M5 Max, CPU18/GPU40, RAM128GiB, macOS26.5/25F71, arm64; LAB28 |
| Артефакт | Qwen3.5-9B Q6_K @3885219b6810b007914f3a7950a8d1b469d598a5, 7458301152 bytes, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59 |
| Runtime | llama.cpp b8407 @312cf03328496df9c56fe843952cf02a8964c59a +[patch](raw/tensor-tile16.patch); Release/arm64, Apple Clang21/SDK26.5, CMake4.4.4 |
| Условия | threads8, batch512/ubatch256, FA1, KVf16/f16, ngl999; PP2048 и TG128@depth4096; новые процессы CLI с внутренним warmup |
| Питание/память | AC/powermode0, telemetry2s, OS floor16GiB, RSS ceiling24GiB, остановка при swap growth/timeout600s |
| Harness/run IDs | Не применимы: аппаратный microbench, агентская задача не запускалась |
| Предыдущая серия | [LAB30 baseline](../LAB30-apple-qwen35-9b-metal-20261007/report.md); её source/build/evidence неизменны |
| Отличие от LAB30 | Повторная сессия для compiler probes и выбора tensor kernels; контроль API-disabled в той же binary |

## Гипотеза и протокол до запуска

[Исходный протокол](raw/protocol.md), [SHA](raw/protocol.sha256), timestamp в manifest. Начальная гипотеза о недостаточной default languageVersion **не поддержана**: default уже Metal4.0 (262144). [Поправка до tile probes](raw/probe-tile-amendment.md) проверила descriptor16×16. [Дополнительный протокол](raw/control-amendment.md) зарегистрировал CPU-reference tests и API-disabled контроль до их запуска. [Порядок серии](raw/series-order.json): прогревы, затем чередующиеся пары tensor/control для трёх повторов. Это авторская регистрация по timestamp/hash, без независимого внешнего удостоверения.

## Ход выполнения

| Шаг | Команда/изменение | Результат | Evidence |
| --- | --- | --- | --- |
| Ошибка исходного probe | Exact b8407 f16/bfloat, default/3.2/4.0 через native Objective-C MTLDevice | Default/4.0: static_assert «At least one of M or N must be a multiple of 16»; 3.2 не предоставляет mpp/dextents | [Все попытки](raw/probe-execution.json), [полная ошибка](raw/probe-f16-default.txt) |
| Контроль tile | Только descriptor8×8→16×16, те же шесть условий | Default/4.0: library и pipeline OK для f16/bfloat; explicit3.2 ожидаемо падает | [Попытки](raw/probe-tile16-execution.json) |
| Native сборка | Новая копия того же SHA, две замены tile и verbose=true; production `.metal` не менялся | Configure/build exit0, Mach-O arm64, без полного Xcode | [Patch](raw/tensor-tile16.patch), [runtime](raw/runtime-manifest.json), [hashes](raw/binaries.sha256) |
| Smoke | `run_bench_case.py smoke`: PP512/TG64 | f16/bfloat OK, has_tensor=true, offload33/33; выбран kernel_mul_mm_q6_K_f32 из GGML_METAL_HAS_TENSOR ветки | [Backend log](raw/smoke-process.txt), [execution](raw/smoke-execution.json) |
| Численная проверка | `test-backend-ops test -b MTL0 -o MUL_MAT -p 'type_a=(q6_K\|f16\|bf16),type_b=f32,m=16,n=16,k=256,'` | 12/12 f16/f32 CPU-reference comparisons, exit0; случаи bs/nr/per включены | [Вывод](raw/operator-check.txt), [argv](raw/operator-execution.json) |
| Дополнительный численный допуск | Отдельный зарегистрированный m1/n64/k256 для q6_K/f32 и bf16/f32 | 2/2 CPU-reference comparisons; исходный regex12 tests покрывал только f16 | [Протокол](raw/operator-coverage-amendment.md), [вывод](raw/operator-quant-check.txt), [argv](raw/operator-quant-execution.json) |
| Измеряемая серия | Один прогрев PP/TG каждого режима +по три повтора, tensor disable только у control | Все17 bench процессов приняты, swap growth0; raw18 PP/TG наблюдений включая smoke | [Summary](raw/results-summary.json), [TSV](measurements.tsv) |

## Результаты

Все значения в tokens/s. Smoke и прогревы сохранены отдельно и не включены в медианы.

| Повтор | Tensor PP2048 | Control PP2048 | Tensor TG128@4096 | Control TG128@4096 |
| --- | --- | --- | --- | --- |
{rows}
| Медиана | {pp['median']:.2f} | {cp['median']:.2f} | {tg['median']:.2f} | {ct['median']:.2f} |
| Min–max | {pp['minimum']:.2f}–{pp['maximum']:.2f} | {cp['minimum']:.2f}–{cp['maximum']:.2f} | {tg['minimum']:.2f}–{tg['maximum']:.2f} | {ct['minimum']:.2f}–{ct['maximum']:.2f} |

Отношение медиан tensor/control: **PP {summary['ratio_tensor_over_control']['pp']:.3f}×**, **TG {summary['ratio_tensor_over_control']['tg']:.3f}×**. Max RSS всех17 процессов: **{summary['max_rss_gib']:.3f}GiB**; swap delta0. PP/TG — отдельные kernels из llama-bench JSON, process wall/RSS в TSV. Память и AC/power mode архивируются до/во время/после каждой попытки. CLI холодный старт не выдаётся за TTFT; allocation buffers могут пересекаться с RSS.

## Ошибки и ограничения

Первая гипотеза опровергнута; исходные failed compiler probes сохранены. Default Metal уже4.0 на этом runtime; standalone `xcrun --find metal` отсутствует, но runtime `newLibraryWithSource` работает через macOS Metal. Отсутствие offline compiler не причина нашего отказа. Explicit3.2 не предоставляет tensor API; на другом runtime может потребоваться явный Metal4.0.

Dummy kernel только компилируется и создаёт pipeline; он не dispatchится. Patch совпадает с функциональными заменами upstream fixes, а verbose нужен для прозрачных ошибок. Реальные model matmul используют штатные блоки32×64 и tensor-ветку, а не dummy8×8. Pipeline selection +successful dispatch/exit подтверждают выбор ветки; GPU instruction disassembly/capture не выполнялись. 14 tests — выборочный численный допуск (12 f16 и отдельно по одному q6_K/bf16), не все формы/операторы. Рандомизированные upstream inputs не закреплены seed. В последних повторах скорость снизилась в обоих режимах; причина не измерена, устойчивое изменение decode не установлено. Три microbench повтора не определяют статистическую значимость; background/температура/энергия не контролировались полностью, разброс сохранён. HTTP/tool use, агентное качество, длительная нагрузка и максимальный GPU budget не измерены. `GGML_METAL_TENSOR_ENABLE=1` не обходит compiler probe и не исправляет8×8; M5 уже входит в список автоматического включения.

## Вывод по гипотезе

Исправленная гипотеза **поддержана**: false-negative capability probe b8407 отключал доступный tensor API из-за недопустимого8×8 descriptor. Две замены на16×16 активируют API на этой машине. [Официальный фикс #21048](https://github.com/ggml-org/llama.cpp/pull/21048), commit `9bcb4eff4d7e7755276645c767948c25c00481b8`, делает ровно эти замены; [архив patch/metadata](raw/upstream-fix-commit.json). [Исходники b8407](https://github.com/ggml-org/llama.cpp/blob/312cf03328496df9c56fe843952cf02a8964c59a/ggml/src/ggml-metal/ggml-metal-device.m) задают automatic enable для M5, но затем выполняют faulty probe. [Apple languageVersion](https://developer.apple.com/documentation/metal/mtlcompileoptions/languageversion) описывает default latest language; локальные probes измерили4.0. Upstream inspected на закреплённом SHA в [sources](raw/sources.json), полная новая версия не собиралась.

Для воспроизведения из чистой отдельной копии b8407 (не baseline directory):

```sh
export LLAMA_SRC='/absolute/path/to/separate-b8407-checkout'
export LLAMA_BUILD='/absolute/path/to/new-tensor-build'
export LAB_DIR='experiments/local-models/measurements/LAB30-apple-tensor-api-20261007'
test "$(git -C "$LLAMA_SRC" rev-parse HEAD)" = '312cf03328496df9c56fe843952cf02a8964c59a'
test -z "$(git -C "$LLAMA_SRC" status --porcelain)"
git -C "$LLAMA_SRC" apply --check "$PWD/$LAB_DIR/raw/tensor-tile16.patch"
git -C "$LLAMA_SRC" apply "$PWD/$LAB_DIR/raw/tensor-tile16.patch"
cmake -S "$LLAMA_SRC" -B "$LLAMA_BUILD" -DCMAKE_BUILD_TYPE=Release \\
  -DCMAKE_OSX_ARCHITECTURES=arm64 -DGGML_METAL=ON -DLLAMA_CURL=OFF
cmake --build "$LLAMA_BUILD" --config Release -j8 --target llama-bench llama-server
# LOCAL_GGUF задаётся путём к закреплённому артефакту; weights не скачиваются.
env -u GGML_METAL_TENSOR_DISABLE -u GGML_METAL_TENSOR_ENABLE \\
  "$LLAMA_BUILD/bin/llama-bench" -m "$LOCAL_GGUF" -ngl999 -t8 \\
  -b512 -ub256 -ctk f16 -ctv f16 -fa1 -p512 -n64 -r1 -v -o json
```

Выполняйте команды по одной, переходя дальше только при exit0. Подтверждение: обе probe OK, has_tensor=true, full offload и загруженный mul_mm kernel. `GGML_METAL_TENSOR_DISABLE=1` — проверенный возврат к SIMD без смены binary. Runtime этого опыта: `/Users/lab/local-model-lab-artifacts/engines/llama.cpp/312cf03328496df9c56fe843952cf02a8964c59a/build-metal-tensor-tile16-arm64/bin/`.

## Ответы на контрольные вопросы

1. Metal build доказывает сборку backend; probes/offload/pipeline/runtime log подтверждают исполнение. Именно probe error отключал tensor при работоспособном SIMD Metal.
2. PP измеряет обработку prompt, TG генерацию при заданной depth; process wall включает загрузку, warmup, компиляцию, teardown. Они различаются.
3. Один commit и артефакт уменьшают различия runtime, но наш tile patch — отдельное условие. Эта сессия сравнивает одну patched binary с включённым/выключенным API, не Ryzen.
4. Unified memory позволяет пересекаться mapped weights, GPU allocations и RSS; их сумма не является RAM peak. RSS из macOS time — bytes.

## Комплект сдачи

- [x] Manifest v2, исходный protocol/hash и поправки, все попытки/сырые ошибки.
- [x] Toolchain/source patch, hashes binary/library и артефакта.
- [x] f16/bfloat probes, numeric tests, smoke, warmup и три повтора двух режимов.
- [x] Memory/power telemetry, TSV и summary; run_ids пусты по причине аппаратного benchmark.
- [x] Сформулированы вывод, ограничения, активация и ответы.

Решение проверяющего: **не проверено**. `lab:check` подтверждает комплектность, не научный вывод.
'''
report = report.replace('-ngl999 -t8', '-ngl 999 -t 8').replace('-b512 -ub256', '-b 512 -ub 256').replace('-fa1 -p512 -n64 -r1', '-fa 1 -p 512 -n 64 -r 1')
(root / 'report.md').write_text(report, encoding='utf-8')
hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file() and p.name != 'evidence-hashes.json'}
(raw / 'evidence-hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
manifest['evidence_files'] = sorted('raw/'+p.name for p in raw.iterdir() if p.is_file())
(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
