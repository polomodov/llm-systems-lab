# Исправление cleanup после первого LAB34

В исходномcontroller resource monitor послал owned native child SIGINT, а shutdown повторно послал SIGINT, когда child ещё завершался. Log: cleaning up before exit → Received second interrupt → GGML_ASSERT([rsets->data count] == 0), native exit -6. Это ошибка lifecyclecontroller; нельзя объявлять её самопроизвольным падениемMetal/OOM во времяинференса. Исходные run_load-at-start.py,registered-source-hashes,log,telemetry,responses и failures сохраняются.

Исправленная версия хранит interrupt_sent и history, записывает guard-trigger; cleanup ждёт уже посланный SIGINT без повторения, затем применяет только заранее bounded SIGKILLfallback при30sdeadline. Новых model runs дляпроверкиэтойправки не было; её влияниенаactualnativeexitнеизвестно. Синтетическаяfixtureпроверяет отсутствиевторогоSIGINT.
