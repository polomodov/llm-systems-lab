# LAB04 — предварительный протокол gpt-oss-120b (preregistration)

Записан ДО парных прогонов. Момент регистрации подтверждается отдельным git-коммитом
до коммита с результатами.

## Гипотеза

Один и тот же GGUF `gpt-oss-120b-MXFP4.gguf` (59 GiB, MoE 117B total / 5.1B active)
работает с полным GPU offload в обеих prebuilt-сборках llama.cpp b8407
(commit `312cf03328496df9c56fe843952cf02a8964c59a`): Vulkan/RADV и ROCm/HIP. При одинаковой
нагрузке backend влияет на скорость prefill/decode и память; направление и величина
эффекта неизвестны до измерений.

## Фактор и константы

- Фактор: backend (Vulkan против HIP/ROCm), один commit и один артефакт.
- Константы: `-ngl 999 -t 8 -b 512 -ub 256 -ctk f16 -ctv f16 -fa 1`;
  `pp2048` и `tg128 @ depth 4096`; модель `:ro` из `$LAB_STORAGE`.
- Бандлы: Vulkan (GNU 11.4) и ROCm/HIP (GNU 13.3), SHA в `raw/{vulkan,hip}-binaries.sha256`.

## Порядок

1. `sha256sum --check raw/weights.sha256`.
2. Snapshot `--version`/`--list-devices` обеих сборок.
3. **Offload-proof** каждой ветви: `llama-bench -v -p 8 -n 1 -r 1`, сохранить
   `load_tensors: layer … assigned to device …` и посчитать число слоёв на GPU.
4. Прогрев каждой ветви (`pp512 + tg128`, не в статистике).
5. Три парных повтора: r1 vulkan→hip, r2 hip→vulkan, r3 vulkan→hip;
   `pp2048 -p 2048 -n 0` и `tg128 -p 0 -n 128 -d 4096`, каждый под `/usr/bin/time -v`.

## Критерий остановки и решение

- OOM, GPU reset, невалидный JSON, выход за бюджет → ветвь останавливается.
- CPU fallback (не все слои на GPU) фиксируется как `fail`, а не как полный offload.
- Сравнение: median по трём повторам, отношение HIP/Vulkan для pp и tg отдельно.

## Границы вывода

Бандлы собраны разными toolchain'ами; сравнение — на одном артефакте и commit, но
не побитово идентичные сборки. Производительность — не качество ответов.
