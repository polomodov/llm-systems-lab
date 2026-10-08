# Remediation for the rocm-gfx1151.Dockerfile (pinned commit 94602c9) build
# failures on this host. Two independent problems:
#
# 1. The host has no BuildKit. The legacy builder drops the body of the
#    `RUN ... && python3 - <<'PY'` heredoc in step 22, so `python3 -` read an
#    empty script and installed none of the runtime extras.
# 2. Even with the heredoc applied, a plain `pip install` cannot keep the
#    image's ROCm stack: the base torch 2.9.1+rocm declares a dependency on
#    triton 3.5.1+rocm (absent from the index) while the image ships
#    triton 3.7.0+amd, so pip backtracks and replaces torch/triton with generic
#    PyPI CUDA builds, which breaks gfx1151.
#
# Fix: install the flattened extras and their closure with `--no-deps`, which
# pins the image's ROCm torch/triton/torchvision in place. The exact resulting
# package set is frozen in sglang-extra-requirements.txt.
FROM lab-sglang:gfx1151-94602c9
COPY sglang-extra-requirements.txt /tmp/sglang-extra-requirements.txt
RUN python3 -m pip install --no-cache-dir --no-deps -r /tmp/sglang-extra-requirements.txt
RUN python3 -c "import torch, sglang; from transformers import Qwen3_5ForConditionalGeneration; assert torch.version.hip; print('sglang', sglang.__version__, 'torch', torch.__version__)"
