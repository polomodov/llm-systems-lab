import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { sha256 } from '../scripts/lib/files.mjs';
import { createLabPractice, listPracticeScenarios, practiceScenarioIds, replayPracticeFixture } from '../scripts/lib/lab-practice.mjs';

const repository = fileURLToPath(new URL('../', import.meta.url));
const sourceFixture = id => JSON.parse(readFileSync(join(repository, `docs/labs/fixtures/practice/${id}.json`), 'utf8'));
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'lab-practice-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'docs/labs/fixtures'), { recursive: true });
  cpSync(join(repository, 'docs/labs/fixtures/practice'), join(root, 'docs/labs/fixtures/practice'), { recursive: true });
  // A directory makes accidental reads of .env fail instead of providing credentials.
  mkdirSync(join(root, '.env'));
  return root;
}

test('every practice scenario replays deterministically and preserves unmeasured values', () => {
  for (const id of practiceScenarioIds) {
    const input = sourceFixture(id), original = structuredClone(input);
    const first = replayPracticeFixture(input), second = replayPracticeFixture(input);
    assert.deepEqual(first, second);
    assert.deepEqual(input, original);
    assert.equal(first.analysis.evidence_class, 'synthetic');
    assert.equal(first.analysis.verdict, null);
    for (const key of ['input_tokens', 'output_tokens', 'cost_usd', 'wall_clock_ms']) {
      assert.equal(first.analysis[key], null);
      assert.ok(first.analysis.unavailable[key]);
    }
    assert.ok(first.trace.every((event, index) => event.sequence === index + 1 && event.evidence_class === 'synthetic'));
  }
});

test('controlled lookup produces its allowlisted result with linked identifiers, not a verdict', () => {
  const { trace, analysis } = replayPracticeFixture(sourceFixture('tool-success'));
  const call = trace.find(event => event.type === 'assistant-tool-call');
  const response = trace.find(event => event.type === 'tool-response');
  assert.equal(response.call_id, call.call_id);
  assert.equal(response.request_id, call.request_id);
  assert.deepEqual(response.result, { key: 'alpha', value: 'LAB_VALUE_42' });
  assert.equal(analysis.response_state, 'final-received');
  assert.equal(analysis.verdict, null);
  assert.equal(analysis.simulated_counter, null);
});

test('a recovered 429 retains its failed attempt and enforces virtual Retry-After', () => {
  const input = sourceFixture('retry-429');
  const { analysis } = replayPracticeFixture(input);
  assert.equal(analysis.attempts.length, 2);
  assert.equal(analysis.attempts[0].response_state, 'http-error');
  assert.equal(analysis.attempts[0].http_status, 429);
  assert.equal(analysis.attempts[1].response_state, 'final-received');
  assert.equal(analysis.errors.length, 1);
  assert.equal(analysis.virtual_elapsed_ms, 1200);
  input.steps[2].at_ms = 1099;
  assert.throws(() => replayPracticeFixture(input), /before Retry-After/);
});

test('stream interruption and an unclosed stream cannot turn partial success text into a final answer', () => {
  const input = sourceFixture('interrupted-stream');
  const { analysis } = replayPracticeFixture(input);
  assert.equal(analysis.response_state, 'incomplete');
  assert.equal(analysis.final_text, null);
  assert.equal(analysis.attempts[0].response_state, 'incomplete');
  assert.equal(analysis.errors[0].kind, 'stream-interrupted');
  assert.equal(analysis.attempts[0].http_status, null);
  input.steps.pop();
  const truncated = replayPracticeFixture(input).analysis;
  assert.equal(truncated.response_state, 'incomplete');
  assert.equal(truncated.final_text, null);
  assert.equal(truncated.attempts[0].ended_at_ms, null);
  assert.equal(truncated.verdict, null);
});

