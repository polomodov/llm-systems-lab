# LAB04 — предварительный протокол (qwen3-coder-30b-a3b)

## Гипотеза
Один GGUF qwen3-coder-30b-a3b полностью выгружается на GPU в обеих prebuilt-сборках llama.cpp b8407 (Vulkan/RADV и ROCm/HIP); backend влияет на скорость, направление неизвестно.

## Порядок
1. `sha256sum --check`; 2. offload-proof `llama-bench -v` обеих ветвей; 3. прогрев; 4. три парных повтора pp2048/tg128@d4096 под `/usr/bin/time -v`.

## Критерий остановки
OOM/невалидный JSON/следы CPU-offload → fail ветви.
