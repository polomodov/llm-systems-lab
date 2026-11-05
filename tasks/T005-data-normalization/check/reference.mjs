// Эталонная реализация T005. Использование: node reference.mjs <workspace/data> — печатает ожидаемый normalized.json.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const dataDir = process.argv[2];
if (!dataDir) { console.error('usage: reference.mjs <data-dir>'); process.exit(64); }

const validDate = (y, m, d) => {
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d
    ? `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null;
};
const cents = (text) => {
  if (typeof text === 'number') return Number.isFinite(text) ? Math.round(text * 100) : null;
  if (typeof text !== 'string') return null;
  const cleaned = text.trim().replace(/^\$/, '').replace(/,(?=\d{3}(\D|$))/g, '').replace(',', '.');
  return /^\d+(\.\d+)?$/.test(cleaned) ? Math.round(Number(cleaned) * 100) : null;
};
const email = (value) => String(value).trim().toLowerCase();

// Простой CSV: поля в кавычках могут содержать запятые; переносов строк внутри полей нет.
const csvRow = (line) => {
  const out = []; let field = ''; let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { out.push(field); field = ''; }
    else field += ch;
  }
  out.push(field);
  return out;
};
const lines = (text) => text.split(/\r?\n/).filter(line => line.trim() !== '');

// Каждая запись приводится к {id, email, date|null, amount_cents|null, currency}.
const fromA = lines(readFileSync(join(dataDir, 'orders_a.csv'), 'utf8')).slice(1).map(csvRow).map(([id, mail, date, amount, currency]) => {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(date.trim());
  return { id: id.trim(), email: email(mail), date: m ? validDate(+m[3], +m[2], +m[1]) : null, amount_cents: cents(amount), currency: currency.trim() };
});
const fromB = lines(readFileSync(join(dataDir, 'orders_b.tsv'), 'utf8')).slice(1).map(line => line.split('\t')).map(([id, mail, date, price]) => {
  const m = /^(\d{4})\/(\d{2})\/(\d{2})$/.exec(date.trim());
  return { id: id.trim(), email: email(mail), date: m ? validDate(+m[1], +m[2], +m[3]) : null, amount_cents: /^\$/.test(price.trim()) ? cents(price) : null, currency: 'USD' };
});
const fromC = JSON.parse(readFileSync(join(dataDir, 'orders_c.json'), 'utf8')).map(record => {
  const stamp = Date.parse(record.created);
  return { id: String(record.order_id).trim(), email: email(record.customer_email), date: Number.isNaN(stamp) ? null : new Date(stamp).toISOString().slice(0, 10), amount_cents: cents(record.total), currency: record.currency };
});

const records = []; const rejected = []; const seen = new Set();
for (const row of [...fromA, ...fromB, ...fromC]) {
  if (row.date === null) { rejected.push({ id: row.id, reason: 'invalid_date' }); continue; }
  if (row.amount_cents === null) { rejected.push({ id: row.id, reason: 'invalid_amount' }); continue; }
  if (seen.has(row.id)) continue;
  seen.add(row.id);
  records.push({ id: row.id, email: row.email, date: row.date, amount_cents: row.amount_cents, currency: row.currency });
}
const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
records.sort(byId); rejected.sort(byId);
process.stdout.write(JSON.stringify({ records, rejected }, null, 2) + '\n');
