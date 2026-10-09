# LAB08: контракт первого изолированного local provider

Выбран Pi SDK 0.73.1, Qwen3.5-9B Q6_K и llama.cpp b8407 / Metal / tile16 на M5 Max. Вход через LAB32: unrestricted-auto 8K прошёл chat/tool JSON/SSE, cancel/overflow/recovery. Полные library pins берутся из нового LAB35 tensor-повтора; максимальный GPU budget неизвестен. Native inference находится вне 2 GiB agent container.

## Граница и API

Agent container находится только во внутренней Docker network и обращается к `http://egress:8080/v1/chat/completions`. Broker также имеет только эту сеть. Его отдельный control listener публикуется Docker на loopback host с временным портом; host-worker сам подключается к нему с одноразовой capability. Capability не передаётся агенту и не хранится в input snapshot. Агент не может выбирать upstream и не знает порт сервера Mac. Нет host networking, Docker socket или GPU devices в agent container. Cloud CONNECT и GET sources отключены для первого local профиля T002.

Broker разрешает GET /health и POST /v1/chat/completions; Host строго egress:8080, без absolute-form URL, query, target header или redirect. Control API на другом порту требует capability. Один запрос одновременно; body ≤1 MiB, response ≤4 MiB, deadline 300 s. Host-worker пересылает только фиксированный chat path на loopback IPv4 endpoint. При ошибке нет retry на cloud или иной alias. SSE сохраняется целиком с проверкой JSON/DONE/finish/model; в первом варианте буферизуется до завершения, поэтому TTFT не измеряется. Client disconnect отменяет собственный upstream request; общий чужой inference process не убивается.

## Identity и данные

Prepare запечатывает deployment manifest v1 и SHA-256. Он содержит repository/revision, exact files/bytes/hashes и quant, engine/build/backend и executable/library pins, tokenizer/template hashes, аппаратный паспорт/OS/power, context/output, sampling/reasoning, KV/batch/offload/slots. Run использует собственный supervisor для нового native процесса: проверка всех файлов до Popen, loopback bind, immutable command, PID и props/template/context. Проверка identity выполняется до старта агента и перед/после каждого запроса; смена identity останавливает попытку. Никаких серверных tool/shell handlers.

Run metadata имеет отдельный версионированный local fingerprint и observed proof; старые cloud записи не меняются. Compare разделяет fingerprint, сохраняя cloud/local различие. Usage берётся из первичных HTTP-ответов; отсутствие usage даёт null с причиной, даже если SDK заполнил его нулями. Inference fee, энергия и амортизация не объявляются нулевыми. SDK dummy marker — публичная строка, не API-ключ; marker не идёт на upstream. Настоящие provider secrets в первом local профиле не поддерживаются.

## Приёмка до модели

B01: штатный Pi streaming tool-call → native tool-result → final на mock. B02: другой port/LAN/IPv6 без upstream вызовов. B03: Host/target/redirect/admin denied. B04: cloud fallback denied. B05: body/response limits, invalid JSON, 4xx/5xx, truncated SSE. B06: timeout/disconnect/cleanup, общий server остаётся жив. B07: тот же alias с изменёнными weights/template/context/backend отвергается или разделяется compare. B08: usage отсутствует → null. B09: sealed tamper и synthetic secret protection. B10: прежние cloud/T001 replay tests остаются зелёными. Затем реальные Docker boundary tests с mock, без модели и настоящих ключей.

## Pilot

Только после приёмки инженерных проверок: новый native server по sealed deployment, свежий resource/power admission, один T002 / a2-janitor / Pi pilot, budget-mode observed, turn/USD contract читается из sealed task. Автоматических compaction/retry, cloud fallback и рестартов нет. Agent timeout ограничен; memory/power guard и owned cleanup обязательны. Все started failures сохраняются в настоящем run.json. Независимая оценка использует штатный lifecycle, hidden checks не читаются/не изменяются. Если проверка или pilot не допущены, LAB08 остаётся blocked с конкретной причиной.

Компоненты регистрируются в ledger как предложенные; вклад в успех агента этим опытом не установлен. Минимальный scope — Pi / GGUF / Metal / macOS. Остальные адаптеры, MLX и Ryzen ждут отдельной приёмки. Изменения исходных опытов и настроек macOS не допускаются.
