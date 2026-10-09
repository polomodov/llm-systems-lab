"""Render the fresh tensor repeat; historical results are never rewritten."""
import json,pathlib
raw=pathlib.Path(__file__).resolve().parent
s=json.loads((raw/'summary.json').read_text());m=json.loads((raw.parent/'manifest.json').read_text())
v=s['variants']['metal-tensor'];p=json.loads((raw/'metal-tensor/startup-process.json').read_text());audit=json.loads((raw/'pin-audit-execution.json').read_text());registration=json.loads((raw/'preregistration.json').read_text())
checks=json.loads((raw/'software-validation.json').read_text()) if (raw/'software-validation.json').exists() else None
lines=['# LAB35 — новый tensor-повтор с полными хешами dylib','',
 f"Сессия `{m['session_id']}`; статус **{s['status']} для отдельного tensor-повтора**. Полный LAB35 по-прежнему ждёт Ryzen-пару и агентную часть.",'',
 '## Паспорт выполнения','',
 'Apple M5 Max / 18 CPU / 40 GPU / 128 GiB / macOS 26.5 (25F71) / arm64; питание AC / mode 0. Qwen3.5-9B Q6_K, revision `3885219b6810b007914f3a7950a8d1b469d598a5`, 7 458 301 152 bytes; SHA-256 `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`.','',
 'Llama.cpp base commit `312cf03328496df9c56fe843952cf02a8964c59a` / b8407 и tile16 patch `561c77562a5caad4772bfc0fcf078f9b1c354296e310300c7b460e635f368863`. [Версии и все хеши сборки](raw/metal-tensor/build-reference.json), [аппаратный снимок](raw/apple-hardware.json). Context 8192, один server slot, threads 8, batch 512 / ubatch 256, KV f16/f16, FA on, Jinja / no-context-shift, reasoning auto / enable_thinking=true, no-cache-prompt. Output cap 2048, temperature 0 / seed 1 / top_p 1; non-streaming, без tools. [Фактическая команда](raw/metal-tensor/runtime-manifest.json). Agent harness не запускался; `run_ids=[]`.','',
 '## Гипотеза и протокол до запуска','',
 'Свежий tensor-процесс завершит общие chat/load запросы с прогревом и тремя повторами после полной проверки библиотек сборки. Отсутствующий или изменённый dylib запрещает запуск. Все пути файлов версий и linker aliases закреплены отдельно; 21 dylib path относится к семи семействам, а не к 21 различной библиотеке.','',
 f"[Протокол](raw/protocol.md), [source registry](raw/registered-source-hashes.json), controller и offline exporter закреплены до старта в commit `{registration['source_commit']}`. [Регистрация](raw/preregistration.json) и [13 безопасных снимков за ≥120 секунд](raw/preflight-power.jsonl) предшествуют запуску модели. Входы побайтно совпадают с прежней LAB35; [источник и их SHA-256](raw/prior-reference.json).",'',
 '## Ход выполнения','',
 'Pin audit → новый startup → chat warmup/r1/r2/r3 → load warmup/r1/r2/r3 → штатный shutdown. Каждый шаг содержит один HTTP-запрос при concurrency 1; startup и прогревы исключены из медиан. OS page cache не сбрасывался. Memory/power guard и проверки других загруженных моделей действовали во время серии.','',
 f"Pin audit: `{audit['timestamp']}`. Повторная проверка 23 хешей: `{p['binaries_verified_at']}`. Вызов Popen: `{p['popen_invoked_at']}`. [Startup record](raw/metal-tensor/startup-process.json) содержит оба executables и все 21 dylib path; [audit](raw/pin-audit-execution.json) совпадает с reference.",'',
 f"Попытки: {s['attempts']}. Новые HTTP-запросы: {s['http_requests']}, transport/probe errors: {s['http_errors']}. Semantic contracts проверены отдельно по первичным ответам. [Manifest](manifest.json), [summary](raw/summary.json).",'',
 '## Результаты','',
 '| Вход | Три измеряемых повтора | Median HTTP latency, s | Median completion tokens/s | Completion tokens r1/r2/r3 |','| --- | --- | --- | --- | --- |']
for fixture,result in v['fixtures'].items():
    latency=f"{result['median_latency_seconds']:.3f}" if result['median_latency_seconds'] is not None else '—'
    rate=f"{result['median_completion_tokens_per_second']:.3f}" if result['median_completion_tokens_per_second'] is not None else '—'
    lines.append(f"| {fixture} | {'completed' if result['complete_three_repeats'] else 'incomplete'} | {latency} | {rate} | {result['completion_tokens']} |")
