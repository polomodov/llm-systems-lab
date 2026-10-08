# LAB01 — подготовка Apple-маршрута

Статус: выполнен обязательный минимум; решение проверяющего ещё не выставлено.

## Паспорт выполнения

- Дата: 07.10.2026; исполнитель — Codex по запросу владельца.
- Node: v24.19.0; git version 2.50.1 (Apple Git-155); GNU bash, version 3.2.57(1)-release (arm64-apple-darwin25).
- Commit: 8ef1cef6b2a9dfed69ee9c1c75e22ed6996e84e3. Дерево содержало новые отчёты; это отражено в provenance.
- Harness: claude-code, pinned профиль experiments/claude-code/harness.json.
- Агент/эпизод: a2-janitor / T002; run `2026-10-07-claude-code-a2-janitor-t002-repo-janitor`.
- API/модель не запускались; network/process isolation без Docker остаётся unverified.

## Гипотеза и протокол до запуска

Гипотеза: повторяемость seed и обнаружение мутации sealed inputs подтверждаются синтетическими тестами; workspace не содержит скрытые проверки и .env. Протокол — raw/protocol.md. Шаблон planned run создан до записи протокола после ошибки кодировки Python; prepare и тесты выполнены после регистрации. Ошибка исправлена явным UTF-8; результаты задним числом не регистрировались.

## Ход выполнения

Созданы новая сессия и planned run, зарегистрирован протокол, выполнен prepare. Проверены публичные manifests/prompt/network и verifyRunIntegrity. Выполнены setup/runtime tests, check до и после. Код задачи не исправлялся.

## Результаты

| Проверка | Наблюдение | Evidence |
| --- | --- | --- |
| Run после создания | planned | raw/new-run.txt |
| После prepare | prepared, verdict pending, execution_started_at null | raw/prepared-summary.json |
| Seed | a05e660e68b81d796b76878039c1642ca28ea76c | raw/prepared-summary.json |
| Manifest/workspace | 28 входных файлов, 22 workspace записи; forbidden paths 0 | raw/prepared-summary.json |
| Воспроизводимость | 14/14 setup tests; тест одинакового seed T002 прошёл | raw/setup-tests.txt |
| Мутация snapshots | 16/16 runtime tests; подмена manifest/inputs обнаруживается | raw/integrity-tests.txt |
| Docker | unverified, дополнительный опыт не выполнялся | manifest unavailable |

| Объект | Местоположение | Видимость для агента | Основание |
| --- | --- | --- | --- |
| Spec/контракт | sealed inputs, текст prompt | Через prompt | raw/prompt-inspection.json |
| Рабочий проект | workspace/sample → /workspace/sample | Чтение/запись | публичный manifest и метод |
| Артефакты | workspace/artifacts → /workspace/artifacts | Чтение/запись | prompt и инфраструктура |
| .env / hidden checks | За пределами workspace | Mount не предусмотрен; Docker здесь не проверен | manifest и публичная инфраструктура |
| run.json / trace | координатор results/runs | Mount не предусмотрен | инфраструктура; Docker unverified |
| Provider credential | Будущий environment harness | Доступен процессу harness/его shell при настоящем запуске | механизм не скрывает ключ от того же контейнера |
| Сеть | api.anthropic.com и registry.npmjs.org | Будущий task-scoped gateway | raw/network.json; реального исполнения нет |

## Ошибки и ограничения

Первая запись протокола не прошла из-за кодировки Python; ошибка произошла до prepare/tests. Шаблон planned record уже был создан, что указано честно. Docker smoke и модельное исполнение не выполнялись. Synthetic tests подтверждают инфраструктуру, не качество агента.

## Вывод по гипотезе

Данные поддерживают гипотезу подготовки: seed воспроизводим по тестам, мутации выявляются, открытый manifest не включает forbidden paths. LAB01 completed относится к учебной подготовке; run остаётся prepared без независимого verdict.

## Ответы на контрольные вопросы

1. Prepared/exit 0 подтверждают этап подготовки; pass требует исполнения задачи и независимого оценивания.
2. SHA фиксирует bytes manifest и позволяет обнаружить подмену; он не доказывает истинность исходных данных или корректность вывода модели.
3. Git index timestamps могут различаться при одинаковом дереве; сравниваются seed commit и содержательные hashes.
4. Отсутствие mount ограничивает доступ технически; текстовый запрет зависит от исполнения инструкции. На этой машине runtime mount ещё не проверен Docker.
5. Credential в окружении harness потенциально доступен shell-процессам того же контейнера; сильное разделение требует broker.

## Комплект сдачи

Отчёт, manifest, пустой TSV с объяснением, raw versions/status/check/test/inspection evidence и prepared run. Статусы модели и стоимости не придуманы. `reviewer_decision=null` до решения человека.
