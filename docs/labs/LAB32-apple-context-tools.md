# ЛР32. Контекст, streaming и инструменты на Mac

## Паспорт

| Поле | Значение |
| --- | --- |
| Тип / готовность | Протокольные и ресурсные измерения / `target-machine` |
| Время | 3–5 часов |
| Предпосылки | Успешная LAB30 **или** LAB31; для сравнения движков — обе |
| Минимум | Один движок, 8K/16K/32K, четыре chat/tool × JSON/SSE случая; прогрев и три повтора каждого, длинный вход, отмена и переполнение |

## Цель

Установить фактические границы рабочего контекста и пригодность протокола локального сервера для агентного цикла.

## Проверяемая гипотеза

На допущенном контексте сервер завершает текстовый и инструментальный round trip, корректно собирает SSE и восстанавливается после отказа/отмены без смены deployment.

## Подготовка

```sh
npm run lab:new -- --lab LAB32 --session apple-protocol
export LAB_DIR='experiments/local-models/measurements/LAB32-apple-protocol'
export LOCAL_URL='http://127.0.0.1:8080'
export MODEL_ALIAS='lab-model'
export CTX=8192
```

Для MLX используйте порт 8081 и model identifier из LAB31. Работает только один сервер. Зафиксируйте protocol/attempts и [общие условия](../../experiments/local-models/apple/README.md). Программу `http_probe.py` переиспользуем из шага 4 LAB05: прохождение Linux-работы не требуется. Следующий код извлекает именно тот опубликованный блок, снимает Markdown indentation и проверяет синтаксис, не запускает его:

```sh
python3 - "$LAB_DIR" <<'PY'
import pathlib, sys, textwrap
source = pathlib.Path('docs/labs/LAB05-context-tools.md').read_text()
marker = '   cat > "$LAB_DIR/raw/http_probe.py" <<\'PY\'\n'
assert source.count(marker) == 1
script = textwrap.dedent(source.split(marker, 1)[1].split('\n   PY\n', 1)[0]) + '\n'
compile(script, 'http_probe.py', 'exec')
with (pathlib.Path(sys.argv[1]) / 'raw/http_probe.py').open('x') as out:
    out.write(script)
PY
```

Это учебный HTTP-клиент для доверенного loopback, не изолирующий provider bridge. Он не предназначен для произвольных URL или production access. Исключите HTTP proxy для loopback (`export no_proxy='127.0.0.1,localhost,::1'`). Входы публичные, сервер не должен перенаправлять клиента.

## Порядок выполнения

1. Для llama.cpp запустите в отдельном терминале pinned server из LAB30 (переменные `LLAMA_BIN`, `LOCAL_GGUF`, `LAB_DIR`, `CTX` задать и там):

   ```sh
   "$LLAMA_BIN/llama-server" -m "$LOCAL_GGUF" --host 127.0.0.1 --port 8080 \
     --alias lab-model -ngl 999 -c "$CTX" -np 1 --jinja --no-context-shift \
     > "$LAB_DIR/raw/server-$CTX.txt" 2>&1
   ```

   Проверьте flags по pinned help. Сохраните `/health`, `/props`, `/v1/models` и GPU allocations. Для MLX используйте команду LAB31; сохраните model/device identity и доступные runtime limits. `CTX` в клиенте само по себе **не** задаёт MLX server cap: если выбранная версия не умеет фиксировать hard context limit, исследуйте input-budget 8K/16K/32K и укажите hard-limit проверку как `unavailable`. Не выдавайте это за одинаковый KV reservation с llama.cpp.

2. Подготовьте четыре запроса на каждый контекст, сохраняя исходные параметры и alias. Перед первой серией добавьте одинаковые model-specific sampling/reasoning настройки в копии, зафиксируйте hashes:

   ```sh
   python3 - "$LAB_DIR" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   raw = pathlib.Path(sys.argv[1]) / 'raw'
   for kind in ('chat', 'tool'):
       data = json.loads(pathlib.Path(f'docs/labs/fixtures/{kind}-request.json').read_text())
       data['model'] = sys.argv[2]
       for stream in (False, True):
           data['stream'] = stream
           suffix = '-stream' if stream else ''
           with (raw / f'{kind}{suffix}-request.json').open('x') as out:
               json.dump(data, out, ensure_ascii=False, indent=2)
   PY
   shasum -a 256 "$LAB_DIR"/raw/*-request.json > "$LAB_DIR/raw/requests.sha256"
   ```

3. Для каждого case выполните отдельный прогрев (`REPEAT=warmup`) и три повтора (`1`, `2`, `3`), осматривая результат между запусками. Пример текстового и инструментального вызова; затем заменить kind на `chat-stream`/`tool-stream`:

   ```sh
   export REPEAT=warmup
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LOCAL_URL" \
     --request "$LAB_DIR/raw/chat-request.json" --out "$LAB_DIR/raw/ctx$CTX-chat-r$REPEAT"
   python3 "$LAB_DIR/raw/http_probe.py" --url "$LOCAL_URL" \
     --request "$LAB_DIR/raw/tool-request.json" --out "$LAB_DIR/raw/ctx$CTX-tool-r$REPEAT" --follow-tool
   ```

   Требуйте `LAB_READY` и `LAB_VALUE_42` в final; одну `lookup_lab_value`, arguments ровно `{"key":"alpha"}`, непустой call ID и связанный tool result. Код модели не исполняется: клиент возвращает фиксированную строку. HTTP 200 сам по себе не pass. Повторите offline allowlist cases из шага 6 LAB05: неизвестное имя, неправильный key, отсутствующий ID должны быть отвергнуты именно validator, а не случайной ошибкой Python. Их synthetic evidence пометьте отдельно от модельных измерений.

