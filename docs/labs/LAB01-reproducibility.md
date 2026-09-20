# ЛР 01. Воспроизводимый эпизод и границы эксперимента

## Паспорт

| Параметр | Условие |
| --- | --- |
| Время оператора | 1–2 часа |
| Предыдущие работы | Нет |
| Среда | Node.js ≥22, Git, Bash; GPU не нужен |
| Готовность | Выполняется текущими командами репозитория |
| Минимальный объём | Одна подготовленная T002 и две проверки подготовки/целостности на синтетических fixtures |
| Расширение | Отдельный Docker isolation smoke; подготовка второго harness |

## Цель

Научиться создавать воспроизводимый эпизод, отличать его подготовку от выполнения задачи и проверить, какие данные видит агент. Результат — подготовленный run record и объяснённая граница между входами, workspace, trace и независимой оценкой.

## Проверяемая гипотеза

«Повторная подготовка одной и той же задачи сохраняет начальное содержимое, а изменение запечатанных входов обнаруживается до исполнения». Отдельное требование границы: скрытые проверки и `.env` не находятся в agent workspace. Не проверяйте его чтением реальных hidden checks; используйте исходный manifest и синтетические тесты.

## Подготовка

1. Откройте корень репозитория. Никаких ключей API для этой работы не требуется.
2. Прочитайте [метод](../method.md), [описание записей](../../results/README.md), открытый [контракт T002](../../tasks/T002-repo-janitor/task.md) и [спецификацию A2](../../agents/a2-janitor/spec.md). Не открывайте каталог `check`.
3. Создайте отчёт:

```bash
npm run lab:new -- --lab LAB01 --session first-pass
LAB_DIR='experiments/local-models/measurements/LAB01-first-pass'
node --version > "$LAB_DIR/raw/node-version.txt"
git --version > "$LAB_DIR/raw/git-version.txt"
bash --version > "$LAB_DIR/raw/bash-version.txt"
```

Если папка уже существует, выберите новый session ID. Во всех последующих командах используйте путь созданной папки. Не затирайте raw логи при повторе опыта.

## Порядок выполнения

1. **До запуска** заполните гипотезу и протокол в `report.md`: будет исследоваться подготовка, без обращения к модели. Укажите текущий commit и факт изменённого дерева:

```bash
git rev-parse HEAD > "$LAB_DIR/raw/revision.txt"
git status --short > "$LAB_DIR/raw/status.txt"
npm run harnesses > "$LAB_DIR/raw/harnesses.txt"
npm run check > "$LAB_DIR/raw/check-before.txt" 2>&1
```

2. **Создайте один новый эпизод**, выбрав реализованный harness:

```bash
npm run new-run -- --harness claude-code --agent a2-janitor --task T002
```

В выводе будет путь `results/runs/<run-id>/run.json`. Скопируйте именно его идентификатор в следующую переменную. Это ручная подстановка из фактического вывода; не используйте строку-заполнитель буквально.

```bash
RUN_ID='<run-id из предыдущей команды>'
test -f "results/runs/$RUN_ID/run.json"
npm run prepare-run -- --run "$RUN_ID" > "$LAB_DIR/raw/prepare.txt" 2>&1
```

Если `test -f` не завершился успешно, исправьте переменную до следующего шага. В `manifest.json` учебного отчёта добавьте полученный ID в `run_ids`. Не изменяйте экспериментальный `run.json` вручную.

3. **Проверьте состояние и состав снимка**, читая только известные открытые файлы. Команда не обращается к hidden checks:

```bash
node --input-type=module - "$RUN_ID" <<'NODE' > "$LAB_DIR/raw/prepared-summary.json"
import { readFileSync } from 'node:fs';
const id = process.argv[2];
const record = JSON.parse(readFileSync(`results/runs/${id}/run.json`, 'utf8'));
const manifest = JSON.parse(readFileSync(`results/runs/${id}/inputs/manifest.json`, 'utf8'));
const forbidden = manifest.workspace.filter(x => /(^|\/)(check|\.env)(\/|$)/.test(x.path));
console.log(JSON.stringify({
  run_id: id, status: record.status, seed_commit: manifest.seed_commit,
  source_mode: manifest.source_mode, input_files: manifest.files.length,
  workspace_files: manifest.workspace.length, forbidden_workspace_paths: forbidden
}, null, 2));
if (record.status !== 'prepared' || forbidden.length) process.exitCode = 1;
NODE
```

Ожидаемый структурный результат — `prepared`, непустой `seed_commit`, отсутствие forbidden paths. Это ожидаемое условие задания, не готовый результат вашей сессии. Сравните `inputs/control/prompt.txt` с открытой спецификацией/контрактом и выпишите, где агент должен работать и сохранять артефакты. Не запускайте команды из task prompt самостоятельно для исправления задачи.

