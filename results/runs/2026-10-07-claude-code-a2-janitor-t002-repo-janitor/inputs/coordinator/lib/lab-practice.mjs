import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { safePath, sha256 } from './files.mjs';

export const practiceScenarioIds = Object.freeze(['tool-success', 'retry-429', 'interrupted-stream', 'duplicate-action']);
const stepTypes = new Set(['request', 'http-error', 'assistant-tool-call', 'tool-response', 'assistant-delta', 'stream-interrupted', 'assistant-final']);
const slug = value => typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value) && value.length <= 64;
const plainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.trim().length > 0;
function require(condition, message) { if (!condition) throw new Error(`Invalid practice fixture: ${message}`); }
function exactKeys(value, allowed, description) {
  require(plainObject(value), `${description} must be an object`);
  for (const key of Object.keys(value)) require(allowed.includes(key), `${description}: unknown field ${key}`);
}

/** Interpret a finite, local teaching script. No model, shell or network is invoked. */
export function replayPracticeFixture(fixture) {
  exactKeys(fixture, ['schema_version', 'kind', 'evidence_class', 'id', 'title', 'related_labs', 'assignment', 'questions', 'steps'], 'fixture');
  require(fixture.schema_version === 1 && fixture.kind === 'lab-practice-fixture' && fixture.evidence_class === 'synthetic', 'synthetic schema version 1 required');
  require(practiceScenarioIds.includes(fixture.id), 'unknown scenario');
  require(text(fixture.title) && text(fixture.assignment), 'missing title or assignment');
  require(Array.isArray(fixture.related_labs) && fixture.related_labs.length > 0 && fixture.related_labs.every(id => /^LAB\d{2}$/.test(id)), 'invalid related labs');
  require(Array.isArray(fixture.questions) && fixture.questions.length > 0 && fixture.questions.every(text), 'missing questions');
  require(Array.isArray(fixture.steps) && fixture.steps.length > 0, 'missing steps');

  const trace = [], attempts = [], calls = new Map(), errors = [], actionLedger = [], idempotency = new Map();
  let active = null, previousTime = -1, retryAt = null, counter = 0, finalText = null;
  const add = event => trace.push({ sequence: trace.length + 1, evidence_class: 'synthetic', ...event });
  for (const step of fixture.steps) {
    require(plainObject(step) && stepTypes.has(step.type), 'unknown step type');
    require(Number.isSafeInteger(step.at_ms) && step.at_ms >= 0 && step.at_ms >= previousTime, 'virtual time must be a monotonic nonnegative integer');
    previousTime = step.at_ms;
    const common = ['type', 'at_ms', 'request_id'];
    require(slug(step.request_id), 'invalid request id');
    if (step.type === 'request') {
      exactKeys(step, common, step.type);
      require(active === null, 'a request is already active');
      require(!attempts.some(attempt => attempt.request_id === step.request_id), 'duplicate request id');
      require(finalText === null, 'cannot request after a final answer');
      require(retryAt === null || step.at_ms >= retryAt, 'retry before Retry-After');
      active = { request_id: step.request_id, response_state: 'incomplete', started_at_ms: step.at_ms, ended_at_ms: null, http_status: null, failure_reason: null };
      attempts.push(active);
      retryAt = null;
      add(step);
      continue;
    }
    require(active !== null && active.request_id === step.request_id, 'step does not belong to an active request');
    if (step.type === 'http-error') {
      exactKeys(step, [...common, 'status', 'retry_after_ms'], step.type);
      require(step.status === 429 && Number.isSafeInteger(step.retry_after_ms) && step.retry_after_ms >= 0, 'only a recorded 429 with Retry-After is supported');
      require(![...calls.values()].some(call => call.request_id === step.request_id) && !trace.some(event => event.request_id === step.request_id && event.type === 'assistant-delta'), 'HTTP error after response data');
      Object.assign(active, { response_state: 'http-error', ended_at_ms: step.at_ms, http_status: step.status, failure_reason: 'recorded-http-429' });
      retryAt = step.at_ms + step.retry_after_ms;
      require(Number.isSafeInteger(retryAt), 'Retry-After overflows virtual time');
      errors.push({ request_id: step.request_id, kind: 'http-error', status: 429, at_ms: step.at_ms });
      active = null;
      add(step);
    } else if (step.type === 'assistant-tool-call') {
      exactKeys(step, [...common, 'call_id', 'name', 'arguments', 'action_id', 'idempotency_key'], step.type);
      require(slug(step.call_id) && !calls.has(step.call_id), 'invalid or duplicate call id');
      require(plainObject(step.arguments), 'tool arguments must be an object');
      let result;
      if (step.name === 'lookup_lab_value') {
        exactKeys(step.arguments, ['key'], 'lookup arguments');
        require(step.arguments.key === 'alpha', 'lookup permits only key alpha');
        require(step.action_id === undefined && step.idempotency_key === undefined, 'lookup is read only');
        result = { key: 'alpha', value: 'LAB_VALUE_42' };
      } else if (step.name === 'increment_demo_counter') {
        exactKeys(step.arguments, ['counter', 'amount'], 'counter arguments');
        require(step.arguments.counter === 'demo' && step.arguments.amount === 1, 'counter permits only a dummy increment of one');
        require(slug(step.action_id), 'missing logical action id');
        require(step.idempotency_key === null || slug(step.idempotency_key), 'idempotency key must be null or a slug');
        const payload = JSON.stringify({ action_id: step.action_id, counter: step.arguments.counter, amount: step.arguments.amount });
        const prior = step.idempotency_key === null ? null : idempotency.get(step.idempotency_key);
        require(!prior || prior.payload === payload, 'idempotency key reused with different action');
        if (prior) result = prior.result;
        else {
          result = { counter: 'demo', value: ++counter };
          if (step.idempotency_key !== null) idempotency.set(step.idempotency_key, { payload, result });
        }
        actionLedger.push({ call_id: step.call_id, action_id: step.action_id, idempotency_key: step.idempotency_key, deduplicated: !!prior, counter_after: counter });
      } else throw new Error(`Invalid practice fixture: tool is not allowlisted: ${step.name}`);
      calls.set(step.call_id, { request_id: step.request_id, name: step.name, response_state: 'unobserved', result });
      add(step);
      if (step.name === 'increment_demo_counter') add({ type: 'simulated-action-audit', at_ms: step.at_ms, request_id: step.request_id, ...actionLedger.at(-1), client_observed: false });
    } else if (step.type === 'tool-response') {
      exactKeys(step, [...common, 'call_id', 'delivery'], step.type);
      const call = calls.get(step.call_id);
      require(call && call.request_id === step.request_id && call.response_state === 'unobserved', 'tool response without a pending call');
      require(['delivered', 'lost'].includes(step.delivery), 'invalid response delivery');
      call.response_state = step.delivery === 'delivered' ? 'observed' : 'unknown';
      add({ ...step, result: step.delivery === 'delivered' ? call.result : null, unavailable_reason: step.delivery === 'lost' ? 'response-lost; tool outcome is unknown to the client' : null });
      if (step.delivery === 'lost') errors.push({ request_id: step.request_id, call_id: step.call_id, kind: 'tool-response-lost', at_ms: step.at_ms });
    } else if (step.type === 'assistant-delta') {
      exactKeys(step, [...common, 'text'], step.type);
      require(text(step.text), 'empty stream chunk');
      add(step);
    } else if (step.type === 'stream-interrupted') {
      exactKeys(step, [...common, 'reason'], step.type);
      require(text(step.reason), 'missing interruption reason');
      Object.assign(active, { response_state: 'incomplete', ended_at_ms: step.at_ms, failure_reason: step.reason });
      errors.push({ request_id: step.request_id, kind: 'stream-interrupted', reason: step.reason, at_ms: step.at_ms });
      active = null;
      add(step);
    } else if (step.type === 'assistant-final') {
      exactKeys(step, [...common, 'text'], step.type);
      require(text(step.text), 'empty final answer');
      require(![...calls.values()].some(call => call.request_id === step.request_id && call.response_state === 'unobserved'), 'final answer before tool response or explicit loss');
      Object.assign(active, { response_state: 'final-received', ended_at_ms: step.at_ms, http_status: 200 });
      finalText = step.text;
      active = null;
      add(step);
    }
  }
  // Ending a fixture without a final event is incomplete, even if its text sounds successful.
  const uncertainCalls = [...calls.values()].filter(call => call.response_state !== 'observed').length;
  return {
    trace,
    analysis: {
      schema_version: 1,
      kind: 'lab-practice-analysis',
      evidence_class: 'synthetic',
      scenario_id: fixture.id,
      response_state: finalText !== null ? 'final-received' : attempts.at(-1)?.response_state ?? 'incomplete',
      final_text: finalText,
      attempts,
      errors,
      tool_calls: [...calls.entries()].map(([call_id, call]) => ({ call_id, request_id: call.request_id, name: call.name, response_state: call.response_state })),
      unobserved_tool_outcomes: uncertainCalls,
      simulated_action_audit: actionLedger,
      simulated_counter: actionLedger.length ? counter : null,
      virtual_elapsed_ms: fixture.steps.at(-1).at_ms - fixture.steps[0].at_ms,
      input_tokens: null,
      output_tokens: null,
      cost_usd: null,
      wall_clock_ms: null,
      unavailable: {
        input_tokens: 'No model was invoked; synthetic fixture has no measured token usage.',
        output_tokens: 'No model was invoked; synthetic fixture has no measured token usage.',
        cost_usd: 'No provider billing observation exists; do not treat an exercise as a zero-cost model run.',
        wall_clock_ms: 'The fixture uses virtual time; it does not measure real inference latency.',
        verdict: 'A final event is not a task verdict; the student and reviewer must interpret the evidence.',
      },
      verdict: null,
    },
  };
}

