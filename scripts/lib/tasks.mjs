// Машинное описание задачи: tasks/<id>/task.json. Контракт task.md остаётся
// текстом для агента; дескриптор говорит координатору, как готовить workspace,
// какую сеть открывать и какие артефакты требовать. Три первые задачи
// описаны и здесь, чтобы запечатанные входы старых прогонов без task.json
// читались так же, как раньше.
import { existsSync, readFileSync, lstatSync } from 'node:fs';
import { join } from 'node:path';
import { safePath } from './files.mjs';

export const WORKSPACE_KINDS = ['repo', 'files'];
export const EVALUATION_METHODS = ['hidden-check', 'rubric'];
export const SETUP_ARGS = ['harness', 'as-of'];
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DOMAIN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/;
const ARTIFACT = /^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$/;

export const LEGACY_TASKS = {
  'T001-dossier-from-sources': { schema_version: 1, id: 'T001-dossier-from-sources', agent: 'a1-dossier', workspace: 'files', branch_prefix: null, evaluation: 'rubric', required_artifacts: ['dossier.md', 'sources.json'], network: { connect_domains: [], sources: true }, setup_args: ['as-of'] },
  'T002-repo-janitor': { schema_version: 1, id: 'T002-repo-janitor', agent: 'a2-janitor', workspace: 'repo', branch_prefix: 'janitor', evaluation: 'hidden-check', required_artifacts: ['report.md'], network: { connect_domains: ['registry.npmjs.org'], sources: false }, setup_args: [] },
  'T003-harness-self-audit': { schema_version: 1, id: 'T003-harness-self-audit', agent: 'a3-ledger-auditor', workspace: 'files', branch_prefix: null, evaluation: 'rubric', required_artifacts: ['ledger.md', 'ablation-plan.md'], network: { connect_domains: [], sources: false }, setup_args: ['harness'] },
};

export function validateTaskDescriptor(value, expectedId) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Task descriptor must be an object');
  if (value.schema_version !== 1) throw new Error('Task descriptor schema_version must be 1');
  if (typeof value.id !== 'string' || !/^T\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value.id)) throw new Error('Task descriptor id must look like T004-feature-name');
  if (expectedId && value.id !== expectedId) throw new Error(`Task descriptor id ${value.id} differs from directory ${expectedId}`);
  if (typeof value.agent !== 'string' || !/^a\d+-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value.agent)) throw new Error('Task descriptor agent must be an agent code like a2-janitor');
  if (!WORKSPACE_KINDS.includes(value.workspace)) throw new Error('Task workspace must be repo or files');
  if (value.branch_prefix !== null && (typeof value.branch_prefix !== 'string' || !SLUG.test(value.branch_prefix))) throw new Error('branch_prefix must be a slug or null');
  if (value.workspace === 'files' && value.branch_prefix !== null) throw new Error('A files workspace has no branch');
  if (!EVALUATION_METHODS.includes(value.evaluation)) throw new Error('Task evaluation must be hidden-check or rubric');
  if (!Array.isArray(value.required_artifacts) || !value.required_artifacts.length || value.required_artifacts.some(name => typeof name !== 'string' || !ARTIFACT.test(name)) || new Set(value.required_artifacts).size !== value.required_artifacts.length) throw new Error('required_artifacts must list distinct plain file names');
  const network = value.network;
  if (!network || typeof network !== 'object' || !Array.isArray(network.connect_domains) || typeof network.sources !== 'boolean') throw new Error('Task network needs connect_domains and sources');
  if (network.connect_domains.some(domain => typeof domain !== 'string' || !DOMAIN.test(domain)) || new Set(network.connect_domains).size !== network.connect_domains.length) throw new Error('connect_domains must be distinct lowercase host names');
  if (!Array.isArray(value.setup_args) || value.setup_args.some(arg => !SETUP_ARGS.includes(arg)) || new Set(value.setup_args).size !== value.setup_args.length) throw new Error(`setup_args may contain only ${SETUP_ARGS.join(', ')}`);
  if (network.sources && !value.setup_args.includes('as-of')) throw new Error('A task with web sources needs the as-of setup argument');
  const known = new Set(['schema_version', 'id', 'agent', 'workspace', 'branch_prefix', 'evaluation', 'required_artifacts', 'network', 'setup_args']);
  for (const key of Object.keys(value)) if (!known.has(key)) throw new Error(`Unknown task descriptor field: ${key}`);
  return value;
}

/** Descriptor of a task in the catalog: tasks/<id>/task.json, or the built-in legacy description of T001–T003. */
export function loadTaskDescriptor(root, taskId) {
  if (typeof taskId !== 'string' || !/^T\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(taskId)) throw new Error(`Invalid task id: ${taskId}`);
  const file = safePath(root, join('tasks', taskId, 'task.json'));
  if (existsSync(file)) {
    if (lstatSync(file).isSymbolicLink() || !lstatSync(file).isFile()) throw new Error('task.json must be a regular file');
    return validateTaskDescriptor(JSON.parse(readFileSync(file, 'utf8')), taskId);
  }
  if (LEGACY_TASKS[taskId]) return LEGACY_TASKS[taskId];
  throw new Error(`Task ${taskId} has no task.json`);
}

/** Descriptor sealed with a run: inputs/task.json, or the legacy description for snapshots made before task.json existed. */
export function sealedTaskDescriptor(runDir, taskId) {
  const file = join(runDir, 'inputs', 'task.json');
  if (existsSync(file)) return validateTaskDescriptor(JSON.parse(readFileSync(file, 'utf8')), taskId);
  if (LEGACY_TASKS[taskId]) return LEGACY_TASKS[taskId];
  throw new Error(`Sealed inputs of ${taskId} have no task.json`);
}

/** Working directory of the agent inside the container. A repo task keeps its project in sample/. */
export const agentCwd = descriptor => descriptor.workspace === 'repo' ? '/workspace/sample' : '/workspace';
