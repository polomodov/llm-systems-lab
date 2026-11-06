// Turn and cost limits belong to the task contract, not the runner.
// The runner reads sealed inputs/task.md, so editing a live task does not
// change a prepared run. Original Russian archives remain readable.
const BUDGET = /^##\s+(Budget|Бюджет)\s*$/m;
const LIMITS = /Up\s+to\s+(\d+)\s+turns?\s+or\s+\$(\d+(?:[.,]\d+)?)/g;
const LEGACY_LIMITS = /До\s+(\d+)\s+ход\S*\s+или\s+\$(\d+(?:[.,]\d+)?)/g;

export function taskLimits(contract) {
  if (typeof contract !== 'string' || !contract.trim()) throw new Error('Task contract is empty');
  const heading = contract.match(BUDGET);
  if (!heading) throw new Error('Task contract has no "## Budget" section');
  const section = contract.slice(heading.index + heading[0].length).split(/^##\s+/m)[0];
  const matches = [...section.matchAll(heading[1] === 'Budget' ? LIMITS : LEGACY_LIMITS)];
  if (matches.length !== 1) throw new Error(`Task budget must state turns and USD exactly once, found ${matches.length}`);
  const turns = Number(matches[0][1]);
  const budget = Number(matches[0][2].replace(',', '.'));
  if (!Number.isInteger(turns) || turns <= 0 || turns > 1000) throw new Error('Task turn limit must be 1..1000');
  if (!Number.isFinite(budget) || budget <= 0 || budget > 1000) throw new Error('Task USD limit must be >0 and <=1000');
  return { turns, budget };
}
