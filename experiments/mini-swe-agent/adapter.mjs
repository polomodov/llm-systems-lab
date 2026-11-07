export function buildCommand({ model, provider = 'anthropic', turns, budget, prompt }) {
  if (!['anthropic','openai'].includes(provider)) throw new Error('mini-SWE-agent: unsupported provider');
  if (typeof model !== 'string' || !model.trim() || model.includes('/')) throw new Error('mini-SWE-agent: exact unprefixed model ID required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('mini-SWE-agent: empty prompt');
  if (!Number.isInteger(turns) || turns <= 0) throw new Error('mini-SWE-agent: positive integer turns required');
  if (budget != null) throw new Error('mini-SWE-agent cost_limit checks AFTER spending; use --budget-mode observed');
  return { command: ['python', '/control/run.py', JSON.stringify({ model: `${provider}/${model}`, turns, prompt })], env: { LITELLM_LOCAL_MODEL_COST_MAP: 'True', MSWEA_COST_TRACKING: 'default' } };
}

export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
  const final = events.findLast(e => e?.type === 'lab_mini_result'), trace = final?.trajectory;
  const loop = {}, metrics_unavailable = {};
  const responses = (trace?.messages ?? []).filter(m => m.role === 'assistant' || m.object === 'response').map(m => m.object === 'response' ? { ...m, usage: m.usage && { prompt_tokens: m.usage.input_tokens, completion_tokens: m.usage.output_tokens } } : m.extra?.response);
  const modelIds = [...new Set(responses.map(r => r?.model).filter(id => typeof id === 'string' && id))];
  const stats = trace?.info?.model_stats;
  if (Number.isInteger(stats?.api_calls) && stats.api_calls >= 0) loop.turns = stats.api_calls;
  if (responses.length > 0 && responses.length === stats?.api_calls && responses.every(r => Number.isFinite(r?.usage?.prompt_tokens) && Number.isFinite(r?.usage?.completion_tokens))) {
    loop.tokens_in = responses.reduce((n,r) => n+r.usage.prompt_tokens,0);
    loop.tokens_out = responses.reduce((n,r) => n+r.usage.completion_tokens,0);
    if (Number.isFinite(stats.instance_cost) && stats.instance_cost > 0) loop.cost_usd = stats.instance_cost;
  }
  for (const key of ['turns','tokens_in','tokens_out','cost_usd']) if (!(key in loop)) metrics_unavailable[`loop.${key}`] = 'mini-SWE-agent: missing final trajectory or usage for every attempted model call';
  return { loop, metrics_unavailable, modelId: modelIds.length === 1 ? modelIds[0] : null, modelIds, stopReason: trace?.info?.exit_status || (final ? 'error' : 'trace_incomplete'), sessionId: null };
}