memory=v.get('memory');shutdown=v.get('shutdown')
lines+=['','Latency — полное время HTTP-ответа. Tokens/s — completion usage / полный wall одного запроса, включая prefill и HTTP; это не decode-only скорость. Все восемь bodies, responses, usage, summaries и contracts сохранены; 56 строк TSV включают прогревы, а таблица медиан — только r1–r3.','',
 '| Native RSS peak, GiB | Min free+speculative, GiB | Max swap, bytes | Pressure levels | Native exit / SIGINT |','| --- | --- | --- | --- | --- |']
if memory and shutdown:lines.append(f"| {memory['max_rss_bytes']/2**30:.3f} | {memory['min_free_speculative_bytes']/2**30:.3f} | {memory['max_swap_bytes']} | {memory['pressure_levels']} | {shutdown['returncode']} / {len(shutdown['interrupts'])} |")
lines+=['',f"`libraries_verified_at_execution={str(v['libraries_verified_at_execution']).lower()}`, `pins_checked_before_popen={str(v['pins_checked_before_popen']).lower()}`; missing library pins: {len(v['missing_library_pins_at_execution'])}. [Native log](raw/metal-tensor/server.txt) подтверждает Apple M5 Max / offload 33/33 / tensor capability=true. Finish reasons, включая прогревы: {s['finish_reasons']}.",'',
 '## Ошибки и ограничения','',
 'Прежний [tensor-процесс LAB35](../LAB35-apple-http-preregistered-20261009/report.md) проверял только executables: его `libraries_verified_at_execution=false` сохранён. Нынешнее совпадение хешей не устанавливает идентичность библиотек уже завершившегося процесса. Этот повтор — отдельные запуск и доказательства; архивные результаты не включены в его counts.','',
 'Load требует непустого assistant content и полного usage; finish length допустим, качество 300 слов не проверено. Tensor capability в startup log не доказывает применение tensor kernel каждым оператором. Сравнения скоростей с standard Metal здесь нет; нет чередованной Ryzen-пары, LAB08/LAB09 и агентных verdicts. TTFT, энергия, температура, maximum GPU budget и Ryzen/agent ratios остаются null с причинами. RSS не равен Metal allocation. Новая короткая серия не повторяет 30 минут LAB34 и не подтверждает его исторические библиотеки.','',
 '## Вывод по гипотезе','',
 ('**Гипотеза отдельного повтора поддержана:** свежий tensor deployment выполнил chat/load с прогревом и тремя повторами при полном pre-start library fingerprint, соблюдении guards и штатном cleanup. Полный LAB35 не завершён.' if v['qualification_completed'] and s['status']=='completed' else '**Повтор не допущен:** отсутствует часть результатов или доказательств. Failed/not-run сохраняются; полный LAB35 не завершён.'),'',
 '## Ответы на контрольные вопросы','',
 '1. **Почему SHA executable недостаточен?** Он не фиксирует исполняемый код динамических библиотек. До нового запуска проверены все bundled dylib paths и executable hashes; ОС закрепляет условия системных frameworks.',
 '2. **Можно ли подтвердить старый процесс новым хешированием?** Нет: нынешний файл не доказывает состояние файла при старом запуске. Нужен самостоятельный опыт с проверкой до запуска.',
 '3. **Что подтверждает tensor log?** Обнаружение capability этой сборкой на M5 Max и GPU offload. Применение kernel каждым оператором из него не следует.',
 '4. **Почему успешные HTTP-запросы не закрывают LAB35?** Для сравнения нужны свежие сопоставимые Ryzen-повторы и реальные агентные runs с принятым bridge. Здесь их нет.',
 '5. **Что ещё нужно для оценки стоимости?** Измеренная энергия и тариф, амортизация, затраты оператора и результат агентной задачи. Model API price=0 не заменяет эти величины.','',
 '## Комплект сдачи','',
 (f"Offline Python tests: {checks['python_tests_passed']}; npm test: {checks['npm_tests_passed']} passed / {checks['npm_tests_skipped']} skipped (Docker gate). npm run check, lab:check submission и git diff --check прошли. [Проверки](raw/software-validation.json)." if checks else 'Программные проверки ещё выполняются; итоговый статус проверок будет сохранён в raw/software-validation.json.'),'',
 'Manifest v2, протокол и source pins, preregistration commit, pin audit, runtime/native logs, requests/responses/usage/contracts, memory timeline, cleanup, TSV и SHA inventories сохранены. [Primary inventory](raw/primary-evidence-sha256.json) защищает первичные данные при offline replay. Submission проверяет комплектность, не назначает экспериментальный verdict. Reviewer decision: **не проверено**.','']
(raw.parent/'report.md').write_text('\n'.join(lines))
