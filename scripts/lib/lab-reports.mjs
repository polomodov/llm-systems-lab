import { readFileSync, lstatSync } from 'node:fs';
import { safePath } from './files.mjs';
import { labReportParent, loadLabCatalog } from './labs.mjs';
import { readRun } from './records.mjs';
import { verifyRunIntegrity } from './integrity.mjs';

const text = value => typeof value === 'string' && value.trim().length > 0;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const slug = value => typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
const stamp = value => {
  if (!text(value) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  return new Date(value).toISOString() === (value.includes('.') ? value : value.replace('Z', '.000Z'));
};
const columns = 'observation_id configuration_id model_id engine backend context_tokens repeat metric value unit status evidence_path unavailable_reason'.split(' ');
const reportSections = ['Паспорт выполнения', 'Гипотеза и протокол до запуска', 'Ход выполнения', 'Результаты', 'Ошибки и ограничения', 'Вывод по гипотезе', 'Ответы на контрольные вопросы', 'Комплект сдачи'];

function localFile(base, path) {
  // Evidence is a regular local file, never a URL, a secret, a hidden check or a symlink.
  if (!text(path) || path.includes('\\') || path.includes(':') || path.split('/').some(part => !part || ['.', '..', 'check'].includes(part) || /^\.env(?:\.|$)/.test(part))) throw new Error('Expected a local evidence path without traversal, secrets or checks');
  const full = safePath(base, path);
  if (!lstatSync(full).isFile()) throw new Error(`Expected a regular file: ${path}`);
  return full;
}

/** Read-only completeness check. It never grades an experiment or changes its status. */
export function checkLabReport(root, { report, mode = 'draft' }) {
  if (!['draft', 'submission'].includes(mode)) throw new Error('Mode must be draft or submission');
  if (typeof report !== 'string' || !/^experiments\/[a-z0-9]+(?:-[a-z0-9]+)*\/measurements\/LAB\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(report)) throw new Error('Report must be an experiments/<harness-or-area>/measurements/LABxx-session directory');
  const dir = safePath(root, report);
  const manifest = JSON.parse(readFileSync(localFile(dir, 'manifest.json'), 'utf8'));
  if (!object(manifest) || manifest.kind !== 'lab-report' || ![1, 2].includes(manifest.schema_version)) throw new Error('Expected a lab-report manifest v1 or v2, not a practice trace or run record');
  const errors = [], warnings = [];
  const check = (condition, message) => { if (!condition) errors.push(message); };
  const attempt = (label, fn) => { try { return fn(); } catch (error) { errors.push(`${label}: ${error.message}`); return null; } };
  const submit = mode === 'submission';
  const lab = loadLabCatalog(root).labs.find(value => value.id === manifest.lab_id);
  check(!!lab, 'Unknown lab_id');
  check(slug(manifest.session_id) && manifest.session_id.length <= 64, 'Invalid session_id');
  if (lab) {
    check(manifest.harness_id === (lab.harness ?? null), 'harness_id differs from lab catalog');
    check(report === `${labReportParent(lab)}/${lab.id}-${manifest.session_id}`, 'Report directory differs from manifest identity');
  }
  check(stamp(manifest.created_at), 'Invalid created_at');
  check(['not-started', 'in-progress', 'completed', 'blocked'].includes(manifest.status), 'Invalid report status');
  for (const field of ['operator', 'hypothesis', 'protocol_before_run', 'conclusion', 'reviewer_decision']) check(manifest[field] === null || text(manifest[field]), `${field} must be nonempty text or null`);
  check(object(manifest.unavailable), 'unavailable must be an object');
  const unavailable = object(manifest.unavailable) ? manifest.unavailable : {};
  const blockedProtocol = manifest.status === 'blocked' && text(unavailable.protocol_before_run);
  for (const [key, value] of Object.entries(unavailable)) check(text(value), `unavailable.${key}: reason required`);
  if (submit) {
    check(manifest.schema_version === 2, 'Submission requires manifest v2 with a planned_attempts register');
    check(['completed', 'blocked'].includes(manifest.status), 'Submission must be completed or explicitly blocked');
    for (const field of ['operator', 'hypothesis', 'conclusion']) check(text(manifest[field]), `${field}: required for submission`);
    check(text(manifest.protocol_before_run) || blockedProtocol, 'protocol_before_run: required unless explicitly blocked with unavailable.protocol_before_run');
    if (manifest.status === 'blocked') check(text(unavailable.completion), 'Blocked report requires unavailable.completion');
  }

  const evidence = new Set();
  check(Array.isArray(manifest.evidence_files), 'evidence_files must be an array');
  for (const path of Array.isArray(manifest.evidence_files) ? manifest.evidence_files : []) {
    check(!evidence.has(path), `Duplicate evidence file: ${path}`);
    evidence.add(path);
    attempt(`evidence_files: ${path}`, () => localFile(dir, path));
  }
  if (submit) check(evidence.size > 0, 'Submission needs evidence_files');
  if (manifest.schema_version === 2) {
    check(manifest.evidence_class === null || ['experimental', 'synthetic', 'protocol'].includes(manifest.evidence_class), 'Invalid evidence_class');
    check(manifest.protocol_recorded_at === null || stamp(manifest.protocol_recorded_at), 'Invalid protocol_recorded_at');
    if (submit) {
      check(manifest.evidence_class !== null, 'evidence_class is required');
      check(stamp(manifest.protocol_recorded_at) || blockedProtocol, 'protocol_recorded_at is required unless protocol absence is explicitly blocked');
    }
    if (text(manifest.protocol_before_run)) {
      attempt('protocol_before_run', () => localFile(dir, manifest.protocol_before_run));
      check(evidence.has(manifest.protocol_before_run), 'Protocol file must be listed in evidence_files');
    }
  } else warnings.push('Legacy v1: draft validation only; use report-validation.md to add the v2 attempt register.');

  check(object(manifest.conditions), 'conditions must be an object');
  for (const field of ['hardware_snapshot', 'model_artifact_manifest', 'runtime_manifest', 'harness_profile']) {
    const value = manifest.conditions?.[field];
    check(value === null || text(value), `conditions.${field}: expected path or null`);
    if (text(value)) attempt(`conditions.${field}`, () => {
      if (!/^(docs|experiments|results\/runs)\//.test(value)) throw new Error('Condition paths must be repository-relative docs/, experiments/ or results/runs/ files');
      localFile(root, value);
    });
    if (submit && value === null) check(text(unavailable[`conditions.${field}`]), `conditions.${field}: supply a file or an unavailable reason`);
  }

  const runs = new Map();
  check(Array.isArray(manifest.run_ids), 'run_ids must be an array');
  for (const id of Array.isArray(manifest.run_ids) ? manifest.run_ids : []) {
    check(!runs.has(id), `Duplicate run ID: ${id}`);
    const record = attempt(`run_ids: ${id}`, () => { const value = readRun(root, id); verifyRunIntegrity(root, value); return value; });
    runs.set(id, record);
    if (record && lab?.harness) check(record.harness.name === lab.harness, `Run ${id} belongs to another harness`);
    if (record && manifest.schema_version === 2 && stamp(manifest.protocol_recorded_at) && record.execution.started_at && Date.parse(manifest.protocol_recorded_at) > Date.parse(record.execution.started_at)) {
      check(blockedProtocol, `Protocol was recorded after run ${id} started`);
      if (blockedProtocol) warnings.push(`Run ${id}: late protocol is retained as an explicit blocker, not pre-registration.`);
    }
  }
  if (manifest.schema_version === 2 && !['experimental', 'protocol'].includes(manifest.evidence_class)) check(runs.size === 0, 'Only experimental or preparation-only protocol reports may reference real run_ids');
  if (manifest.schema_version === 2 && manifest.evidence_class === 'protocol') for (const [id, record] of runs) {
    if (record) check(['planned', 'prepared', 'aborted'].includes(record.status) && !record.execution.started_at, `Protocol report cannot contain a started run: ${id}`);
  }

  const plans = Array.isArray(manifest.planned_attempts) ? manifest.planned_attempts : [];
  const planIds = new Set(), configurations = new Set(), linkedRuns = new Set();
  if (manifest.schema_version === 2) check(Array.isArray(manifest.planned_attempts), 'planned_attempts must be an array');
  if (submit) check(plans.length > 0, 'Submission requires all planned attempts, including failures and omissions');
  for (const plan of plans) {
    if (!object(plan)) { errors.push('Invalid planned attempt'); continue; }
    check(slug(plan.id) && !planIds.has(plan.id), 'Attempt ID must be a unique slug'); planIds.add(plan.id);
    check(slug(plan.configuration_id), `Attempt ${plan.id}: invalid configuration_id`); configurations.add(plan.configuration_id);
    check(['agent-run', 'measurement', 'exercise'].includes(plan.kind), `Attempt ${plan.id}: invalid kind`);
    check(['planned', 'completed', 'failed', 'not-run'].includes(plan.status), `Attempt ${plan.id}: invalid status`);
    check(plan.reason === null || text(plan.reason), `Attempt ${plan.id}: reason must be text or null`);
    if (submit) check(plan.status !== 'planned', `Attempt ${plan.id}: unresolved planned attempt`);
    if (['failed', 'not-run'].includes(plan.status)) check(text(plan.reason), `Attempt ${plan.id}: failure or omission needs a reason`);
    check(Array.isArray(plan.evidence_files), `Attempt ${plan.id}: evidence_files must be an array`);
    for (const path of Array.isArray(plan.evidence_files) ? plan.evidence_files : []) check(evidence.has(path), `Attempt ${plan.id}: unlisted evidence ${path}`);
    if (plan.kind !== 'agent-run') {
      check(plan.run_id === null, `Attempt ${plan.id}: only agent-run may have a run_id`);
      if (submit && ['completed', 'failed'].includes(plan.status)) check(plan.evidence_files?.length > 0, `Attempt ${plan.id}: performed work requires evidence`);
    } else {
      if (manifest.schema_version === 2) check(manifest.evidence_class === 'experimental' || manifest.evidence_class === 'protocol' && ['planned', 'not-run'].includes(plan.status), 'Started agent attempts require evidence_class=experimental');
      check(plan.run_id === null || text(plan.run_id), `Attempt ${plan.id}: invalid run_id`);
      if (plan.run_id !== null) {
        check(runs.has(plan.run_id), `Attempt ${plan.id}: run_id absent from run_ids`);
        check(!linkedRuns.has(plan.run_id), `Attempt ${plan.id}: reused run_id`); linkedRuns.add(plan.run_id);
      }
      const record = runs.get(plan.run_id);
      if (['completed', 'failed'].includes(plan.status)) {
        check(!!record, `Attempt ${plan.id}: missing run record`);
        if (record) {
          check(record.status === (plan.status === 'completed' ? 'completed' : 'aborted'), `Attempt ${plan.id}: status disagrees with run record`);
          if (plan.status === 'failed') check(!!record.execution.started_at, `Attempt ${plan.id}: failure before launch belongs to not-run`);
        }
      }
      if (record && plan.status === 'not-run') check(['planned', 'prepared', 'aborted'].includes(record.status) && !record.execution.started_at, `Attempt ${plan.id}: a started run cannot be omitted as not-run`);
    }
  }
  if (manifest.schema_version === 2) for (const id of runs.keys()) check(linkedRuns.has(id), `Run ${id} is absent from the attempt register`);
  if (submit && manifest.status === 'completed') check(plans.some(plan => ['completed', 'failed'].includes(plan?.status)), 'A completed report needs at least one performed attempt');
  if (submit && lab?.harness && manifest.status === 'completed') check([...runs.values()].some(record => record?.status === 'completed'), 'A completed harness lab requires an independently judged run');

  const markdown = attempt('report.md', () => readFileSync(localFile(dir, 'report.md'), 'utf8'));
  if (markdown !== null) {
    for (const section of reportSections) check(markdown.split('\n').some(line => line.trim() === `## ${section}`), `report.md: missing section ${section}`);
    check(!/\{\{[A-Z_]+\}\}/.test(markdown), 'report.md: unexpanded template placeholders');
  }
  const tsv = attempt('measurements.tsv', () => readFileSync(localFile(dir, 'measurements.tsv'), 'utf8'));
  let observations = 0;
  if (tsv !== null) {
    const lines = tsv.replace(/\r\n/g, '\n').split('\n');
    while (lines.at(-1) === '') lines.pop();
    check(lines[0] === columns.join('\t'), 'measurements.tsv: unexpected header');
    const ids = new Set();
    for (const [index, line] of lines.slice(1).entries()) {
      const values = line.split('\t'), label = `measurements.tsv:${index + 2}`;
      if (values.length !== columns.length) { errors.push(`${label}: expected ${columns.length} columns`); continue; }
      const row = Object.fromEntries(columns.map((key, i) => [key, values[i]])); observations++;
      check(text(row.observation_id) && !ids.has(row.observation_id), `${label}: missing or duplicate observation_id`); ids.add(row.observation_id);
      check(text(row.configuration_id) && text(row.metric), `${label}: configuration_id and metric required`);
      if (plans.length) check(configurations.has(row.configuration_id), `${label}: configuration absent from attempt register`);
      for (const key of ['context_tokens', 'repeat']) check(row[key] === '' || /^[1-9]\d*$/.test(row[key]) && Number.isSafeInteger(Number(row[key])), `${label}: invalid ${key}`);
      check(['measured', 'failed', 'not-run', 'unavailable'].includes(row.status), `${label}: invalid status`);
      if (row.evidence_path) {
        check(evidence.has(row.evidence_path), `${label}: evidence_path absent from evidence_files`);
        attempt(label, () => localFile(dir, row.evidence_path));
      }
      if (row.status === 'measured') {
        if (plans.length) check(plans.some(plan => plan?.configuration_id === row.configuration_id && ['completed', 'failed'].includes(plan.status)), `${label}: measured data requires a performed attempt for this configuration`);
        check(/^-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(row.value) && Number.isFinite(Number(row.value)), `${label}: measured value must be a finite decimal number`);
        check(text(row.unit) && text(row.evidence_path), `${label}: measured value requires unit and evidence`);
        check(row.unavailable_reason === '', `${label}: measured value cannot have an unavailable reason`);
      } else {
        check(row.value === '' && text(row.unavailable_reason), `${label}: unknown/failed/not-run needs an empty value and reason, never a fabricated zero`);
      }
    }
    if (submit && observations === 0) check(text(unavailable.measurements), 'Empty measurements.tsv requires unavailable.measurements');
  }
  warnings.push('Completeness only: the reviewer checks the hypothesis, lab-specific minimum, truth of evidence and pre-registration; no verdict is assigned.');
  return { report, mode, status: manifest.status, evidence_class: manifest.evidence_class ?? null, attempts: plans.length, observations, errors, warnings, ready_for_review: submit && errors.length === 0, experiment_pass: null };
}
