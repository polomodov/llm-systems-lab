// CLI 0.0.1789920039-gafe14b: amp --help; https://ampcode.com/docs/cli/streaming-json
// Режим Amp задаёт маршрутизацию сервиса, а не точный ID модели.
const modes = new Set(['low', 'medium', 'high', 'ultra']);
export function buildCommand({ model, provider = 'amp', turns, budget, prompt }) {
  if (provider !== 'amp') throw new Error('Amp: поддержан только provider=amp');
  if (!modes.has(model)) throw new Error('Amp требует управляемый режим low, medium, high или ultra; точный model ID через этот адаптер недоступен');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Пустой prompt');
  if (turns != null && (!Number.isInteger(turns) || turns <= 0)) throw new Error('turns должен быть положительным целым');
  if (budget != null) throw new Error('Amp: жёсткий лимит USD не поддержан; задайте --budget-mode observed');
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
  else metrics_unavailable['loop.turns'] = 'Amp не вернул итоговый result.num_turns';
  // Только итоговый usage: сумма assistant-сообщений может пропускать служебные вызовы.
  const usage = result?.usage;
  const inputKeys = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'];
  if (usage && inputKeys.every(key => count(usage[key]))) {
    const total = inputKeys.reduce((sum, key) => sum + usage[key], 0);
    if (count(total)) loop.tokens_in = total;
  }
  if (count(usage?.output_tokens)) loop.tokens_out = usage.output_tokens;
  if (loop.tokens_in === undefined) metrics_unavailable['loop.tokens_in'] = 'Нет полного input/cache breakdown в итоговом result.usage';
  if (loop.tokens_out === undefined) metrics_unavailable['loop.tokens_out'] = 'Нет output_tokens в итоговом result.usage';
  metrics_unavailable['loop.cost_usd'] = 'Документированная stream-json схема Amp не возвращает итоговую стоимость в USD';
  const sessions = [...new Set(events.map(event => event.session_id).filter(value => typeof value === 'string' && value))];
  const reason = result ? result.is_error ? (result.subtype !== 'success' && typeof result.subtype === 'string' ? result.subtype : 'error')
    : result.subtype === 'success' ? 'completed' : 'trace_incomplete' : error?.subtype ?? 'trace_incomplete';
  return { loop, metrics_unavailable, modelId: null, modelIds: [], stopReason: reason,
    sessionId: sessions.length === 1 ? sessions[0] : null };
}