4. **Проверьте гипотезу на синтетических fixtures**. Не портите реальный подготовленный run ради демонстрации. Эти тесты создают собственные временные эпизоды:

```bash
node --test tests/setup.test.mjs > "$LAB_DIR/raw/setup-tests.txt" 2>&1
node --test tests/runtime.test.mjs > "$LAB_DIR/raw/integrity-tests.txt" 2>&1
```

В первом логе найдите проверку одинакового начального Git commit, во втором — обнаружение мутации запечатанного входа/manifest. Запишите названия тестов и фактический результат. Если тест упал, прочитайте ошибку и сохраните её; не меняйте task contract или проверки, чтобы получить зелёный результат.

5. **Опишите границу наблюдаемости.** По [общей инфраструктуре](../../experiments/common/README.md) и `inputs/control/network.json` заполните таблицу ниже: что смонтировано/разрешено, где лежат `.env`, hidden checks, run.json и trace. Подготовка доказывает состав файлов; сетевую/процессную границу без Docker теста считать `unverified`.

6. **Завершите структурную проверку**:

```bash
npm run check > "$LAB_DIR/raw/check-after.txt" 2>&1
```

Run остаётся `prepared`; не переводите его в `completed`, поскольку модель не запускалась и независимого verdict нет. Учебную ЛР01 можно завершить после её критериев. Добавьте в вывод, почему эти два статуса различаются.

7. **Расширенное задание:** если Docker Engine и локальный `node:24.13.1-bookworm-slim` доступны, выполните `npm run test:docker > "$LAB_DIR/raw/docker-tests.txt" 2>&1`. Сохраните version/image сведения и результат; этот smoke не вызывает модель. Можно подготовить отдельный T002 для `opencode` и сопоставить открытые manifests, сохранив оба run ID. Состав `.git` с timestamps не обязан совпасть побайтно; сравнивайте исходный commit и содержательные файлы по методу.

## Таблицы результатов

| Проверка | Ожидаемое условие | Наблюдение | Raw evidence |
| --- | --- | --- | --- |
| Начальное состояние run | `planned` до prepare | — | — |
| После prepare | `prepared`, без verdict pass | — | — |
| Начальное Git дерево T002 | Повторяемый seed commit | — | — |
| Запечатанные входы | Мутация обнаруживается тестом | — | — |
| Workspace | Нет check/.env | — | — |
| Docker isolation, расширение | Синтетический тест проходит либо причина недоступности | — | — |

| Объект | Где находится | Видит ли агент | Основание / ограничение проверки |
| --- | --- | --- | --- |
| Контракт/spec | — | — | — |
| Рабочие файлы T002 | — | — | — |
| `.env`, hidden checks | — | — | — |
| `run.json`, trace | — | — | — |
| API credential в окружении harness | — | — | — |

## Что сдать

`report.md` с обеими таблицами и ответами; учебный `manifest.json` со ссылкой на run ID; `raw/` с версиями, состоянием дерева, выводом prepare, summary, тестами и двумя check. Реальный prepared run оставить в `results/runs/<run-id>/` вместе с входами. `measurements.tsv` может остаться без строк: объясните, что проверялась целостность, а не производительность модели.

## Критерии завершения

- [ ] Новый эпизод создан без перезаписи существующего и находится в `prepared`.
- [ ] Приложены run ID, seed commit, результаты проверки manifest и обеих серий тестов.
- [ ] Отсутствие hidden checks подтверждено без чтения их содержимого.
- [ ] Разделены проверка подготовки и необязательный Docker smoke.
- [ ] Учебный вывод не содержит выдуманного качества модели, tokens/s или стоимости.
- [ ] `npm run check` проходит; отчёт и вопросы заполнены.

## Контрольные вопросы

1. Почему `prepared` и exit 0 не равны `pass` задачи?
2. Что фиксирует SHA-256 manifest и чего он не доказывает?
3. Почему timestamps `.git/index` не подходят для сравнения содержания эпизода?
4. Чем отсутствие mount отличается от текстового запрета агенту читать файл?
5. Какое ограничение остаётся, если ключ API находится в окружении harness?

## Источники

[Метод эксперимента](../method.md), [жизненный цикл записей](../../results/README.md), [общая инфраструктура](../../experiments/common/README.md), открытые [T002](../../tasks/T002-repo-janitor/task.md) и [A2](../../agents/a2-janitor/spec.md). Исходники команд: [new-run](../../scripts/new-run.mjs), [prepare-run](../../scripts/prepare-run.mjs).
