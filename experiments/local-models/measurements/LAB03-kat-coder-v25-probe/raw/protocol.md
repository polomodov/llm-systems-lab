# LAB03 — предварительный протокол (kat-coder-v25)

## Гипотеза
Локальная копия артефакта bartowski/Kwaipilot_KAT-Coder-V2.5-Dev-GGUF@d8f684f08d2950ea9d2db6a35ef7dada0707858b совпадает с публикацией по размеру и SHA-256.

## Порядок
1. Скачать с закреплённой ревизии `fetch_artifact.py --download`.
2. Offline-проверка размеров и SHA-256.
3. Записать checksum-файл для LAB04/LAB05.

## Критерий остановки
Расхождение размера/SHA → `fail`/`no-artifact`; артефакт дальше не передаётся.