test('lost tool responses remain unknown to the client even though a separate synthetic audit records duplicate effects', () => {
  const { trace, analysis } = replayPracticeFixture(sourceFixture('duplicate-action'));
  const lost = trace.find(event => event.type === 'tool-response' && event.delivery === 'lost');
  assert.equal(lost.result, null);
  assert.match(lost.unavailable_reason, /unknown/);
  assert.equal(analysis.tool_calls[0].response_state, 'unknown');
  assert.equal(analysis.tool_calls[1].response_state, 'observed');
  assert.equal(analysis.unobserved_tool_outcomes, 1);
  assert.equal(analysis.simulated_counter, 2);
  assert.equal(analysis.errors[0].kind, 'tool-response-lost');
  assert.equal(analysis.response_state, 'final-received');
  assert.equal(analysis.verdict, null);
  const audit = trace.filter(event => event.type === 'simulated-action-audit');
  assert.equal(audit.length, 2);
  assert.ok(audit.every(event => event.client_observed === false));
});

test('the same idempotency key deduplicates the dummy action and rejects changed logical actions', () => {
  const input = sourceFixture('duplicate-action');
  const calls = input.steps.filter(event => event.type === 'assistant-tool-call');
  for (const call of calls) call.idempotency_key = 'stable-action-key';
  calls[1].arguments = { amount: 1, counter: 'demo' }; // Object key order does not change the logical payload.
  const { analysis } = replayPracticeFixture(input);
  assert.equal(analysis.simulated_counter, 1);
  assert.deepEqual(analysis.simulated_action_audit.map(row => row.deduplicated), [false, true]);
  assert.equal(analysis.tool_calls[0].response_state, 'unknown');
  assert.equal(analysis.verdict, null);
  calls[1].action_id = 'other-action';
  assert.throws(() => replayPracticeFixture(input), /key reused with different action/);
});

test('finite script validation rejects executable tools, extra claims and invalid event transitions', () => {
  for (const mutate of [
    value => { value.kind = 'run'; },
    value => { value.evidence_class = 'ours'; },
    value => { value.command = 'touch /tmp/never-executed'; },
    value => { value.steps[1].name = 'shell'; value.steps[1].arguments = { command: 'echo no' }; },
    value => { value.steps[1].arguments.key = 'other'; },
    value => { value.steps[1].arguments.url = 'https://example.invalid'; },
    value => { value.steps[1].at_ms = -1; },
    value => { value.steps[1].at_ms = 0.5; },
    value => { value.steps[2].at_ms = 39; },
    value => { value.steps[2].request_id = 'other-request'; },
    value => { value.steps[2].call_id = 'other-call'; },
    value => { value.steps[2].delivery = 'success'; },
    value => { value.steps[2].type = 'execute'; },
    value => { value.steps[3].usage = { input_tokens: 0 }; },
    value => { value.steps.splice(2, 1); },
    value => { value.steps.splice(2, 0, structuredClone(value.steps[1])); },
    value => { value.steps.push({ type: 'request', at_ms: 90, request_id: 'request-2' }); },
  ]) {
    const input = sourceFixture('tool-success');
    mutate(input);
    assert.throws(() => replayPracticeFixture(input), /Invalid practice fixture/);
  }
});

test('creation writes only a synthetic exercise with blank worksheet, source hashes and no run record', t => {
  const root = fixture(t);
  const result = createLabPractice(root, { scenario: 'duplicate-action', session: 'first-pass' });
  assert.equal(result.directory, 'experiments/local-models/practice/duplicate-action-first-pass');
  const dir = join(root, result.directory);
  assert.deepEqual(readdirSync(dir).sort(), ['analysis.json', 'fixture.json', 'manifest.json', 'trace.jsonl', 'worksheet.md']);
  const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json')));
  assert.equal(manifest.kind, 'lab-practice');
  assert.equal(manifest.evidence_class, 'synthetic');
  assert.equal(manifest.status, 'not-started');
  assert.equal(manifest.student_conclusion, null);
  assert.equal(manifest.reviewer_decision, null);
  assert.deepEqual(manifest.run_ids, []);
  for (const [field, name] of [['fixture_sha256', 'fixture.json'], ['trace_sha256', 'trace.jsonl'], ['analysis_sha256', 'analysis.json']]) assert.equal(manifest[field], sha256(readFileSync(join(dir, name))));
  assert.match(readFileSync(join(dir, 'worksheet.md'), 'utf8'), /Решение проверяющего: \*\*не проверено\*\*/);
  assert.equal(existsSync(join(root, 'results')), false);
  assert.equal(existsSync(join(root, 'experiments/local-models/measurements')), false);
});

