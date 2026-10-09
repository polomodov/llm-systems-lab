# LAB04 — предварительный протокол (gemma4-31b-it)

## Гипотеза
Один GGUF gemma4-31b-it полностью выгружается на GPU в обеих prebuilt-сборках llama.cpp b10000 (ROCm 7.2 / Vulkan) (Vulkan/RADV и ROCm/HIP); backend влияет на скорость, направление неизвестно.

## Порядок
1. `sha256sum --check`; 2. offload-proof `llama-bench -v` обеих ветвей; 3. прогрев; 4. три парных повтора pp2048/tg128@d4096 под `/usr/bin/time -v`.

## Критерий остановки
OOM/невалидный JSON/следы CPU-offload → fail ветви.
