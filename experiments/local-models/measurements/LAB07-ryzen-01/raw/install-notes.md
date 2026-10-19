# LAB07 — установочные заметки (session ryzen-01)

Хост: Ryzen AI Max+ 395 / 128 GB, Ubuntu 24.04.4 LTS, x86_64. Дата установки: 2026-10-15.
Установка — в пользовательский префикс (без sudo; `sudo` на хосте требует пароль).
Установка не входит во время inference.

## Ollama v0.34.2

- Источник: https://github.com/ollama/ollama/releases/tag/v0.34.2 (дата доступа 2026-10-15).
- Артефакты и SHA-256 (сверено с release `sha256sum.txt`):
  - `ollama-linux-amd64.tar.zst` — `e155b83589986d2c581fdbf1381ea3ebdb16549883679cd5a0627f7cdc05b12b` (1 427 542 079 B)
  - `ollama-linux-amd64-rocm.tar.zst` — `0bcad4a1908e4beba8de87bdc7af6476ea3ff8f57d10d218dadaf2b5ab0ebde9` (1 053 070 787 B)
- Установка (ручная распаковка, без установочного скрипта, т.к. он пишет в `/usr/local` через sudo):
  ```sh
  PREFIX="$HOME/local-model-lab-artifacts/lab07-apps/ollama"
  mkdir -p "$PREFIX" && cd "$PREFIX"
  tar --zstd -xf ollama-linux-amd64.tar.zst
  tar --zstd -xf ollama-linux-amd64-rocm.tar.zst   # ROCm libs overlay: lib/ollama/rocm_v7_2
  ```
- Бинарь: `$PREFIX/bin/ollama`; библиотеки ROCm: `$PREFIX/lib/ollama/rocm_v7_2`.
- Проверка: `ollama --version` → `client version is 0.34.2` (`raw/ollama-version.txt`).

## LM Studio (llmster CLI)

- Источник: `https://lmstudio.ai/install.sh` (дата доступа 2026-10-15). APP_NAME=`llmster`, APP_VERSION=`0.0.25-1`, variant=`full`.
- Установка: `sh install.sh --no-modify-path` → `${HOME}/.lmstudio/bin`. `libatomic1` проверен установщиком как присутствующий.
- CLI: `${HOME}/.lmstudio/bin/lms`; `lms --version` → `CLI commit: 69d945a` (`raw/lms-version.txt`).
- GUI-версия отдельно не устанавливалась (CLI-only дистрибутив `llmster`); для отчёта GUI-версия = `not-applicable: llmster CLI distribution`.
- Runtime (LLM engine), выбран до первого запроса:
  - `llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0` — скачан (1.67 GB) и выбран для GGUF.
  - Также установлены `avx2@2.41.0`, `nvidia-cuda-avx2@2.41.0`, `vulkan-avx2@2.41.0` (последний был выбран по умолчанию до выбора ROCm).
  - До/после выбора: `raw/lms-runtimes-before.txt`, `raw/lms-runtimes-selected.txt`.
  - Команды: `lms runtime get llama.cpp-linux-x86_64-amd-rocm-avx2 -y`; `lms runtime select llama.cpp-linux-x86_64-amd-rocm-avx2@2.58.0`.

## Lemonade v11.9.0 — не запущен (blocker)

- Источник: https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0 (дата доступа 2026-10-15).
- Артефакт: `lemonade-server_11.9.0-debian13_amd64.deb` — SHA-256 `e42b4883e6bb1acec2677ace22071c1bc098ac31264322117b2e4523f347712a` (3 865 468 B).
- Распакован через `dpkg-deb -x` (без dpkg): `usr/bin/lemonade`, `usr/bin/lemond`.
- Причина blocker: сборка для Debian 13 требует `libcpp-httplib0.41`, `libmbedcrypto16`, `libwebsockets19t64` и `libstdc++6 >= 14`; на Ubuntu 24.04 отсутствуют (нет `libcpp-httplib`/`libmbedcrypto16`/`libwebsockets19t64`; `libstdc++.so.6.0.33` = GCC 13). Бинарь не стартует: `error while loading shared libraries: libmbedcrypto.so.16` / `libcpp-httplib.so.0.41` (`raw/lemonade-version.txt`, `raw/lemond-help.txt`).
- Официальный путь Ubuntu (`ppa:lemonade-team/stable` либо `snap install lemonade-server`) требует root; sudo без пароля недоступен.
- Следующий конкретный шаг: установить Lemonade из PPA/snap с правами root (или собрать из исходников под Ubuntu 24.04), затем выполнить шаг 4 методички с `LAB_LLAMA_BIN` = ROCm-bin ЛР04.
