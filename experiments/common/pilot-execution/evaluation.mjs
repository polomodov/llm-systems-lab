// Data-only evaluator handoff. Hidden checks and task code are never executed.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, resolve, relative, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { readRun } from '../../../scripts/lib/records.mjs';
import { inventory, copyTree, sha256, safePath } from '../../../scripts/lib/files.mjs';
import { verifyInputs } from '../../../scripts/run.mjs';
import { sealedTaskDescriptor } from '../../../scripts/lib/tasks.mjs';
import { judgeRun } from '../../../scripts/judge-run.mjs';
import { args, options, main } from '../../../scripts/lib/cli.mjs';

const TASKS = new Set(['T002-repo-janitor', 'T004-feature-from-spec']);
const read = file => JSON.parse(readFileSync(file, 'utf8'));
const write = (file, value) => writeFileSync(file, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
const hash = file => sha256(readFileSync(file));
const require = (value, message) => { if (!value) throw new Error(message); };
const within = (parent, path) => { const r = relative(resolve(parent), resolve(path)); return r === '' || (!r.startsWith('..') && !isAbsolute(r)); };

function checkedRun(root, runId) {
  const record = readRun(root, runId), dir = safePath(root, join('results/runs', runId));
  require(TASKS.has(record.task) && record.status === 'awaiting_review', 'Only awaiting_review T002/T004 runs can be handed off');
  verifyInputs(dir, record, { workspace: false });
  require(JSON.stringify(inventory(join(dir, 'artifacts'))) === JSON.stringify(read(join(dir, 'trace/artifacts.json'))), 'Final artifacts changed');
  require(JSON.stringify(inventory(join(dir, 'workspace'))) === JSON.stringify(read(join(dir, 'trace/final-workspace.json'))), 'Final workspace changed');
  require(sealedTaskDescriptor(dir, record.task).evaluation === 'hidden-check', 'The sealed evaluation method is not hidden-check');
  return { record, dir };
}

export function prepareHandoff(root, runId, output, { solverId, checkerRevision }) {
  require(typeof solverId === 'string' && solverId.trim(), 'A solving actor identity is required');
  require(/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(checkerRevision), 'Pin the evaluator check revision before handoff');
  const { record, dir } = checkedRun(root, runId);
  const out = resolve(output);
  require(!within(dir, out) && !within(out, dir), 'Handoff output must be separate from the source record');
  for (const area of ['tasks', 'agents', 'results', 'scripts', 'docs']) require(!within(join(root, area), out), 'Handoff output cannot modify repository source/results');
  require(!existsSync(out), 'Handoff output already exists; never overwrite a submission');
  mkdirSync(out, { recursive: true });
  const submission = join(out, 'submission');
  mkdirSync(submission);
  copyTree(join(dir, 'workspace'), join(submission, 'workspace'));
  copyTree(join(dir, 'artifacts'), join(submission, 'artifacts'));
  mkdirSync(join(submission, 'public'));
  for (const file of ['task.md', 'spec.md']) writeFileSync(join(submission, 'public', file), readFileSync(join(dir, 'inputs', file)), { flag: 'wx' });
  write(join(submission, 'public/task.json'), sealedTaskDescriptor(dir, record.task));
  const manifest = { schema_version: 1, kind: 'independent-evaluation-submission',
    submission_id: randomUUID(), task: record.task, method: 'hidden-check', checker_revision: checkerRevision,
    artifacts_sha256: hash(join(dir, 'trace/artifacts.json')),
    workspace_sha256: hash(join(dir, 'trace/final-workspace.json')), files: inventory(submission) };
  write(join(submission, 'manifest.json'), manifest);
  write(join(out, 'private-binding.json'), { schema_version: 1, run_id: runId, solver_id: solverId,
    submission_id: manifest.submission_id, submission_manifest_sha256: hash(join(submission, 'manifest.json')),
    source_run_sha256: hash(join(dir, 'run.json')), inputs_manifest_sha256: record.inputs.manifest_sha256 });
  checkedRun(root, runId);
  return { submission, submission_id: manifest.submission_id, source_unchanged: true };
}

export function validateVerdict(root, handoff, receipt) {
  const submission = join(resolve(handoff), 'submission'), binding = read(join(handoff, 'private-binding.json'));
  const manifestPath = join(submission, 'manifest.json'), manifest = read(manifestPath);
  const { record, dir } = checkedRun(root, binding.run_id);
  require(hash(join(dir, 'run.json')) === binding.source_run_sha256 && record.inputs.manifest_sha256 === binding.inputs_manifest_sha256, 'Source record changed after handoff');
  require(hash(manifestPath) === binding.submission_manifest_sha256, 'Submission manifest changed');
  const files = inventory(submission).filter(row => row.path !== 'manifest.json');
  require(JSON.stringify(files) === JSON.stringify(manifest.files), 'Submission changed during evaluation');
  require(receipt.submission_id === manifest.submission_id && receipt.submission_manifest_sha256 === binding.submission_manifest_sha256, 'Verdict is for a different submission');
  require(receipt.checker_revision === manifest.checker_revision, 'Checker revision changed');
  require(receipt.method === 'hidden-check' && ['pass', 'fail', 'partial'].includes(receipt.result), 'Explicit independent verdict is required');
  require(typeof receipt.evaluator === 'string' && receipt.evaluator.trim() && receipt.evaluator !== binding.solver_id, 'Evaluator must be identified separately from the solving actor');
  for (const field of ['check_output', 'check_command', 'check_environment', 'checked_at']) require(typeof receipt[field] === 'string' && receipt[field].trim(), `Missing evaluator evidence: ${field}`);
  require(receipt.independent_context === true && receipt.network === 'none', 'Evaluation requires an independent offline context');
  require(receipt.infrastructure_failure === null && receipt.source_unchanged === true, 'Infrastructure failure or changed inputs require investigation, not a verdict');
  require(Number.isInteger(receipt.checker_exit_code) && (receipt.result !== 'pass' || receipt.checker_exit_code === 0), 'A pass requires a successful checker execution as well as independent judgment');
  require(/^[a-f0-9]{64}$/.test(receipt.check_package_sha256), 'Evaluator must identify the exact trusted checker package');
  require(receipt.artifacts_sha256 === manifest.artifacts_sha256 && receipt.workspace_sha256 === manifest.workspace_sha256, 'Evaluator did not bind the final artifact/workspace hashes');
  return { run_id: binding.run_id, result: receipt.result, method: 'hidden-check', evaluator: receipt.evaluator,
    check_output: JSON.stringify({ checker_revision: receipt.checker_revision, command: receipt.check_command,
      environment: receipt.check_environment, checked_at: receipt.checked_at, network: receipt.network,
      observations: receipt.check_output, submission_sha256: binding.submission_manifest_sha256 }),
    human_notes: 'Independent evaluator supplied this verdict; the handoff tool did not run a hidden check or infer pass from exit0.',
    artifacts_sha256: manifest.artifacts_sha256, workspace_sha256: manifest.workspace_sha256 };
}

export function importVerdict(root, handoff, receiptFile) {
  const receipt = read(receiptFile);
  const evaluation = validateVerdict(root, handoff, receipt);
  const logs = {};
  for (const stream of ['stdout', 'stderr']) {
    const file = join(resolve(receiptFile, '..'), `${stream}.txt`);
    require(hash(file) === receipt[`${stream}_sha256`], `Evaluator ${stream} log changed`);
    logs[stream] = readFileSync(file, 'utf8');
  }
  evaluation.check_output = JSON.stringify({ ...JSON.parse(evaluation.check_output),
    checker_package_sha256: receipt.check_package_sha256, raw_check_logs: logs });
  const candidate = join(handoff, 'bound-evaluation.json');
  write(candidate, evaluation);
  return judgeRun(root, evaluation.run_id, candidate);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main(() => {
  const cli = args();
  options(cli, ['action', 'run', 'out', 'solver', 'checker-revision', 'handoff', 'receipt'], ['action']);
  if (cli.action === 'prepare') {
    require(cli.run && cli.out, 'prepare requires --run and --out');
    console.log(JSON.stringify(prepareHandoff(process.cwd(), cli.run, cli.out, { solverId: cli.solver, checkerRevision: cli['checker-revision'] })));
  } else if (cli.action === 'import') {
    require(cli.handoff && cli.receipt, 'import requires --handoff and --receipt');
    const record = importVerdict(process.cwd(), resolve(cli.handoff), resolve(cli.receipt));
    console.log(JSON.stringify({ run_id: record.run_id, result: record.verdict.result }));
  } else throw new Error('action must be prepare or import');
});