function readScenario(root, id) {
  if (!practiceScenarioIds.includes(id)) throw new Error(`Unknown practice scenario: ${id}`);
  const source = `docs/labs/fixtures/practice/${id}.json`;
  const raw = readFileSync(safePath(root, source), 'utf8');
  const fixture = JSON.parse(raw);
  if (fixture.id !== id) throw new Error('Practice fixture id does not match its filename');
  const replay = replayPracticeFixture(fixture);
  return { source, raw, fixture, ...replay };
}

export function listPracticeScenarios(root) {
  return practiceScenarioIds.map(id => {
    const { fixture } = readScenario(root, id);
    return { id, title: fixture.title, related_labs: fixture.related_labs };
  });
}

/** Create synthetic teaching material only; never creates a run or an assessed report. */
export function createLabPractice(root, { scenario, session }) {
  if (!slug(session)) throw new Error('Session must be a lowercase slug of at most 64 characters');
  const { source, raw, fixture, trace, analysis } = readScenario(root, scenario);
  const traceContent = trace.map(event => JSON.stringify(event)).join('\n') + '\n';
  const analysisContent = JSON.stringify(analysis, null, 2) + '\n';
  const manifest = {
    schema_version: 1, kind: 'lab-practice', evidence_class: 'synthetic',
    scenario_id: scenario, session_id: session, related_labs: fixture.related_labs,
    created_at: new Date().toISOString(), status: 'not-started',
    source_fixture: source, fixture_sha256: sha256(raw), trace_sha256: sha256(traceContent), analysis_sha256: sha256(analysisContent),
    run_ids: [], student_conclusion: null, reviewer_decision: null,
  };
  const worksheet = `# Учебное упражнение: ${fixture.title}\n\nСценарий: \`${scenario}\`; сессия: \`${session}\`. Связанные работы: ${fixture.related_labs.join(', ')}.\n\n**Синтетические данные.** Модель, adapter, сеть и shell не запускались. Статус работы: **не начато**, проверяющий: **не проверено**. Этот комплект не является run record или выполненной лабораторной.\n\n## Задание\n\n${fixture.assignment}\n\nЧитайте \`trace.jsonl\` по \`sequence\`; время \`at_ms\` виртуальное. \`simulated-action-audit\` — учебный журнал dummy-сервиса, недоступный клиенту в момент потерянного ответа. \`analysis.json\` содержит разбор событий, а не оценку качества.\n\n## До разбора трассы\n\nПредположение о поведении системы и правило, по которому вы отличите полученный ответ от успеха задачи:\n\n—\n\n## Наблюдения\n\n| Событие / sequence | Что известно клиенту | Что неизвестно | Доказательство / ограничение |\n| --- | --- | --- | --- |\n| — | — | — | — |\n\n## Ответы\n\n${fixture.questions.map((question, index) => `### ${index + 1}. ${question}\n\n—`).join('\n\n')}\n\n## Предлагаемая обработка\n\nЗапишите алгоритм обработки ошибки/инструмента и проверку, которая отличит исправление от случайного успеха. Не выполняйте записанные tool calls в реальной системе.\n\n—\n\n## Вывод и границы переноса\n\nЧто подтверждает учебная трасса, что нужно отдельно измерить на настоящем harness:\n\n—\n\nРешение проверяющего: **не проверено**.\n`;
  const parentPath = 'experiments/local-models/practice';
  mkdirSync(safePath(root, parentPath), { recursive: true });
  const dir = safePath(root, `${parentPath}/${scenario}-${session}`);
  mkdirSync(dir); // Existing coursework is never reused or overwritten.
  for (const [name, content] of Object.entries({
    'fixture.json': raw, 'trace.jsonl': traceContent, 'analysis.json': analysisContent,
    'manifest.json': JSON.stringify(manifest, null, 2) + '\n', 'worksheet.md': worksheet,
  })) writeFileSync(join(dir, name), content, { flag: 'wx' });
  return { directory: relative(root, dir), scenario, session, status: 'not-started', evidence_class: 'synthetic', response_state: analysis.response_state };
}
