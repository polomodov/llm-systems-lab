#!/usr/bin/env bash
set -u
LAB_DIR="${LAB_DIR:?}"
VUL="${VUL:?}"
GGUF="${GGUF:?}"
cd "$LAB_DIR" || exit 1

echo "start $(date -u +%FT%TZ) fa=1" >> raw/vulkan-run-progress.txt
# warmup
"$VUL/llama-bench" -m "$GGUF" -ngl 999 -t 8 -b 512 -ub 256 \
  -ctk f16 -ctv f16 -fa 1 -p 512 -n 128 -r 1 -o json \
  > raw/vulkan-warmup.json 2> raw/vulkan-warmup.log
echo "warmup exit=$? $(date -u +%FT%TZ)" >> raw/vulkan-run-progress.txt

for repeat in 1 2 3; do
  for mode in pp tg; do
    prefix="raw/vulkan-r${repeat}-${mode}"
    free -b > "$prefix-memory-before.txt"
    cat /proc/vmstat > "$prefix-vmstat-before.txt"
    if [ "$mode" = pp ]; then
      args="-p 2048 -n 0 -r 1"
    else
      args="-p 0 -n 128 -d 4096 -r 1"
    fi
    /usr/bin/time -v -o "$prefix-process.txt" \
      "$VUL/llama-bench" -m "$GGUF" -ngl 999 -t 8 -b 512 -ub 256 \
      -ctk f16 -ctv f16 -fa 1 $args -o json \
      > "$prefix.json" 2> "$prefix.log"
    echo "r${repeat}-${mode} exit=$? $(date -u +%FT%TZ)" >> raw/vulkan-run-progress.txt
    cat /proc/vmstat > "$prefix-vmstat-after.txt"
    free -b > "$prefix-memory-after.txt"
  done
done
echo "done $(date -u +%FT%TZ)" >> raw/vulkan-run-progress.txt
