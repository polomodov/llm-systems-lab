import { test } from 'node:test';
import assert from 'node:assert/strict';
import { replayFetcher } from '../experiments/common/egress.mjs';
const record = { type: 'source', requested_url: 'https://example.com/article', url: 'https://example.com/article', body: '<p>Frozen evidence</p>', status: 200, content_type: 'text/html', fetched_at: '2026-09-20T10:00:00.000Z' };
test('source replay returns archived bytes and refuses missing URLs without a live network fallback', async () => {
  const fetch = replayFetcher(JSON.stringify(record) + '\n');
  assert.deepEqual(await fetch(record.requested_url), record);
  await assert.rejects(fetch('https://example.com/new'), /missing from frozen/);
});
test('source replay rejects empty, ambiguous and malformed archives before preparation', () => {
  assert.throws(() => replayFetcher(''), /empty/);
  assert.throws(() => replayFetcher(JSON.stringify(record) + '\n' + JSON.stringify(record)), /Duplicate/);
  for (const invalid of [{...record, url:'file:///etc/passwd'}, {...record, status:0}, {...record,body:null}, {...record,content_type:null}]) assert.throws(() => replayFetcher(JSON.stringify(invalid)));
});
