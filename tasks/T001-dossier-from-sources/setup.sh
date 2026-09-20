#!/usr/bin/env bash
# Использование: setup.sh <dest> [YYYY-MM-DD]; дата также задаётся T001_AS_OF.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo 'usage: setup.sh <dest> [YYYY-MM-DD]' >&2
  exit 64
fi
node --input-type=module - "$1" "${2:-${T001_AS_OF:-2026-09-19}}" <<'JS'
import { createHash } from 'node:crypto';
import { lstatSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const [destination, asOf] = process.argv.slice(2);
if (!/^\d{4}-\d{2}-\d{2}$/.test(asOf) || Number.isNaN(Date.parse(asOf)) || new Date(asOf).toISOString().slice(0, 10) !== asOf) {
  throw new Error('Дата среза должна быть существующей датой YYYY-MM-DD.');
}
if (!destination.trim()) throw new Error('Нужен явный непустой путь рабочего каталога.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Отказ перезаписывать непустой каталог, файл или ссылку: ${dest}`);
}
const sources = `https://code.claude.com/docs/en/glossary  # определение вендора
https://www.langchain.com/blog/the-anatomy-of-an-agent-harness  # Agent = Model + Harness
https://martinfowler.com/articles/harness-engineering.html  # guides vs sensors
https://www.anthropic.com/engineering/harness-design-long-running-apps  # предположения о модели
https://metr.org/notes/2026-02-13-measuring-time-horizon-using-claude-code-and-codex/  # контрсвидетельство
https://modelcontextprotocol.io/specification/2026-07-28/changelog  # stateless MCP
`;
mkdirSync(join(dest, 'artifacts'), { recursive: true });
writeFileSync(join(dest, 'brief.md'), `# Досье: как источники 2026 года определяют обвязку агента

Дата среза: ${asOf}. Ответить на три вопроса:
1. Как каждый источник определяет обвязку (harness) и чем она отличается от лесов (scaffold) и фреймворка?
2. Какие числа об эффекте обвязки при фиксированной модели есть в источниках и при каких условиях они получены?
3. Что в источниках противоречит друг другу?

Результаты: artifacts/dossier.md и artifacts/sources.json относительно этого рабочего каталога.
Список источников зафиксирован в sources.txt; его дата и SHA-256 — в sources.snapshot.json.
Это снимок списка ссылок, а не содержимого страниц: страницы могут измениться или быть недоступны.
Фиксировать фактическую дату доступа. Не выдавать текущую страницу за архив на дату среза;
материалы позднее даты среза отмечать отдельно, без включения в факты среза.
`);
writeFileSync(join(dest, 'sources.txt'), sources);
writeFileSync(join(dest, 'sources.snapshot.json'), JSON.stringify({
  id: 'T001-sources-v1',
  as_of: asOf,
  kind: 'url-list-only',
  content_archived: false,
  sha256: createHash('sha256').update(sources).digest('hex'),
  urls: sources.trim().split('\n').map(line => line.split(/\s+#/)[0]),
}, null, 2) + '\n');
console.log(`[T001] workspace ready in ${dest}; as of ${asOf}`);
JS
