// Контракт CLI сверён 2026-09-20: https://code.claude.com/docs/en/cli-reference
// Поля result: anthropics/claude-agent-sdk-python, _internal/message_parser.py.
export function buildCommand({ model, turns, budget, prompt }) {
  if (typeof model !== 'string' || !model.trim()) throw new Error('Нужен точный model ID');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Пустой prompt');
  const command = [
    'claude', '-p', '--model', model, '--output-format', 'stream-json', '--verbose',
    '--permission-mode', 'dontAsk', '--settings', '/control/settings.json',
    '--setting-sources', '',
  ];
  if (turns != null) {
    if (!Number.isInteger(turns) || turns <= 0) throw new Error('turns должен быть положительным целым');
    command.push('--max-turns', String(turns));
  }
  if (budget != null) {
    if (!Number.isFinite(budget) || budget <= 0) throw new Error('budget должен быть положительным числом');
    command.push('--max-budget-usd', String(budget));
  }
  command.push('--', prompt);
  return { command, env: { DISABLE_AUTOUPDATER: '1' } };
}

function eventsFrom(stdout) {
  try {
    const value = JSON.parse(stdout);
    return Array.isArray(value) ? value : [value];
  } catch {
    return String(stdout).split(/\r?\n/).filter((line) => line.trim()).flatMap((line) => {
      try { return [JSON.parse(line)]; } catch { return []; }
    });
  }
}

const count = (value) => Number.isSafeInteger(value) && value >= 0;
const amount = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0;

export function parseTrace(stdout) {
  const events = eventsFrom(stdout).filter((event) => event && typeof event === 'object');
  const result = events.findLast((event) => event.type === 'result' && !event.parent_tool_use_id);
  const loop = {};
  const metrics_unavailable = {};
  const missing = 'CLI не вернул итоговое result-сообщение с этой метрикой';
  if (count(result?.num_turns)) loop.turns = result.num_turns;
  else metrics_unavailable['loop.turns'] = missing;
  if (amount(result?.total_cost_usd)) loop.cost_usd = result.total_cost_usd;
  else metrics_unavailable['loop.cost_usd'] = missing;

  // Не складывать result.usage и modelUsage: это два представления одной работы.
  // modelUsage учитывает вспомогательные модели; raw trace сохраняет разбивку.
  const modelUsage = result?.modelUsage && typeof result.modelUsage === 'object'
    ? Object.values(result.modelUsage) : [];
  const usage = modelUsage.length ? modelUsage : result?.usage ? [result.usage] : [];
  const inputKeys = modelUsage.length
    ? ['inputTokens', 'cacheCreationInputTokens', 'cacheReadInputTokens']
    : ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'];
  const outputKey = modelUsage.length ? 'outputTokens' : 'output_tokens';
  if (usage.length && usage.every((entry) => entry && inputKeys.every((key) => count(entry[key])))) {
    const total = usage.reduce((sum, entry) => sum + inputKeys.reduce((part, key) => part + entry[key], 0), 0);
    if (count(total)) loop.tokens_in = total;
  }
  if (usage.length && usage.every((entry) => entry && count(entry[outputKey]))) {
    const total = usage.reduce((sum, entry) => sum + entry[outputKey], 0);
    if (count(total)) loop.tokens_out = total;
  }
  if (loop.tokens_in === undefined) metrics_unavailable['loop.tokens_in'] = 'Нет полной разбивки input и cache tokens в итоговом usage';
  if (loop.tokens_out === undefined) metrics_unavailable['loop.tokens_out'] = missing;

  // init.model отражает настройку; assistant.message.model — наблюдаемый ответ.
  const models = new Set(events.filter((event) => event.type === 'assistant' && !event.parent_tool_use_id)
    .map((event) => event.message?.model).filter((value) => typeof value === 'string' && value && value !== '<synthetic>'));
  const modelId = models.size === 1 ? [...models][0] : null;
  const reason = !result ? 'trace_incomplete' : result.is_error
    ? result.subtype && result.subtype !== 'success' ? result.subtype : 'error'
    : result.terminal_reason || result.stop_reason || result.subtype || 'completed';
  return {
    loop, metrics_unavailable, modelId, modelIds: [...models],
    stopReason: typeof reason === 'string' ? reason : 'trace_incomplete',
    sessionId: typeof result?.session_id === 'string' ? result.session_id : null,
  };
}
