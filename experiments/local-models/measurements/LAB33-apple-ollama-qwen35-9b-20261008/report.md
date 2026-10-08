# LAB33 — установка Ollama и LM Studio, ожидание AC

Статус: **blocked до инференса**. Централизованная установка выполнена по запросу владельца; гипотеза API ещё не проверена.

## Паспорт выполнения

| Поле | Условие |
| --- | --- |
| Исполнитель / дата | Codex по запросу владельца, 2026-10-08 |
| Машина | Apple M5 Max / 128 GiB / macOS 26.5; исходный паспорт из LAB32 сохранён; текущее питание Battery Power |
| Модель | План: Qwen3.5-9B-Q6_K GGUF, revision 3885219… / SHA256 91898433…; manifest LAB29 скопирован. Проверка текущего hash не началась из-за AC guard |
| Ollama | /Applications/Ollama.app 0.40.1; CLI через /usr/local/bin/ollama и /opt/homebrew/bin/ollama; API version 0.40.1 |
| LM Studio | /Applications/LM Studio.app 0.4.25+1; /opt/homebrew/bin/lms → ~/.lmstudio/bin/lms, CLI commit 69d945a |
| Runtime / backend | Ollama CLI archive содержит runner commit 631109b34; GUI runner и Metal ещё не проверены загрузкой. LMS selected llama.cpp 2.54.0 и MLX 1.13.1; inventory не доказывает исполнение |
| План | 8K, один slot, threads8, KV f16, FA on, temp0 / seed1 / top_p1 / outputcap2048; reasoning enabled |
| Harness / run IDs | Нет; аппаратные HTTP-пробы запланированы, агентные попытки не выполнялись, run_ids=[] |
| Отличия | По запросу владельца приложения установлены централизованно до импорта/инференса. Продолжение требует amendment для фактических app runtime |

## Гипотеза и протокол до запуска

[Исходный протокол](raw/protocol.md) зарегистрирован до импорта/инференса. UTC timestamp — утверждение оператора; независимой отметки времени до подготовки этой сессии нет. 42 попытки: preflight, synthetic validator, ветви Ollama/LM Studio/direct, короткие chat/tool JSON/SSE с warmup+3, отмена/recovery и остановка. AC/powermode0, freepages ≥16 GiB, swap0 обязательны. При отказе эксперимент останавливается.

Скачивание исходного Ollama CLI, проверка release digest и чтение help/source — подготовка до регистрации. [Изменение задания](raw/installation-steering.md) фиксирует последующий запрос центральной установки; установка не является inference измерением. Отсутствие LM Studio перестало быть blocker после установки: его обе модельные ветви остаются not-run из-за AC.

## Ход выполнения

| Шаг | Фактическое действие | Результат / evidence |
| --- | --- | --- |
| Подготовка CLI | Официальный Ollama v0.40.1 tarball, checksum, version/help, pinned OpenAI/envconfig source | [Release](raw/ollama-release.json), [CLI](raw/ollama-cli-version.txt), [runner](raw/ollama-bundled-runner-version.txt) |
| Preflight | python3 raw/lab33_runner.py preflight | failed: Battery Power; freepages достаточно, swap0. [Отказ](raw/preflight-initial-rejection.json); hash/import/model не начинались |
| Центральный Ollama | Официальный ZIP → SHA256 → ditto в /Applications → codesign verify → CLI symlink → open -a Ollama | [Установка](raw/ollama-central-installation.json), /api/version 0.40.1; моделей в Ollama нет |
| Центральный LM Studio | Brew задержался на HEAD; официальный arm64 DMG скачан curl, SHA256, hdiutil readonly, ditto в /Applications, codesign verify, open -a 'LM Studio' | [Установка](raw/lm-studio-central-installation.json), CLI/runtime inventory работают |
| CLI / PATH | zsh -lc 'command -v ollama; command -v lms; ollama --version; lms --version' | [Проверка](raw/central-cli-verification.txt) |
| Серия | Модель не импортировалась/загружалась, direct не запускался | Остальные 41 попытка not-run, причины в manifest |

