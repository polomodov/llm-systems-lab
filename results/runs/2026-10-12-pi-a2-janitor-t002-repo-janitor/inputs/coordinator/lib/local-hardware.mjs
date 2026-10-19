import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { validateEngineHardware } from './local-engines.mjs';

export const DEFAULT_HARDWARE = 'ryzen-ai-max-395-128gb-linux';
export const HARDWARE_PROFILES = Object.freeze({
  [DEFAULT_HARDWARE]: Object.freeze({ directory: '', os: 'linux' }),
  'apple-m5-max-128gb-macos': Object.freeze({ directory: 'apple', os: 'macos' }),
});

/** Explicit selection only: the host running the planner never chooses the target. */
export function loadLocalHardware(root, selector = DEFAULT_HARDWARE, { engines = false } = {}) {
  if (typeof selector !== 'string' || !Object.hasOwn(HARDWARE_PROFILES, selector)) {
    throw new Error(`Unknown hardware: ${selector}; expected ${Object.keys(HARDWARE_PROFILES).join(', ')}`);
  }
  const profile = HARDWARE_PROFILES[selector];
  const directory = join(root, 'experiments', 'local-models', profile.directory);
  const read = name => JSON.parse(readFileSync(join(directory, name), 'utf8'));
  const hardware = read('hardware.json');
  if (hardware.id !== selector || hardware.os !== profile.os) throw new Error(`Hardware profile identity/OS mismatch: ${selector}`);
  const catalog = engines ? read('engines.json') : null;
  if (catalog) validateEngineHardware(hardware, catalog);
  return { hardware, engines: catalog };
}
