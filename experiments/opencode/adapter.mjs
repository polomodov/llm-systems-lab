// Контракт CLI v1 сверён 2026-09-20: https://opencode.ai/docs/cli/
// События stdout не доказывают полноту учёта всех моделей/подагентов.
export function buildCommand({ model, turns, budget, prompt }) {
  if (typeof model !== 'string' || !model.trim()) throw new Error('Нужен точный model ID');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Пустой prompt');
  if (budget != null) throw new Error('OpenCode CLI: жёсткий лимит USD не поддержан адаптером; для исследовательского прогона явно задайте --budget-mode observed');
  if (turns != null && (!Number.isInteger(turns) || turns <= 0)) throw new Error('turns должен быть положительным целым');
  const selected = model.startsWith('anthropic/') ? model : `anthropic/${model}`;
  if (selected.slice('anthropic/'.length).includes('/')) throw new Error('Адаптер поддерживает только провайдера anthropic');
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
  const missing = 'OpenCode stdout — поток событий без гарантии полного итогового учёта; нужен проверенный экспорт сессии';
  return {
    loop: {},
    metrics_unavailable: { 'loop.turns': missing, 'loop.cost_usd': missing, 'loop.tokens_in': missing, 'loop.tokens_out': missing },
    modelId: null,
    modelIds: [],
    stopReason: hasError ? 'error' : typeof terminal?.part?.reason === 'string' ? terminal.part.reason : 'trace_incomplete',
    sessionId: sessions.size === 1 ? [...sessions][0] : null,
  };
}
