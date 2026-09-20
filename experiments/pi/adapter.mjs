// Tagged SDK contract: pi-mono v0.73.1; see README.md.
export function resolveModel(registry, provider, model) {
  const exact = registry.find(provider, model);
  if (exact) return exact;
  // Pi's OpenAI catalogue uses family IDs; preserve the requested snapshot ID
  // while taking transport/context/pricing metadata from its known family.
  const family = provider === 'openai' ? model.match(/^(.+)-\d{4}-\d{2}-\d{2}$/)?.[1] : null;
  const base = family ? registry.find(provider, family) : null;
  if (base) return { ...base, id: model, name: model };
  throw new Error(`Pi registry does not contain exact model or OpenAI snapshot family ${provider}/${model}`);
}
export function buildCommand({ model, provider = 'anthropic', turns, budget, prompt }) {
  if (!['anthropic', 'openai'].includes(provider)) throw new Error('Pi: unsupported provider');
  if (typeof model !== 'string' || !model.trim() || model.includes('/')) throw new Error('Pi: exact unprefixed model ID required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Pi: empty prompt');
  if (!Number.isInteger(turns) || turns <= 0) throw new Error('Pi: positive integer turns required');
  if (budget != null) throw new Error('Pi: hard USD limit unavailable; use --budget-mode observed');
  return { command: ['node', '/control/run.mjs', JSON.stringify({ model, provider, turns, prompt })], env: {} };
}

export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
  const final = events.findLast(e => e?.type === 'lab_pi_result');
  const messages = events.filter(e => e?.type === 'message_end' && e.message?.role === 'assistant').map(e => e.message);
  const loop = {}, metrics_unavailable = {};
  const available = (key, value) => { if (Number.isFinite(value) && value >= 0) loop[key] = value; };
  if (final) {
    available('turns', final.turns);
    available('compactions', final.compactions);
    if (messages.length && messages.every(m => m.usage && ['input','output','cacheRead','cacheWrite'].every(k => Number.isFinite(m.usage[k])) && !['error','aborted'].includes(m.stopReason))) {
      available('tokens_in', messages.reduce((n,m) => n + m.usage.input + m.usage.cacheRead + m.usage.cacheWrite, 0));
      available('tokens_out', messages.reduce((n,m) => n + m.usage.output, 0));
      if (messages.every(m => Number.isFinite(m.usage.cost?.total) && m.usage.cost.total > 0)) available('cost_usd', messages.reduce((n,m) => n + m.usage.cost.total, 0));
    }
  }
  for (const key of ['turns','tokens_in','tokens_out','cost_usd','compactions']) if (!(key in loop)) metrics_unavailable[`loop.${key}`] = 'Pi: missing complete final trace or complete response usage/pricing; partial totals are not reported';
  return { loop, metrics_unavailable, modelId: null, modelIds: [], stopReason: final?.stopReason ?? 'trace_incomplete', sessionId: final?.sessionId ?? null };
}
