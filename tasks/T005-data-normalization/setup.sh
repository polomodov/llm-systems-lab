#!/usr/bin/env bash
# Создаёт стартовое состояние T005 в каталоге $1: data/ с тремя выгрузками и brief.md.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo 'usage: setup.sh <dest>' >&2
  exit 64
fi
node --input-type=module - "$1" <<'JS'
import { lstatSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const destination = process.argv[2];
if (!destination.trim()) throw new Error('Нужен явный непустой путь рабочего каталога.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Отказ перезаписывать непустой каталог, файл или ссылку: ${dest}`);
}

// Данные зафиксированы: никакой случайности, одинаковый байтовый состав при каждом запуске.
const ordersA = [
  'id,email,date,amount,currency',
  'ORD-1001,anna@example.com,03.01.2026,"1250,00",RUB',
  'ORD-1002,boris.k@example.org,05.01.2026,"99,90",RUB',
  'ORD-1003,Clara@Example.com,07.01.2026,"15000,50",RUB',
  'ORD-1004,dmitry@example.net,31.02.2026,"500,00",RUB',
  'ORD-1005,elena@example.com,12.01.2026,"3200,00",RUB',
  'ORD-1006,farid@example.org,15.01.2026,"780,25",RUB',
  'ORD-1007,galina@example.com,20.01.2026,"12,00",RUB',
  'ORD-1008,hamid@example.net,22.01.2026,"4999,99",RUB',
  'ORD-1009,irina@example.com,25.01.2026,"60,00",RUB',
  'ORD-1010,ivan@example.org,28.01.2026,"2100,00",RUB',
  'ORD-1011,julia@example.com,30.01.2026,"845,10",RUB',
  '',
].join('\n');

const ordersB = [
  ['order_id', 'customer', 'ordered_on', 'price'],
  ['ORD-1002', 'Boris.K@example.org ', '2026/01/05', '$89.90'],
  ['ORD-1012', 'Kirill@Example.COM  ', '2026/02/01', '$1,234.50'],
  ['ORD-1013', 'lena@example.org ', '2026/02/03', '$45.00'],
  ['ORD-1014', 'mark@example.net', '2026/02/04', '$2,000.00'],
  ['ORD-1015', 'nina@example.com', '2026/02/06', 'n/a'],
  ['ORD-1016', 'oleg@example.org', '2026/02/08', '$10,500.75'],
  ['ORD-1007', 'Galina@example.com', '2026/01/20', '$0.15'],
  ['ORD-1017', 'pavel@example.com', '2026/02/10', '$300.00'],
  ['ORD-1018', 'Rita@example.net ', '2026/02/12', '$75.25'],
  ['ORD-1019', 'sergey@example.org', '2026/02/14', '$1,999.99'],
  ['ORD-1020', 'tanya@example.com', '2026/02/15', '$12.00'],
].map(row => row.join('\t')).join('\n') + '\n';

const ordersC = JSON.stringify([
  { order_id: 'ORD-1012', customer_email: 'kirill@example.com', total: 1234.5, created: '2026-02-01T10:00:00Z', currency: 'USD' },
  { order_id: 'ORD-1021', customer_email: 'ulyana@example.com', total: 410.5, created: '2026-03-01T23:30:00+03:00', currency: 'RUB' },
  { order_id: 'ORD-1022', customer_email: 'VIKTOR@example.org', total: 15.99, created: '2026-03-02T01:00:00+05:00', currency: 'USD' },
  { order_id: 'ORD-1023', customer_email: 'wera@example.net', total: null, created: '2026-03-03T10:00:00Z', currency: 'RUB' },
  { order_id: 'ORD-1024', customer_email: 'yana@example.com', total: 2500, created: '2026-03-04T00:00:00Z', currency: 'RUB' },
  { order_id: 'ORD-1025', customer_email: 'zahar@example.org', total: 99.99, created: '2026-03-05T12:00:00-07:00', currency: 'USD' },
  { order_id: 'ORD-1026', customer_email: 'anna@example.com', total: 120, created: '2026-03-05T22:00:00-05:00', currency: 'USD' },
  { order_id: 'ORD-1010', customer_email: 'ivan@example.org', total: 2100, created: '2026-01-28T09:00:00+03:00', currency: 'RUB' },
  { order_id: 'ORD-1027', customer_email: 'boris.k@example.org', total: 7.5, created: '2026-03-07T08:15:00+00:00', currency: 'RUB' },
  { order_id: 'ORD-1028', customer_email: ' clara@example.com ', total: 64, created: '2026-03-08T18:45:30+02:00', currency: 'USD' },
], null, 2) + '\n';

const brief = `# Нормализация заказов из трёх выгрузок

В каталоге data/ три выгрузки одного и того же вида записей (заказы) из разных систем:
- \`orders_a.csv\` — CSV через запятую, с заголовком \`id,email,date,amount,currency\`; даты \`DD.MM.YYYY\`;
  сумма с десятичной запятой в кавычках (\`"1250,00"\`); валюта в колонке \`currency\`.
- \`orders_b.tsv\` — TSV с заголовком \`order_id, customer, ordered_on, price\`; даты \`YYYY/MM/DD\`;
  сумма со знаком \`$\` и разделителем тысяч (\`$1,234.50\`) — валюта всегда USD; в e-mail встречаются
  хвостовые пробелы и смешанный регистр.
- \`orders_c.json\` — массив объектов \`{order_id, customer_email, total, created, currency}\`; \`total\` — число
  в основных единицах валюты или \`null\`; \`created\` — ISO 8601 с часовым поясом.

Данные только читать. Записывать только в artifacts/. Сторонние пакеты не нужны и не допускаются.

## Целевая схема

\`artifacts/normalized.json\`:
\`\`\`
{
  "records": [ { "id": string, "email": string, "date": "YYYY-MM-DD", "amount_cents": integer, "currency": "RUB" | "USD" } ],
  "rejected": [ { "id": string, "reason": "invalid_date" | "invalid_amount" } ]
}
\`\`\`
Правила:
1. \`id\` — идентификатор заказа как есть (\`ORD-1001\`). \`email\` — обрезаны пробелы по краям, приведён к нижнему регистру.
2. \`date\` — календарная дата. Для \`orders_c.json\` момент переводится в UTC и берётся дата в UTC
   (\`2026-03-02T01:00:00+05:00\` → \`2026-03-01\`). Несуществующая дата (например, 31 февраля) — отклонение \`invalid_date\`.
3. \`amount_cents\` — целое число минимальных единиц: сумма × 100 с округлением до ближайшего целого.
   Сумма, которую нельзя разобрать как число (\`n/a\`), и \`null\` — отклонение \`invalid_amount\`.
4. \`currency\` — \`RUB\` или \`USD\`: из колонки \`currency\` (a, c) или \`USD\` по знаку \`$\` (b).
5. Дубликаты — записи с одинаковым \`id\` в разных файлах. Остаётся первое вхождение в порядке файлов a → b → c;
   остальные отбрасываются молча (не попадают ни в records, ни в rejected). Отклонённая запись в разрешении
   дубликатов не участвует. Внутри одного файла дубликатов нет.
6. Отклонённые записи в \`records\` не попадают; у каждой ровно одна причина (первая проверка — дата, затем сумма).
7. \`records\` и \`rejected\` отсортированы по \`id\` как строке (возрастание). Ключи объектов — ровно перечисленные.

\`artifacts/report.md\`: по каждому файлу — сколько записей прочитано, принято, отброшено как дубликат, отклонено;
отдельный список отклонений с \`id\` и причиной; принятые решения.
`;

mkdirSync(join(dest, 'artifacts'), { recursive: true });
mkdirSync(join(dest, 'data'), { recursive: true });
writeFileSync(join(dest, 'data', 'orders_a.csv'), ordersA);
writeFileSync(join(dest, 'data', 'orders_b.tsv'), ordersB);
writeFileSync(join(dest, 'data', 'orders_c.json'), ordersC);
writeFileSync(join(dest, 'brief.md'), brief);
console.log(`[T005] workspace ready in ${dest}`);
JS
