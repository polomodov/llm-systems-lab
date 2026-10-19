export function args(argv = process.argv.slice(2)) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (!/^--[a-z][a-z-]*$/.test(key) || !argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error(`Expected --name value: ${key}`);
    if (key.slice(2) in out) throw new Error(`Duplicate option: ${key}`);
    out[key.slice(2)] = argv[++i];
  }
  return out;
}
export function options(opts, allowed, required = []) {
  for (const key of Object.keys(opts)) if (!allowed.includes(key)) throw new Error(`Unknown option --${key}`);
  for (const key of required) if (!opts[key]) throw new Error(`Required: --${key}`);
}
export async function main(fn) {
  try { await fn(); } catch (error) { console.error(`[lab] ${error.message}`); process.exitCode = 1; }
}
