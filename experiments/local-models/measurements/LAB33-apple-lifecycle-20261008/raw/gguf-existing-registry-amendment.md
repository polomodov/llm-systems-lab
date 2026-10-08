# Подготовка GGUF: новый namespace после отказа повторного import

Начальный lms-metal-startup отказал: registry destination уже существует. Модель не загружалась. Отказ/cleanup/not-run сохраняются. До повторения зарегистрирован lms-metal-existing: вместо повторного import проверяются существующая symlink target и exact GGUF SHA256; inference/runtime/8K/parallel1/params/resource thresholds неизменны. Исходный controller сохранён. Успех нового namespace не заменяет прежний failure.
