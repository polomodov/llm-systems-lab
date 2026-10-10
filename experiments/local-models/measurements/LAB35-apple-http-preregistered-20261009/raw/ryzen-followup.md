# Следующая парная регистрация LAB35

Команды ниже не выполнялись. Нужен SSH alias/доверенный endpoint Ryzen и fresh manifests; HTTP-архивы BF16 из LAB06 и microbench LAB04 не заменяют эти данные.

1. Проверить свободный endpoint/отсутствие чужой GPU-нагрузки, current OS/kernel/driver, memory/swap и фактический binary/model SHA. Архивный HIP server SHA: `be8c03c5c5b8d096a0498b30eedaaaccdc784ba80e72290dfa1f0dd3d63ee54b`; GGUF SHA: `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59`. Другой binary означает новое условие, а не скрытую замену.
2. Создать отдельный LAB35 report/register до новых парных запросов. Перенести `chat-request.json`, `load-request.json` и общий bounded driver из этой сессии с SHA-256. Исходный Metal выбран заранее как основная пара; tensor patch — отдельный дополнительный deployment.
3. Запустить owned HIP server с теми же параметрами (пути задаются по проверенному локальному артефакту, не по alias):

```sh
"$LAB35_SERVER" -m "$LAB35_GGUF" --host 127.0.0.1 --port 18080 \
  --alias lab-model -ngl 999 -c 8192 -np 1 -t 8 -b 512 -ub 256 \
  -ctk f16 -ctv f16 -fa on --jinja --no-context-shift \
  --reasoning auto --chat-template-kwargs '{"enable_thinking":true}' \
  --no-cache-prompt --slots --metrics
```

4. Readiness/props/slots/log должны подтвердить реальное GPU execution, context/KV/FA/cache/template и отсутствие незавершённой очереди. Запрошенный `-ngl 999` не заменяет actual offload proof. Метаданные, compile flags и power/background/network placement обеих машин сохранить отдельно.
5. Один warmup на input и три измеряемых повтора на каждый input/стенд. Чередование до запуска: r1 Apple→Ryzen, r2 Ryzen→Apple, r3 Apple→Ryzen. Все запросы concurrency1/output2048; источник клиента и туннель/RTT включить в условия. При localhost-клиентах на двух машинах сравниваются deployments с разными клиентами; не описывать как изолированный backend эффект.
6. Actual driver вызов (один request/repeat, пути outputs уникальны):

```sh
python3 -B concurrency_driver.py \
  --endpoint http://127.0.0.1:18080/v1/chat/completions \
  --request chat-request.json --concurrency 1 --requests 1 \
  --timeout 300 --out ryzen-chat-r1
```

Повторить заранее перечисленные chat/load warmup/r1/r2/r3, синхронизируя порядок с Apple controller. TTFT остаётся неизвестным при non-streaming. Macrobenchmark `pp2048/tg128` и HTTP latency не объединять в одну метрику.

7. Перенести весь raw archive, source session/PIDs/dates и hashes; проверить responses/usage/contracts и все failures. Предыдущая односторонняя qualification Apple не становится чередованной парной серией задним числом.
8. Agent T002/a2-janitor/Pi: сначала реализовать и принять LAB08 и local lifecycle LAB09, deployment fingerprint grouping и network policy. До этого не создавать фиктивные run.json, не запускать cloud fallback и не расширять существующий cloud egress до LAN.
