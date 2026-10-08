# LAB33: отдельная диагностика жизненного цикла 08.10.2026

Прежняя LAB33-apple-serving-central-20261008 сохраняется blocked: unknown почему GUI PID303 исчез во время MLX chat. Владелец не сообщил причину, user quit не исключён. Новый опыт использует уже работающий LM Studio --run-as-service (PID фиксируется до load), а не переобъявляет исходный отказ успехом. Без смены runtimes, весов, ОС/power settings или уничтожения GUI.

Порядок MLX1.13.1 затем GGUF2.54.0, по отдельности 8K/parallel1/gpu max/ttl600. Уникальные aliases lab-lifecycle-qwen35-mlx и lab-lifecycle-qwen35-gguf. Pinned files из LAB29, app0.4.25+1/CLI69d945a. Перед load lms ps=[] и loopback1234 свободен. Для каждого — startup, четыре клетки chat/tool JSON/SSE × warmup+r1/r2/r3, cancel+recovery и unload/stop. Exact finals/tool allowlist/ID/DONE/usage сохранены; независимый exporter проверяет первичные данные.

MLX: free+speculative>=16GiB, pressure free>=50%, swap0, AC/powermode0; GGUF: freepages>=16GiB, swap0/AC/powermode0. App-tree RSS<=24GiB для обоих, каждые2s. Monitor сохраняет alive/PID/RSS, при resource guard разгружает только собственный alias, не убивает приложение. First failure прекращает ветвь; независимая следующая ветвь начинается только после cleanup/ps[]. HTTP deadline180s, cancel client1s и recovery<=60s. Cancel log не равен измерению GPU release. Обнаружение чужой модели/сервера — blocker, без остановки чужих процессов.

LMS GGUF backend/device/offload: сохраним runtime logs и оценим actual load lines. --gpu max или runtime package не выдаётся за независимое доказательство offload. Отсутствие строк остаётся unverified. Crash cause при невоспроизведённом исходном сбое не устанавливается. Это hardware/API опыт, без agent harness/run_ids.