## Результаты

| Deployment | App / CLI / runtime | Artifact | Backend / protocol / latency / memory |
| --- | --- | --- | --- |
| Ollama GGUF | 0.40.1; loopback API-version подтверждён | Запланирован pinned GGUF, импорт not-run | Неизвестны: AC preflight отказан |
| LM Studio GGUF | 0.4.25+1; CLI 69d945a; selected llama.cpp 2.54.0 | GGUF импорт not-run | Неизвестны: модель не загружена |
| LM Studio MLX | 0.4.25+1; selected MLX 1.13.1 | Отдельный artifact LAB29/31 ещё не зарегистрирован в приложении | Неизвестны: модель не загружена |

| Сравнение | Условия / различия | Вывод |
| --- | --- | --- |
| Ollama и direct | Планируемые одинаковые weights/входы; разные commits/renderer/cache. Центральный GUI runtime требует pin | Чистый overhead неизвестен; сравнение deployments не выполнялось |

Численных модельных наблюдений нет; measurements.tsv содержит заголовок. Результаты LAB32 не выданы за замеры LAB33. В LM Studio ls видна bundled embedding модель 84.11 MB, lms ps подтверждает отсутствие загруженных моделей.

## Ошибки и ограничения

- Preflight отказал на Battery Power до модели; результат сохранён, не переписан успехом установки.
- Ollama запущен как обычное приложение и слушает 11434. Для лаборатории нужно использовать GUI-server по отдельному протоколу либо штатно остановить его перед собственным сервером; второй экземпляр не запускался.
- При первом запуске LMS selected runtime llama.cpp 2.54.0 / MLX 1.13.1 отличались от bundled 2.41.0 / 1.11.0. Inventory не доказывает backend/offload; версии и hashes необходимо закрепить перед серией.
- UI observer LM Studio завершился timeout; процесс приложения и CLI проверены, состояние первого экрана неизвестно. У Ollama UI observer не нашёл окна; API отвечает.
- GPU budget, imported blob identity, actual template, TTFT, overhead, cancellation/recovery неизвестны. Модельный инференс не выполнялся.
- Контроллер — подготовленная, ещё не выполненная модельная серия. После центральной установки он требует адаптации; не запускать исходный preflight повторно с тем же ID и не перезаписывать отказ.

## Вывод по гипотезе

**Данных недостаточно.** Установка и CLI подтверждены. Минимум LAB33 по модельным smoke не выполнен; blocker — батарея. Далее: AC, повторный preflight отдельной попыткой и amendment с фактическими централизованными runtime, затем Ollama/Metal, LM Studio/Metal, LM Studio/MLX. LAB34 пока не допущен.

## Ответы на контрольные вопросы

1. **Почему версия GUI не является pin engine?** LM Studio имеет несколько runtime и выбирает/обновляет их независимо. Нужны selected package/version/hash и load logs.
2. **Когда импорт того же файла меняет входной протокол?** Если renderer/importer выбирает новый chat template, defaults, tool parser или reasoning mapping.
3. **Что нужно для чистого wrapper overhead?** Одинаковые commit/build/artifact/tokenizer/template/cache/context/slots/sampling и нагрузка. Здесь commits различаются; вывод будет сравнением deployments.
4. **Чем observed runner полезнее alias?** Alias — имя; process/runtime/load/backend/offload показывают реальный движок и размещение. В этой сессии модельный runner ещё не наблюдался.

## Комплект сдачи

Manifest: 42 попытки с причинами failed/not-run. Исходный protocol, commands/controllers/requests, install/version/help/inventory, evidence hashes и пустой TSV сохранены. Комплект сдаётся как blocked, не выполненная LAB33. Реальных run records нет: агент не запускался. Проверка комплектности не присваивает эксперименту pass.

Решение проверяющего: не проверено.
