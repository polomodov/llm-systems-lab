# Перед отдельной MLX ветвью

CLI inventory использует format=safetensors для MLX artifact (в API compatibility_type=mlx). В MLX-варианте выбирать этот формат и точный indexedModelIdentifier/path, чтобы общий modelKey qwen3.5-9b не подменил MLX ранее импортированным GGUF. GGUF-серия выполняется с исходным контроллером a9c35e4, сохранённым отдельно lms-metal-controller-at-start.py. В ней общий key до добавления MLX однозначно выбрал GGUF; это подтверждают startup-loaded/native-models и hash. Условия/входы/критерии MLX не меняются, исправлен только selector до его исполнения.