test('sessions cannot overwrite student work or traverse paths, and fixtures validate before any output directory is made', t => {
  const root = fixture(t);
  for (const [scenario, session] of [['../escape', 'valid'], ['tool-success', '../escape'], ['tool-success', 'Uppercase'], ['tool-success', 'a'.repeat(65)], ['https://example.invalid', 'valid']]) assert.throws(() => createLabPractice(root, { scenario, session }));
  assert.equal(existsSync(join(root, 'experiments')), false);
  const broken = sourceFixture('tool-success');
  broken.steps[1].name = 'shell';
  writeFileSync(join(root, 'docs/labs/fixtures/practice/tool-success.json'), JSON.stringify(broken));
  assert.throws(() => createLabPractice(root, { scenario: 'tool-success', session: 'broken' }), /not allowlisted/);
  assert.equal(existsSync(join(root, 'experiments')), false);
  const result = createLabPractice(root, { scenario: 'retry-429', session: 'existing' });
  const worksheet = join(root, result.directory, 'worksheet.md');
  writeFileSync(worksheet, 'student response');
  assert.throws(() => createLabPractice(root, { scenario: 'retry-429', session: 'existing' }), /EEXIST/);
  assert.equal(readFileSync(worksheet, 'utf8'), 'student response');
});

test('symlink destinations, parents and fixture sources are rejected without writing outside the exercise', t => {
  const root = fixture(t);
  const outside = mkdtempSync(join(tmpdir(), 'lab-practice-outside-'));
  t.after(() => rmSync(outside, { recursive: true, force: true }));
  mkdirSync(join(root, 'experiments/local-models/practice'), { recursive: true });
  symlinkSync(outside, join(root, 'experiments/local-models/practice/tool-success-linked'));
  assert.throws(() => createLabPractice(root, { scenario: 'tool-success', session: 'linked' }), /Symlinks/);
  rmSync(join(root, 'experiments/local-models/practice'), { recursive: true });
  symlinkSync(outside, join(root, 'experiments/local-models/practice'));
  assert.throws(() => createLabPractice(root, { scenario: 'tool-success', session: 'parent' }), /Symlinks/);
  assert.deepEqual(readdirSync(outside), []);
  rmSync(join(root, 'docs/labs/fixtures/practice/tool-success.json'));
  symlinkSync(join(repository, 'docs/labs/fixtures/practice/tool-success.json'), join(root, 'docs/labs/fixtures/practice/tool-success.json'));
  assert.throws(() => listPracticeScenarios(root), /Symlinks/);
});

test('CLI lists the finite scenarios without writes and refuses unsupported options', t => {
  const root = fixture(t), script = join(repository, 'scripts/lab-practice.mjs');
  const run = argv => spawnSync(process.execPath, [script, ...argv], { cwd: root, encoding: 'utf8' });
  const listing = run(['--list', 'true']);
  assert.equal(listing.status, 0, listing.stderr);
  assert.equal(listing.stdout.trim().split('\n').length, 4);
  assert.equal(existsSync(join(root, 'experiments')), false);
  for (const argv of [[], ['--list', 'false'], ['--list', 'true', '--session', 'unused'], ['--scenario', 'tool-success'], ['--scenario', 'tool-success', '--session', 'unused', '--run', 'true'], ['--scenario', 'tool-success', '--scenario', 'retry-429', '--session', 'unused']]) assert.equal(run(argv).status, 1);
  assert.equal(existsSync(join(root, 'experiments')), false);
  const created = run(['--scenario', 'interrupted-stream', '--session', 'cli']);
  assert.equal(created.status, 0, created.stderr);
  assert.match(created.stdout, /synthetic; status=not-started; response_state=incomplete/);
  assert.equal(existsSync(join(root, 'results')), false);
});
