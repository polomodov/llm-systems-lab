import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { safePath } from './files.mjs';
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const segment = value => typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
export const relativeFile = value => typeof value === 'string' && /^[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_.-]+)*$/.test(value) && value.split('/').every(part => part !== '.' && part !== '..');
// Единственный источник пина: профиль. Dockerfile, документация и прогон сверяются с ним.
export const VERSION_PIN = /^\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?$/;
export function validateProfile(profile, expectedId) {
  if (!object(profile) || profile.schema_version !== 1 || !segment(profile.id) || (expectedId && profile.id !== expectedId)) throw new Error('Invalid harness profile identity');
  if (typeof profile.version !== 'string' || !VERSION_PIN.test(profile.version)) throw new Error('Harness profile requires an exact version pin');
  if (profile.mode !== undefined && !['cli','sdk'].includes(profile.mode)) throw new Error('Unknown harness execution mode');
  if (profile.native_cache !== undefined && typeof profile.native_cache !== 'boolean') throw new Error('native_cache must be boolean');
  if (!/^L\d{3}$/.test(profile.ledger)) throw new Error('Harness profile requires a ledger ID');
  if (!['explicit','managed'].includes(profile.model_policy)) throw new Error('Unknown model selection policy');
  if (profile.model_policy === 'managed' && (!Array.isArray(profile.managed_modes) || !profile.managed_modes.length || profile.managed_modes.some(mode => !segment(mode)))) throw new Error('Managed harness must enumerate verified modes');
  if (!Array.isArray(profile.version_command) || !profile.version_command.length || profile.version_command.some(arg => typeof arg !== 'string' || !arg || arg.includes('\0'))) throw new Error('Harness requires a version command');
  if (!object(profile.providers) || !Object.hasOwn(profile.providers, profile.default_provider)) throw new Error('Invalid default provider');
  for (const [name, provider] of Object.entries(profile.providers)) {
    if (!segment(name) || !object(provider) || !Array.isArray(provider.credential_env) || !provider.credential_env.length || provider.credential_env.some(key => !/^[A-Z][A-Z0-9_]*$/.test(key))) throw new Error('Invalid provider credentials');
    if (!Array.isArray(provider.connect_domains) || !provider.connect_domains.length || provider.connect_domains.some(host => !/^[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}$/.test(host))) throw new Error('Provider needs exact DNS hostnames, never wildcards');
    if (typeof provider.model_prefix !== 'string') throw new Error('Provider needs an explicit model prefix');
  }
  if (!Array.isArray(profile.config_files) || profile.config_files.some(file => !object(file) || !relativeFile(file.source) || !relativeFile(file.target))) throw new Error('Unsafe harness config path');
  if (!Array.isArray(profile.runtime_files) || profile.runtime_files.some(file => !relativeFile(file))) throw new Error('Unsafe runtime file path');
  const targets = ['adapter.mjs','harness.json','entrypoint.mjs','egress.mjs','prompt.txt','network.json','launch.json','sources.replay.jsonl', ...profile.config_files.map(file=>file.target), ...profile.runtime_files];
  if (new Set(targets).size !== targets.length) throw new Error('Harness files collide with coordinator files');
  if (!object(profile.budget) || !['hard','observed'].includes(profile.budget.usd) || !['hard','advisory','unavailable'].includes(profile.budget.turns)) throw new Error('Unknown harness budget capability');
  return profile;
}
export function loadProfile(root, id) {
  if (!segment(id)) throw new Error('Invalid harness ID');
  return validateProfile(JSON.parse(readFileSync(safePath(root, `experiments/${id}/harness.json`), 'utf8')), id);
}
export function selectProvider(profile, requested) {
  const name = requested ?? profile.default_provider;
  if (!Object.hasOwn(profile.providers, name)) throw new Error(`Provider ${name} is not configured for ${profile.id}`);
  return { name, ...profile.providers[name] };
}
export function selectModel(profile, provider, value) {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim() || /[\s\0]/.test(value)) throw new Error('Explicit model ID or managed selector is required');
  if (profile.model_policy === 'managed') {
    if (!value.startsWith('managed:') || !profile.managed_modes.includes(value.slice(8))) throw new Error(`Use an explicit managed selector: ${profile.managed_modes.map(mode=>`managed:${mode}`).join(', ')}`);
    return { recorded: value, requested: value.slice(8), locked: true, policy: 'managed' };
  }
  const id = provider.model_prefix && value.startsWith(provider.model_prefix) ? value.slice(provider.model_prefix.length) : value;
  if (!id || /^(default|auto|sonnet|opus|haiku|latest)$/i.test(id) || /latest/i.test(id) || value.startsWith('managed:')) throw new Error('Floating model aliases are not accepted');
  return { recorded: id, requested: id, locked: false, policy: 'explicit' };
}
export function controlFiles(profile) {
  return [{source:'adapter.mjs',target:'adapter.mjs'}, {source:'harness.json',target:'harness.json'}, ...profile.config_files, ...profile.runtime_files.map(source=>({source,target:source}))];
}
