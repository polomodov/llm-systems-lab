# LAB08 — новая нативная квалификация и отдельный pilot

Зарегистрировано до исполнения. Предыдущие два aborted runs не меняются.

Условие из deployment.json: Qwen3.5-9B Q6_K / tensor tile16 / Metal / 8192 / output2048 / reasoning auto / thinking true / один slot, Pi0.73.1.

1. Запустить исправленный startNative из текущего commit, проверив все 25 artifact/engine/passport pins до Popen. Guard: 2s resource samples, gap >15s или clock backwards — отказ; AC/mode0/swap0/pressure1/RSS≤24GiB. Caffeinate только process-bound.
2. Четыре одинаковых SSE chat: прогрев и три повтора; exact LAB_READY, stop, complete usage и DONE. До/после каждого — verify. 20s idle, затем verify и штатный cleanup. Global wall180s; failure сохраняется, pilot не запускается. Не имитировать suspend/clock jump на машине пользователя: negative guards уже покрыты synthetic/Docker tests.
3. Только после успешной короткой серии — новый run.json T002/Pi, prepare с тем же deployment, sealed code. Timeout900s, observed budget, собственный native child/container. Не менять task/hidden check, не запускать параллельно модельные нагрузки.
4. awaiting_review не означает pass. Независимый hidden-check задаёт оператор; без него расширение агентной серии блокируется. Последующие независимые аппаратные работы разрешены.

Неизвестны energy/temperature/maxGPU/TTFT; SSE буферизуется. Минимум измерений warmup+3; cold startup отдельно. Любой gap внутри полной host suspension остаётся неизвестным; wall/stale guards исполняются только при активном host execution.
