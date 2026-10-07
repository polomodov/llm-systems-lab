---
base_model: Qwen/Qwen3.5-9B
library_name: mlx
pipeline_tag: image-text-to-text
tags:
  - mlx
  - qwen3.5
  - vision-language-model
  - quantized
  - 4bit
license: apache-2.0
---

# Qwen3.5-9B-MLX-4bit

This is a quantized MLX version of [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) for Apple Silicon.

## Model Details

- **Original Model:** [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- **Quantization:** 4-bit (~5.059 bits per weight)
- **Group Size:** 64
- **Format:** MLX SafeTensors
- **Framework:** [mlx-vlm](https://github.com/Blaizzy/mlx-vlm)

## Conversion Details

This model was converted using `mlx-vlm` with 4-bit quantization.

**Conversion command:**
```bash
python3 -m mlx_vlm convert \
  --hf-path "Qwen/Qwen3.5-9B" \
  --mlx-path "./mlx_models/Qwen3.5-9B-MLX-4bit" \
  -q --q-bits 4 --q-group-size 64
```

## Important Note

A better, more optimized conversion may be available from **@Prince** ([@Blaizzy](https://huggingface.co/Blaizzy)) in the MLX VLM community. Check the [mlx-community](https://huggingface.co/mlx-community) organization for updated versions as official Qwen3.5 support is merged into the main `mlx-vlm` branch.

## Usage

```python
from mlx_vlm import load, generate

model, processor = load("mlx-community/Qwen3.5-9B-MLX-4bit")

output = generate(
    model,
    processor,
    prompt="Describe this image in detail",
    image="path/to/image.jpg",
    max_tokens=200
)
print(output)
```

Or from the command line:
```bash
mlx_vlm generate \
  --model mlx-community/Qwen3.5-9B-MLX-4bit \
  --prompt "Describe this image" \
  --image path/to/image.jpg \
  --max-tokens 200
```

## Performance

- **Disk Size:** ~5.6 GB
- Runs efficiently on Apple Silicon Macs (M1/M2/M3/M4)
- Lower memory footprint compared to 8-bit quantization

## License

This model inherits the [Apache 2.0 license](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/LICENSE) from the original Qwen3.5-9B model.
