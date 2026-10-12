#!/usr/bin/env node
// LAB08 Linux/Ryzen: assemble a sealed local-llama-cpp deployment manifest from
// validated on-disk artifacts. Hashes are computed from the actual files; the
// tokenizer/template hashes are supplied from measured sources.
import { createReadStream, readFileSync, statSync, writeFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, resolve } from 'node:path';
import { args, options, main } from '../../scripts/lib/cli.mjs';

async function hashFile(path) {
  const h = createHash('sha256');
  for await (const chunk of createReadStream(path)) h.update(chunk);
  return { path, bytes: statSync(path).size, sha256: h.digest('hex') };
}

await main(async () => {
  const a = args();
  options(a, ['engine-dir', 'backend', 'executable', 'model', 'repository', 'revision', 'quantization', 'tokenizer-sha', 'chat-template-sha', 'passport', 'hardware-id', 'driver', 'port', 'context', 'out'], ['engine-dir', 'executable', 'model', 'repository', 'revision', 'quantization', 'tokenizer-sha', 'chat-template-sha', 'passport', 'out']);
  const backend = a.backend ?? 'rocm';
  if (!['rocm', 'vulkan'].includes(backend)) throw new Error('backend must be rocm or vulkan');
  const engineDir = resolve(a['engine-dir']), executablePath = resolve(a.executable), modelPath = resolve(a.model), passportPath = resolve(a.passport);
  const names = readdirSync(engineDir, { withFileTypes: true }).filter(d => d.isFile()).map(d => d.name).sort();
  const selected = names.filter(name => name.includes('.so') || ['llama-server', 'llama-cli', 'llama-bench'].includes(name));
  const engineFiles = [];
  for (const name of selected) engineFiles.push(await hashFile(join(engineDir, name)));
  const executable = engineFiles.find(f => f.path === executablePath);
  if (!executable) engineFiles.push(await hashFile(executablePath));
  if (engineFiles.length > 64) throw new Error(`engine files ${engineFiles.length} exceed the 64-file schema limit`);
  const deployment = {
    schema_version: 1,
    kind: 'local-llama-cpp',
    endpoint: { host: '127.0.0.1', port: Number(a.port ?? 18080), transport: 'http' },
    alias: 'lab-model',
    model: {
      repository: a.repository,
      revision: a.revision,
      format: 'GGUF',
      quantization: a.quantization,
      files: [await hashFile(modelPath)],
      tokenizer_sha256: a['tokenizer-sha'],
      chat_template_sha256: a['chat-template-sha']
    },
    engine: {
      id: 'llama-cpp',
      version: 'b8407',
      commit: '312cf03328496df9c56fe843952cf02a8964c59a',
      backend,
      build_flags: ['Release', 'x86_64', `GGML_${backend === 'rocm' ? 'HIP' : 'VULKAN'}=ON`, 'prebuilt ggml-org bundle b8407 (ROCm 7.2.1 gfx110X/gfx115X/gfx120X)'],
      executable: a.executable,
      files: engineFiles
    },
    hardware: {
      id: a['hardware-id'] ?? 'ryzen-ai-max-395-128gb-linux',
      passport: await hashFile(passportPath),
      driver: a.driver ?? 'Ubuntu 24.04 / kernel 7.0.0-38 / ROCm 7.2.0 / gfx1151',
      power_mode: 0
    },
    protocol: {
      context_tokens: Number(a.context ?? 8192), output_tokens: 2048, temperature: 0, seed: 1, top_p: 1,
      reasoning: 'auto', thinking: true, kv: ['f16', 'f16'], batch: 512, ubatch: 256,
      threads: 8, slots: 1, offload: 999, prefix_cache: false, tool_protocol: 'openai-chat'
    }
  };
  writeFileSync(a.out, JSON.stringify(deployment, null, 2) + '\n');
  console.log(`[local-deployment] ${a.out}: engine files=${engineFiles.length}, model bytes=${deployment.model.files[0].bytes}`);
});
