// Compare artifacts/normalized.json with the reference using canonical JSON (sorted keys).
// Usage: node compare.mjs <expected.json> <actual.json>; prints records=ok|differ rejected=ok|differ.
import { readFileSync } from 'node:fs';
const canonical = (value) => Array.isArray(value) ? `[${value.map(canonical).join(',')}]`
  : value && typeof value === 'object' ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
  : JSON.stringify(value);
const [expectedPath, actualPath] = process.argv.slice(2);
const expected = JSON.parse(readFileSync(expectedPath, 'utf8'));
let actual;
try { actual = JSON.parse(readFileSync(actualPath, 'utf8')); } catch (error) { console.log(`records=differ rejected=differ error=${error.code ?? error.name}`); process.exit(0); }
const same = key => Array.isArray(actual?.[key]) && canonical(actual[key]) === canonical(expected[key]);
if (!same('records')) {
  const got = new Map((actual?.records ?? []).map(r => [r?.id, canonical(r)]));
  for (const row of expected.records) if (got.get(row.id) !== canonical(row)) console.error(`  record differs or missing: ${row.id}`);
  for (const row of actual?.records ?? []) if (!expected.records.some(e => e.id === row?.id)) console.error(`  unexpected record: ${row?.id}`);
}
console.log(`records=${same('records') ? 'ok' : 'differ'} rejected=${same('rejected') ? 'ok' : 'differ'}`);
