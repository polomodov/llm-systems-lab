# ЛР 05. Контекст 8/16/32K, streaming и инструменты

## Паспорт

| Поле | Значение |
| --- | --- |
| Время-ориентир | 2–4 часа для одного кандидата; это не прогноз скорости модели |
| Предпосылки | Выполнена ЛР 04; модель прошла базовый smoke; доступен target Linux и pinned llama.cpp |
| Статус готовности | Инструкция и fixtures готовы; аппаратная вместимость и протокол каждой конфигурации `unverified` |
| Результат | Матрица context × protocol и архив воспроизводимых HTTP-запросов |

## Цель

Проверить, что сервер действительно выдерживает выбранный контекст, возвращает корректные streaming-события и сохраняет tool round trip. Отдельно проверить, как reasoning учитывается в лимите output и отделяется от final answer.

## Проверяемая гипотеза

У одной закреплённой модели увеличение контекста с 8K до 16K и 32K не нарушает память и протокол. Нельзя подтверждать эту гипотезу только запуском сервера с большим `-c`: контекст должен быть заполнен. Валидный обычный чат не доказывает поддержку tools.

## Подготовка

- Возьмите прошедшие ЛР 04 GGUF, binary SHA, template, GPU offload, KV precision и FA. Начинайте с одного backend; для другого повторите работу в новом архиве.
- Используйте один server slot и одну модель. Ни сервер, ни HTTP-клиент не получают инструменты доступа к shell, файлам задач или скрытым проверкам.
- Общие входы: [chat-request.json](fixtures/chat-request.json) и [tool-request.json](fixtures/tool-request.json). Ожидаемые final values — `LAB_READY` и `LAB_VALUE_42`; reasoning оценивается отдельно. Лимит fixtures 2048 output tokens не гарантирует завершение любой thinking-модели: `finish_reason=length` фиксируется как ограничение конфигурации.
- Подготовьте Python 3, curl и зависимости предыдущей работы. Новые пакеты и веса автоматически не устанавливаются.

## Порядок выполнения

1. Создайте архив и задайте пути, заменив абсолютные placeholders:

   ```sh
   npm run lab:new -- --lab LAB05 --session my-session
   export LAB_DIR='experiments/local-models/measurements/LAB05-my-session'
   export LLAMA_BIN='/absolute/path/to/LAB04-my-session/build-hip/bin'
   export LOCAL_GGUF='/absolute/path/to/model.gguf'
   cp docs/labs/fixtures/chat-request.json "$LAB_DIR/raw/chat-request.json"
   cp docs/labs/fixtures/tool-request.json "$LAB_DIR/raw/tool-request.json"
   sha256sum "$LAB_DIR/raw/chat-request.json" "$LAB_DIR/raw/tool-request.json" \
     > "$LAB_DIR/raw/fixtures.sha256"
   "$LLAMA_BIN/llama-server" --help > "$LAB_DIR/raw/server-help.txt" 2>&1
   "$LLAMA_BIN/llama-bench" --help > "$LAB_DIR/raw/bench-help.txt" 2>&1
   sha256sum "$LLAMA_BIN/llama-server" "$LLAMA_BIN/llama-bench" \
     > "$LAB_DIR/raw/binaries.sha256"
   ```

   Сохраните SHA всех shards из ЛР 03/04. Проверьте наличие `--alias`, `--no-context-shift`, `-np`, `-fa`, `-d` в pinned help. Зафиксируйте параметры sampling/reasoning из карточки модели в `raw/model-settings.txt` и в manifest; применяйте их одинаково во всех трёх контекстах. Любой изменённый template получает свой SHA и отдельный вариант.

