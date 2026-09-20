export function buildCommand({ model, provider = 'anthropic', turns, budget, prompt }) {
  if (!['anthropic','openai'].includes(provider)) throw new Error('OpenHands: unsupported provider');
  if (typeof model !== 'string' || !model.trim() || model.includes('/')) throw new Error('OpenHands: exact unprefixed model ID required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('OpenHands: empty prompt');
  if (!Number.isInteger(turns) || turns <= 0) throw new Error('OpenHands: positive integer turns required');
  if (budget != null) throw new Error('OpenHands: hard USD limit unavailable; use --budget-mode observed');
  return { command: ['python', '/control/run.py', JSON.stringify({ model: `${provider}/${model}`, provider, turns, prompt })], env: { LITELLM_LOCAL_MODEL_COST_MAP: 'True', DO_NOT_TRACK: '1' } };
}

export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
  const final = events.findLast(e => e?.type === 'lab_openhands_result'), metrics = final?.metrics;
  const loop = {}, metrics_unavailable = {};
  const usages = metrics?.token_usages;
  if (Array.isArray(usages) && usages.length > 0) {
    // One SDK token_usage item per completed LLM response. Errors may hide calls.
    if (!final.error && usages.every(u => Number.isFinite(u.prompt_tokens) && Number.isFinite(u.completion_tokens))) {
      loop.turns = usages.length;
      loop.tokens_in = usages.reduce((n,u) => n+u.prompt_tokens,0);
      loop.tokens_out = usages.reduce((n,u) => n+u.completion_tokens,0);
      if (Array.isArray(metrics.costs) && metrics.costs.length === usages.length && metrics.costs.every(item => Number.isFinite(item?.cost) && item.cost > 0) && Number.isFinite(metrics.accumulated_cost) && metrics.accumulated_cost > 0) loop.cost_usd = metrics.accumulated_cost;
    }
  }
  for (const key of ['turns','tokens_in','tokens_out','cost_usd']) if (!(key in loop)) metrics_unavailable[`loop.${key}`] = 'OpenHands: incomplete final response metrics or pricing; partial totals are not reported';
  return { loop, metrics_unavailable, modelId: null, modelIds: [], stopReason: final?.stopReason ?? 'trace_incomplete', sessionId: final?.sessionId ?? null };
}
