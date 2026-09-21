import assert from 'node:assert/strict';
import { checkout } from './src/checkout.mjs';
import { reserve } from './src/inventory.mjs';

const cases = [
  ['valid-single', () => {
    const stock = { pen: 5 };
    assert.deepEqual(checkout([{ sku: ' pen ', quantity: 2 }], stock), { items: [{ sku: 'pen', quantity: 2 }] });
    assert.deepEqual(stock, { pen: 3 });
  }],
  ['reject-zero', () => {
    const stock = { pen: 5 };
    assert.throws(() => checkout([{ sku: 'pen', quantity: 0 }], stock));
    assert.deepEqual(stock, { pen: 5 });
  }],
  ['merge-duplicates', () => {
    const stock = { pen: 5, ink: 4 };
    assert.deepEqual(checkout([{ sku: ' pen ', quantity: 1 }, { sku: 'ink', quantity: 1 }, { sku: 'pen', quantity: 2 }], stock), {
      items: [{ sku: 'pen', quantity: 3 }, { sku: 'ink', quantity: 1 }]
    });
    assert.deepEqual(stock, { pen: 2, ink: 3 });
  }],
  ['duplicate-shortage-is-atomic', () => {
    const stock = { pen: 5, ink: 4 };
    assert.throws(() => checkout([{ sku: 'pen', quantity: 3 }, { sku: ' pen ', quantity: 3 }], stock));
    assert.deepEqual(stock, { pen: 5, ink: 4 });
  }],
  ['direct-reserve-is-atomic', () => {
    const stock = { pen: 5, ink: 1 };
    assert.throws(() => reserve([{ sku: 'pen', quantity: 2 }, { sku: 'ink', quantity: 2 }], stock));
    assert.deepEqual(stock, { pen: 5, ink: 1 });
  }]
];
const observations = cases.map(([name, check]) => {
  try { check(); return { name, pass: true }; }
  catch (error) { return { name, pass: false, reason: error.message }; }
});
const passed = observations.filter(item => item.pass).length;
console.log(JSON.stringify({ kind: 'public-training-check', observations, passed, failed: cases.length - passed }, null, 2));
process.exitCode = passed === cases.length ? 0 : 1;
