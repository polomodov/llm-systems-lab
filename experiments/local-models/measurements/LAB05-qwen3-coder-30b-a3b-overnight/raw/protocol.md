# LAB05 — предварительный протокол (qwen3-coder-30b-a3b)

## Гипотеза
qwen3-coder-30b-a3b на HIP llama.cpp b8407 проходит bench-заполнения 8K/16K/32K и серверный протокол chat/tool/stream на loopback.

## Порядок
8K → 16K → 32K, каждый только при успехе предыдущего; bench `-p 0 -n 128 -d CTX-128 -r 3`; сервер 8080; `http_probe.py` 4×2; long/overflow/cancel.

## Критерий остановки
OOM/reset/подкачка-за-бюджетом → стоп ветви, следующий контекст не запускается.
