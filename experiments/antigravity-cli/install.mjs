import { readFileSync, renameSync, chmodSync, rmSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

// Снимок официального release manifest; latest не запрашивается при сборке.
const version = process.argv[2];
if (!/^\d+\.\d+\.\d+$/.test(version ?? '')) throw new Error('Нужна точная HARNESS_VERSION');
const release = JSON.parse(readFileSync(new URL(`./releases/${version}.json`, import.meta.url), 'utf8'));
const asset = release[process.arch];
if (release.version !== version || !asset) throw new Error('Нет закреплённого релиза для версии/архитектуры');
const archive = '/tmp/agy-release.tar.gz';
execFileSync('curl', ['--fail', '--location', '--silent', '--show-error', '--output', archive, asset.url], { stdio: 'inherit' });
const actual = createHash('sha512').update(readFileSync(archive)).digest('hex');
if (actual !== asset.sha512) throw new Error('Antigravity archive SHA-512 mismatch');
execFileSync('tar', ['-xzf', archive, '-C', '/tmp', 'antigravity'], { stdio: 'inherit' });
renameSync('/tmp/antigravity', '/usr/local/bin/agy');
chmodSync('/usr/local/bin/agy', 0o755);
rmSync(archive);
