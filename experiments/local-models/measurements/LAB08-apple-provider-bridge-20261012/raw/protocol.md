# LAB08 Apple — повтор после wall/stale guards

Зарегистрировано 2026-10-12T12:38:00.808119Z до исполнения. Исходная серия 20261009 сохраняется.

Условия: Pi 0.73.1/T002, Qwen3.5-9B Q6_K, native llama.cpp b8407+tile16/Metal, context8192/output2048, reasoning auto, temperature0/seed1, один слот, cache off. Deployment скопирован из прежней серии; путь аппаратного паспорта перенесён в текущий checkout с сохранением bytes/SHA256.

План: offline B01–B10 и Docker boundary; нативный startup/identity/chat/cleanup и отдельный stale guard с паузой координатора 16s; затем один новый T002 pilot timeout900s/budget observed/30turns/$2 по контракту. Синтетический сбой часов уже покрыт unit test, системные часы не меняются. При отказе квалификации pilot не запускается. Никаких автоматических retry или смены deployment.

Допуск: guard при возобновлении отвергает запрос, cleanup own PID; AC, swap0, pressure1, RSS<24GiB; foreign models отсутствуют. Независимая hidden оценка выполняется отдельно оператором; исполнитель скрытые проверки не читает.
