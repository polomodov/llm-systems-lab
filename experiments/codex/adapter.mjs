// Checked against OpenAI Docs non-interactive mode and codex exec --help on 2026-09-20.
export function buildCommand({ model, provider = 'openai', turns, budget, prompt }) {
  if (provider !== 'openai') throw new Error('Codex: adapter supports only openai');
  if (typeof model !== 'string' || !model.trim()) throw new Error('An exact model ID is required');
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('Empty prompt');
  if (budget != null) throw new Error('Codex: hard USD limits are unsupported; specify --budget-mode observed');
  if (turns != null) throw new Error('Codex: hard turn limits are unsupported by this adapter');
  const selected = model.replace(/^openai\//, '');
  if (!selected || selected.includes('/')) throw new Error('Codex: invalid openai model ID');
  return {
    command: [
      'codex', 'exec', '--model', selected, '--json', '--color', 'never',
      '--skip-git-repo-check', '--ephemeral', '--ignore-user-config', '--ignore-rules',
      '--sandbox', 'danger-full-access', '-c', 'approval_policy="never"',
      '-c', 'web_search="disabled"', '-c', 'agents.enabled=false',
      '--', prompt,
    ],
    env: {},
  };
}

const count = (value) => Number.isSafeInteger(value) && value >= 0;

export function parseTrace(stdout) {
  const lines = String(stdout).split(/\r?\n/).filter((line) => line.trim());
  let malformed = false;
  const events = lines.flatMap((line) => {
    try { const value = JSON.parse(line); return value && typeof value === 'object' && !Array.isArray(value) ? [value] : []; }
    catch { malformed = true; return []; }
  });
  const terminal = events.findLast((event) => ['turn.completed', 'turn.failed', 'error', 'turn.started'].includes(event.type));
  const completed = terminal?.type === 'turn.completed' && !malformed;
  const loop = {};
  const metrics_unavailable = {
    'loop.turns': 'A Codex turn is a user request with an internal loop; JSONL does not report the full model-turn count',
    'loop.cost_usd': 'Codex JSONL does not report USD cost',
  };
  // input_tokens already includes cached_input_tokens; do not add cache again.
  const usages = events.filter((event) => event.type === 'turn.completed').map((event) => event.usage);
  for (const [field, key] of [['tokens_in', 'input_tokens'], ['tokens_out', 'output_tokens']]) {
    if (completed && usages.length && usages.every((usage) => count(usage?.[key]))) {
      const total = usages.reduce((sum, usage) => sum + usage[key], 0);
      if (count(total)) loop[field] = total;
    }
    if (loop[field] === undefined) metrics_unavailable[`loop.${field}`] = 'No complete valid turn.completed usage for the finished run';
  }
  const ids = new Set(events.filter((event) => event.type === 'thread.started').map((event) => event.thread_id).filter((id) => typeof id === 'string' && id));
  return {
    loop, metrics_unavailable, modelId: null, modelIds: [],
    stopReason: terminal?.type === 'turn.failed' || terminal?.type === 'error' ? 'error' : completed ? 'completed' : 'trace_incomplete',
    sessionId: ids.size === 1 ? [...ids][0] : null,
  };
}