4. Исследуйте реальный длинный вход. В llama.cpp примените генератор `/apply-template` + `/tokenize` из шага 7 LAB05 с текущим `CTX`; это HTTP-код, переносимый на macOS. Для MLX считайте вход pinned tokenizer из **своего** артефакта. Пример подготовки без загрузки весов (Python из LAB31):

   ```sh
   "$MLX_ENV/bin/python" - "$LOCAL_MLX" "$LAB_DIR" "$CTX" "$MODEL_ALIAS" <<'PY'
   import json, pathlib, sys
   from transformers import AutoTokenizer
   tokenizer = AutoTokenizer.from_pretrained(sys.argv[1], local_files_only=True, trust_remote_code=False)
   ctx = int(sys.argv[3])
   def make(n):
       return [{'role':'user', 'content':'Контрольное значение LAB_SENTINEL_42.\n' +
           ''.join(f'Строка {i}: нейтральные данные.\n' for i in range(n)) +
           'Верни контрольное значение из первой строки.'}]
   def count(messages):
       return len(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
   lo, hi = 0, ctx
   while lo < hi:
       mid = (lo + hi + 1) // 2
       if count(make(mid)) <= ctx - 4096: lo = mid
       else: hi = mid - 1
   messages = make(lo)
   payload = {'model':sys.argv[4], 'messages':messages, 'max_tokens':2048, 'stream':True}
   raw = pathlib.Path(sys.argv[2]) / 'raw'
   for name, data in [(f'ctx{ctx}-long-request.json',payload),
                      (f'ctx{ctx}-long-count.json',{'input_tokens':count(messages),'input_budget':ctx-4096})]:
       with (raw / name).open('x') as out: json.dump(data,out,ensure_ascii=False,indent=2)
   PY
   ```

   Подтвердите, что server использует тот же template и reasoning options; иначе счёт не доказан. Выполните long request тем же probe: warmup и три повтора, ожидая `LAB_SENTINEL_42`. Проверяйте actual input usage, truncation и память. Нельзя измерять «32K» коротким prompt в большом пустом context.

5. Отмена: подготовьте отдельный streaming long request с достаточным output cap, сохраните `curl --no-buffer --max-time 1` ответ/exit code. Затем проверьте серверную очередь и recovery chat до возвращения к baseline. Timeout клиента не доказывает отмену GPU generation. Сохраните длительность освобождения слота и изменение памяти; если запрос успел завершиться раньше timeout, опыт отмены не состоялся, отметьте это.

6. Переполнение: для runtime с подтверждённым hard cap создайте вход, который **после template/tokenization** превышает cap с output reserve. Сохраните точный count, request и ответ/ошибку, затем обычный recovery chat. Тихое усечение или context shift зафиксируйте как поведение, а не успешный контроль лимита. Если cap недоступен, оформите blocker этого опыта; не доводите машину до OOM для его имитации.

7. Только после проверки 8K перейдите к 16K, затем 32K с новым runtime condition и перезапуском собственного сервера. Для второго движка создайте отдельную сессию. Не объединяйте warm/prefix-cached и cold запросы; покажите TTFT content отдельно от reasoning, отсутствующий usage не заменяйте оценкой по символам.

## Таблицы результатов

| Engine / context | Case / повтор | Input/output tokens | TTFT content / reasoning s | Total s | Final / tool / SSE correct | Память / swap | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

| Воздействие | Подтверждённый cap/count | Ответ | Recovery / slot release | Допуск / blocker |
| --- | --- | --- | --- | --- |
| Отмена | | | | |
| Переполнение | | | | |

## Что сдать

Отчёт/TSV/manifest, четыре request fixtures и hashes, probe, runtime identity, все JSON/SSE outputs, token counts, memory timeline, отмена/переполнение/recovery evidence и offline validation. Пропущенные context/cases остаются в planned attempts.

## Критерии завершения

- [ ] Контексты подтверждены фактической длиной входа и runtime conditions.
- [ ] Четыре protocol cases имеют warmup и три повтора на каждом допущенном контексте.
- [ ] Tool allowlist, IDs, final content и SSE completion проверены.
- [ ] Отмена/overflow не выданы за pass без recovery evidence.
- [ ] Выдан отдельный допуск/blocker для LAB08 и нагрузочных работ.
- [ ] Комплект проверен по общему протоколу.

## Контрольные вопросы

1. Почему TTFT нельзя получить из времени non-streaming ответа?
2. Почему client CTX не задаёт server context limit?
3. Чем timeout соединения отличается от отмены generation?
4. Почему prefix cache и reasoning меняют интерпретацию задержки?

## Источники

- [LAB05: переносимый HTTP/SSE probe и allowlist](LAB05-context-tools.md).
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server).
- [MLX-LM server](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py).
- [Transformers chat templates](https://huggingface.co/docs/transformers/chat_templating).
