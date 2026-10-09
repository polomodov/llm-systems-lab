import json, pathlib, time, torch, transformers
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

assert torch.version.hip and torch.cuda.is_available()
assert "gfx1151" in torch.cuda.get_device_properties(0).gcnArchName
request = json.loads(pathlib.Path("/evidence/raw/chat-request.json").read_text())
tokenizer = AutoTokenizer.from_pretrained("/model", local_files_only=True)
# Явный BF16, SDPA и полный checkpoint; vision inputs в этой пробе отсутствуют.
model = Qwen3_5ForConditionalGeneration.from_pretrained(
    "/model", dtype=torch.bfloat16, attn_implementation="sdpa",
    local_files_only=True).to("cuda:0").eval()
template = tokenizer.apply_chat_template(
    request["messages"], tokenize=False, add_generation_prompt=True,
    enable_thinking=False)
pathlib.Path("/evidence/raw/reference-prompt.txt").write_text(template)
inputs = tokenizer(template, return_tensors="pt", add_special_tokens=False).to("cuda:0")
assert inputs.input_ids.shape[1] + request["max_tokens"] <= 4096
torch.cuda.reset_peak_memory_stats()
torch.cuda.synchronize()
start = time.perf_counter()
with torch.inference_mode():
    outputs = model.generate(**inputs, max_new_tokens=request["max_tokens"], do_sample=False)
torch.cuda.synchronize()
elapsed = time.perf_counter() - start
generated = outputs[0, inputs.input_ids.shape[1]:]
print(json.dumps({"torch": torch.__version__, "hip": torch.version.hip,
    "transformers": transformers.__version__, "thinking": False,
    "sampling": "greedy", "input_tokens": inputs.input_ids.shape[1],
    "output_tokens": generated.numel(), "generate_seconds": elapsed,
    "peak_allocated_bytes_after_load": torch.cuda.max_memory_allocated(),
    "peak_reserved_bytes_after_load": torch.cuda.max_memory_reserved(),
    "final": tokenizer.decode(generated, skip_special_tokens=True)}, ensure_ascii=False))
