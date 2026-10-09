# LAB35 — квалификация Mac и готовность сравнения с Ryzen

Сессия apple-qualification-20261009. Статус **blocked**, после model startup HTTP qualification не началась.

## Паспорт выполнения

Apple M5 Max, 128 GiB, macOS26.5/arm64. Два отдельных llama.cpp b8407 deployments: исходный Metal из LAB30 и дополнительный Metal/tensor tile16 из LAB34. Один Qwen3.5-9B Q6_K GGUF, одинаковые public chat/load inputs, context8192/slot1. Build/model hashes и условия закреплены в [протоколе](raw/protocol.md). Артефакт MLX не используется. Агентных попыток нет, run_ids=[].

## Гипотеза и протокол до запуска

Оба Apple deployment завершат общий public chat и load fixture: warmup1 и три repeats, по одному HTTP request/repeat. Это односторонняя qualification, а не парная серия Mac/Ryzen. Основная будущая пара — unmodified Metal против HIP b8407; tensor patch — отдельное дополнительное условие. Исторические bench-архивы допускают только audit, не заменяют fresh HTTP pair.

## Ход выполнения

37 запланированных шагов: archive/bridge audit, 20 Apple шагов, 10 Ryzen шагов и шесть будущих agent attempts. Агентные шаги not-run по LAB08/LAB09; реальных records нет. Перед GPU —13samples за две минуты с AC и прежним memory guard. SSH/endpoint Ryzen пока неизвестен, вопрос владельцу задан.

## Результаты

Новых измерений пока нет; TSV содержит заголовок. Из archive подтверждаются общий weights SHA и upstream commit; patched tensor source отличается от Ryzen prebuilt. BF16 vLLM/SGLang из LAB06 не эквивалентен общему GGUF.

## Ошибки и ограничения

Без доступа к Ryzen нельзя чередовать стенды и завершить paired minimum. Без принятого bridge и local deployment fingerprints нельзя запускать или сравнивать Pi T002/a2-janitor. [Bridge readiness](raw/bridge-readiness.json) показывает только cloud providers в profile Pi0.73.1. [Access readiness](raw/access-readiness.json) фиксирует отсутствие connection target. Никаких fake runs или fallback в облако.

## Вывод по гипотезе

Данных недостаточно до новых квалификационных измерений. Полный LAB35 останется blocked без paired inference и настоящих agent verdicts.

## Ответы на контрольные вопросы

Будут дополнены после серии. Различия hardware/OS/compiler/patch должны оставаться в условиях; tokens/s не доказывает лучшее качество агента, RSS не равен максимальному GPU budget, цена API0 не означает бесплатное электричество.

## Комплект сдачи

Manifest/protocol/conditions/source references подготовлены до исполнения. Все failures/not-run сохраняются. Submission оформляется после квалификации; structural ready_for_review не заменяет критерии LAB35.

## Подготовительная остановка

Исходный Metal startup подтвердил M5/offload33/33/tensor=false. Перед chat warmup child Python завершился с exit2: неверный путь raw/metal-standard/concurrency_driver.py. HTTP-запрос не отправлен, primary request/summary отсутствуют. Это failed подготовка клиента, не записанная модельная latency. Native exit0, один SIGINT, guard=null; 3completed/1failed/33not-run. Runtime descriptor [1,2,4] — наследие LAB34; здесь concurrency не измерялась. Исправленные path и descriptor зарегистрированы отдельно в apple-qualification-retry-20261009.