2. Проверьте заполнение памяти без HTTP на 8K. Затем, только после проверки бюджета, повторите для 16K и 32K, заменяя `CTX`:

   ```sh
   export CTX=8192
   DEPTH=$((CTX - 128))
   free -b > "$LAB_DIR/raw/context-$CTX-memory-before.txt"
   cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-before.txt"
   if /usr/bin/time -v -o "$LAB_DIR/raw/context-$CTX-process.txt" \
     "$LLAMA_BIN/llama-bench" -m "$LOCAL_GGUF" -ngl 999 -t 8 \
     -b 512 -ub 256 -ctk f16 -ctv f16 -fa on \
     -p 0 -n 128 -d "$DEPTH" -r 3 -o json \
     > "$LAB_DIR/raw/context-$CTX-bench.json" \
     2> "$LAB_DIR/raw/context-$CTX-bench.log"; then
     bench_status=0
   else
     bench_status=$?
   fi
   printf '%s\n' "$bench_status" > "$LAB_DIR/raw/context-$CTX-exit.txt"
   free -b > "$LAB_DIR/raw/context-$CTX-memory-after.txt"
   cat /proc/vmstat > "$LAB_DIR/raw/context-$CTX-vmstat-after.txt"
   test "$bench_status" -eq 0
   ```

   Глубины — 8064, 16256 и 32640 токенов перед 128 generated tokens. Во втором терминале с тем же `LAB_DIR` и `CTX` заранее запустите `vmstat -w 1 > "$LAB_DIR/raw/context-$CTX-vmstat-series.txt"`; после измерения остановите Ctrl-C. Сохраняйте GPU allocations из bench log, GNU time RSS и изменения swap. Встроенный прогрев не входит в три измеряемых повтора. Проверьте сохранённый exit code bench, прежде чем переходить дальше. При OOM, GPU reset, постоянной подкачке, fallback или выходе за бюджет остановите эту конфигурацию; более длинный контекст не запускайте автоматически. Изменение KV/FA ради вместимости — новый вариант, не исправление результата.

3. После успешной пробы запустите сервер этого контекста в отдельном терминале, из корня репозитория с теми же переменными. Добавьте заранее записанные model-specific sampling/reasoning flags. Сервер остаётся только на loopback:

   ```sh
   "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" \
     --host 127.0.0.1 --port 8080 --alias lab-model \
     -ngl 999 -c "$CTX" -np 1 -t 8 -b 512 -ub 256 \
     -ctk f16 -ctv f16 -fa on --jinja --no-context-shift \
     > "$LAB_DIR/raw/server-$CTX.log" 2>&1
   ```

   В рабочем терминале дождитесь успешного health response и сохраните свойства:

   ```sh
   curl --fail --max-time 10 http://127.0.0.1:8080/health \
     > "$LAB_DIR/raw/health-$CTX.json"
   curl --fail --max-time 10 http://127.0.0.1:8080/props \
     > "$LAB_DIR/raw/props-$CTX.json"
   curl --fail --max-time 10 http://127.0.0.1:8080/v1/models \
     > "$LAB_DIR/raw/models-$CTX.json"
   ```

   Подтвердите alias `lab-model`, GPU offload, effective context/slots и template. `--reasoning-format` описывает разбор результата, а не сам режим thinking. Нельзя объявлять thinking отключённым только потому, что reasoning не видно в `content`.

