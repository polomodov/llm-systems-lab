# Заметки · Pi (pi-mono)

Независимо оценённых завершённых прогонов пока нет.

21.09.2026 — offline сверка собранного образа на машине оператора (Docker Engine 29.5.2, host darwin/arm64), без ключей и без запросов к провайдеру: `pi --version` в read-only контейнере вернула ровно закреплённый пин 0.73.1. Идентификатор проверенного локального образа: `sha256:524a101a8e20cee137cf236ad0651b105a3b3ffee60ad3f53e5ad20d39e297e4`. Пересборка может дать другой ID; для серии сохраняют один образ. Это проверка установки, не результат задачи.

10.10.2026 — [LAB08 native requalification](../local-models/measurements/LAB08-apple-native-requalification-20261010/report.md): новая8Kshort4/4; настоящий T0028K aborted/error8265>8192. Первая16Kshort4/4HTTP не допущена из-заfree+spec7.785<8GiB; исправлено сохранение первой причиныguard. После120s stablepreflight отдельный16Kshort4/4/cleanup0. Новыйrun `2026-10-10-pi-a2-janitor-t002-repo-janitor-2`:16turns/244s/exit0/**length**,16HTTPresponses; awaiting_review, verdictpending. ПолныйLAB08/LAB09допуск отсутствует. Никакие aborted не переписаны.
