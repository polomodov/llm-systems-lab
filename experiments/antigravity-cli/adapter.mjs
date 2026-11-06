// https://antigravity.google/docs/cli/headless/ — contract checked on 2026-09-20.
export function buildCommand({ model, provider = 'google', turns, budget, prompt }) {
  if (provider !== 'google') throw new Error('Antigravity: adapter supports only google through the Gemini API');
  if (typeof model !== 'string' || !model.trim()) throw new Error('An exact model ID is required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Empty prompt');
  if (budget != null) throw new Error('Antigravity: hard USD limits are unsupported; specify --budget-mode observed');
  if (turns != null) throw new Error('Antigravity: hard turn limits are unsupported by this adapter');
  const selected = model.replace(/^google\//, '');
  if (!selected || selected.includes('/')) throw new Error('Antigravity: invalid google model ID');
  return {
    command: ['node', '/control/run-cli.mjs', '--model', selected, '--output-format', 'stream-json', '--print-timeout', '0', '--disable-slash-commands', '--dangerously-skip-permissions', '--print', prompt],
    env: {},
  };
}

const count = (value) => Number.isSafeInteger(value) && value >= 0;

export function parseTrace(stdout) {
  let malformed = false;
  const events = String(stdout).split(/\r?\n/).filter((line) => line.trim()).flatMap((line) => {
    try { const value = JSON.parse(line); return value && typeof value === 'object' && !Array.isArray(value) ? [value] : []; }
    catch { malformed = true; return []; }
  });
  const last = events.at(-1);
  const result = last?.event === 'result' && !malformed ? last.result : undefined;
  const loop = {};
  const metrics_unavailable = {
    'loop.turns': 'Antigravity num_turns counts user requests, not internal model turns',
    'loop.cost_usd': 'Antigravity result does not report USD cost',
    'loop.tokens_in': 'The relationship between cache_read_tokens and input_tokens requires a real run to verify; no total is invented',
  };
  // Result counters are cumulative; do not add step_update again.
  if (count(result?.usage?.output_tokens)) loop.tokens_out = result.usage.output_tokens;
  else metrics_unavailable['loop.tokens_out'] = 'No valid final result.usage.output_tokens';
  const status = typeof result?.status === 'string' ? result.status : '';
  return {
    loop, metrics_unavailable, modelId: null, modelIds: [],
    stopReason: status === 'SUCCESS' ? 'completed' : ['ERROR', 'INVALID'].includes(status) ? 'error' : ['CANCELED', 'INTERRUPTED'].includes(status) ? 'interrupted' : 'trace_incomplete',
    sessionId: typeof result?.conversation_id === 'string' && result.conversation_id ? result.conversation_id : null,
  };
}
