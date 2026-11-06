// CLI v1 contract checked on 2026-09-20: https://opencode.ai/docs/cli/
// Stdout events do not establish complete accounting for every model/subagent.
export function buildCommand({ model, turns, budget, prompt }) {
  if (typeof model !== 'string' || !model.trim()) throw new Error('An exact model ID is required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Empty prompt');
  if (budget != null) throw new Error('OpenCode CLI: this adapter does not support hard USD limits; explicitly select --budget-mode observed for a research run');
  if (turns != null && (!Number.isInteger(turns) || turns <= 0)) throw new Error('turns must be a positive integer');
  const selected = model.startsWith('anthropic/') ? model : `anthropic/${model}`;
  if (selected.slice('anthropic/'.length).includes('/')) throw new Error('The adapter supports only provider anthropic');
  return {
    command: ['opencode', 'run', '--model', selected, '--agent', 'build', '--format', 'json', '--', prompt],
    env: {
      OPENCODE_CONFIG: '/control/opencode.json',
      OPENCODE_DISABLE_AUTOUPDATE: 'true',
      OPENCODE_CONFIG_CONTENT: JSON.stringify({
        model: selected, small_model: selected,
        agent: { build: { model: selected, ...(turns == null ? {} : { steps: turns }) } },
      }),
    },
  };
}

export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).filter((line) => line.trim()).flatMap((line) => {
    try { const item = JSON.parse(line); return item && typeof item === 'object' ? [item] : []; }
    catch { return []; }
  });
  const sessions = new Set(events.map((event) => event.sessionID).filter((value) => typeof value === 'string' && value));
  const terminal = events.findLast((event) => event.type === 'step_finish');
  const hasError = events.some((event) => event.type === 'error');
  const missing = 'OpenCode stdout is an event stream without guaranteed complete final accounting; a verified session export is required';
  return {
    loop: {},
    metrics_unavailable: { 'loop.turns': missing, 'loop.cost_usd': missing, 'loop.tokens_in': missing, 'loop.tokens_out': missing },
    modelId: null,
    modelIds: [],
    stopReason: hasError ? 'error' : typeof terminal?.part?.reason === 'string' ? terminal.part.reason : 'trace_incomplete',
    sessionId: sessions.size === 1 ? [...sessions][0] : null,
  };
}
