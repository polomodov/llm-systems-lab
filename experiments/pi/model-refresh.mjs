// Compatibility patch for the pinned Pi0.73.1 artifact, not an upstream release.
// Sonnet5.5 accepts adaptive thinking and requires empty signed blocks replayed.
import fs from 'node:fs';
import crypto from 'node:crypto';
const path = '/opt/pi/node_modules/@mariozechner/pi-ai/dist/providers/anthropic.js';
let source = fs.readFileSync(path, 'utf8');
const before = crypto.createHash('sha256').update(source).digest('hex');
if (before !== '4e60212df9184658d9bb0219d339b276fe7ea0320a7130285412ba11ac737b31') throw new Error('Pi provider source differs from patch pin');
const edits = [
  ['return (modelId.includes("opus-4-6") ||', 'return (modelId === "claude-sonnet-5-5" || modelId.includes("opus-4-6") ||'],
  ['if (block.thinking.trim().length === 0)', 'if (block.thinking.trim().length === 0 && !block.thinkingSignature)'],
];
for (const [from, to] of edits) {
  if (source.split(from).length !== 2) throw new Error('Pi patch anchor is ambiguous');
  source = source.replace(from, to);
}
fs.writeFileSync(path, source);
console.log(JSON.stringify({provider_source_before:before,provider_source_after:crypto.createHash('sha256').update(source).digest('hex')}));
