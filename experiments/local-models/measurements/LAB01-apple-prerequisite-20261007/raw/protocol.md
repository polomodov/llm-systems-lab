# Предварительный протокол LAB01

Объект: подготовка T002/a2-janitor с pinned claude-code; модель не запускается.
Гипотеза: повторная подготовка воспроизводима, мутация sealed inputs обнаруживается, manifest workspace не включает hidden checks или .env.
Действия: подготовка уже созданного planned record, чтение открытого manifest/prompt/network; tests/setup.test.mjs и tests/runtime.test.mjs; check до/после. Docker smoke необязателен и в минимуме не планируется.
Шаблон planned record создан до регистрации протокола, но prepare/измерения/модель ещё не запускались. Первая попытка записи протокола завершилась ошибкой кодировки Python, без записи файла.
При ошибке сохраняем exit/status и причину, не меняем task/hidden checks. Run останется prepared и без независимого verdict.

Зарегистрирован: 2026-10-07T13:33:16.845Z
