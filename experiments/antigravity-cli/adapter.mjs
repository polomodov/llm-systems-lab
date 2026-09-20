// https://antigravity.google/docs/cli/headless/ — контракт сверён 2026-09-20.
export function buildCommand({ model, provider = 'google', turns, budget, prompt }) {
  if (provider !== 'google') throw new Error('Antigravity: адаптер поддерживает только google через Gemini API');
  if (typeof model !== 'string' || !model.trim()) throw new Error('Нужен точный model ID');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Пустой prompt');
  if (budget != null) throw new Error('Antigravity: жёсткий лимит USD не поддержан; задайте --budget-mode observed');
  if (turns != null) throw new Error('Antigravity: жёсткий лимит ходов не поддержан адаптером');
  const selected = model.replace(/^google\//, '');
  if (!selected || selected.includes('/')) throw new Error('Antigravity: неверный google model ID');
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
    'loop.turns': 'Antigravity num_turns считает пользовательские запросы, а не внутренние модельные ходы',
    'loop.cost_usd': 'Antigravity result не сообщает стоимость USD',
    'loop.tokens_in': 'Семантика cache_read_tokens относительно input_tokens требует проверки реальным прогоном; сумма не выдумывается',
  };
  // Счётчики result накопительные; step_update повторно не суммируем.
  if (count(result?.usage?.output_tokens)) loop.tokens_out = result.usage.output_tokens;
  else metrics_unavailable['loop.tokens_out'] = 'Нет корректного итогового result.usage.output_tokens';
  const status = typeof result?.status === 'string' ? result.status : '';
  return {
    loop, metrics_unavailable, modelId: null, modelIds: [],
    stopReason: status === 'SUCCESS' ? 'completed' : ['ERROR', 'INVALID'].includes(status) ? 'error' : ['CANCELED', 'INTERRUPTED'].includes(status) ? 'interrupted' : 'trace_incomplete',
    sessionId: typeof result?.conversation_id === 'string' && result.conversation_id ? result.conversation_id : null,
  };
}
