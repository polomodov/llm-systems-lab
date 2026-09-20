import { mkdirSync, copyFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

// CLI читает modelProvider только из своего HOME. В контейнере HOME — временный.
const configDir = join(process.env.HOME, '.gemini', 'antigravity-cli');
mkdirSync(configDir, { recursive: true });
copyFileSync('/control/settings.json', join(configDir, 'settings.json'));
const child = spawn('agy', process.argv.slice(2), { stdio: 'inherit', env: process.env });
child.on('error', (error) => { console.error(error.message); process.exitCode = 127; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 128 : 1); });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
