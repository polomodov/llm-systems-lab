# Зависимость LAB05 mistral-small-4-119b

LAB05 не запускался: LAB04-mistral-small-4-119b-probe завершилась blocked (partial).
HIP/ROCm-ветвь llama.cpp b8407 зависла на загрузке модели (`offloaded 37/37 layers to GPU`,
ROCm0 buffer 69794.53 MiB, без прогресса >14 ч). Vulkan offload-proof прошёл
(68.69 GiB, pp8 77.38 t/s, tg1 33.26 t/s). См. LAB04 manifest/report и raw evidence.
