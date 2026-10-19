# LAB06 — предварительный протокол (qwen36-35b-a3b)

Зарегистрирован до запусков.

## Гипотеза
BF16 native checkpoint `Qwen/Qwen3.6-35B-A3B` (revision 995ad96eacd98c81ed38be0c5b274b04031597b0)
загружается на gfx1151 в трёх runtime (vLLM v0.29.0, SGLang v0.5.20 gfx1151-fixed,
Transformers reference) и проходит контрольный chat; серверы — полный tool round trip.

## Изменяемый фактор
engine (vLLM / SGLang / Transformers); context 4096 (минимум), 8192 — расширение.

## Константы
- Артефакт: BF16 native, 71 926 799 705 bytes, смонтирован :ro, HF_HUB_OFFLINE=1.
- GPU gfx1151, ROCm 7.2; /dev/kfd, /dev/dri.
- Одна последовательность; dtype bfloat16; parsers qwen3 / qwen3_coder; alias lab-model.
- vLLM: --gpu-memory-utilization 0.90 --enforce-eager --no-enable-prefix-caching.
- SGLang: fixed image (sglang-fix), --mem-fraction-static 0.85 --attention-backend triton, graph bs=1.
- Порты: vLLM 8000, SGLang 30000. Двигатели последовательно.

## Порядок
GPU probe → verify → vLLM c4096 (chat/stream/tool/tool-stream) → SGLang c4096 → reference.

## Критерий остановки
GPU probe fail / OOM при загрузке / нет control answer → ветвь fail, зафиксировать лог.
