// Пин версии обвязки живёт в experiments/<id>/harness.json. Здесь проверяется,
// что Dockerfile и документация повторяют ровно его: иначе таблица «проверенный
// pin» расходится с образом молча. Совпадение пина с реальным образом проверяет
// run.mjs при запуске и ЛР11–19 при сборке.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { loadProfile } from './harnesses.mjs';

const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function harnessIds(root) {
  return readdirSync(join(root, 'experiments')).filter(name => existsSync(join(root, 'experiments', name, 'harness.json'))).sort();
}

export function auditPins(root) {
  const ids = harnessIds(root), errors = [];
  const readme = readFileSync(join(root, 'README.md'), 'utf8');
  const matrix = readFileSync(join(root, 'docs/harnesses.md'), 'utf8');
  for (const id of ids) {
    const { version } = loadProfile(root, id);
    const dockerfile = readFileSync(join(root, 'experiments', id, 'Dockerfile'), 'utf8');
    if (!dockerfile.includes(`ARG HARNESS_VERSION=${version}`)) errors.push(`${id}: Dockerfile must default HARNESS_VERSION to the pinned ${version}`);
    if (!new RegExp(`RUN test "\\$HARNESS_VERSION" = "${escape(version)}"`).test(dockerfile)) errors.push(`${id}: Dockerfile must assert the pinned ${version}`);
    if (!readme.includes(`harness-lab/${id}:${version}`)) errors.push(`${id}: README.md must show the image tag harness-lab/${id}:${version}`);
    const row = matrix.split('\n').find(line => line.includes(`experiments/${id}/README.md`));
    if (!row) errors.push(`${id}: docs/harnesses.md has no matrix row`);
    else if (!row.includes(version)) errors.push(`${id}: docs/harnesses.md row must state the pinned ${version}`);
    if (!readFileSync(join(root, 'experiments', id, 'README.md'), 'utf8').includes(version)) errors.push(`${id}: experiments/${id}/README.md must state the pinned ${version}`);
  }
  return { ids, errors };
}
