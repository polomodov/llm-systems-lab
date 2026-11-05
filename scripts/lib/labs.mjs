import { existsSync, readdirSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { safePath } from './files.mjs';
import { loadProfile } from './harnesses.mjs';

const sections = ['Паспорт', 'Цель', 'Проверяемая гипотеза', 'Подготовка', 'Порядок выполнения', 'Таблицы результатов', 'Что сдать', 'Критерии завершения', 'Контрольные вопросы', 'Источники'];

export function validateLabCatalog(catalog) {
  if (!catalog || catalog.schema_version !== 1 || !Array.isArray(catalog.labs) || !catalog.labs.length) throw new Error('Invalid lab catalog');
  if (catalog.require_harness_coverage !== undefined && typeof catalog.require_harness_coverage !== 'boolean') throw new Error('Invalid harness coverage policy');
  if (typeof catalog.updated_at !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(catalog.updated_at) || !Number.isFinite(Date.parse(catalog.updated_at)) || new Date(catalog.updated_at).toISOString().slice(0, 10) !== catalog.updated_at) throw new Error('Invalid lab catalog date');
  const ids = new Set(), harnesses = new Set();
  for (const lab of catalog.labs) {
    if (!lab || !/^LAB\d{2}$/.test(lab.id) || ids.has(lab.id)) throw new Error('Invalid or duplicate lab ID');
    ids.add(lab.id);
    if (typeof lab.title !== 'string' || !lab.title.trim() || /[\r\n]/.test(lab.title)) throw new Error(`Invalid lab title: ${lab.id}`);
    if (typeof lab.file !== 'string' || !new RegExp(`^${lab.id}-[a-z0-9]+(?:-[a-z0-9]+)*\\.md$`).test(lab.file)) throw new Error(`Unsafe lab file: ${lab.id}`);
    if (!['foundation', 'measurement', 'engineering', 'agent'].includes(lab.kind)) throw new Error(`Invalid lab kind: ${lab.id}`);
    if (lab.harness !== undefined) {
      if (typeof lab.harness !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(lab.harness) || lab.kind !== 'agent' || harnesses.has(lab.harness)) throw new Error(`Invalid or duplicate lab harness: ${lab.id}`);
      harnesses.add(lab.harness);
    }
    if (lab.area !== undefined && (typeof lab.area !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(lab.area) || lab.harness !== undefined || lab.area === 'local-models')) throw new Error(`Invalid lab area: ${lab.id}`);
    if (!['available', 'target-machine', 'implementation-required', 'frozen'].includes(lab.readiness)) throw new Error(`Invalid lab readiness: ${lab.id}`);
    // A frozen manual keeps its text and prerequisites but opens no new sessions until it is
    // extracted to its own repository or thawed; the planned readiness is kept for that day.
    if (lab.readiness === 'frozen') {
      const frozen = lab.frozen;
      if (!frozen || typeof frozen !== 'object' || !['available', 'target-machine', 'implementation-required'].includes(frozen.planned_readiness) || typeof frozen.reason !== 'string' || !frozen.reason.trim()) throw new Error(`Frozen lab needs planned_readiness and reason: ${lab.id}`);
      if (typeof frozen.since !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(frozen.since) || !Number.isFinite(Date.parse(frozen.since)) || new Date(frozen.since).toISOString().slice(0, 10) !== frozen.since) throw new Error(`Invalid freeze date: ${lab.id}`);
    } else if (lab.frozen !== undefined) throw new Error(`Only a frozen lab carries a freeze record: ${lab.id}`);
    if (typeof lab.effort !== 'string' || !lab.effort.trim()) throw new Error(`Missing lab effort: ${lab.id}`);
    if (!Array.isArray(lab.prerequisites) || new Set(lab.prerequisites).size !== lab.prerequisites.length) throw new Error(`Invalid lab prerequisites: ${lab.id}`);
    if (lab.prerequisites_any !== undefined && (!Array.isArray(lab.prerequisites_any) || !lab.prerequisites_any.length || new Set(lab.prerequisites_any).size !== lab.prerequisites_any.length || lab.prerequisites_any.some(id => lab.prerequisites.includes(id)))) throw new Error(`Invalid alternative prerequisites: ${lab.id}`);
  }
  const map = new Map(catalog.labs.map(lab => [lab.id, lab]));
  const done = new Set(), visiting = new Set();
  function visit(id) {
    if (!map.has(id)) throw new Error(`Unknown prerequisite: ${id}`);
    if (visiting.has(id)) throw new Error(`Cyclic lab prerequisites: ${id}`);
    if (done.has(id)) return;
    visiting.add(id);
    for (const prerequisite of [...map.get(id).prerequisites, ...(map.get(id).prerequisites_any ?? [])]) visit(prerequisite);
    visiting.delete(id); done.add(id);
  }
  for (const id of ids) visit(id);
  return catalog;
}

/** Reports live with their harness, then with their non-harness area, then in the shared local-models tree. */
export function labReportParent(lab) {
  return `experiments/${lab.harness ?? lab.area ?? 'local-models'}/measurements`;
}

export function loadLabCatalog(root, { checkDocuments = false } = {}) {
  const catalog = validateLabCatalog(JSON.parse(readFileSync(safePath(root, 'docs/labs/catalog.json'), 'utf8')));
  if (checkDocuments) for (const lab of catalog.labs) {
    const content = readFileSync(safePath(root, `docs/labs/${lab.file}`), 'utf8');
    for (const section of sections) if (!content.split('\n').some(line => line.trim() === `## ${section}`)) throw new Error(`${lab.id}: missing section ${section}`);
    if (lab.harness) loadProfile(root, lab.harness);
    if (lab.area && existsSync(safePath(root, `experiments/${lab.area}/harness.json`))) throw new Error(`${lab.id}: area ${lab.area} is a harness profile; use harness`);
  }
  if (checkDocuments && catalog.require_harness_coverage) {
    const experiments = safePath(root, 'experiments');
    const profiles = readdirSync(experiments, { withFileTypes: true })
      .filter(entry => entry.isDirectory() || entry.isSymbolicLink())
      .map(entry => entry.name)
      .filter(name => existsSync(safePath(root, `experiments/${name}/harness.json`)));
    const covered = new Set(catalog.labs.map(lab => lab.harness).filter(Boolean));
    for (const id of profiles) {
      loadProfile(root, id);
      if (!covered.has(id)) throw new Error(`Missing laboratory for harness: ${id}`);
    }
  }
  return catalog;
}

/** Create blank coursework only. Never create or execute an experimental run. */
export function createLabReport(root, { lab: id, session }) {
  if (typeof session !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(session) || session.length > 64) throw new Error('Session must be a lowercase slug of at most 64 characters');
  const catalog = loadLabCatalog(root);
  const lab = catalog.labs.find(entry => entry.id === id);
  if (!lab) throw new Error(`Unknown lab: ${id}`);
  if (lab.readiness === 'frozen') throw new Error(`${id} is frozen since ${lab.frozen.since}: ${lab.frozen.reason}`);
  if (lab.harness) loadProfile(root, lab.harness);
  // Read every input before creating a destination; a missing template leaves no draft.
  const template = name => readFileSync(safePath(root, `docs/labs/templates/${name}`), 'utf8');
  let report = template('report.md');
  const measurements = template('measurements.tsv');
  const manifest = JSON.parse(template('manifest.json'));
  if (manifest.kind !== 'lab-report' || manifest.status !== 'not-started' || manifest.lab_id !== null || manifest.session_id !== null || manifest.created_at !== null || !Array.isArray(manifest.run_ids) || manifest.run_ids.length) throw new Error('Lab manifest template must be an unstarted draft');
  const created = new Date().toISOString();
  for (const [name, value] of Object.entries({ LAB_ID: id, LAB_TITLE: lab.title, SESSION_ID: session, CREATED_AT: created })) report = report.replaceAll(`{{${name}}}`, value);
  Object.assign(manifest, { lab_id: id, session_id: session, created_at: created, harness_id: lab.harness ?? null });
  const reportParent = labReportParent(lab);
  const parent = safePath(root, reportParent);
  mkdirSync(parent, { recursive: true });
  const dir = safePath(root, `${reportParent}/${id}-${session}`);
  mkdirSync(dir); // EEXIST is intentional: never overwrite or reuse a previous report.
  mkdirSync(join(dir, 'raw'));
  writeFileSync(join(dir, 'report.md'), report, { flag: 'wx' });
  writeFileSync(join(dir, 'measurements.tsv'), measurements, { flag: 'wx' });
  writeFileSync(join(dir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
  return { directory: relative(root, dir), lab: id, session, status: 'not-started' };
}