4. Создайте переносимый HTTP/SSE измеритель. Он читает подготовленные fixtures и допускает только одну фиктивную функцию; никакой код модели не исполняется. Этот файл можно использовать в последующих лабораторных с другим endpoint:

   ```sh
   cat > "$LAB_DIR/raw/http_probe.py" <<'PY'
   import argparse, json, pathlib, time, urllib.error, urllib.request

   parser = argparse.ArgumentParser()
   parser.add_argument('--url')
   parser.add_argument('--request')
   parser.add_argument('--out', required=True)
   parser.add_argument('--follow-tool', action='store_true')
   parser.add_argument('--validate-tool-message')
   args = parser.parse_args()
   def save(path, value):
       pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))

   def validate_tool(message):
       calls = message.get('tool_calls', [])
       if len(calls) != 1:
           raise ValueError('expected exactly one tool call')
       tool = calls[0]
       function = tool['function']
       arguments = json.loads(function['arguments'])
       if tool.get('type') != 'function':
           raise ValueError('only function tools allowed')
       if function['name'] != 'lookup_lab_value' or arguments != {'key': 'alpha'}:
           raise ValueError('tool/arguments rejected by allowlist')
       if not tool.get('id'):
           raise ValueError('missing tool call id')
       return tool

   if args.validate_tool_message:
       try:
           validate_tool(json.loads(pathlib.Path(args.validate_tool_message).read_text()))
           save(args.out + '.tool-validation.json', {'accepted': True})
       except Exception as error:
           save(args.out + '.tool-rejected.json', {'reason': str(error)})
           raise SystemExit(1)
       raise SystemExit(0)
   if not args.url or not args.request:
       parser.error('--url and --request are required for HTTP probes')

   def call(payload, prefix):
       save(prefix + '.request.json', payload)
       metrics = {'ttft_content_s': None, 'ttft_reasoning_s': None, 'usage': None}
       start = time.perf_counter()
       request = urllib.request.Request(args.url.rstrip('/') + '/v1/chat/completions',
           data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
       try:
           with urllib.request.urlopen(request, timeout=900) as response:
               metrics['http_status'] = response.status
               if not payload.get('stream'):
                   value = json.load(response)
                   save(prefix + '.response.json', value)
                   message = value['choices'][0]['message']
                   metrics['finish_reason'] = value['choices'][0].get('finish_reason')
                   metrics['usage'] = value.get('usage')
               else:
                   message = {'role': 'assistant', 'content': ''}
                   tools, reasoning, done = {}, '', False
                   with open(prefix + '.sse', 'wb') as raw:
                       for line in response:
                           raw.write(line)
                           raw.flush()
                           if not line.startswith(b'data:'):
                               continue
                           data = line[5:].strip()
                           if data == b'[DONE]':
                               done = True
                               break
                           if not data:
                               continue
                           event = json.loads(data)
                           if event.get('error'):
                               raise ValueError(str(event['error']))
                           if event.get('usage') is not None:
                               metrics['usage'] = event['usage']
                           for choice in event.get('choices', []):
                               delta = choice.get('delta', {})
                               content = delta.get('content') or ''
                               thought = delta.get('reasoning_content') or ''
                               if content and metrics['ttft_content_s'] is None:
                                   metrics['ttft_content_s'] = time.perf_counter() - start
                               if thought and metrics['ttft_reasoning_s'] is None:
                                   metrics['ttft_reasoning_s'] = time.perf_counter() - start
                               message['content'] += content
                               reasoning += thought
                               for piece in delta.get('tool_calls', []):
                                   item = tools.setdefault(piece['index'], {'id': '',
                                       'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                   if piece.get('id'):
                                       item['id'] = piece['id']
                                   function = piece.get('function', {})
                                   item['function']['name'] += function.get('name') or ''
                                   item['function']['arguments'] += function.get('arguments') or ''
                               if choice.get('finish_reason') is not None:
                                   metrics['finish_reason'] = choice['finish_reason']
                   if tools:
                       message['tool_calls'] = [tools[index] for index in sorted(tools)]
                   if reasoning:
                       message['reasoning_content'] = reasoning
                   metrics['stream_done'] = done
                   save(prefix + '.assembled.json', message)
                   if not done:
                       raise ValueError('SSE ended without [DONE]')
               metrics['duration_s'] = time.perf_counter() - start
               save(prefix + '.metrics.json', metrics)
               return message
       except Exception as error:
           if isinstance(error, urllib.error.HTTPError):
               metrics['http_status'] = error.code
               pathlib.Path(prefix + '.http-error.txt').write_bytes(error.read())
           metrics.update(error=str(error), duration_s=time.perf_counter() - start)
           save(prefix + '.metrics.json', metrics)
           raise

   payload = json.loads(pathlib.Path(args.request).read_text())
   message = call(payload, args.out)
   if args.follow_tool:
       try:
           tool = validate_tool(message)
       except Exception as error:
           save(args.out + '.tool-rejected.json', {'reason': str(error)})
           raise
       followup = dict(payload)
       followup['messages'] = payload['messages'] + [message, {
           'role': 'tool', 'tool_call_id': tool['id'], 'content': 'LAB_VALUE_42'}]
       message = call(followup, args.out + '.followup')
   save(args.out + '.final.json', {'content': message.get('content'),
       'tool_calls': message.get('tool_calls'), 'reasoning_content': message.get('reasoning_content')})
   PY
   ```

   Этот клиент измеряет TTFT только для streaming: задержка получения полного JSON не является TTFT. `ttft_content_s` отделено от первого reasoning-токена. Неподдерживаемый формат reasoning требует отдельного документированного parser, а не догадки по тегам. Ошибки и отклонённые tools остаются в архиве.

