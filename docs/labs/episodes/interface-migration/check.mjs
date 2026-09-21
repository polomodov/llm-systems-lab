import assert from 'node:assert/strict';
import { createFixtureApi } from './fixture-api.mjs';
import { loadInvoices } from './src/api.mjs';
import { buildReport } from './src/report.mjs';

const expected = [{ id: '0007', amountMinor: 1299, currency: 'RUB' }, { id: '0100', amountMinor: 201, currency: 'RUB' }];
const cases = [
  ['result-is-array', async () => {
    const api = createFixtureApi();
    assert.ok(Array.isArray(await loadInvoices(api.fetchPage)));
  }],
  ['load-all-pages-and-map', async () => {
    const api = createFixtureApi();
    assert.deepEqual(await loadInvoices(api.fetchPage), expected);
    assert.deepEqual(api.calls, [null, 'empty', 'last']);
  }],
  ['report-consumes-v2', async () => {
    assert.deepEqual(await buildReport(async () => structuredClone(expected), async () => { throw new Error('Unused'); }), {
      invoiceIds: ['0007', '0100'], count: 2, totalMinor: 1500, currency: 'RUB'
    });
  }],
  ['reject-cursor-cycle', async () => {
    const api = createFixtureApi({ cycle: true });
    await assert.rejects(() => loadInvoices(api.fetchPage), error => error.message !== 'Fixture call guard exceeded');
    assert.ok(api.calls.length <= 3, 'Cycle must be caught before repeating a page');
  }]
];
const observations = [];
for (const [name, check] of cases) {
  try { await check(); observations.push({ name, pass: true }); }
  catch (error) { observations.push({ name, pass: false, reason: error.message }); }
}
const passed = observations.filter(item => item.pass).length;
console.log(JSON.stringify({ kind: 'public-training-check', observations, passed, failed: cases.length - passed }, null, 2));
process.exitCode = passed === cases.length ? 0 : 1;
