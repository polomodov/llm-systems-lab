#!/usr/bin/env bash
# Usage: setup.sh <dest> [YYYY-MM-DD]; T001_AS_OF can also set the date.
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
  throw new Error('The cutoff date must be a valid YYYY-MM-DD date.');
}
if (!destination.trim()) throw new Error('An explicit nonempty workspace path is required.');
const dest = resolve(destination);
let stat;
try { stat = lstatSync(dest); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (stat && (!stat.isDirectory() || stat.isSymbolicLink() || readdirSync(dest).length)) {
  throw new Error(`Refusing to overwrite a nonempty directory, file, or symlink: ${dest}`);
}
const sources = `https://code.claude.com/docs/en/glossary  # vendor definition
https://www.langchain.com/blog/the-anatomy-of-an-agent-harness  # Agent = Model + Harness
https://martinfowler.com/articles/harness-engineering.html  # guides vs sensors
https://www.anthropic.com/engineering/harness-design-long-running-apps  # model assumptions
https://metr.org/notes/2026-02-13-measuring-time-horizon-using-claude-code-and-codex/  # counterevidence
https://modelcontextprotocol.io/specification/2026-07-28/changelog  # stateless MCP
`;
mkdirSync(join(dest, 'artifacts'), { recursive: true });
writeFileSync(join(dest, 'brief.md'), `# Dossier: how 2026 sources define an agent harness

Cutoff date: ${asOf}. Answer three questions:
1. How does each source define a harness, and how does it differ from a scaffold and a framework?
2. Which numbers about harness effects with a fixed model appear in the sources, and under what conditions were they obtained?
3. Where do the sources contradict one another?

Outputs: artifacts/dossier.md and artifacts/sources.json relative to this working directory.
The source list is fixed in sources.txt; its date and SHA-256 are in sources.snapshot.json.
This is a snapshot of the link list, not page contents: pages may change or become unavailable.
Record the actual access date. Do not present a current page as an archive from the cutoff date;
identify materials published after the cutoff separately, excluding them from cutoff-date facts.
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
