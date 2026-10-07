# LAB29: предварительный протокол

Гипотеза: выбранный Qwen3.5-9B GGUF Q6_K и опубликованный MLX 4-bit можно закрепить immutable revisions и проверить hashes/комплектность. Совпадение source revision после conversion не предполагается.
GGUF: unsloth/Qwen3.5-9B-GGUF @3885219b6810b007914f3a7950a8d1b469d598a5, Qwen3.5-9B-Q6_K.gguf, SHA91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59. Это тот же файл, что в Ryzen LAB03.
MLX: mlx-community/Qwen3.5-9B-MLX-4bit @938d8919941c6e7efd3c7150eff7fe9d12afa631; все публичные model/tokenizer/config/index shards, без .gitattributes. Conversion по карточке mlx-vlm, исходный commit не опубликован: future GGUF/MLX comparison только deployment целиком.
Source reference: Qwen/Qwen3.5-9B @c202236235762e1c871ad0ccb60c8ee5ba337b9a — закреплённый справочник config/tokenizer/license/model card; его веса не скачиваем. Этот reference не объявляем source conversion commit MLX.
Limits: SSD download ceiling 30 GiB включая выбранные веса/metadata; минимум свободного SSD 40 GiB до старта. Проверка памяти без inference; модель не загружается в GPU. Первая серия LAB30/31 позже: сумма weights/runtime/state ≤24 GiB по рекомендации LAB28, GPUbudget пока null.
Acquisition: изолированный временный venv, pinned huggingface_hub; public token=False, без чтения секретов. Хранилище вне Git: /Users/lab/local-model-lab-artifacts/<repo>/<revision>. Существующие корректные bytes можно переиспользовать; исходные файлы не менять.
Checks: publisher LFS SHA256, Git blob SHA для small files, size и index completeness; полный повторный offline SHA256 каждого выбранного файла. GGUF embedded metadata/tokenizer/chat template извлечь parser в отдельном toolchain и hash его версии; никакого исполнения remote model code.
Pass of preparation: закреплены pins, полный состав и реальные hashes; неизвестное provenance/конверсия/поддержка runtime записаны. Ошибки/несовпадения сохраняем failed и прекращаем допуск.

Зарегистрирован: 2026-10-07T13:47:38.818Z
