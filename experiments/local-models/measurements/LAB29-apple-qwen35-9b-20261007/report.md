# LAB29 — Qwen3.5-9B: GGUF и MLX

Сессия: apple-qwen35-9b-20261007. Обязательный минимум подготовки выполнен; независимое решение проверяющего ещё не выставлено.

## Паспорт выполнения

| Поле | Значение |
| --- | --- |
| Дата / оператор | 07.10.2026; Codex по запросу владельца |
| Стенд | M5 Max 18 CPU / 40 GPU, 128 GiB, macOS 26.5 arm64 |
| Предпосылки | LAB01-apple-prerequisite-20261007 и LAB28-apple-first-20261007 |
| Source reference | Qwen/Qwen3.5-9B @ c202236235762e1c871ad0ccb60c8ee5ba337b9a |
| Инструменты | Python 3.12.14 arm64, huggingface_hub 2.1.1, gguf 0.19.0; успешная передача curl HTTP/1.1 |
| Хранилище | /Users/lab/local-model-lab-artifacts/<repository>/<revision>/; вне Git |
| Лицензия | Apache-2.0 по source LICENSE и карточкам |
| Инференс / GPU | Не выполнялись; GPU budget null |

## Гипотеза и протокол до запуска

Протокол raw/protocol.md зарегистрирован до загрузки/verification. Выбраны небольшой Qwen3.5-9B, тот же GGUF Q6_K, что уже проверен на Ryzen, и MLX 4-bit. Заданы immutable revisions, ожидаемые hashes, предел загрузки 30 GiB с временными частями и запас SSD ≥40 GiB. Фактического свободного SSD перед стартом было более 7 TiB.

Pinned source reference служит справочником config/tokenizer/license, а не доказательством source commit конверсии MLX. Этот conversion commit и точная версия conversion tool не опубликованы: заранее предусмотрено сравнение deployments с явным ограничением происхождения.

После начала загрузки добавлены raw/transport-amendment.md, raw/range-transport-amendment.md и raw/curl-transport-amendment.md. Менялся транспорт, не веса/quant/revision/hash. Все неудачные первоначальные попытки оставлены в planned_attempts и raw evidence.

## Ход выполнения

1. Проверены HF API на immutable revisions и опубликованные размеры/LFS SHA-256. Для small files использованы Git blob SHA-1 плюс локальный SHA-256.
2. Первый Xet downloader завершился RuntimeError после repeated request errors. Single-stream HTTP работал медленно и был остановлен оператором после подтверждённой Range-пробы; последовательный префикс сохранён. Python range/TLS и отдельный HF metadata helper встретили EOF/URLError; ошибочные/неполные данные не объявлялись успешными.
3. Продолжена передача стандартным curl HTTP/1.1, максимум два range workers. Проверялись HTTP206, Content-Range, длина каждого тела и полная publisher SHA после сборки. GGUF и оба MLX shards успешно собраны и сверены.
4. Получены 19 выбранных файлов общим объёмом 12.513 GiB с configs/tokenizers/cards/reference LICENSE. Веса составляют GGUF 6.9461 GiB и MLX 5.5416 GiB. Карточки и конфигурации сохраняются в raw; полные tokenizer JSON и веса остаются вне Git.
5. Все 19 файлов повторно хешированы офлайн независимо от transfer checks. Результат — all_match=true. safetensors index покрывает ровно два shards и 1260 тензоров; headers/offsets/extent согласованы и payload gaps/overlap не обнаружены.
6. Read-only parser gguf 0.19.0 извлёк 427 tensor descriptors, embedded tokenizer и chat template. Это не inference runtime и не загрузка модели на GPU.
7. Сопоставлены templates, vocab/merges и EOS fields; результаты находятся в raw/protocol-comparison.json. Один вспомогательный импорт отсутствующего GGUFFileType был исправлен до финализации manifest; успешный finalize_manifest.py не зависит от этого символа.

## Результаты

| Вариант | Repository / revision | Quant | Веса | SHA / комплектность | Допуск |
| --- | --- | --- | --- | --- | --- |
| GGUF | unsloth/Qwen3.5-9B-GGUF @ 3885219b6810b007914f3a7950a8d1b469d598a5 | Q6_K; также Q8_0/F32 tensors | 7458301152 bytes = 6.9461 GiB | 91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59; совпадает с Ryzen LAB03 | К LAB30 после установки CMake и pinned build |
| MLX | mlx-community/Qwen3.5-9B-MLX-4bit @ 938d8919941c6e7efd3c7150eff7fe9d12afa631 | affine 4-bit, group_size=64 | 5950221072 bytes = 5.5416 GiB | Оба publisher SHA совпали; index complete | К пробе LAB31 после pinned окружения |

