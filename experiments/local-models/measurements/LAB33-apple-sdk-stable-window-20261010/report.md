# LAB33 — LM Studio: явная отмена и фактический backend

Сессия `apple-sdk-stable-window-20261010`, статус **blocked**. AssertionError: SDK chat failed

## Паспорт выполнения

Apple M5 Max / 128 GiB / macOS 26.5 (25F71), AC/mode 0. Существующий центральный LM Studio 0.4.25+1 и selected runtimes llama.cpp/Metal 2.54.0, MLX/Metal 1.13.1. [Runtime](raw/runtime-manifest.json), [deployments](raw/deployments.json). GGUF Q6_K и MLX 4-bit — разные артефакты. SDK 1.5.0 установлен в отдельном venv; его wheels/dependencies закреплены hashes. Веса не скачивались, центральный app не переустанавливался.

Loader context 8192/parallel 1/gpu max — запрошенные настройки, не доказательство hard cap или всех 33 layers. SDK temperature 0/top_p 1/output cap 2048; seed, reasoning, KV и cache — defaults приложения с явными ограничениями. Точный source и pins для этой сессии находятся в её raw; отсутствие pinfile в неудачной preparation-сессии означает отсутствие модельной фазы, а не успешную проверку.

## Гипотеза и протокол до запуска

[Протокол](raw/protocol.md) и source-registration закреплены commit до модели. Принимаются только собственные alias, один сервер 127.0.0.1:1234 и один loaded model. Admission — 120 с стабильно free+spec ≥16 GiB, pressure level 1, swap 0, AC/mode 0. Resource guard сохраняет минимум 8 GiB, RSS mapped backend ≤24 GiB, samples каждые 2 с/gap ≤15 с, bounded wall/request. Пороги не ослаблялись.

SDK chat/cancel/recovery и HTTP disconnect/recovery — отдельные условия, с прогревом и тремя повторами. SDK cancel после start и 1 с; iterator продолжается до primary stats, критерий userStopped и recovery. Final извлекается только по declared fragment reasoning_type, без trim/Markdown normalization. HTTP timeout и recovery не заменяют attributable request-id native stop. Физическое освобождение GPU страниц оценивается отдельно и остаётся unknown без collector.

## Ход выполнения

SDK schema/wheel verification → model/registry/backend pins → stable admission → controlled load → SDK/HTTP observations → собственный unload/server stop. Root PID и foreign models наблюдаются; чужие процессы не завершаются. [Контроллер](raw/run_lms.py), [клиент](raw/sdk_probe.py), [сводка](raw/runtime-summary.json).

Первый prototype сохранил SDK KeyError identifier после реального ответа LAB_READY. Result.model_info — LlmInfo с path/modelKey, instance identifier находится в loaded handle. Следующая preparation отказала при выборе GGUF вместо MLX и не создала pins; модели не запускались. Исправленный full-pin вариант сначала отказал на baseline resource admission. Эти сессии не переписаны; retry создаётся отдельно после стабильного resource window. Новая модельная фаза использует exact format/repository/revision selector и все 12 MLX registry bindings.

## Результаты

Attempts: {"completed": 14, "failed": 1, "not-run": 19, "planned": 0}. В таблице — primary SDK status, raw final и фактическое время. Sample влияет на latency, поэтому sampled GGUF requests не сравниваются с unsampled baseline как одинаковые условия.

| Deployment/case/repeat | Статус | Primary stop / proof | Final / limit | Total / recovery, с |
| --- | --- | --- | --- | --- |
| lms-gguf/chat/1 | completed | eosFound | 'LAB_READY' | 3.270073890686035 |
| lms-gguf/chat/2 | completed | eosFound | 'LAB_READY' | 3.2762398719787598 |
| lms-gguf/chat/3 | completed | eosFound | 'LAB_READY' | 3.306475877761841 |
| lms-gguf/chat/warmup | completed | eosFound | 'LAB_READY' | 3.295073986053467 |
| lms-gguf/backend-1 | Metal call path: True | stream complete: True | all layers: null | — |
| lms-gguf/backend-2 | Metal call path: True | stream complete: True | all layers: null | — |
| lms-gguf/backend-3 | Metal call path: True | stream complete: True | all layers: null | — |
| lms-gguf/backend-warmup | Metal call path: True | stream complete: True | all layers: null | — |
| lms-mlx/chat/warmup | failed | eosFound | '\n\nLAB_READY' | 2.794051170349121 |

## Ошибки и ограничения

AssertionError: SDK chat failed SDK userStopped — измеренный API status, не самостоятельный счётчик физических GPU страниц. OS stack sample доказывает наблюдаемый Metal call path во время контролируемого ответа; он не считает все offloaded layers. Runtime name/gpu ratio не заменяют фактическое доказательство. В частности, `stopGenerating() without a request_id … Taking no action` — отрицательное свидетельство, не pass отмены.

## Вывод по гипотезе

API cancellation/backend observations recorded; full LAB33 admission still requires attributable native HTTP cancellation and physical GPU/all-layer evidence. Source/API/model identity и cancellation conclusions ограничены конкретной выполненной сессией. Offline review audit принимает только counted compute/dispatch frames из Call graph, исключая Binary Images, сводки и wait-only frames. Исходные proof.json/samples/execution и pins не переписаны; active-metal-proof.json и lifecycle-audit.json — отдельные производные результаты. Исполнявшийся source сохранён в run_lms.executed.py с original SHA-256 в controller-review-audit.json. Исправленный run_lms.py требует новой сессии и свежих pins, включая lms_evidence.py. Нормальная успешная выгрузка теперь сбрасывает loaded; историческое loaded=true при models_after=[] оставлено в первичном record и объяснено audit. Старый evidence inventory относится к исходным bytes; соответствие изменённого controller path исходному snapshot задаёт controller-review-audit.json. Прежние preparation failures и resource refusal не объявляются аппаратной несовместимостью. Полный LAB33 допуск сохраняет перечисленные blockers; unknown показатели не заменяются нулями.

## Ответы на контрольные вопросы

1. Общий API не удостоверяет backend: нужны version/package pins, loaded identity и фактические события/call path.
2. GPU ratio — конфигурация, не счётчик исполненных layers. Model path и registry hashes проверяются отдельно.
3. HTTP disconnect, SDK cancel, recovery, unload и освобождение физических GPU страниц — разные наблюдения.
4. Разные GGUF/MLX quantization/template/defaults исключают вывод об эффекте одного frontend по общей latency.

## Комплект сдачи

Manifest/TSV/protocol/source registrations, SDK wheel hashes/schema, model/backend/registry pins, raw SDK/HTTP/runtime events/OS samples, resources и cleanup сохранены. Агентных episodes нет, run_ids пуст. Submission проверяет комплектность; reviewer decision **не проверено**, experiment pass автоматически не назначается.
