# Предварительный протокол LAB28

Гипотеза: машина — Apple M5 Max / 128 GiB / native arm64 macOS, пригодная для подготовки артефактов и маленького smoke при резерве ОС 16 GiB.
Измерения: sw_vers, uname -m, sysctl CPU/memsize, GPU-only system_profiler; developer path/compiler/SDK; pmset power settings и текущий источник питания. Metal device query без allocations для модели.
Память: vm_stat, sysctl vm.swapusage и memory_pressure -Q, два снимка с интервалом не менее 60 секунд. Metal-проба до первого снимка, чтобы компиляция не вмешивалась в интервал. Паспорт имеет специальный минимум в два снимка; inference не проводится. Не меняем power/limits/ОС, не устанавливаем SDK и не загружаем веса.
Границы допуска: native arm64/M5 Max/128 GiB; Metal hasUnifiedMemory/device query; обнаруженный toolchain. Memory pressure и swap сравниваются по фактическому выводу. Рост swap/critical pressure — причина отложить smoke.
16 GiB OS reserve — политика, не измерение. Tentative ceiling 32 GiB для суммарных весов/runtime/state первой небольшой модели — управленческая эвристика; применим только при положительной памяти/Metal диагностике, не GPU allocation limit. gpu_budget_gib остаётся null до калибровки загрузкой в LAB30/31. Single allocation сверяем с maxBufferLength.
Timestamps снимков сохраняются; фоновые процессы не прекращаем и не меняем автоматически. Ограничения наблюдаемости и ошибки команд сохраняем явно.
Принятие: паспорт, два memory snapshots, tentative budget и admission/blocker LAB29/30/31. LAB01 оформляется отдельно.

Зарегистрирован: 2026-10-07T13:33:16.845Z