| MLX shard | Bytes | Проверенный SHA-256 |
| --- | --- | --- |
| model-00001-of-00002.safetensors | 5349771222 | a68b87558c6ef43f74c2bd63ce7e9092ceddc3101f3def0030774bae5f42aadd |
| model-00002-of-00002.safetensors | 600449850 | b0a770bf8469c7f3f18756a0e0283f1c1174344a83e059a4e483f6af4907352d |

| Входной протокол | GGUF | MLX | Вывод |
| --- | --- | --- | --- |
| Chat template SHA | 7f0e529032c25183bcd66c7f238da2d377f43be754a94e2725a58c4e16d2ed67 | a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715 | Templates отличаются |
| Обычные/специальные ID из существующего MLX словаря | Совпали с MLX | 248077 decoded vocabulary entries | Общий префикс совпадает |
| GGUF extra vocabulary | 243 [PAD...] entries | Отдельно не перечислены в tokenizer JSON | Полный vocab hash отличается из-за padding; это не другая нумерация общих токенов |
| BPE merges | Совпали | Совпали | Совпадение canonical hashes |
| EOS metadata/config | 248046 = im_end | text_config eos=248044 = endoftext; tokenizer_config eos=im_end | Эффективный stop runtime проверить в LAB32 |
| Source conversion commit | Не выводился из имени модели | Не опубликован | Reference revision не приписывается конверсии |

В GGUF 178 tensors Q6_K, 72 Q8_0 и 177 F32; в MLX packing хранится U32 с scale/state BF16/F32. Названия Q6_K и 4-bit не задают одинаковую квантовку.

GGUF-грубая оценка для 8K: округлённые 7 GiB weights + 6 GiB runtime + 4 GiB KV/state = 17 GiB, ниже рекомендованного LAB28 потолка 24 GiB. Это эвристика, не проверенный peak/fit. Для MLX runtime/state ещё не калиброваны; итоговая память неизвестна. Веса на SSD не подтверждают GPU allocation.

## Ошибки и ограничения

Три первоначальные GGUF попытки retained как failed: Xet runtime failure, операторская остановка single-stream и Python range/TLS failure. Metadata SDK helper также имел TLS error; успешный curl metadata register показан отдельно. Временные части до их финальной сборки не считались verified model artifacts. Source conversion commit/версия MLX неизвестны.

Карточка MLX описывает mlx-vlm conversion. Archived MLX-LM qwen3_5 source показывает text-only loader/sanitize vision weights, но это документированный кандидат, а не аппаратный smoke. Будущая совместимость M5 Max, kernels, chat/tools и stop/reasoning подтверждается LAB30–32. Веса модели не исполнялись; remote model code не запускался; ключи не использовались.

## Вывод по гипотезе

Гипотеза подготовки поддержана: все выбранные revisions закреплены, publisher и повторные local hashes совпали, shards/index/header комплектны. GGUF совпадает с Ryzen baseline. Артефакты готовы к следующим smoke, при подготовке runtime. Разные quant/templates и неопубликованный source conversion commit позволяют сравнивать deployments целиком; чистый эффект engine из этой пары не выводится.

## Ответы на контрольные вопросы

1. GGUF Q4/Q6 и MLX 4-bit различаются схемой packing/scales, group_size, исключениями и неизменёнными tensors; один nominal bit count не фиксирует качество/peak memory.
2. SHA подтверждает одинаковые bytes и сверку с опубликованным объектом. Он не доказывает корректность conversion или истинность source provenance, если её не опубликовали.
3. Template override меняет сериализованный prompt, role/tool markers и reasoning prefix; получает отдельный hash и condition.
4. MoE хранит полный набор экспертов; активные параметры описывают вычисления одного токена, не размер всех weights. Выбранная 9B модель здесь hybrid-dense.

## Комплект сдачи

- [x] Source reference, artifact revisions, sizes и hashes закреплены.
- [x] GGUF и MLX manifests независимы, обе publisher SHA и повторные hashes проверены.
- [x] Config/cards/license/tokenizer/template evidence и tools lock сохранены.
- [x] Неудачные попытки и ограничения provenance/runtime отражены.
- [x] report.md, measurements.tsv и manifest v2 заполнены.

Проверка комплектности lab:check --mode submission не выставляет экспериментальный pass; reviewer_decision остаётся null.
