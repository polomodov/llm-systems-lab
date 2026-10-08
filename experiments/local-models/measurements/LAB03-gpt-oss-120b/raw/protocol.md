# LAB03 — протокол проверки артефакта gpt-oss-120b

Процедура, сохранённая до сверки артефакта (сессия `gpt-oss-120b`).

## Цель

Закрепить ровно один GGUF `gpt-oss-120b` MXFP4 из `ggml-org/gpt-oss-120b-GGUF`
и подтвердить, что локальная копия совпадает с публикацией по байтовому размеру и SHA-256.

## Вход

- `model_id`: `openai/gpt-oss-120b` (config revision `b5c939de8f754692c1647ca79fbf85e8c1e70f8a`).
- `repository`: `ggml-org/gpt-oss-120b-GGUF`, `revision`: `238abdd290bb874b90a5da1b4549881b7d05c091`.
- Файл: `gpt-oss-120b-MXFP4.gguf`, ожидаемый размер 63 387 346 208 B,
  ожидаемый SHA-256 `582bd40f6886200101f4c4ed9f25f3fe80cc14c86e9e2b37746cd8904a0c622d`.

## Шаги

1. Получить metadata закреплённой ревизии: HF API `?blobs=true`; зафиксировать repository,
   revision, имена файлов, `bytes` и `lfs.sha256` каждого файла.
2. Проверить, что запрошенный `sha` ответа равен закреплённой ревизии.
3. Скачать файл в `$LAB_STORAGE/<repo>/<rev>/`; при обрыве — `curl -C -` (resume), без
   переименования и склейки. Если `lfs.sha256` у файла отсутствует — это `publisher_hash_present=false`,
   а не выдуманный размер.
4. Пересчитать SHA-256 и размер локального файла, сравнить с publisher.
5. Записать результат в формате `{repository, revision, files:[{path, bytes, sha256,
   publisher_hash_present, status}]}` (структура `fetch_artifact.py`), файл `raw/verification.json`.
6. Выгрузить checksum-файл `raw/weights.sha256` для `sha256sum --check` в LAB04/LAB05.

## Критерий остановки и решения

- Любое расхождение размера или SHA-256 → `status: fail` для файла, ветвь останавливается,
  артефакт в LAB04/05 не передаётся (`no-artifact`).
- Отсутствующий файл → `no-artifact`, не размер 0.
- Успех: все файлы `status: verified`.

## Повторы и расширения

Сверка идемпотентна; повторный `fetch_artifact.py` без `--download` повторяет проверку существующих
файлов. Inference и выбор backend — вне LAB03 (LAB04/LAB05).
