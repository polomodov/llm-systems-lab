# Новая попытка после failed readiness

Первый настоящий run 2026-10-09-pi-a2-janitor-t002-repo-janitor остаётся aborted: native server и все pins/props прошли, но fetch readiness на 127.0.0.1 с ручным Host не прошёл строгую проверку broker. Agent container ещё не запускался, HTTP inference requests отсутствуют; native exit 0 / один SIGINT. Execution.started_at относится к началу инфраструктурного исполнения, не к первой модели в агенте.

В новом snapshot readiness использует реальное имя egress:8080, то же, что SDK. Проверка включена в Docker regression, которая прошла. Новый run ID и новая source registration создаются до повторного native старта. Архив первого run не переподготавливается и не перезаписывается. Compare дополнительно разделяет запечатанные исходники bridge/адаптера, чтобы изменения policy не смешивались прежним alias.
