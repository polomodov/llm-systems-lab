# Поправка после настоящего overflow8K

Новая попытка8K остаётся aborted/error: 22-й prompt8265>8192, сохранён HTTP400. 21 полный ответ,146samples/gap≤2.161s, cleanup0/одинSIGINT. Расширение до16K — другое условие, не исправление старого run. Основа допуска: LAB32-apple-qwen35-9b-metal-auto-20261007, unrestricted-auto16K прошёл.

Перед новым pilot короткий native16K warmup+3 по qualify16.mjs; те же sampling/reasoning/output/slot/native source pins/guards. Меняется только context_tokens16384. После короткого pass новыйrun, prepare/seal; timeout900/observed budget. Отказ сохранится, автоматического перехода32K нет. Независимый judge остаётся необходим для pass, новые hardware labs независимы.
