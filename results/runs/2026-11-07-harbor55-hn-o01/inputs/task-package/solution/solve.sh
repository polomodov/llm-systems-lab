#!/bin/sh
set -eu
node - <<'JS'
const fs = require('node:fs');
const os = require('node:os');
const assert = require('node:assert/strict');
const absent = ['/tests', '/opt/verifier-fixtures', '/var/run/docker.sock'];
assert.equal(process.getuid(), 1000);
assert(absent.every(path => !fs.existsSync(path)));
const input = JSON.parse(fs.readFileSync('/app/input.json', 'utf8'));
const output = [...new Set(input.map(value => value.replace(/^[\t\n\v\f\r ]+|[\t\n\v\f\r ]+$/g, '').toLowerCase()).filter(Boolean))].sort();
fs.mkdirSync('/app/output', {recursive: true});
fs.writeFileSync('/app/output/result.json', JSON.stringify(output) + '\n');
const request = require('node:https').get('https://example.com/', {timeout: 3000}, response => {
  response.resume();
  throw new Error('External HTTPS unexpectedly succeeded');
});
request.on('timeout', () => request.destroy(new Error('blocked by timeout')));
request.on('error', () => fs.writeFileSync('/logs/agent/boundary.json', JSON.stringify({effective_uid: process.getuid(), hostname: os.hostname(), absent_paths: absent, external_https_probe_blocked: true}) + '\n'));
JS
