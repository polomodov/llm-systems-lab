#!/usr/bin/env bash
# Создаёт стартовое состояние T004 в каталоге $1/sample.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo 'usage: setup.sh <dest>' >&2
  exit 64
fi
WORKSPACE=$(node --input-type=module - "$1" <<'JS'
import { lstatSync, mkdirSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
const destination = process.argv[2];
if (!destination.trim()) throw new Error('Нужен явный непустой путь рабочего каталога.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Отказ перезаписывать непустой каталог, файл или ссылку: ${dest}`);
}
mkdirSync(join(dest, 'artifacts'), { recursive: true });
console.log(dest);
JS
)
DEST="$WORKSPACE/sample"
umask 022
mkdir -p "$DEST/src" "$DEST/test"
cat > "$DEST/package.json" <<'EOF'
{
  "name": "duration-sample",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "test": "node --test test/*.test.js"
  }
}
EOF
cat > "$DEST/src/duration.js" <<'EOF'
// Разбор и форматирование длительностей. Спецификация — в brief.md.

/**
 * Разбирает строку вида "1h 30m" в целое число миллисекунд.
 * @param {string} text
 * @returns {number}
 */
export function parseDuration(text) {
  throw new Error("not implemented");
}

/**
 * Форматирует целое число миллисекунд в строку вида "1h 30m".
 * @param {number} ms
 * @returns {string}
 */
export function formatDuration(ms) {
  throw new Error("not implemented");
}
EOF
cat > "$DEST/test/duration.test.js" <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseDuration, formatDuration } from "../src/duration.js";

test("parses hours and minutes without spaces", () => assert.equal(parseDuration("1h30m"), 5400000));
test("parses seconds", () => assert.equal(parseDuration("45s"), 45000));
test("parses days", () => assert.equal(parseDuration("2d"), 172800000));
test("parses zero", () => assert.equal(parseDuration("0ms"), 0));
test("formats hours and minutes", () => assert.equal(formatDuration(5400000), "1h 30m"));
test("round trip keeps the value", () => assert.equal(parseDuration(formatDuration(93784005)), 93784005));
EOF
cat > "$DEST/brief.md" <<'EOF'
# Длительности для duration-sample

Проверка: `npm test` в каталоге sample/. Реализовать `parseDuration` и `formatDuration` в `src/duration.js`
по спецификации ниже. Видимые тесты в `test/` покрывают только базовые случаи; скрытая проверка — всю спецификацию.
Запрещено: удалять или ослаблять тесты, менять имена и сигнатуры экспортов, добавлять зависимости.
Ветка исходного состояния: main; рабочая ветка: feature/<run-id>.
Отчёт: ../artifacts/report.md относительно sample/ (artifacts/report.md в корне workspace) — что реализовано,
какие решения приняты по спорным местам, какие тесты добавлены.

## Спецификация

### `parseDuration(text) -> number`
1. Вход — строка; любой другой тип (число, `null`, `undefined`, объект) — `TypeError`.
2. Строка состоит из одного или нескольких компонентов `<число><единица>`. Единицы: `d` (сутки, 86 400 000 мс),
   `h` (час, 3 600 000 мс), `m` (минута, 60 000 мс), `s` (секунда, 1 000 мс), `ms` (миллисекунда).
3. Единицы нечувствительны к регистру: `1H 30M`, `2MS` допустимы.
4. Пробелы (включая табуляции) допустимы в начале, в конце и между компонентами: `"1h 30m"`, `" 90m "`, `"1h30m"` равнозначны.
   Пробел между числом и единицей (`"1 h"`) недопустим — `TypeError`.
5. Число — неотрицательное целое из десятичных цифр. Знак минус (`"-5s"`), знак плюс, дробная часть (`"1.5h"`, `"1,5h"`),
   экспонента — `TypeError`. Ведущие нули допустимы (`"007s"` = 7000).
6. Каждая единица встречается не более одного раза: `"1h1h"` — `TypeError`. Порядок компонентов любой: `"30m 1h"` = 5 400 000.
7. Пустая строка, строка из одних пробелов, число без единицы (`"90"`), неизвестная единица (`"3w"`, `"5 sec"`),
   любой посторонний текст — `TypeError`.
8. Результат — сумма компонентов в миллисекундах, целое число. Переполнение не рассматривается: вход не превышает 2^53 - 1 мс.

### `formatDuration(ms) -> string`
1. Вход — конечное неотрицательное целое число (`Number.isInteger`). Отрицательное, дробное, `NaN`, `Infinity`,
   строка, `bigint` — `TypeError`.
2. Значение раскладывается жадно по единицам в порядке `d`, `h`, `m`, `s`, `ms`.
3. Нулевые компоненты опускаются; компоненты разделяются одним пробелом; порядок всегда `d h m s ms`.
   Примеры: `5400000` → `"1h 30m"`, `86400000` → `"1d"`, `1500` → `"1s 500ms"`, `93784005` → `"1d 2h 3m 4s 5ms"`.
4. `ms` выводится только при ненулевом остатке миллисекунд.
5. Ноль форматируется как `"0ms"`.
6. Для любого допустимого `ms` выполняется `parseDuration(formatDuration(ms)) === ms`.
EOF
(
  cd "$DEST"
  # Не наследовать шаблоны, hooks, подписи и настройки окончания строк оператора.
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
  export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=0
  export GIT_AUTHOR_DATE=2026-09-19T00:00:00Z GIT_COMMITTER_DATE=2026-09-19T00:00:00Z
  export GIT_AUTHOR_NAME=setup GIT_AUTHOR_EMAIL=setup@example.com
  export GIT_COMMITTER_NAME=setup GIT_COMMITTER_EMAIL=setup@example.com
  git -c init.templateDir= init -q --initial-branch=main
  git -c core.autocrlf=false add -A
  git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm "T004 start state"
)
echo "[T004] workspace ready in $DEST"
