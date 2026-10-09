# Дополнение контракта до native pilot

Первая Docker-проверка установила: контейнер только в internal network не публикует port 8081 (`docker port`: no public port). Исходный вывод сохранён в docker-local-initial-failed.txt; GPU и реальные задачи ещё не запускались.

Broker теперь имеет default bridge и отдельную internal сеть агента, как существующий egress gateway. Агент по-прежнему имеет только internal сеть, DNS отключён, CAP_DROP=ALL, нет host networking/Docker socket. Broker не выполняет CONNECT, не выбирает upstream и не открывает внешние sockets; HTTP control port опубликован только на loopback host. Его API требует одноразовую capability, отсутствующую в task container и sealed files. Host-worker инициирует reverse connection и единолично пересылает фиксированный запрос на loopback inference server. Эта корректировка не разрешает прямую сеть агенту. Реальные проверки direct LAN/cloud и запрета control API повторяются перед native pilot.
