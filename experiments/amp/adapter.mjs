// CLI 0.0.1789920039-gafe14b: amp --help; https://ampcode.com/docs/cli/streaming-json
// Amp mode selects service routing, not an exact model ID.
const modes = new Set(['low', 'medium', 'high', 'ultra']);
export function buildCommand({ model, provider = 'amp', turns, budget, prompt }) {
  if (provider !== 'amp') throw new Error('Amp: only provider=amp is supported');
  if (!modes.has(model)) throw new Error('Amp requires a managed mode: low, medium, high, or ultra; this adapter cannot select an exact model ID');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Empty prompt');
  if (turns != null && (!Number.isInteger(turns) || turns <= 0)) throw new Error('turns must be a positive integer');
  if (budget != null) throw new Error('Amp: hard USD limits are unsupported; specify --budget-mode observed');
  return {
    command: ['amp', '--mode', model, '--executor', 'local', '--stream-json',
      '--settings-file', '/control/amp-settings.json', '--visibility', 'private',
      '--no-ide', '--no-notifications', '--no-remote-control-terminal', '--no-color', `--execute=${prompt}`],
    env: { AMP_URL: 'https://ampcode.com/', AMP_REMOTE_CONTROL_TERMINAL: '0' },
  };
}

const count = value => Number.isSafeInteger(value) && value >= 0;
export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).flatMap(line => {
    try { const item = JSON.parse(line); return item && typeof item === 'object' && !Array.isArray(item) ? [item] : []; }
    catch { return []; }
  });
  const result = events.findLast(event => event.type === 'result' && !event.parent_tool_use_id);
  const error = events.findLast(event => event.type === 'system' && ['error_max_turns', 'error_during_execution'].includes(event.subtype));
  const loop = {}, metrics_unavailable = {};
  if (count(result?.num_turns)) loop.turns = result.num_turns;
  else metrics_unavailable['loop.turns'] = 'Amp did not return final result.num_turns';
  // Use final usage only: summing assistant messages may omit auxiliary calls.
  const usage = result?.usage;
  const inputKeys = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'];
  if (usage && inputKeys.every(key => count(usage[key]))) {
    const total = inputKeys.reduce((sum, key) => sum + usage[key], 0);
    if (count(total)) loop.tokens_in = total;
  }
  if (count(usage?.output_tokens)) loop.tokens_out = usage.output_tokens;
  if (loop.tokens_in === undefined) metrics_unavailable['loop.tokens_in'] = 'Final result.usage lacks a complete input/cache breakdown';
  if (loop.tokens_out === undefined) metrics_unavailable['loop.tokens_out'] = 'Final result.usage lacks output_tokens';
  metrics_unavailable['loop.cost_usd'] = 'The documented Amp stream-json schema does not return final USD cost';
  const sessions = [...new Set(events.map(event => event.session_id).filter(value => typeof value === 'string' && value))];
  const reason = result ? result.is_error ? (result.subtype !== 'success' && typeof result.subtype === 'string' ? result.subtype : 'error')
    : result.subtype === 'success' ? 'completed' : 'trace_incomplete' : error?.subtype ?? 'trace_incomplete';
  return { loop, metrics_unavailable, modelId: null, modelIds: [], stopReason: reason,
    sessionId: sessions.length === 1 ? sessions[0] : null };
}
