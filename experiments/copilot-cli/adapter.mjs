// CLI 1.0.86: copilot --help; https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference
// CLI JSONL фильтрует assistant.usage/session.shutdown и завершает поток
// {type:'result', sessionId, exitCode, usage:{premiumRequests,...}}.
// Проверено в app.js установленного пакета 1.0.86, formatter EVt / filter VPr.
export function buildCommand({ model, provider = 'copilot', turns, budget, prompt }) {
  if (provider !== 'copilot') throw new Error('Copilot CLI: поддержан только provider=copilot');
  if (typeof model !== 'string' || !model.trim() || /^(auto|default|latest)$/i.test(model) || model.startsWith('managed:')) throw new Error('Нужен явный Copilot model ID');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Пустой prompt');
  if (turns != null && (!Number.isInteger(turns) || turns <= 0)) throw new Error('turns должен быть положительным целым');
  if (budget != null) throw new Error('Copilot CLI: жёсткий лимит USD не поддержан; задайте --budget-mode observed');
  return {
    command: ['copilot', '--model', model, '--output-format', 'json', '--allow-all',
      '--no-ask-user', '--no-auto-update', '--no-custom-instructions', '--no-bash-env',
      '--disable-builtin-mcps', '--no-remote', '--no-remote-export', '--no-color', `--prompt=${prompt}`],
    env: { COPILOT_AUTO_UPDATE: 'false', COPILOT_HOME: '/tmp/copilot', CI: 'true' },
  };
}

const id = value => typeof value === 'string' && value.length > 0;
export function parseTrace(stdout) {
  const events = String(stdout).split(/\r?\n/).flatMap(line => {
    try { const item = JSON.parse(line); return item && typeof item === 'object' && !Array.isArray(item) ? [item] : []; }
    catch { return []; }
  });
  const root = events.filter(event => !event.agentId && !event.data?.parentToolCallId);
  const result = root.findLast(event => event.type === 'result');
  const start = root.find(event => event.type === 'session.start');
  const loop = {}, metrics_unavailable = {};
  for (const field of ['tokens_in', 'tokens_out']) metrics_unavailable[`loop.${field}`] = 'Copilot CLI JSONL фильтрует assistant.usage/session.shutdown и не возвращает итоговые token totals; нужен отдельный проверенный экспорт usage';
  const starts = new Set(root.filter(event => event.type === 'assistant.turn_start').map(event => event.data?.turnId).filter(id));
  const ends = new Set(root.filter(event => event.type === 'assistant.turn_end').map(event => event.data?.turnId).filter(id));
  if (start && result && starts.size > 0 && starts.size === ends.size && [...starts].every(turn => ends.has(turn))) loop.turns = starts.size;
  else metrics_unavailable['loop.turns'] = 'Нет полного набора пар assistant.turn_start/turn_end между session.start и result';
  metrics_unavailable['loop.cost_usd'] = 'Copilot возвращает premium requests/AI credits/множители, а не измеренную стоимость прогона в USD';
  const error = root.findLast(event => event.type === 'session.error');
  return {
    loop, metrics_unavailable, modelId: null, modelIds: [],
    stopReason: error || (Number.isInteger(result?.exitCode) && result.exitCode !== 0) ? 'error' : result?.exitCode === 0 ? 'completed' : 'trace_incomplete',
    sessionId: id(result?.sessionId) ? result.sessionId : id(start?.data?.sessionId) ? start.data.sessionId : null,
  };
}
