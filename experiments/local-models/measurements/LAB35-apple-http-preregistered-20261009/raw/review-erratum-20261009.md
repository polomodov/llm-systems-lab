# Review correction: tensor bundled dylib pins

Замечание PR26: исходный tensor build-reference и variants содержали лишь llama-server/llama-bench. LAB35 startup не проверил связанные dylibs перед модельным исполнением. Исходная standard ветвь включала library hashes; в tensor первичном startup-process осталось только два executable pins.

Сохранены byte-for-byte оригиналы registered-source-hashes.json, variants.json, metal-tensor/build-reference.json, run_qualification.py, exporter/report generator/summary с суффиксом .before-review-20261009; исходный report.md также сохранён. Raw requests/responses/process/runtime/telemetry не переписываются. Протокол и commit00de4f7 относятся к исходной регистрации, не к новым hashes.

Исправленная forward-регистрация содержит23tensorentries: два executables и21dylibpaths (семь семейств, versioned files + linker aliases). Hashes взяты из сохранённой LAB30 binaries.sha256 от07.10 и сверены с нынешними файлами. Read-only otool dependency capture сохранён в tensor-library-review-verification.json. Системные frameworks относятся к recorded macOS/SDK; их shared cache не копируется.

Новый startup требует канонические bundled библиотеки и pins для всех *.dylib в build/bin, затем проверяет каждый SHA до Popen. Missing/changed/new unpinned library отказывает допуску. Offline exporter проверяет и исправленную forward source registry, и исходную execution registry через сохранённые byte backups. Execution-time library identity берётся только из первичного startup-process record.

Все16HTTPслучаев остаются успешными наблюдениями. Однако tensor libraries_verified_at_execution=false и qualification_completed=false: post-review hash match не доказывает загруженный library code во время прошлой серии. Для полного tensor fingerprint допуска требуется новая отдельная preregistered серия. Standard HTTP qualification и её recorded library pins остаются подтверждёнными. LAB35 по-прежнему blocked также по Ryzen access и LAB08/LAB09.
