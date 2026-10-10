# LAB32 — fresh model identity repeat

Новая полная серия 8K→16K→32K input budgets, не продолжение старой unverified модели. Ранее GGUF ошибочно выбран artifacts[0]; все старые MLX measurements сохраняются с audit/model_identity_verified_at_execution=false. Новые хеши не подтверждают их задним числом.

Перед запуском selector требует exact format MLX/safetensors, repository mlx-community/Qwen3.5-9B-MLX-4bit, revision938d8919941c6e7efd3c7150eff7fe9d12afa631, один match. Все12model files проверяются bytes/SHA против artifact reference; pin coverage и model directory должны совпадать с native --model. Native binaries/MLX sources/Python/observer/selector тоже фиксируются hashes; actual loaded images сверяются при before/after.

Те же SDK/runtime versions: MLX-LM0.32.0/MLX0.32.3/Transformers5.19.0, thinkingfalse/temp0/seed1/topP1/output2048, cache0, concurrency1, prefill2048, full-precisionKV, offline/no downloads/no operator memory tuning. CPUtokenizer return_dict=False и flat IDs; long≤budget-4096, cancel<budget-2048; long final ровноLAB_SENTINEL_42, явныйзапретMarkdown. Не нормализуем outputs.

На каждом budget: собственный cold server127.0.0.1:8081; startup включает reuseaddr+listen (не reuseport), проверку foreign models и fullpins доPopen. Четыре chat/tool JSON/SSE cases, long и cancel/recovery, warmup+3. Cancel curlmax-time1/exit28/noDONE, native observer связываетstopflag/end поsameGenerationContext иfixedphase, window60s+exactrecovery. PhysicalGPUrelease отдельноunknown. Guard2s/gap15s/clockbackwards/free+spec8GiB/pressure1/freepercentage≥50/swap0/ACmode0/RSS24GiB/wall900s/request240s. Критерии и пороги не ослабляются. При отказе futurecontextsnot-run; никакойO O M дляhardcap. Hardcap/overflownull.

Registration commit до GPU; всеошибки сохраняются. Это HTTPhardware measurement, неagentepisode; run_ids пуст. Программы и preparatory pins фиксируются до запуска; source checksum/marker/schema fixes отделены от предыдущих серий.