5. Подготовьте streaming-варианты и выполните четыре protocol cases по два раза:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   for kind in ('chat', 'tool'):
       value = json.loads((root / (kind + '-request.json')).read_text())
       value['stream'] = True
       (root / (kind + '-stream-request.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
   PY

   for repeat in 1 2; do
     for kind in chat chat-stream; do
       python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
         --request "$LAB_DIR/raw/$kind-request.json" \
         --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat"
     done
     for kind in tool tool-stream; do
       python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
         --request "$LAB_DIR/raw/$kind-request.json" \
         --out "$LAB_DIR/raw/ctx$CTX-$kind-r$repeat" --follow-tool
     done
   done
   ```

   Проверяйте final `LAB_READY` / `LAB_VALUE_42`, корректность `call_id`, валидный JSON arguments, завершающее событие и finish reason. Второй запрос того же процесса может использовать prefix cache: первый и повторный запрос обозначайте отдельно. Отсутствующий usage записывайте `null`; не вычисляйте токены из длины текста. Незавершённый tool round trip — не pass даже при HTTP 200.

6. Проверьте отказ локального диспетчера неизвестному инструменту на синтетическом ответе. Тот же `validate_tool` используется реальным round trip и тестом ниже; endpoint не вызывается:

   ```sh
   python3 - <<'PY'
   import copy, json, os, pathlib, subprocess, sys
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   valid = {'role': 'assistant', 'content': None, 'tool_calls': [{
       'id': 'offline-case-1', 'type': 'function',
       'function': {'name': 'lookup_lab_value', 'arguments': '{"key":"alpha"}'}}]}
   cases = {'valid': valid}
   for name, field, value in [('unknown-name', 'name', 'unexpected_tool'),
                             ('wrong-arguments', 'arguments', '{"key":"beta"}')]:
       message = copy.deepcopy(valid)
       message['tool_calls'][0]['function'][field] = value
       cases[name] = message
   message = copy.deepcopy(valid)
   del message['tool_calls'][0]['id']
   cases['missing-id'] = message
   results = {}
   for name, message in cases.items():
       prefix = root / ('offline-tool-' + name)
       source = pathlib.Path(str(prefix) + '-message.json')
       source.write_text(json.dumps(message, indent=2))
       result = subprocess.run([sys.executable, str(root / 'http_probe.py'),
           '--validate-tool-message', str(source), '--out', str(prefix)], check=False)
       expected = 0 if name == 'valid' else 1
       results[name] = {'exit_code': result.returncode, 'expected_exit_code': expected}
   (root / 'offline-tool-checks.json').write_text(json.dumps(results, indent=2))
   assert all(row['exit_code'] == row['expected_exit_code'] for row in results.values())
   PY
   ```

   В `offline-tool-*.tool-rejected.json` подтвердите конкретные причины `tool/arguments rejected by allowlist` и `missing tool call id`, а не произвольный Python error; для valid ожидается `accepted: true`. Это тест границы клиента; он не доказывает, что модель самостоятельно избегает неизвестных функций.

7. Подготовьте **длинный HTTP-вход** с учётом шаблона. Следующий генератор использует `/apply-template` и `/tokenize`, не выполняя inference. Он подбирает input не более `CTX − 4096`, оставляя output reserve. Если pinned server не поддерживает эти endpoints, фиксируйте blocker этой методики и считайте длину его tokenizer отдельно:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib, urllib.request
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   context = int(os.environ['CTX'])
   budget = context - 4096
   def post(route, value):
       request = urllib.request.Request('http://127.0.0.1:8080' + route,
           data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
       with urllib.request.urlopen(request, timeout=60) as response:
           return json.load(response)
   def candidate(rows):
       text = 'Контрольное значение: LAB_SENTINEL_42.\n'
       text += ''.join(f'Строка {i}: нейтральные данные измерения.\n' for i in range(rows))
       text += 'Верни только контрольное значение из первой строки.'
       messages = [{'role': 'user', 'content': text}]
       prompt = post('/apply-template', {'messages': messages})['prompt']
       tokens = post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens']
       return messages, prompt, len(tokens)
   low, high, best = 0, context, None
   while low <= high:
       middle = (low + high) // 2
       messages, prompt, count = candidate(middle)
       if count <= budget:
           best = (messages, prompt, count)
           low = middle + 1
       else:
           high = middle - 1
   if best is None:
       raise RuntimeError('template exceeds input budget')
   messages, prompt, count = best
   payload = {'model': 'lab-model', 'messages': messages, 'max_tokens': 4096, 'stream': True}
   prefix = root / ('ctx' + str(context) + '-long')
   pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
   pathlib.Path(str(prefix) + '-prompt.txt').write_text(prompt)
   pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({
       'context': context, 'input_tokens': count, 'output_reserve': 4096, 'input_budget': budget}, indent=2))
   PY

   for repeat in 1 2; do
     python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
       --request "$LAB_DIR/raw/ctx$CTX-long-request.json" \
       --out "$LAB_DIR/raw/ctx$CTX-long-r$repeat"
   done
   ```

   Сравните server `usage.prompt_tokens` с предварительным count. Различие означает другой effective template/tokenization и требует объяснения. Проверка считается проверкой данного длинного входа только при отсутствии truncation/context shift; ожидаемый final — `LAB_SENTINEL_42`. Синтетическая строка не оценивает исследовательское качество модели.

8. В том же контексте проверьте переполнение. Создайте вход длиннее `CTX` и сохраните tokenizer count:

   ```sh
   python3 - <<'PY'
   import json, os, pathlib, urllib.request
   root = pathlib.Path(os.environ['LAB_DIR']) / 'raw'
   context = int(os.environ['CTX'])
   source = root / ('ctx' + str(context) + '-long-request.json')
   payload = json.loads(source.read_text())
   text = payload['messages'][0]['content']
   for attempt in range(8):
       text = text + '\n' + text
       payload['messages'][0]['content'] = text
       def post(route, value):
           request = urllib.request.Request('http://127.0.0.1:8080' + route,
               data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
           with urllib.request.urlopen(request, timeout=60) as response:
               return json.load(response)
       prompt = post('/apply-template', {'messages': payload['messages']})['prompt']
       count = len(post('/tokenize', {'content': prompt,
           'add_special': False, 'parse_special': True})['tokens'])
       if count > context:
           break
   else:
       raise RuntimeError('could not construct overflow within bounded attempts')
   payload['max_tokens'] = 128
   prefix = root / ('ctx' + str(context) + '-overflow')
   pathlib.Path(str(prefix) + '-request.json').write_text(json.dumps(payload, ensure_ascii=False))
   pathlib.Path(str(prefix) + '-count.json').write_text(json.dumps({'input_tokens': count, 'context': context}))
   PY
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/ctx$CTX-overflow-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-overflow"
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/chat-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-overflow-recovery"
   ```

   Запускайте recovery отдельной командой, даже когда ожидаемый HTTP error завершил probe с ненулевым кодом. Ожидается явный отказ либо документированное ограничение; тихое обрезание несовместимо с baseline. Затем проверьте отмену и снова короткий запрос:

   ```sh
   if curl --no-buffer --max-time 1 -H 'Content-Type: application/json' \
     --data-binary @"$LAB_DIR/raw/ctx$CTX-long-request.json" \
     http://127.0.0.1:8080/v1/chat/completions \
     > "$LAB_DIR/raw/ctx$CTX-cancel.sse" 2> "$LAB_DIR/raw/ctx$CTX-cancel.log"; then
     printf '0\n' > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
   else
     printf '%s\n' "$?" > "$LAB_DIR/raw/ctx$CTX-cancel-exit.txt"
   fi
   python3 "$LAB_DIR/raw/http_probe.py" --url http://127.0.0.1:8080 \
     --request "$LAB_DIR/raw/chat-request.json" \
     --out "$LAB_DIR/raw/ctx$CTX-cancel-recovery"
   ```

   Timeout клиента не доказывает, что сервер отменил вычисление: проверьте server log, slot и время восстановления. Если запрос успел закончиться за секунду, это не проверка отмены; повторите с заранее сохранённым более длительным запросом.

9. Остановите сервер через Ctrl-C в его терминале, убедитесь, что процесс завершился и память освобождена. Повторите шаги 2–8 для `CTX=16384`, затем `CTX=32768`, только если предыдущие бюджеты соблюдены. Не поднимайте три сервера одновременно. В manifest сохраните одинаковые settings и отдельно context каждого запуска. Основной агентский baseline — 16K; 32K остаётся отдельным вариантом.

## Таблицы результатов

| Контекст | Depth + generation | Три bench повтора / raw | Пик памяти / источник | Swap / full GPU offload | Допуск |
| --- | --- | --- | --- | --- | --- |
| 8192 | 8064 + 128 | | | | |
| 16384 | 16256 + 128 | | | | |
| 32768 | 32640 + 128 | | | | |

| Context | Case | Повтор | HTTP / finish reason | Final / tool validity | TTFT content / reasoning, s | Total, s | Raw prefix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | chat | | | | | | |
| | chat-stream | | | | | | |
| | tool round trip | | | | | | |
| | tool-stream round trip | | | | | | |
| | long context | | | | | | |
| | overflow / cancel / recovery | | | | | | |

| Context | Input count до запуска | usage.prompt_tokens | Output / reasoning tokens | Truncation / shift | Вывод |
| --- | --- | --- | --- | --- | --- |
| 8192 | | | | | |
| 16384 | | | | | |
| 32768 | | | | | |

## Что сдать

- `report.md`, `measurements.tsv`, `manifest.json` со ссылкой на ЛР 04 и pinned settings.
- `raw/http_probe.py`, SHA общих fixtures и их локальные копии, `raw/model-settings.txt`, help и binary hashes.
- `raw/context-*-bench.*`, `raw/server-*.log`, `raw/props-*.json`, `raw/health-*.json`, `raw/models-*.json` и память/swap observations.
- Все HTTP request/response/SSE, assembled messages, metrics, followup, errors и rejected tools; длинные prompts и token counts.
- Описанные overflow/cancel/recovery cases и ответы на контрольные вопросы.

## Критерии завершения

- [ ] Для каждого контекста выполнена проба заполнения либо сохранён blocker.
- [ ] Есть два повтора chat, streaming, tools и streaming tools для допущенных контекстов.
- [ ] Tool round trip проверен через allowlist, без исполнения произвольного кода.
- [ ] Длинный HTTP-вход посчитан tokenizer и проверен на тихое обрезание.
- [ ] Reasoning и final, output cap и finish reason описаны раздельно.
- [ ] Проверены обработка ошибки/отмены и восстановление slot.
- [ ] Нет смешения короткого smoke с подтверждением 32K; неудачные случаи сохранены.

Работа с корректно зафиксированным пределом 16K считается выполненной. Это не означает, что модель прошла конфигурацию 32K или готова к любому агентному протоколу.

## Контрольные вопросы

1. Почему `-c 32768` и короткий успешный ответ не подтверждают вместимость 32K?
2. Чем TTFT первого reasoning-токена отличается от TTFT final content?
3. Почему HTTP 200 с `finish_reason=length` может означать незавершённый tool round trip?
4. Чем подтверждение отказа allowlist отличается от отказа модели вызвать неизвестный tool?
5. Почему prefix cache влияет на повторный prefill и как это отразить в отчёте?

## Источники

- [llama-server: API, context, slots, reasoning, tokenize и apply-template](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- [llama.cpp: function calling и tool-aware templates](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md).
- [llama-bench: заполнение контекста и повторы](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md).
- [Общий практикум](README.md), [описание fixtures](fixtures/README.md), [ЛР 04](LAB04-backends.md).
