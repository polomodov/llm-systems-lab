import test from 'node:test';
import assert from 'node:assert/strict';
import { ledgerStatuses, renderStatus } from '../scripts/status.mjs';

const record = (run_id, status, overrides = {}) => ({
  run_id, status, task: 'T002', harness: { name: 'pi' }, model: { id: 'lab-model', provider: 'local' },
  verdict: { result: 'pending' }, execution: {}, ...overrides,
});
const executed = finished_at => ({ execution: { started_at: '2026-10-01T00:00:00Z', finished_at } });
const ledger = '| # | Component | Status |\n| --- | --- | --- |\n| L001 | a | proposed |\n| L002 | b | proposed |\n| L003 | c | removed |\n';
const report = (triples = 0, harnesses = 1) => ({ groups: [{ harnesses: Array.from({ length: harnesses }, () => ({ triples: Array(triples).fill({}) })) }] });

test('status counts executions and verdicts from records', () => {
  const text = renderStatus([
    record('a', 'completed', { verdict: { result: 'pass' }, ...executed('2026-10-15T01:00:00Z') }),
    record('b', 'completed', { verdict: { result: 'fail' }, ...executed('2026-10-12T01:00:00Z') }),
    record('c', 'aborted', executed('2026-10-20T01:00:00Z')),
    record('d', 'aborted'),
    record('e', 'prepared'),
    record('f', 'awaiting_review', executed('2026-10-11T01:00:00Z')),
  ], report(), ledger);
  assert.match(text, /Run records: 6\./);
  assert.match(text, /Agent executions started: 4; the latest finished on 2026-10-20\./);
  assert.match(text, /Independently evaluated: 2 \(pass 1, fail 1, partial 0\)\./);
  assert.match(text, /Complete triples under matching conditions: 0\./);
  assert.match(text, /Ledger rows: 3 \(2 proposed, 1 removed\)\./);
  assert.match(text, /- `f`/);
});

test('status keeps unknown fields visible and reports no date without executions', () => {
  const text = renderStatus([record('a', 'prepared', { model: {} })], report(), ledger);
  assert.match(text, /Agent executions started: 0\./);
  assert.match(text, /`pi` \| `T002` \| `not set` \| `not set` \|/);
  assert.match(text, /## Awaiting independent evaluation\n\nNone\./);
});

test('status reports triples and cross-harness groups from the comparison report', () => {
  const text = renderStatus([record('a', 'prepared')], report(2, 3), ledger);
  assert.match(text, /Complete triples under matching conditions: 6\./);
  assert.match(text, /Condition groups with more than one harness: 1\./);
});

test('status is deterministic regardless of record order', () => {
  const a = record('a', 'prepared'), b = record('b', 'prepared', { harness: { name: 'codex' } });
  assert.equal(renderStatus([a, b], report(), ledger), renderStatus([b, a], report(), ledger));
});

test('ledger statuses read only data rows', () => {
  assert.deepEqual(ledgerStatuses(ledger), { proposed: 2, removed: 1 });
});
