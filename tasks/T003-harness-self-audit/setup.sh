#!/usr/bin/env bash
# Использование: setup.sh <dest> <harness>; скрытые проверки не читаются.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo 'usage: setup.sh <dest> <harness>' >&2
  exit 64
fi
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
node --input-type=module - "$1" "$2" "$REPO_ROOT" <<'JS'
import { createHash } from 'node:crypto';
import { lstatSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
const [destination, harness, root] = process.argv.slice(2);
const relativeFile = value => typeof value === 'string' && /^[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_.-]+)*$/.test(value) && value.split('/').every(part => part !== '.' && part !== '..');
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(harness)) throw new Error('Недопустимый идентификатор обвязки');
const readAllowed = relative => {
  if (!relativeFile(relative)) throw new Error(`Недопустимый путь снимка: ${relative}`);
  let current = root;
  for (const part of relative.split('/')) {
    current = join(current, part);
    if (lstatSync(current).isSymbolicLink()) throw new Error(`Ссылка недопустима в снимке: ${relative}`);
  }
  if (!lstatSync(current).isFile()) throw new Error(`Ожидался обычный файл: ${relative}`);
  return readFileSync(current);
};
const profilePath = `experiments/${harness}/harness.json`;
const profile = JSON.parse(readAllowed(profilePath));
if (profile.schema_version !== 1 || profile.id !== harness || !Array.isArray(profile.config_files) || !Array.isArray(profile.runtime_files)) throw new Error('Неизвестный формат профиля обвязки');
const control = [
  { source:'adapter.mjs', target:'adapter.mjs' },
  { source:'harness.json', target:'harness.json' },
  ...profile.config_files,
  ...profile.runtime_files.map(source => ({ source, target:source })),
];
for (const file of control) if (!relativeFile(file.source) || !relativeFile(file.target)) throw new Error('Недопустимый путь конфигурации');
if (new Set(control.map(file=>file.target)).size !== control.length) throw new Error('Коллизия путей конфигурации');
if (!destination.trim()) throw new Error('Нужен явный непустой путь рабочего каталога.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) throw new Error(`Отказ перезаписывать непустой каталог, файл или ссылку: ${dest}`);
// Явный список допуска; никаких обходов check/, .env, .git или результатов.
const files = [
  'README.md','AGENTS.md','CLAUDE.md','package.json',
  'docs/method.md','docs/harnesses.md','docs/harness-ledger.md',
  'agents/README.md','agents/a1-dossier/spec.md','agents/a2-janitor/spec.md','agents/a3-ledger-auditor/spec.md',
  'agents/a4-implementer/spec.md','agents/a5-data-wrangler/spec.md','agents/a6-hardener/spec.md',
  'tasks/README.md',
  ...['T001-dossier-from-sources','T002-repo-janitor','T003-harness-self-audit','T004-feature-from-spec','T005-data-normalization','T006-security-hardening'].flatMap(id => [`tasks/${id}/task.md`,`tasks/${id}/task.json`,`tasks/${id}/setup.sh`]),
  'experiments/README.md',`experiments/${harness}/README.md`,`experiments/${harness}/NOTES.md`,
  'experiments/common/entrypoint.mjs','experiments/common/egress.mjs',
  'scripts/run.mjs','scripts/lib/harnesses.mjs','scripts/lib/tasks.mjs',
  ...control.map(file=>`experiments/${harness}/${file.source}`),
];
const snapshot = new Map([...new Set(files)].map(file => [file, readAllowed(file)]));
for (const file of control) snapshot.set(`.harness/control/${file.target}`, snapshot.get(`experiments/${harness}/${file.source}`));
const activeConfig = harness === 'claude-code' ? '.claude/settings.json' : harness === 'opencode' ? 'opencode.json' : '.harness/control/harness.json';
if (harness === 'claude-code') snapshot.set(activeConfig, snapshot.get('experiments/claude-code/settings.example.json'));
if (harness === 'opencode') snapshot.set(activeConfig, snapshot.get('experiments/opencode/opencode.json'));
snapshot.set('ledger-template.md', snapshot.get('docs/harness-ledger.md'));
snapshot.set('brief.md', Buffer.from(`# Аудит обвязки ${harness}

Модель и провайдер задаются метаданными прогона; из конфигурации их не угадывать.
Здесь снимок разрешённых исходников лаборатории без секретов, результатов и скрытых проверок.
Активная конфигурация для просмотра: ${activeConfig}.
Файлы, монтируемые runner в /control, отражены в .harness/control/; исходники — experiments/${harness}/.
Границы контейнера и сети реализованы в scripts/run.mjs и experiments/common/egress.mjs.
Форма реестра — docs/harness-ledger.md (копия — ledger-template.md).
Файлы снимка и SHA-256 перечислены в repository.snapshot.json.
Результаты: artifacts/ledger.md и artifacts/ablation-plan.md. Не запускать аудируемые скрипты и хуки. Записывать только в artifacts/.
`));
mkdirSync(join(dest,'artifacts'), { recursive:true });
for (const [path,contents] of snapshot) {
  mkdirSync(dirname(join(dest,path)), { recursive:true });
  writeFileSync(join(dest,path), contents, { mode:path.endsWith('.sh') ? 0o755 : 0o644 });
}
writeFileSync(join(dest,'repository.snapshot.json'), JSON.stringify({
  kind:'allowlisted-repository',harness,active_config:activeConfig,
  files:[...snapshot].map(([path,contents])=>({path,sha256:createHash('sha256').update(contents).digest('hex')})),
},null,2)+'\n');
console.log(`[T003] workspace ready in ${dest} for ${harness}`);
JS
